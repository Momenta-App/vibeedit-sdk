"""Project-bound loopback review service; browser and CLI share Project.correct."""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

from vibeedit.data import data_path
from vibeedit.local_http import LoopbackHTTPServer
from vibeedit.ffmpeg import ffmpeg_path
from vibeedit.myriograph import MyriographError
from vibeedit.project import Project, RevisionConflict, atomic_json, canonical, file_digest, within


def waveform(project, source_id):
    source = project.source(source_id)
    path = within(project.root, source["path"])
    if file_digest(path) != source["sha256"]:
        raise ValueError("Source changed; waveform not generated")
    target = within(project.root, f".vibeedit/waveforms/{source['sha256']}.json")
    if target.is_file():
        return json.loads(target.read_text(encoding="utf-8"))
    # 1 ms peak bins at 8kHz keep the portable review light; these are not stems.
    process = subprocess.Popen([ffmpeg_path(), "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    peaks = []
    while block := process.stdout.read(16 * 4096):
        samples = array.array("h", block)
        if sys.byteorder != "little":
            samples.byteswap()
        peaks.extend(max((abs(v) / 32768 for v in samples[index:index + 8]), default=0) for index in range(0, len(samples), 8))
        if len(peaks) > 14_400_000:
            process.kill()
            process.wait()
            raise ValueError("Waveform exceeds four-hour review limit")
    if process.wait():
        raise ValueError("Audio waveform decode failed")
    result = {"schemaVersion": "vibeedit.waveform.v1", "sourceSha256": source["sha256"], "durationSec": source["durationUs"] / 1_000_000, "binUs": 1000, "bands": {"volume": peaks}, "meaning": "Full-mix peak envelope; not separated stems"}
    atomic_json(target, result)
    return result


def browser_state(project, source_id, domain, baseline_id=None, *, offset=0, limit=200):
    state = project.review(source_id, domain, baseline_id, offset=offset, limit=limit)
    machine = state.get("machine")
    if machine:
        # Retain the original file for agents; browser receives only review fields.
        keys = {"id", "ordinal", "text", "start", "end", "startUs", "endUs", "pts", "frameOrdinal", "timeBase", "bbox", "box", "landmarks", "appearanceId", "appearanceKey", "groupId", "voiceGroupId", "speakerId", "personId", "ownershipStatus", "status", "name", "wordOrdinals", "sourceId", "portraitSourceId", "confidence"}
        state["machine"] = {"schemaVersion": machine.get("schemaVersion"), "sourceSha256": machine.get("sourceSha256"), "clock": machine.get("clock")}
        for key in ("words", "voiceGroups", "appearances", "faceAppearances", "groups"):
            if isinstance(machine.get(key), list):
                state["machine"][key] = [{k: v for k, v in item.items() if k in keys} for item in machine[key] if isinstance(item, dict)]
        timeline = machine.get("preparedAudio", {}).get("sourceTimeline", machine.get("sourceTimeline", {}))
        if isinstance(timeline, dict):
            state["machine"]["sourceTimeline"] = {k: v for k, v in timeline.items() if k in {"audioToVideoMillis", "audioOriginPts", "videoOriginPts", "timeBase", "discontinuities"}}
    state["mode"] = domain
    if domain == "faces":
        applied = {item["payload"]["operationId"]: item["payload"]["appliedRevisionSha256"] for item in state["corrections"] if item["action"] == "acknowledge"}
        state["corrections"] = [{**item, **({"remoteStatus": "applied", "appliedRevisionSha256": applied[item["operationId"]]} if item["operationId"] in applied else {})} for item in state["corrections"]]
    return state


def face_index(project, source_id, baseline_id):
    review = project.review(source_id, "faces", baseline_id)
    baseline = review["machine"]
    if not baseline or baseline.get("schemaVersion") != "vibeedit.faceReviewIndex.v1":
        raise ValueError("Import the original face package with project import-faces and select its baseline")
    index = within(project.root, baseline["index"])
    if file_digest(index) != baseline["indexSha256"]:
        raise ValueError("Registered native face index changed")
    return index, review


def face_library(index):
    from vibeedit.face_review import page_groups
    from vibeedit.myriograph import Myriograph, read_config
    library = page_groups(index, limit=1)["library"]
    if not library:
        raise ValueError("This package has no persistent cloud library")
    client = Myriograph(read_config())
    head = client.call("/v1/faces/libraries/" + library["libraryId"])
    if head.get("libraryId") != library["libraryId"] or not re.fullmatch(r"[a-f0-9]{64}", str(head.get("revisionSha256", ""))) or head.get("embeddingSpaceSha256") != library["embeddingSpaceSha256"]:
        raise ValueError("Authoritative customer library binding changed")
    revision = client.call("/v1/faces/libraries/" + library["libraryId"] + "/revisions/" + head["revisionSha256"])
    from vibeedit.face_review import prepare_library_command
    # Validate exact native revision bytes/scope even for this read-only census.
    prepare_library_command(index, operation_id="head-validation", expected_revision_sha256=head["revisionSha256"], action={"kind": "restore", "revisionSha256": head["revisionSha256"]}, library_revision={"value": revision["state"], "reference": revision["revision"]})
    return {**{key: head[key] for key in ("libraryId", "revisionSha256", "embeddingSpaceSha256", "sequence", "identityCount", "contributionCount") if key in head}, "identityIds": revision["state"]["identityIds"]}


def send_face_correction(project, event):
    from vibeedit.myriograph import Myriograph, MyriographError, read_config
    pending = event["payload"]["pendingCommand"]
    acknowledgement = next((item for item in project.corrections() if item["action"] == "acknowledge" and item["payload"].get("operationId") == event["operationId"]), None)
    if acknowledgement:
        return {"ok": True, "event": event, "remoteStatus": "applied", "appliedRevisionSha256": acknowledgement["payload"]["appliedRevisionSha256"]}
    if pending.get("relativePath") != "/v1/faces/libraries/" + pending["libraryId"] + "/corrections" or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", pending["libraryId"]) or pending.get("commandSha256") != hashlib.sha256(canonical({key: value for key, value in pending.items() if key != "commandSha256"}).encode()).hexdigest():
        raise ValueError("Saved face correction has an invalid customer route")
    try:
        response = Myriograph(read_config()).call(pending["relativePath"], pending["body"], key=event["operationId"])
    except MyriographError as error:
        return {"ok": True, "event": event, "remoteStatus": "pending", "error": error.code, "recovery": "Retry this original saved operation; do not change its revision or selectors"}
    applied = response.get("appliedRevisionSha256")
    if response.get("libraryId") != pending["libraryId"] or not re.fullmatch(r"[a-f0-9]{64}", str(applied or "")):
        return {"ok": True, "event": event, "remoteStatus": "pending", "error": "authoritative_acknowledgement_missing"}
    project.correct({"operationId": "ack-" + hashlib.sha256(event["operationId"].encode()).hexdigest(), "expectedRevision": project.read()["revision"], "author": "remote:myriograph", "sourceId": event["sourceId"], "sourceSha256": event["sourceSha256"], "baselineId": event["baselineId"], "domain": "faces", "action": "acknowledge", "targetId": event["targetId"], "payload": {"operationId": event["operationId"], "commandSha256": pending["commandSha256"], "libraryId": pending["libraryId"], "appliedRevisionSha256": applied}})
    return {"ok": True, "event": event, "remoteStatus": "applied", "appliedRevisionSha256": applied}


def face_correction(project, body):
    from vibeedit.face_review import prepare_library_command, preview_request, page_groups
    index, review = face_index(project, body["sourceId"], body["baselineId"])
    action = body["action"]
    if not isinstance(action, dict):
        raise ValueError("Choose an explicit face review action")
    if action.get("kind") == "portrait":
        if set(action) != {"kind", "appearanceId"}:
            raise ValueError("Choose one saved source appearance for the local portrait overlay")
        request = preview_request(index, action["appearanceId"])
        payload = {"appearanceId": action["appearanceId"], "previewRequest": request}
        target = action["appearanceId"]
    else:
        original = next((event for event in project.corrections() if event["operationId"] == body["operationId"]), None)
        if original:
            pending = original["payload"]["pendingCommand"]
            if pending["expectedRevisionSha256"] != body["expectedLibraryRevisionSha256"] or original["sourceId"] != body["sourceId"] or original["baselineId"] != body["baselineId"]:
                raise RevisionConflict("Recover the original face operation without changing its source, baseline or library revision")
            if original["payload"].get("action") != action:
                raise RevisionConflict("Face operation identity reused with different selectors")
        else:
            from vibeedit.myriograph import Myriograph, read_config
            revision_sha = body["expectedLibraryRevisionSha256"]
            library = page_groups(index, limit=1)["library"]
            if not library or not re.fullmatch(r"[a-f0-9]{64}", str(revision_sha)):
                raise ValueError("Read and explicitly accept the authoritative library revision first")
            revision = Myriograph(read_config()).call("/v1/faces/libraries/" + library["libraryId"] + "/revisions/" + revision_sha)
            pending = prepare_library_command(index, operation_id=body["operationId"], expected_revision_sha256=revision_sha, action=action, library_revision={"value": revision["state"], "reference": revision["revision"]})
        payload = {"libraryId": pending["libraryId"], "pendingCommand": pending, "action": action}
        target = pending["libraryId"]
    event = project.correct({"operationId": body["operationId"], "expectedRevision": body["expectedRevision"], "author": "human:local-review", "sourceId": body["sourceId"], "sourceSha256": review["source"]["sha256"], "baselineId": body["baselineId"], "domain": "faces", "action": action["kind"], "targetId": target, "payload": payload})
    return {"ok": True, "event": event, "remoteStatus": "local-note"} if action["kind"] == "portrait" else send_face_correction(project, event)


class ReviewServer(LoopbackHTTPServer):
    daemon_threads = True

    def __init__(self, project, mode, source_id, baseline_id=None, port=0, token=None):
        self.project = project
        self.mode = mode
        self.source_id = source_id
        self.baseline_id = baseline_id
        self.token = token or secrets.token_urlsafe(32)
        self.preview_slots = threading.BoundedSemaphore(2)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.cookie_name = f"vibeedit_review_{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass  # Never log capabilities, paths, words or signed URLs.

    def _headers(self, status, content_type, size, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()

    def _json(self, status, value, extra=None):
        raw = canonical(value).encode()
        self._headers(status, "application/json; charset=utf-8", len(raw), extra)
        self.wfile.write(raw)

    def _host(self):
        return self.headers.get("Host") == urlsplit(self.server.origin).netloc

    def _authorized(self):
        bearer = self.headers.get("Authorization", "").removeprefix("Bearer ")
        cookie = next((part.strip().removeprefix(self.server.cookie_name + "=") for part in self.headers.get("Cookie", "").split(";") if part.strip().startswith(self.server.cookie_name + "=")), "")
        return any(secrets.compare_digest(v, self.server.token) for v in (bearer, cookie))

    def do_GET(self):
        if not self._host():
            return self._json(403, {"ok": False, "error": "Unrecognized local host"})
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/") or path.startswith("/media/"):
            if not self._authorized():
                return self._json(401, {"ok": False, "error": "Project review capability required"})
        try:
            query = parse_qs(urlsplit(self.path).query)
            mode = query.get("mode", [self.server.mode])[0]
            source_id = query.get("source", [self.server.source_id])[0]
            baseline_id = query.get("baseline", [self.server.baseline_id])[0]
            if mode not in {"beats", "faces", "words", "video"}:
                raise ValueError("Unsupported review mode")
            if path == "/api/status":
                return self._json(200, {"schemaVersion": "vibeedit.reviewStatus.v1", "ok": True, "serviceVersion": "vibeedit.reviewService.v2", "projectId": self.server.project.read()["id"], "mode": self.server.mode, "sourceId": self.server.source_id})
            if path == "/api/state":
                return self._json(200, browser_state(self.server.project, source_id, mode, baseline_id, offset=int(query.get("offset", ["0"])[0]), limit=int(query.get("limit", ["200"])[0])))
            if path == "/api/waveform":
                return self._json(200, waveform(self.server.project, source_id))
            if path.startswith("/api/faces/"):
                from vibeedit.face_review import page_groups, page_appearances, preview_request, render_preview
                index, review = face_index(self.server.project, source_id, baseline_id)
                if path == "/api/faces/groups":
                    result = page_groups(index, offset=int(query.get("offset", ["0"])[0]), limit=int(query.get("limit", ["100"])[0]))
                    for group in result["groups"]:
                        group.pop("native", None)
                    result["library"] = {key: result["library"][key] for key in ("libraryId", "embeddingSpaceSha256")} if result["library"] else None
                    return self._json(200, result)
                if path == "/api/faces/appearances":
                    result = page_appearances(index, group_id=query.get("groupId", [None])[0], person_id=query.get("personId", [None])[0], offset=int(query.get("offset", ["0"])[0]), limit=int(query.get("limit", ["100"])[0]))
                    for appearance in result["appearances"]:
                        appearance.pop("native", None)
                    return self._json(200, result)
                if path == "/api/faces/library":
                    return self._json(200, face_library(index))
                if path == "/api/faces/preview":
                    request = preview_request(index, query["appearanceId"][0])
                    portrait = query.get("portrait", ["0"])[0] == "1"
                    # Render fresh from exact source evidence; never serve a stale cache.
                    if not self.server.preview_slots.acquire(timeout=30):
                        return self._json(429, {"ok": False, "error": "Two source previews are already rendering; retry this same preview"})
                    try:
                        with tempfile.TemporaryDirectory(prefix="vibeedit-face-preview-") as temporary:
                            output = Path(temporary) / "preview.png"
                            render_preview(index, within(self.server.project.root, review["source"]["path"]), request, output, portrait=portrait)
                            return self._file(output)
                    finally:
                        self.server.preview_slots.release()
            if path.startswith("/media/"):
                source = self.server.project.source(path.removeprefix("/media/"))
                return self._file(within(self.server.project.root, source["path"]), ranges=True)
            parts = path.strip("/").split("/")
            route_mode = parts[0] if parts[0] in {"beats", "faces", "words", "video"} else self.server.mode
            relative = parts[1] if parts[0] in {"beats", "faces", "words", "video"} and len(parts) == 2 else ("index.html" if path == "/" or path == f"/{route_mode}/" else path.lstrip("/"))
            # A finite registered static directory, never arbitrary project files.
            if "/" in relative or relative.startswith("."):
                return self._json(404, {"ok": False, "error": "Not found"})
            return self._file(within(data_path("review-assets", route_mode if route_mode in {"beats", "faces"} else "desk"), relative))
        except MyriographError as error:
            self._json(error.status or 503, {"ok": False, "error": error.code})
        except (OSError, ValueError, KeyError) as error:
            self._json(400, {"ok": False, "error": str(error)})

    def do_POST(self):
        if not self._host() or self.headers.get("Origin") != self.server.origin:
            return self._json(403, {"ok": False, "error": "Same-origin mutation required"})
        if not self._authorized():
            return self._json(401, {"ok": False, "error": "Project capability required"})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._json(415, {"ok": False, "error": "JSON required"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 2_000_000:
                return self._json(413, {"ok": False, "error": "Request too large"})
            body = json.loads(self.rfile.read(size) or b"{}")
            path = urlsplit(self.path).path
            if path == "/api/session":
                return self._json(200, {"ok": True}, {"Set-Cookie": f"{self.server.cookie_name}={self.server.token}; HttpOnly; SameSite=Strict; Path=/"})
            if path == "/api/corrections":
                return self._json(200, {"ok": True, "event": self.server.project.correct(body)})
            if path == "/api/faces/corrections":
                result = face_correction(self.server.project, body)
                return self._json(202 if result["remoteStatus"] == "pending" else 200, result)
            retry = re.fullmatch(r"/api/faces/corrections/([^/]+)/retry", path)
            if retry:
                event = next((item for item in self.server.project.corrections() if item["operationId"] == retry[1] and item["domain"] == "faces" and item["payload"].get("pendingCommand")), None)
                if not event:
                    raise ValueError("Original pending face operation not found")
                result = send_face_correction(self.server.project, event)
                return self._json(202 if result["remoteStatus"] == "pending" else 200, result)
            return self._json(404, {"ok": False, "error": "Not found"})
        except RevisionConflict as error:
            self._json(409, {"ok": False, "error": str(error), "revision": self.server.project.read()["revision"]})
        except MyriographError as error:
            self._json(error.status or 503, {"ok": False, "error": error.code})
        except (OSError, ValueError, KeyError) as error:
            self._json(400, {"ok": False, "error": str(error)})

    def _file(self, path, ranges=False):
        if not path.is_file():
            return self._json(404, {"ok": False, "error": "Not found"})
        with path.open("rb") as stream:
            size = os.fstat(stream.fileno()).st_size
            start, end = 0, size - 1
            status = 200
            extra = {"Accept-Ranges": "bytes"} if ranges else {}
            if ranges and self.headers.get("Range"):
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers["Range"])
                if not match or not any(match.groups()):
                    return self._json(416, {"ok": False, "error": "Unsupported range"}, {"Content-Range": f"bytes */{size}"})
                if match[1]:
                    start = int(match[1]); end = min(int(match[2]) if match[2] else end, end)
                else:
                    start = max(0, size - int(match[2]))
                if start > end or start >= size:
                    return self._json(416, {"ok": False, "error": "Range outside media"}, {"Content-Range": f"bytes */{size}"})
                status = 206
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"
            self._headers(status, mimetypes.guess_type(path)[0] or "application/octet-stream", max(0, end - start + 1), extra)
            stream.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = stream.read(min(262144, remaining))
                if not data:
                    break
                self.wfile.write(data)
                remaining -= len(data)


def register_commands(subparsers):
    parser = subparsers.add_parser("review", help="open persistent beat, face, word or final-video review")
    parser.add_argument("mode", choices=("beats", "faces", "words", "video", "status"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--source-id")
    parser.add_argument("--baseline-id")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--foreground", action="store_true")
    parser.set_defaults(handler=_command)


def _command(args):
    project = Project(args.project)
    config_path = project.root / ".vibeedit" / "review-session.json"
    if args.mode == "status":
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else None
        result = {"schemaVersion": "vibeedit.reviewStatus.v1", "ok": True, "running": False}
        if config:
            try:
                request = urllib.request.Request(config["origin"] + "/api/status", headers={"Authorization": "Bearer " + config["token"]})
                with urllib.request.urlopen(request, timeout=2) as response:
                    result.update(json.load(response), running=True)
            except (OSError, urllib.error.URLError):
                pass
        print(json.dumps(result))
        return 0
    source_id = args.source_id or next((s["id"] for s in project.read()["sources"]), None)
    if not source_id:
        raise ValueError("Import a source first, then select --source-id")
    project.source(source_id)
    if args.mode in {"words", "faces"} and not args.baseline_id:
        args.baseline_id = next((entry["id"] for entry in reversed(project.read()["analysis"]) if entry["sourceId"] == source_id and entry["service"] in ({"speakers", "local-caption-input"} if args.mode == "words" else {"faces"})), None)
    if not args.foreground and config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        try:
            request = urllib.request.Request(config["origin"] + "/api/status", headers={"Authorization": "Bearer " + config["token"]})
            with urllib.request.urlopen(request, timeout=2) as response:
                status = json.load(response)
            if status["projectId"] == project.read()["id"] and status.get("serviceVersion") == "vibeedit.reviewService.v2":
                url = config["origin"] + "/" + args.mode + "/?" + urlencode({"source": source_id, **({"baseline": args.baseline_id} if args.baseline_id else {})}) + "#" + config["token"]
                print(json.dumps({"schemaVersion": "vibeedit.reviewReady.v1", "ok": True, "url": url, "pid": config["pid"], "reused": True, "projectId": status["projectId"]}))
                return 0
        except (OSError, urllib.error.URLError):
            pass
    if args.foreground:
        server = ReviewServer(project, args.mode, source_id, args.baseline_id)
        config = {"origin": server.origin, "token": server.token, "mode": args.mode, "sourceId": source_id, "baselineId": args.baseline_id, "pid": os.getpid()}
        config_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(canonical(config))
        os.chmod(config_path, 0o600)
        print(json.dumps({"schemaVersion": "vibeedit.reviewReady.v1", "ok": True, "url": server.origin + "/" + args.mode + "/?" + urlencode({"source": source_id, **({"baseline": args.baseline_id} if args.baseline_id else {})}) + "#" + server.token, "pid": os.getpid(), "projectId": project.read()["id"]}), flush=True)
        server.serve_forever()
        return 0
    # Parent reads a ready receipt; child remains detached from the parent chat.
    child = subprocess.Popen([sys.executable, "-m", "vibeedit.review", args.mode, "--project", str(project.root), "--source-id", source_id, *(["--baseline-id", args.baseline_id] if args.baseline_id else []), "--foreground", "--json"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True, text=True)
    ready = child.stdout.readline()
    child.stdout.close()
    if not ready:
        raise ValueError("Review service failed before readiness")
    print(ready.strip())
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    register_commands(sub)
    args = parser.parse_args(["review", *sys.argv[1:]])
    raise SystemExit(args.handler(args))
