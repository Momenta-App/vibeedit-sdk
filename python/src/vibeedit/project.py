"""Portable project state and revisioned human overlays around CompositionSpec."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import uuid
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

from vibeedit.ffmpeg import ffprobe_path, probe
from vibeedit.validation import validate_composition


class RevisionConflict(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def within(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Expected a project-relative path")
    path = (Path(root).resolve() / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()) or path == Path(root).resolve():
        raise ValueError("Path escapes the project")
    return path


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf8") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Project:
    def __init__(self, path):
        self.root = Path(path).resolve()
        if self.root.is_file():
            self.root = self.root.parent
        self.manifest = within(self.root, "project.vibeedit.json")
        self.database = within(self.root, ".vibeedit/project.sqlite3")
        if not self.manifest.is_file():
            raise ValueError("Project not found; run vibeedit project create PATH")
        self.database.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            self.database.parent.chmod(0o700)
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        if manifest.get("schemaVersion") != "vibeedit.project.v1":
            raise ValueError("Unsupported project schema")
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM project").fetchone():
                db.execute("INSERT INTO project VALUES (1,?)", (canonical(manifest),))
            if json.loads(db.execute("SELECT document FROM project WHERE singleton=1").fetchone()[0])["id"] != manifest["id"]:
                raise ValueError("Project manifest and durable state identity differ")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        if os.name != "nt":
            self.database.chmod(0o600)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.executescript("""
          CREATE TABLE IF NOT EXISTS project (singleton INTEGER PRIMARY KEY CHECK(singleton=1), document TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS correction (revision INTEGER PRIMARY KEY, operation_id TEXT UNIQUE NOT NULL,
            intent TEXT NOT NULL, document TEXT NOT NULL);
        """)
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def read(self):
        with self.connect() as db:
            return json.loads(db.execute("SELECT document FROM project WHERE singleton=1").fetchone()[0])

    def update(self, expected_revision, transform):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            value = json.loads(db.execute("SELECT document FROM project WHERE singleton=1").fetchone()[0])
            if value["revision"] != expected_revision:
                raise RevisionConflict(f"Expected revision {expected_revision}; current {value['revision']}")
            transform(value)
            value["revision"] += 1
            db.execute("UPDATE project SET document=? WHERE singleton=1", (canonical(value),))
        # SQLite is authoritative after a crash; this snapshot is rebuildable.
        self.snapshot()
        return value

    def snapshot(self):
        # Hold the writer lock through publication so an old snapshot cannot win.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            value = json.loads(db.execute("SELECT document FROM project WHERE singleton=1").fetchone()[0])
            atomic_json(self.manifest, value)
        return value

    def register_source(self, path, *, expected_revision, receipt=None):
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError("Source does not exist")
        digest = file_digest(path)
        target = within(self.root, f"sources/{digest}{path.suffix.lower()}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name(f".{uuid.uuid4().hex}.tmp")
            shutil.copyfile(path, temporary)
            if file_digest(temporary) != digest:
                temporary.unlink()
                raise ValueError("Source changed while copying")
            os.replace(temporary, target)
        if file_digest(target) != digest:
            raise ValueError("Registered source checksum mismatch")
        metadata = probe(target)
        streams = [{key: stream[key] for key in ("index", "codec_type", "codec_name", "time_base", "start_pts", "start_time", "duration_ts", "duration", "r_frame_rate", "avg_frame_rate", "sample_rate", "width", "height", "nb_frames", "disposition", "side_data_list") if key in stream} for stream in metadata["streams"]]
        # Large native clocks stay streamed and lossless outside agent context.
        clock_path = within(self.root, f"sources/{digest}.clock.jsonl")
        existing = next((s for s in self.read()["sources"] if s["sha256"] == digest), None)
        if existing and file_digest(within(self.root, existing["clock"])) != existing["clockSha256"]:
            raise ValueError("Saved native source clock was altered")
        if not clock_path.exists():
            _clock_census(target, clock_path, streams, digest)
        source = {"id": f"source-{digest[:24]}", "path": target.relative_to(self.root).as_posix(), "sha256": digest, "byteLength": target.stat().st_size, "streams": [{key: str(value) if key in {"start_pts", "duration_ts"} else value for key, value in stream.items()} for stream in streams], "clock": clock_path.relative_to(self.root).as_posix(), "clockSha256": file_digest(clock_path), "clockSchemaVersion": "vibeedit.sourceClock.v1", "durationUs": round(Fraction(metadata.get("format", {}).get("duration", "0")) * 1_000_000)}
        if receipt is not None:
            source["acquisition"] = receipt
        def add(value):
            existing = next((s for s in value["sources"] if s["id"] == source["id"]), None)
            if existing and existing["sha256"] != digest:
                raise ValueError("Source ID conflict")
            if not existing:
                value["sources"].append(source)
        return self.update(expected_revision, add)

    def relink(self, source_id, path, *, expected_revision):
        source = self.source(source_id)
        if file_digest(path) != source["sha256"] or Path(path).stat().st_size != source["byteLength"]:
            raise ValueError("Relink requires identical source bytes")
        return self.register_source(path, expected_revision=expected_revision)

    def source(self, source_id):
        source = next((s for s in self.read()["sources"] if s["id"] == source_id), None)
        if source is None:
            raise ValueError("Unknown project source")
        return source

    def import_analysis(self, source_id, path, *, service, job_id, schema_version, expected_revision):
        source = self.source(source_id)
        if Path(path).stat().st_size > 256 * 1024 * 1024:
            raise ValueError("Analysis exceeds the 256 MiB JSON import limit; use a range/index adapter")
        raw = Path(path).read_bytes()
        baseline = json.loads(raw)
        supplied = baseline.get("sourceSha256", baseline.get("source", {}).get("sha256"))
        if supplied != source["sha256"]:
            raise ValueError("Analysis must carry the exact registered source SHA256")
        if baseline.get("schemaVersion") != schema_version:
            raise ValueError("Analysis schema differs from declared contract")
        digest = hashlib.sha256(raw).hexdigest()
        destination = within(self.root, f"analysis/{digest}.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError("Immutable baseline conflict")
        destination.write_bytes(raw)
        record = {"id": digest, "sourceId": source_id, "sourceSha256": source["sha256"], "service": service, "jobId": job_id, "schemaVersion": schema_version, "path": destination.relative_to(self.root).as_posix(), "sha256": digest}
        def add(value):
            if not any(a["id"] == digest for a in value["analysis"]):
                value["analysis"].append(record)
        return self.update(expected_revision, add)

    def corrections(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT document FROM correction ORDER BY revision")]

    def import_faces(self, source_id, archive, *, job_id, archive_sha256, archive_bytes, expected_revision):
        from vibeedit.face_review import import_face_package, page_groups
        if not all(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) for value in (job_id, archive_sha256)) or type(archive_bytes) is not int or archive_bytes < 1:
            raise ValueError("Exact native job/archive SHA256 and positive archive length are required")
        source = self.source(source_id)
        directory = within(self.root, f"reviews/faces-{archive_sha256}")
        if directory.exists():
            receipt = json.loads((directory / "import-receipt.json").read_text(encoding="utf-8"))
            if receipt.get("jobId") != job_id or receipt.get("sourceSha256") != source["sha256"] or receipt.get("archiveSha256") != archive_sha256 or receipt.get("archiveByteLength") != archive_bytes or file_digest(directory / "native.faces.zip") != archive_sha256:
                raise ValueError("Existing face import differs from original identities")
            page_groups(directory / "review-index.sqlite3", limit=1)
        else:
            import_face_package(archive, directory, job_id=job_id, source_sha256=source["sha256"], source_byte_length=source["byteLength"], archive_sha256=archive_sha256, archive_bytes=archive_bytes)
        baseline = json.loads((directory / "review-baseline.json").read_text(encoding="utf-8"))
        baseline["index"] = (directory / "review-index.sqlite3").relative_to(self.root).as_posix()
        baseline["nativeManifest"] = (directory / "native/manifest.json").relative_to(self.root).as_posix()
        digest = hashlib.sha256(canonical(baseline).encode()).hexdigest()
        destination = within(self.root, f"analysis/{digest}.json")
        atomic_json(destination, baseline)
        files = [{"path": p.relative_to(self.root).as_posix(), "sha256": file_digest(p), "byteLength": p.stat().st_size} for p in sorted(directory.rglob("*")) if p.is_file()]
        artifact = {"id": "reviews-" + hashlib.sha256(canonical(files).encode()).hexdigest(), "path": directory.relative_to(self.root).as_posix(), "files": files, "kind": "directory", "sourceId": source_id, "sourceSha256": source["sha256"]}
        record = {"id": digest, "sourceId": source_id, "sourceSha256": source["sha256"], "service": "faces", "jobId": job_id, "schemaVersion": baseline["schemaVersion"], "path": destination.relative_to(self.root).as_posix(), "sha256": file_digest(destination)}
        def add(value):
            if not any(item["id"] == record["id"] for item in value["analysis"]):
                value["analysis"].append(record)
            if not any(item["id"] == artifact["id"] for item in value["reviews"]):
                value["reviews"].append(artifact)
        return self.update(expected_revision, add)

    def register_artifact(self, category, path, *, expected_revision, source_id=None):
        if category not in {"beats", "masks", "reviews", "renders"}:
            raise ValueError("Expected beats, masks, reviews or renders artifact category")
        relative = Path(path).as_posix()
        if Path(relative).parts[:1] == (".vibeedit",) or any((self.root / Path(*Path(relative).parts[:index])).is_symlink() for index in range(1, len(Path(relative).parts) + 1)):
            raise ValueError("Private runtime state and symlink artifacts cannot be registered")
        artifact = within(self.root, relative)
        candidates = sorted(artifact.rglob("*")) if artifact.is_dir() else [artifact]
        if any(".vibeedit" in p.relative_to(self.root).parts or p.is_symlink() or not (p.is_file() or p.is_dir()) for p in candidates):
            raise ValueError("Artifact trees cannot contain links or special files")
        files = [{"path": p.relative_to(self.root).as_posix(), "sha256": file_digest(p), "byteLength": p.stat().st_size} for p in candidates if p.is_file()]
        if not files or len(files) > 100_000:
            raise ValueError("Expected 1–100000 regular artifact files")
        record = {"id": f"{category}-" + hashlib.sha256(canonical(files).encode()).hexdigest(), "path": relative, "files": files, "kind": "directory" if artifact.is_dir() else "file"}
        if source_id:
            source = self.source(source_id)
            record.update(sourceId=source_id, sourceSha256=source["sha256"])
        if category == "renders":
            state = self.read()
            record.update(composition=state["composition"], compositionSha256=file_digest(within(self.root, state["composition"])))
        def add(value):
            if not any(item["id"] == record["id"] for item in value[category]):
                value[category].append(record)
        self.update(expected_revision, add)
        return record

    def use_composition(self, relative, *, expected_revision):
        state = self.read()
        path = within(self.root, relative)
        spec = json.loads(path.read_text(encoding="utf-8"))
        validate_composition(spec)
        for source in spec.get("sources", []):
            uri = source["uri"]
            if Path(uri).is_absolute() or "://" in uri:
                raise ValueError("Project compositions require registered relative sources")
            actual = file_digest(within(self.root, (path.parent / uri).relative_to(self.root).as_posix()))
            if source.get("identity", {}).get("value") != actual or not any(item["sha256"] == actual for item in state["sources"]):
                raise ValueError("Composition source must match registered exact bytes")
        old = within(self.root, state["composition"])
        previous = json.loads(old.read_text(encoding="utf-8"))
        if old.name.startswith("composition-") and len(old.stem) == 76 and old.stem[12:] != hashlib.sha256(canonical(previous).encode()).hexdigest():
            raise RevisionConflict("Restore the exact immutable reviewed composition before adopting a new revision")
        record = {"id": "composition-" + file_digest(old), "kind": "composition-history", "path": state["composition"], "sha256": file_digest(old), "byteLength": old.stat().st_size}
        def adopt(value):
            if not any(item["id"] == record["id"] for item in value["reviews"]):
                value["reviews"].append(record)
            value["composition"] = path.relative_to(self.root).as_posix()
        return self.update(expected_revision, adopt)

    def correct(self, command):
        required = {"operationId", "expectedRevision", "author", "sourceId", "sourceSha256", "domain", "action", "targetId", "payload"}
        if not isinstance(command, dict) or not required <= command.keys():
            raise ValueError("Correction lacks required identity/revision/author fields")
        if not all(isinstance(command[k], str) and 0 < len(command[k]) <= 256 for k in ("operationId", "author", "sourceId", "sourceSha256", "targetId")):
            raise ValueError("Invalid correction identity")
        if type(command["expectedRevision"]) is not int or not isinstance(command["payload"], dict):
            raise ValueError("Invalid revision or payload")
        if command["domain"] not in {"beats", "words", "faces", "video"} or command["action"] not in {"set", "delete", "undo", "merge", "split", "assign", "portrait", "restore", "note", "acknowledge"}:
            raise ValueError("Unsupported correction")
        if command["domain"] in {"words", "faces"} and not isinstance(command.get("baselineId"), str):
            raise ValueError("Word/face corrections require the immutable baseline ID")
        payload = command["payload"]
        if command["domain"] == "beats" and command["action"] == "set":
            if not isinstance(payload.get("beats"), list) or len(payload["beats"]) > 100_000:
                raise ValueError("Expected bounded beat list")
            if any(not isinstance(b, dict) or type(b.get("timeSec")) not in (float, int) or not math.isfinite(b["timeSec"]) or b["timeSec"] < 0 for b in payload["beats"]):
                raise ValueError("Invalid beat time")
        if any(k in payload and (type(payload[k]) is not int) for k in ("startUs", "endUs")):
            raise ValueError("Normalized anchors must be integer microseconds")
        if "startUs" in payload and "endUs" in payload and payload["endUs"] <= payload["startUs"]:
            raise ValueError("Expected a nonempty half-open range")
        if command["domain"] == "words" and "text" in payload and (not isinstance(payload["text"], str) or len(payload["text"]) > 4096):
            raise ValueError("Invalid word text")
        if command["domain"] == "words" and (("startUs" in payload) != ("endUs" in payload)):
            raise ValueError("Word timing edits require both half-open range endpoints")
        if command["domain"] == "words" and command["action"] == "assign":
            if payload.get("confirmation") != "human-reviewed" or not (payload.get("personId") is None or isinstance(payload.get("personId"), str) and 0 < len(payload["personId"]) <= 256):
                raise ValueError("Speaker/person assignment requires explicit human-reviewed confirmation or unresolved null")
        intent = canonical(command)
        if len(intent.encode()) > 2_000_000:
            raise ValueError("Correction exceeds 2 MB")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT intent,document FROM correction WHERE operation_id=?", (command["operationId"],)).fetchone()
            if old:
                if old["intent"] != intent:
                    raise RevisionConflict("Operation ID reused with different correction")
                return json.loads(old["document"])
            value = json.loads(db.execute("SELECT document FROM project WHERE singleton=1").fetchone()[0])
            if value["revision"] != command["expectedRevision"]:
                raise RevisionConflict(f"Stale correction; current revision {value['revision']}")
            source = next((s for s in value["sources"] if s["id"] == command["sourceId"]), None)
            if source is None or source["sha256"] != command["sourceSha256"]:
                raise ValueError("Correction source identity mismatch")
            if "baselineId" in command and not any(a["id"] == command["baselineId"] and a["sourceId"] == source["id"] for a in value["analysis"]):
                raise ValueError("Correction baseline is not registered to this source")
            if command["action"] == "acknowledge":
                original = db.execute("SELECT document FROM correction WHERE operation_id=?", (payload.get("operationId"),)).fetchone()
                original = json.loads(original[0]) if original else None
                pending = original.get("payload", {}).get("pendingCommand", {}) if original else {}
                if command["domain"] != "faces" or not original or original["sourceId"] != source["id"] or original.get("baselineId") != command.get("baselineId") or not re.fullmatch(r"[a-f0-9]{64}", str(pending.get("commandSha256", ""))) or pending.get("commandSha256") != payload.get("commandSha256") or not re.fullmatch(r"[a-f0-9]{64}", str(payload.get("appliedRevisionSha256", ""))):
                    raise ValueError("Face acknowledgement must bind the original saved cloud command and applied revision")
            if command["action"] == "undo":
                target = db.execute("SELECT document FROM correction WHERE operation_id=?", (payload.get("operationId"),)).fetchone()
                if not target:
                    raise ValueError("Undo target missing")
                original = json.loads(target[0])
                if original["sourceId"] != source["id"] or original["domain"] != command["domain"]:
                    raise ValueError("Undo must reference this source and domain")
                if command["domain"] == "faces" and (original["payload"].get("pendingCommand") or original["action"] == "acknowledge"):
                    raise ValueError("Use an authoritative library restore operation to undo a cloud correction; local history cannot reverse the remote library")
            value["revision"] += 1
            event = {**command, "revision": value["revision"], "schemaVersion": "vibeedit.correction.v1"}
            if command["domain"] == "faces":
                event["remoteStatus"] = "acknowledged" if command["action"] == "acknowledge" else "pending" if payload.get("libraryId") else "local-note"
            db.execute("INSERT INTO correction VALUES (?,?,?,?)", (value["revision"], command["operationId"], intent, canonical(event)))
            db.execute("UPDATE project SET document=? WHERE singleton=1", (canonical(value),))
        self.snapshot()
        return event

    def review(self, source_id, domain, baseline_id=None, *, offset=0, limit=200):
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 1000:
            raise ValueError("Review offset must be nonnegative and limit 1–1000")
        with self.connect() as db:
            db.execute("BEGIN")
            value = json.loads(db.execute("SELECT document FROM project WHERE singleton=1").fetchone()[0])
            all_events = [json.loads(row[0]) for row in db.execute("SELECT document FROM correction ORDER BY revision")]
        source = next((s for s in value["sources"] if s["id"] == source_id), None)
        if source is None:
            raise ValueError("Unknown project source")
        baseline = next((a for a in value["analysis"] if a["id"] == baseline_id and a["sourceId"] == source_id), None) if baseline_id else None
        raw = None
        if baseline:
            path = within(self.root, baseline["path"])
            if file_digest(path) != baseline["sha256"]:
                raise ValueError("Baseline digest mismatch")
            raw = json.loads(path.read_text(encoding="utf-8"))
        coverage = {}
        if raw is not None:
            for key in ("words", "appearances", "faceAppearances", "groups"):
                if isinstance(raw.get(key), list):
                    coverage[key] = {"offset": offset, "limit": limit, "total": len(raw[key])}
                    raw[key] = raw[key][offset:offset + limit]
        undone = set()
        for event in reversed(all_events):
            if event["operationId"] not in undone and event["action"] == "undo":
                undone.add(event["payload"]["operationId"])
        events = [e for e in all_events if e["sourceId"] == source_id and e["domain"] == domain and e["operationId"] not in undone and e["action"] != "undo"]
        conflicts = [e for e in events if e.get("baselineId") and e["baselineId"] != baseline_id]
        active = [e for e in events if e not in conflicts]
        return {"schemaVersion": "vibeedit.review.v1", "ok": True, "revision": value["revision"], "source": source, "baseline": baseline, "machine": raw, "corrections": active, "mappingConflicts": conflicts, "coverage": coverage, "beats": next((e["payload"]["beats"] for e in reversed(active) if domain == "beats" and e["action"] == "set"), [])}

    def apply_review(self, source_id, domain, *, expected_revision, baseline_id=None, source_start_us=0, composition_start_frame=0):
        state = self.read()
        if state["revision"] != expected_revision:
            raise RevisionConflict("Project changed before applying review")
        review = self.review(source_id, domain, baseline_id)
        if review["mappingConflicts"]:
            raise RevisionConflict("Map prior baseline corrections explicitly before applying review")
        composition_file = within(self.root, state["composition"])
        spec = json.loads(composition_file.read_text(encoding="utf-8"))
        if composition_file.name.startswith("composition-") and len(composition_file.stem) == 76 and composition_file.stem[12:] != hashlib.sha256(canonical(spec).encode()).hexdigest():
            raise RevisionConflict("The immutable reviewed composition was edited outside its revision. Save intentional edits as a new composition and use project use-composition before applying review again.")
        rate = Fraction(spec["canvas"]["frameRate"]["numerator"], spec["canvas"]["frameRate"]["denominator"])
        def frame(time_us):
            return composition_start_frame + round(Fraction(time_us - source_start_us, 1_000_000) * rate)
        applied = []
        unmapped = []
        if domain == "beats":
            frames = [frame(round(Fraction(str(beat["timeSec"])) * 1_000_000)) for beat in review["beats"]]
            spec["timeline"]["markers"] = [m for m in spec["timeline"].get("markers", []) if m.get("metadata", {}).get("beatSourceId") != source_id] + [{"id": f"beat-{source_id}-{index}", "frame": time, "label": f"Beat {index + 1}", "kind": "beat", "metadata": {"beatSourceId": source_id, "sourceSha256": review["source"]["sha256"], "reviewRevision": expected_revision}} for index, time in enumerate(frames) if 0 <= time < spec["durationFrames"]]
            for track in spec["timeline"]["tracks"]:
                for item in track["items"]:
                    binding = item.get("metadata", {}).get("reviewBeat")
                    if binding and binding.get("sourceId") == source_id:
                        original = item["metadata"].setdefault("reviewBeatOriginal", {"startFrame": item["placement"]["startFrame"]})
                        item["placement"]["startFrame"] = original["startFrame"]
                        if not any(e["action"] == "set" for e in review["corrections"]):
                            continue
                        index = binding["index"]
                        if type(index) is not int or not 0 <= index < len(frames) or frames[index] < 0:
                            unmapped.append(item["id"])
                            continue
                        item["placement"]["startFrame"] = frames[index] + binding.get("offsetFrames", 0)
                        applied.append(item["id"])
        if domain == "words":
            for track in spec["timeline"]["tracks"]:
                for item in track["items"]:
                    binding = item.get("metadata", {}).get("reviewWord")
                    if not binding or binding.get("sourceId") != source_id or binding.get("baselineId") != baseline_id:
                        continue
                    original = item["metadata"].setdefault("reviewWordOriginal", {"hasText": "text" in item.get("props", {}), "text": item.get("props", {}).get("text"), "startFrame": item["placement"]["startFrame"], "durationFrames": item["placement"]["durationFrames"], "enabled": item["placement"].get("enabled", True), "hasPersonLink": "reviewedPersonLink" in item["metadata"], "personLink": item["metadata"].get("reviewedPersonLink")})
                    if original["hasText"]:
                        item.setdefault("props", {})["text"] = original["text"]
                    else:
                        item.setdefault("props", {}).pop("text", None)
                    item["placement"].update({key: original[key] for key in ("startFrame", "durationFrames", "enabled")})
                    if original.get("hasPersonLink"):
                        item["metadata"]["reviewedPersonLink"] = original["personLink"]
                    else:
                        item["metadata"].pop("reviewedPersonLink", None)
            for event in review["corrections"]:
                matches = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item.get("metadata", {}).get("reviewWord") == {"sourceId": source_id, "baselineId": baseline_id, "targetId": event["targetId"]}]
                if not matches:
                    unmapped.append(event["operationId"])
                for item in matches:
                    if event["action"] == "delete":
                        item["placement"]["enabled"] = False
                    if event["action"] in {"set", "restore"}:
                        if event["action"] == "restore":
                            item["placement"]["enabled"] = True
                        if "text" in event["payload"]:
                            item.setdefault("props", {})["text"] = event["payload"]["text"]
                        if "startUs" in event["payload"] and "endUs" in event["payload"]:
                            if event["payload"].get("clock") == "first-decoded-audio-sample" and any(stream["codec_type"] == "video" for stream in review["source"]["streams"]):
                                unmapped.append(event["operationId"] + ":audio-video-projection-required")
                                continue
                            item["placement"]["startFrame"] = frame(event["payload"]["startUs"])
                            item["placement"]["durationFrames"] = max(1, frame(event["payload"]["endUs"]) - frame(event["payload"]["startUs"]))
                    if event["action"] == "assign":
                        item.setdefault("metadata", {})["reviewedPersonLink"] = {"personId": event["payload"].get("personId"), "status": "human-confirmed" if event["payload"].get("personId") else "unresolved", "sourceId": source_id, "baselineId": baseline_id, "wordId": event["targetId"], "operationId": event["operationId"]}
                    applied.append(item["id"])
        spec.setdefault("metadata", {})["reviewApplication"] = {"sourceId": source_id, "sourceSha256": review["source"]["sha256"], "domain": domain, "revision": expected_revision, "parentCompositionSha256": file_digest(composition_file), "parentComposition": state["composition"], "sourceStartUs": source_start_us, "compositionStartFrame": composition_start_frame, "appliedLayers": applied, "unmapped": unmapped}
        if unmapped:
            return {"schemaVersion": "vibeedit.reviewApplication.v1", "ok": False, "unmapped": unmapped, "action": "Resolve source clocks and layer bindings, then retry the same project revision; composition was preserved"}
        validate_composition(spec)
        digest = hashlib.sha256(canonical(spec).encode()).hexdigest()
        output = within(self.root, f"composition-{digest}.json")
        atomic_json(output, spec)
        self.update(expected_revision, lambda value: value.update(composition=output.name))
        return {"schemaVersion": "vibeedit.reviewApplication.v1", "ok": True, "composition": output.name, "sha256": file_digest(output), "appliedLayers": applied, "unmapped": unmapped, "renderCommand": ["vibeedit", "render", str(output), "--json"]}


def _clock_census(source, destination, streams, digest):
    temporary = destination.with_name(f".{uuid.uuid4().hex}.tmp")
    process = subprocess.Popen([ffprobe_path(), "-v", "error", "-show_frames", "-show_entries", "frame=stream_index,media_type,pts,best_effort_timestamp,pkt_dts,duration,nb_samples,key_frame,width,height", "-of", "compact=p=0:nk=0", str(source)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    counts = {}
    previous = {}
    discontinuities = 0
    with temporary.open("x", encoding="utf8") as output:
        output.write(canonical({"schemaVersion": "vibeedit.sourceClock.v1", "kind": "header", "sourceSha256": digest, "nativeIntegerEncoding": "decimal-string", "streams": [{key: str(value) if key in {"start_pts", "duration_ts"} else value for key, value in stream.items()} for stream in streams]}) + "\n")
        for line in process.stdout:
            values = dict(part.split("=", 1) for part in line.strip().split("|") if "=" in part)
            if "stream_index" not in values or values.get("media_type") not in {"audio", "video"}:
                continue
            stream = values["stream_index"]
            ordinal = counts.get(stream, 0)
            counts[stream] = ordinal + 1
            record = {"kind": "frame", "streamIndex": int(stream), "frameOrdinal": ordinal, **values}
            if "pts" in values and values["pts"] != "N/A":
                pts = int(values["pts"])
                prior = previous.get(stream)
                if prior and (pts < prior[0] or prior[1] is not None and pts != prior[0] + prior[1]):
                    record["discontinuity"] = {"previousPts": str(prior[0]), "previousDuration": str(prior[1]) if prior[1] is not None else None, "deltaTicks": str(pts - prior[0] - prior[1]) if prior[1] is not None else None, "backward": pts < prior[0]}
                    discontinuities += 1
                previous[stream] = (pts, int(values["duration"]) if values.get("duration", "N/A") != "N/A" else None)
            output.write(canonical(record) + "\n")
        if process.wait():
            temporary.unlink(missing_ok=True)
            raise ValueError("Native source clock census failed")
        output.write(canonical({"kind": "census", "complete": True, "nativeFrameCounts": counts, "discontinuities": discontinuities}) + "\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, destination)


def create_project(path, composition):
    root = Path(path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / "project.vibeedit.json").exists():
        return Project(root).snapshot()
    original = Path(composition).resolve()
    spec = json.loads(original.read_text(encoding="utf-8"))
    validate_composition(spec)
    if spec.get("sources"):
        raise ValueError("Import media after creating the project; source copies must be content bound")
    atomic_json(root / "composition.json", spec)
    value = {"schemaVersion": "vibeedit.project.v1", "id": f"project-{uuid.uuid4()}", "revision": 0, "composition": "composition.json", **{k: [] for k in ("sources", "analysis", "beats", "masks", "reviews", "workers", "goals", "renders")}}
    atomic_json(root / "project.vibeedit.json", value)
    return Project(root).read()


def normalize_word(word, source_timeline):
    projected = source_timeline.get("audioToVideoMillis") is not None
    offset = Fraction(str(source_timeline["audioToVideoMillis"])) if projected else Fraction(0)
    return {"ordinal": word["ordinal"], "startUs": round((Fraction(str(word["start"])) + offset) * 1000), "endUs": round((Fraction(str(word["end"])) + offset) * 1000), "native": word, "clock": "video-relative" if projected else "first-decoded-audio-sample", "videoProjectionAvailable": projected, "offsetMillis": str(offset) if projected else None, "independentlyVerified": False}


def register_commands(subparsers):
    parser = subparsers.add_parser("project", help="portable content-bound projects and human corrections")
    actions = parser.add_subparsers(dest="project_command", required=True)
    for name in ("create", "inspect", "import", "relink", "export", "bundle", "restore", "register-artifact", "use-composition", "correct", "review", "apply-review", "import-analysis", "import-faces"):
        action = actions.add_parser(name)
        action.add_argument("path")
        action.add_argument("--json", action="store_true")
        action.add_argument("--composition")
        action.add_argument("--media")
        action.add_argument("--source-id")
        action.add_argument("--expected-revision", type=int)
        action.add_argument("--command-file")
        action.add_argument("--output")
        action.add_argument("--archive")
        action.add_argument("--archive-bytes", type=int)
        action.add_argument("--sha256")
        action.add_argument("--omit-media", action="store_true")
        action.add_argument("--max-bytes", type=int, default=64 * 1024**3)
        action.add_argument("--domain", choices=("beats", "faces", "words", "video"), default="video")
        action.add_argument("--baseline-id")
        action.add_argument("--offset", type=int, default=0)
        action.add_argument("--limit", type=int, default=200)
        action.add_argument("--analysis-file")
        action.add_argument("--artifact")
        action.add_argument("--category", choices=("beats", "masks", "reviews", "renders"))
        action.add_argument("--service", choices=("video", "faces", "speakers"))
        action.add_argument("--job-id")
        action.add_argument("--schema-version")
        action.add_argument("--source-start-us", type=int, default=0)
        action.add_argument("--composition-start-frame", type=int, default=0)
        action.set_defaults(handler=_command)


def _command(args):
    if args.project_command == "restore":
        if not args.archive:
            raise ValueError("--archive is required")
        from vibeedit.portable import restore_project
        result = restore_project(args.archive, args.path, expected_sha256=args.sha256, max_bytes=args.max_bytes)
    elif args.project_command == "bundle":
        if not args.output:
            raise ValueError("--output is required")
        from vibeedit.portable import bundle_project
        result = bundle_project(args.path, args.output, include_media=not args.omit_media, max_bytes=args.max_bytes)
    elif args.project_command == "create":
        if not args.composition:
            raise ValueError("--composition is required")
        result = create_project(args.path, args.composition)
    else:
        project = Project(args.path)
        if args.project_command == "import":
            if not args.media or args.expected_revision is None:
                raise ValueError("--media and --expected-revision are required")
            result = project.register_source(args.media, expected_revision=args.expected_revision)
        elif args.project_command == "relink":
            if not args.source_id or not args.media or args.expected_revision is None:
                raise ValueError("--source-id, --media and --expected-revision are required")
            result = project.relink(args.source_id, args.media, expected_revision=args.expected_revision)
        elif args.project_command == "correct":
            if not args.command_file:
                raise ValueError("--command-file is required")
            result = project.correct(json.loads(Path(args.command_file).read_text(encoding="utf-8")))
        elif args.project_command == "register-artifact":
            if not args.artifact or not args.category or args.expected_revision is None:
                raise ValueError("--artifact, --category and --expected-revision are required")
            result = project.register_artifact(args.category, args.artifact, expected_revision=args.expected_revision, source_id=args.source_id)
        elif args.project_command == "use-composition":
            if not args.composition or args.expected_revision is None:
                raise ValueError("--composition and --expected-revision are required")
            result = project.use_composition(args.composition, expected_revision=args.expected_revision)
        elif args.project_command == "import-analysis":
            if not all((args.source_id, args.analysis_file, args.service, args.job_id, args.schema_version)) or args.expected_revision is None:
                raise ValueError("--source-id, --analysis-file, --service, --job-id, --schema-version and --expected-revision are required")
            result = project.import_analysis(args.source_id, args.analysis_file, service=args.service, job_id=args.job_id, schema_version=args.schema_version, expected_revision=args.expected_revision)
        elif args.project_command == "import-faces":
            if not all((args.source_id, args.archive, args.job_id, args.sha256, args.archive_bytes)) or args.expected_revision is None:
                raise ValueError("--source-id, --archive, --job-id, --sha256, --archive-bytes and --expected-revision are required")
            result = project.import_faces(args.source_id, args.archive, job_id=args.job_id, archive_sha256=args.sha256, archive_bytes=args.archive_bytes, expected_revision=args.expected_revision)
        elif args.project_command == "apply-review":
            if args.expected_revision is None:
                raise ValueError("--expected-revision is required")
            result = project.apply_review(args.source_id, args.domain, expected_revision=args.expected_revision, baseline_id=args.baseline_id, source_start_us=args.source_start_us, composition_start_frame=args.composition_start_frame)
        elif args.project_command == "review":
            result = project.review(args.source_id, args.domain, args.baseline_id, offset=args.offset, limit=args.limit)
        elif args.project_command == "export":
            result = {"schemaVersion": "vibeedit.projectExport.v1", "project": project.snapshot(), "corrections": project.corrections()}
            if args.output:
                atomic_json(args.output, result)
        else:
            result = project.snapshot()
    print(json.dumps({"schemaVersion": "vibeedit.projectCommand.v1", "ok": True, "result": result}, ensure_ascii=False))
    return 0
