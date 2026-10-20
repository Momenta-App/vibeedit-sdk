"""Read-only native face-package import and source-bound review adapters.

No identity model or cloud mutation runs here. Original ZIP/member bytes remain
separate from the derived SQLite index and any caller-owned correction journal.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import uuid
import zipfile
from collections import Counter
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from vibeedit.ffmpeg import ffmpeg_path, ffprobe_path

SCHEMA = "vibeedit.faceReviewIndex.v1"
MAX_FRAMES = 120 * 14400


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _sha(value):
    return isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value) is not None


def _id(value):
    return isinstance(value, str) and 0 < len(value) <= 256 and not any(ord(c) < 32 for c in value)


def _person(value):
    return isinstance(value, str) and re.fullmatch("person_[a-f0-9]{32}", value) is not None


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _member(name):
    _require(isinstance(name, str) and name and "\\" not in name and ":" not in name and not name.startswith("/") and all(p not in {"", ".", ".."} for p in name.split("/")), "Unsafe native face package member")
    _require(all(part.rstrip(" .") == part and part.split(".")[0].upper() not in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]} for part in name.split("/")), "Native member is not portable to Windows")
    return PurePosixPath(name)


def _document(path, ceiling=16 * 1024 ** 2):
    _require(path.stat().st_size <= ceiling, "Native face metadata exceeds its bound")
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "Expected a native face metadata object")
    return value


def import_face_package(archive, destination, *, job_id, source_sha256, archive_sha256, archive_bytes, source_byte_length=None, package_reference=None, max_expanded_bytes=2 * 1024 ** 3):
    """Verify exact transport, every member and native census before publishing."""
    archive = Path(archive).resolve(strict=True)
    destination = Path(destination).absolute()
    _require(all(_sha(x) for x in (job_id, source_sha256, archive_sha256)) and _integer(archive_bytes, 1), "Exact native job/source/archive identities are required")
    _require(_integer(max_expanded_bytes, 1) and archive.stat().st_size == archive_bytes and _digest(archive) == archive_sha256, "Native face archive SHA256/length mismatch")
    _require(source_byte_length is None or _integer(source_byte_length, 1), "Expected source byte length must be a positive integer")
    if package_reference is not None:
        _require(isinstance(package_reference, dict) and set(package_reference) == {"bucket", "key", "versionId", "artifactSha256", "byteLength"} and all(isinstance(package_reference[k], str) and package_reference[k] for k in ("bucket", "key", "versionId")) and package_reference["versionId"] != "null" and package_reference["artifactSha256"] == archive_sha256 and package_reference["byteLength"] == archive_bytes, "Exact versioned native package reference changed")
    _require(not destination.exists() and not destination.is_symlink(), "Face import destination exists; preserve the original import")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".face-import-", dir=destination.parent))
    try:
        native = stage / "native"
        native.mkdir(mode=0o700)
        with zipfile.ZipFile(archive) as zipped:
            infos = zipped.infolist()
            names = [i.filename for i in infos]
            _require(0 < len(names) <= 100_000 and len(set(names)) == len(names), "Duplicate or excessive native ZIP members")
            for info in infos:
                _member(info.filename)
                mode = stat.S_IFMT(info.external_attr >> 16)
                _require(mode in {0, stat.S_IFREG} and not info.flag_bits & 1 and info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}, "Native ZIP permits only unencrypted regular files")
            _require(sum(i.file_size for i in infos) <= max_expanded_bytes and zipped.getinfo("manifest.json").file_size <= 16 * 1024 ** 2, "Native face expansion limit exceeded")
            manifest = json.loads(zipped.read("manifest.json"))
            _require(manifest.get("schemaVersion") in {"myriograph.faceIdentityResult.v1", "myriograph.faceIdentityResult.v2"} and manifest.get("jobId") == job_id and manifest.get("sourceSha256") == source_sha256 and _sha(manifest.get("runtimeSha256")), "Native face manifest identity changed")
            declarations = manifest.get("files")
            _require(isinstance(declarations, list) and len(declarations) == len(names) - 1 and set(names) == {"manifest.json", *(d["path"] for d in declarations)}, "Native face ZIP has unbound or repeated members")
            _require({"source.json", "people.json", "tracks.json", "faces.jsonl", "provenance.json"} <= set(names), "Native face package is missing its declared review files")
            free = shutil.disk_usage(stage).free
            _require(free > 2 * sum(i.file_size for i in infos) + archive_bytes + 64 * 1024 ** 2, "Insufficient disk for verified native face import/index")
            for info in infos:
                target = native / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(info) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
            for item in declarations:
                _require(_sha(item.get("sha256")) and _integer(item.get("byteLength")) and (native / item["path"]).stat().st_size == item["byteLength"] and _digest(native / item["path"]) == item["sha256"], "Native face member SHA256/length mismatch")
        metadata = _build_index(native, stage / "review-index.sqlite3", manifest, source_byte_length)
        shutil.copyfile(archive, stage / "native.faces.zip")
        _require(_digest(stage / "native.faces.zip") == archive_sha256, "Native archive changed during import")
        receipt = {"schemaVersion": SCHEMA, "ok": True, "sourceSha256": source_sha256, "sourceByteLength": metadata["sourceByteLength"], "jobId": job_id, "archiveSha256": archive_sha256, "archiveByteLength": archive_bytes, "packageReference": package_reference, "manifestSha256": _digest(native / "manifest.json"), "nativeSchemaVersion": manifest["schemaVersion"], "index": "review-index.sqlite3", "indexSha256": _digest(stage / "review-index.sqlite3"), "members": declarations, "coverage": metadata["coverage"], "library": metadata["library"], "cloudAppearanceSelectorsAvailable": metadata["mappingAvailable"], "state": "unreviewed-native-predictions", "limits": ["Anonymous assignments may fragment or remain null; import integrity is not identity accuracy", "Representative JPEGs are evidence cards, not native source frames", "Cloud commands remain pending until authoritative revision acknowledgement", "Native v1/v2 source clock is upstream CFR-qualified; no VFR timing is invented"]}
        (stage / "import-receipt.json").write_text(_json(receipt) + "\n", encoding="utf-8")
        baseline = {"schemaVersion": SCHEMA, "sourceSha256": source_sha256, "jobId": job_id, "archiveSha256": archive_sha256, "index": "review-index.sqlite3", "indexSha256": receipt["indexSha256"], "nativeManifest": "native/manifest.json", "coverage": metadata["coverage"], "library": metadata["library"], "cloudAppearanceSelectorsAvailable": metadata["mappingAvailable"], "limitations": receipt["limits"]}
        (stage / "review-baseline.json").write_text(_json(baseline) + "\n", encoding="utf-8")
        # An unexpected new destination is never merged or overwritten.
        _require(not destination.exists() and not destination.is_symlink(), "Face import destination appeared during validation")
        destination.mkdir(mode=0o700)  # Exclusive destination claim; never replace another import.
        # The receipt is the commit marker; partial unpublished imports stay inspectable.
        for path in sorted(stage.iterdir(), key=lambda path: path.name == "import-receipt.json"):
            os.rename(path, destination / path.name)
        stage.rmdir()
        return {**receipt, "directory": str(destination.resolve()), "indexPath": str(destination.resolve() / receipt["index"]), "baselinePath": str(destination.resolve() / "review-baseline.json")}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _build_index(native, index, manifest, source_byte_length):
    source = _document(native / "source.json")
    people = _document(native / "people.json")
    tracks = _document(native / "tracks.json")["tracks"]
    provenance = _document(native / "provenance.json")
    specification = source["specification"]
    source_ref = specification["source"]
    _require(isinstance(source_ref, dict) and set(source_ref) == {"bucket", "key", "versionId", "artifactSha256", "byteLength"} and all(isinstance(source_ref[k], str) and source_ref[k] for k in ("bucket", "key", "versionId")) and source_ref["versionId"] != "null", "Native versioned source reference changed")
    v2 = manifest["schemaVersion"].endswith(".v2")
    _require(source.get("schemaVersion") == ("myriograph.faceSource.v2" if v2 else "myriograph.faceSource.v1") and source.get("jobId") == manifest["jobId"] and specification["source"]["artifactSha256"] == manifest["sourceSha256"] and specification["runtimeSha256"] == manifest["runtimeSha256"], "Native source/specification binding changed")
    _require(provenance.get("schemaVersion") == "myriograph.faceProvenance.v1" and all(provenance.get(k) == manifest[k] for k in ("jobId", "sourceSha256", "runtimeSha256")), "Native provenance binding changed")
    _require(people.get("schemaVersion") == "myriograph.facePeople.v1" and isinstance(people.get("appearanceGroups"), dict) and isinstance(people.get("people"), list) and isinstance(tracks, list), "Native person/track inventory changed")
    dimensions = [source["width"], source["height"]]
    _require(all(_integer(v, 1) and v <= 8192 for v in dimensions) and _integer(source["frameCount"], 1) and source["frameCount"] <= MAX_FRAMES and _integer(source["faceObservationCount"]), "Native geometry/census outside bounds")
    byte_length = specification["source"]["byteLength"]
    _require(_integer(byte_length, 1) and (source_byte_length is None or source_byte_length == byte_length), "Original native source byte length changed")
    rate, tick = Fraction(source["rate"]), Fraction(source["timeBase"])
    _require(0 < rate <= 120 and tick > 0, "Invalid native rational source clock")
    first, end = source["sourceFrameRange"] if v2 else (0, source["frameCount"])
    total = source["sourceTotalFrameCount"] if v2 else source["frameCount"]
    _require(all(_integer(v) for v in (first, end, total)) and 0 <= first < end <= total <= MAX_FRAMES and end - first == source["frameCount"], "Native source-frame range changed")
    tolerance = Fraction(str(source["maximumAllowedClockResidualMicros"])) / 1_000_000 if v2 else min(Fraction(1, 1000) + tick, Fraction(1, 4) / rate)
    _require(0 < tolerance <= min(Fraction(1, 1000) + tick, Fraction(1, 4) / rate), "Native clock tolerance outside qualified contract")
    library = specification.get("library") if v2 else None
    if v2:
        _require(isinstance(library, dict) and set(library) == {"libraryId", "revision", "embeddingSpaceSha256"} and isinstance(library["libraryId"], str) and re.fullmatch("[a-z0-9][a-z0-9-]{0,63}", library["libraryId"]) and _sha(library["embeddingSpaceSha256"]) and isinstance(library["revision"], dict) and set(library["revision"]) == {"bucket", "key", "versionId", "artifactSha256", "byteLength"} and _sha(library["revision"]["artifactSha256"]) and _integer(library["revision"]["byteLength"], 1) and all(isinstance(library["revision"][k], str) and library["revision"][k] for k in ("bucket", "key", "versionId")) and library["revision"]["versionId"] != "null", "Native persistent library pin changed")
        _require(specification.get("schemaVersion") == "myriograph.faceIdentityJob.v2" and (specification.get("frameRange") or [0, total]) == [first, end] and provenance["library"]["input"] == library, "Native requested range or pinned library changed")
    mapping_path = native / "library-mapping.json"
    group_keys = {}
    if mapping_path.is_file():
        mapping = _document(mapping_path)
        review = mapping.get("reviewBinding", {})
        _require(v2 and mapping.get("schemaVersion") == "myriograph.faceLibraryAppearances.v1" and mapping.get("jobId") == manifest["jobId"] and mapping.get("sourceSha256") == manifest["sourceSha256"] and mapping.get("frameRange") == [first, end] and review.get("library") == library and _sha(review.get("sourceMappingSha256")), "Native library review mapping binding changed")
        group_keys = review["appearanceGroupKeys"]
        _require(isinstance(group_keys, dict) and set(group_keys) == set(people["appearanceGroups"]) and len(set(group_keys.values())) == len(group_keys), "Native library display-group bridge changed")
        _require(all(isinstance(key, str) and re.fullmatch("[a-f0-9]{64}:G[0-9]{3,5}", key) and mapping["appearances"].get(key) == people["appearanceGroups"][g] for g, key in group_keys.items()), "Native library appearance selectors changed")
    metadata = {"schemaVersion": SCHEMA, "jobId": manifest["jobId"], "sourceSha256": manifest["sourceSha256"], "sourceByteLength": byte_length, "width": dimensions[0], "height": dimensions[1], "rate": str(rate), "timeBase": str(tick), "library": library, "organizationId": specification.get("organizationId"), "projectId": specification.get("projectId"), "mappingAvailable": bool(group_keys) or mapping_path.is_file(), "coverage": {"sourceFrameRange": [first, end], "sourceTotalFrameCount": total, "requestedFrameCount": end - first, "faceObservationCount": source["faceObservationCount"], "nativeRangeUnits": provenance.get("library", {}).get("nativeRangeUnits", [])}}
    proof = provenance.get("nativeConsumerProof", {})
    _require(proof.get("allNativePtsVerified") is True and proof.get("allFramesCropsEmbeddingsAndMembershipsVerified") is True and proof.get("sourceSha256") == manifest["sourceSha256"] and proof.get("frameCount") == end - first, "Native upstream consumer proof binding changed")
    groups = people["appearanceGroups"]
    person_ids = {p["personId"] for p in people["people"]}
    _require(len(person_ids) == len(people["people"]) and all(_person(p) for p in person_ids), "Invalid native anonymous person IDs")
    db = sqlite3.connect(index)
    try:
        db.executescript("""PRAGMA journal_mode=DELETE;
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE frames(ordinal INTEGER PRIMARY KEY,pts INTEGER UNIQUE,timestamp_us INTEGER,end_us INTEGER);
        CREATE TABLE people(id TEXT PRIMARY KEY,native_json TEXT);
        CREATE TABLE groups(id TEXT PRIMARY KEY,person_id TEXT,status TEXT,appearance_key TEXT,native_json TEXT);
        CREATE TABLE tracks(id TEXT PRIMARY KEY,group_id TEXT,first_frame INTEGER,last_frame INTEGER,frame_count INTEGER,native_json TEXT);
        CREATE TABLE appearances(id TEXT PRIMARY KEY,ordinal INTEGER,face_id TEXT,track_id TEXT,group_id TEXT,person_id TEXT,status TEXT,appearance_key TEXT,embedding_row INTEGER UNIQUE,native_cache_id TEXT,native_embedding_row INTEGER,native_json TEXT,UNIQUE(native_cache_id,native_embedding_row));
        CREATE INDEX group_appearances ON appearances(group_id,ordinal,embedding_row);
        CREATE INDEX person_appearances ON appearances(person_id,ordinal,embedding_row);
        CREATE INDEX frame_appearances ON appearances(ordinal,embedding_row);
        CREATE INDEX track_appearances ON appearances(track_id,ordinal);
        """)
        db.execute("INSERT INTO metadata VALUES ('document',?)", (_json(metadata),))
        for person in people["people"]:
            _require(isinstance(person.get("appearanceGroupIds"), list) and set(person["appearanceGroupIds"]) == {g for g, row in groups.items() if row.get("personId") == person["personId"]}, "Native person/group membership changed")
            db.execute("INSERT INTO people VALUES (?,?)", (person["personId"], _json(person)))
        statuses = Counter()
        for group, row in groups.items():
            _require(_id(group) and row.get("status") in {"single", "mixed", "uncertain"} and (row.get("personId") is not None) == (row["status"] == "single") and (row.get("personId") is None or row["personId"] in person_ids), "Native unresolved/group membership changed")
            statuses[row["status"]] += 1
            db.execute("INSERT INTO groups VALUES (?,?,?,?,?)", (group, row.get("personId"), row["status"], group_keys.get(group), _json(row)))
        _require(dict(statuses) == people["groupStatusCounts"], "Native status census changed")
        for track in tracks:
            _require(_id(track.get("trackId")) and track.get("appearanceGroupId") in groups and _integer(track.get("frameCount"), 1) and first <= track["firstFrameOrdinal"] <= track["lastFrameOrdinal"] < end and track.get("personId") == groups[track["appearanceGroupId"]]["personId"] and track.get("status") == groups[track["appearanceGroupId"]]["status"], "Native track/group binding changed")
            db.execute("INSERT INTO tracks VALUES (?,?,?,?,?,?)", (track["trackId"], track["appearanceGroupId"], track["firstFrameOrdinal"], track["lastFrameOrdinal"], track["frameCount"], _json(track)))
        cache_ids = {unit["cacheId"] for unit in metadata["coverage"]["nativeRangeUnits"]}
        count = frame_count = 0
        previous_pts = None
        with (native / "faces.jsonl").open("rb") as stream:
            while raw := stream.readline(4 * 1024 ** 2 + 1):
                _require(0 < len(raw) <= 4 * 1024 ** 2 and frame_count < source["frameCount"], "Native face row/frame census exceeds bound")
                frame = json.loads(raw)
                ordinal, pts = frame["frameOrdinal"], frame["pts"]
                _require(type(ordinal) is int and ordinal == first + frame_count and type(pts) is int and (previous_pts is None or pts > previous_pts) and abs(pts * tick - Fraction(ordinal, 1) / rate) <= tolerance and frame["timestampMicros"] == round(pts * tick * 1_000_000), "Native face frame/PTS clock changed")
                if frame_count:
                    db.execute("UPDATE frames SET end_us=? WHERE ordinal=?", (frame["timestampMicros"], ordinal - 1))
                db.execute("INSERT INTO frames VALUES (?,?,?,NULL)", (ordinal, pts, frame["timestampMicros"]))
                previous_pts = pts
                frame_count += 1
                seen = set()
                _require(isinstance(frame["faces"], list) and len(frame["faces"]) <= 1000, "Native face frame list exceeds bound")
                for face in frame["faces"]:
                    group = face["appearanceGroupId"]
                    _require(group in groups and _id(face.get("faceId")) and face["faceId"] not in seen and face.get("embeddingRow") == count and type(face["embeddingRow"]) is int and face.get("personId") == groups[group]["personId"] and face.get("identityStatus") == groups[group]["status"], "Native face observation/group binding changed")
                    seen.add(face["faceId"])
                    _require(isinstance(face.get("bbox"), list) and len(face["bbox"]) == 4 and all(type(v) in (int, float) and math.isfinite(v) for v in face["bbox"]) and face["bbox"][2] > 0 and face["bbox"][3] > 0, "Native normalized xywh geometry changed")
                    _require(isinstance(face.get("landmarks"), list) and all(isinstance(p, dict) and all(type(p.get(k)) in (int, float) and math.isfinite(p[k]) for k in ("x", "y")) for p in face["landmarks"]), "Native landmark geometry changed")
                    native_cache = face.get("nativeCacheId")
                    native_row = face.get("nativeEmbeddingRow")
                    if v2:
                        _require(native_cache in cache_ids and _sha(native_cache) and _integer(native_row) and (group not in group_keys or group_keys[group].split(":")[0] == native_cache), "Native cache/group appearance bridge changed")
                    track = db.execute("SELECT group_id FROM tracks WHERE id=?", (face["trackId"],)).fetchone()
                    _require(track is not None and track[0] == group, "Native face references an unknown track")
                    appearance = hashlib.sha256(_json([manifest["jobId"], ordinal, face["faceId"], face["embeddingRow"]]).encode()).hexdigest()
                    db.execute("INSERT INTO appearances VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (appearance, ordinal, face["faceId"], face["trackId"], group, face.get("personId"), face["identityStatus"], group_keys.get(group), count, native_cache, native_row, _json(face)))
                    count += 1
        _require(frame_count == source["frameCount"] and count == source["faceObservationCount"], "Native complete requested frame/face census changed")
        for track in db.execute("SELECT id,first_frame,last_frame,frame_count FROM tracks"):
            actual = db.execute("SELECT min(ordinal),max(ordinal),count(*) FROM appearances WHERE track_id=?", (track[0],)).fetchone()
            _require(tuple(actual) == tuple(track[1:]), "Native track observation census changed")
        db.commit()
    finally:
        db.close()
    return metadata


@contextmanager
def _open_index(index):
    path = Path(index).resolve(strict=True)
    _require(path.name == "review-index.sqlite3", "Choose the verified native face review index")
    receipt = _document(path.parent / "import-receipt.json")
    _require(receipt.get("schemaVersion") == SCHEMA and receipt.get("indexSha256") == _digest(path), "Derived face index changed; reimport original native ZIP to a new directory")
    db = sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    try:
        metadata = json.loads(db.execute("SELECT value FROM metadata WHERE key='document'").fetchone()[0])
        _require(metadata["jobId"] == receipt["jobId"] and metadata["sourceSha256"] == receipt["sourceSha256"], "Face index receipt binding changed")
        yield db, metadata, receipt
    finally:
        db.close()


def _page(offset, limit):
    _require(_integer(offset) and type(limit) is int and 1 <= limit <= 500, "Review page requires nonnegative offset and limit 1–500")


def page_groups(index, *, offset=0, limit=100):
    _page(offset, limit)
    with _open_index(index) as (db, metadata, receipt):
        total = db.execute("SELECT count(*) FROM groups").fetchone()[0]
        rows = []
        for row in db.execute("SELECT g.*,count(a.id) observations,min(a.ordinal) first_frame,max(a.ordinal) last_frame FROM groups g LEFT JOIN appearances a ON a.group_id=g.id GROUP BY g.id ORDER BY g.id LIMIT ? OFFSET ?", (limit, offset)):
            rows.append({"id": row["id"], "personId": row["person_id"], "status": row["status"], "appearanceKey": row["appearance_key"], "observationCount": row["observations"], "firstFrameOrdinal": row["first_frame"], "lastFrameOrdinal": row["last_frame"], "native": json.loads(row["native_json"])})
        return {"schemaVersion": SCHEMA, "ok": True, "jobId": metadata["jobId"], "sourceSha256": metadata["sourceSha256"], "archiveSha256": receipt["archiveSha256"], "library": metadata["library"], "cloudAppearanceSelectorsAvailable": metadata["mappingAvailable"], "coverage": metadata["coverage"], "offset": offset, "limit": limit, "total": total, "groups": rows, "nextOffset": offset + limit if offset + limit < total else None}


def page_appearances(index, *, offset=0, limit=100, group_id=None, person_id=None, start_frame=None, end_frame=None):
    _page(offset, limit)
    conditions, values = [], []
    for key, value in (("a.group_id", group_id), ("a.person_id", person_id)):
        if value is not None:
            _require(_id(value), "Invalid face review selector")
            conditions.append(key + "=?"); values.append(value)
    for operator, value in ((">=", start_frame), ("<", end_frame)):
        if value is not None:
            _require(_integer(value), "Frame filters require native ordinals")
            conditions.append("a.ordinal" + operator + "?"); values.append(value)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with _open_index(index) as (db, metadata, receipt):
        total = db.execute("SELECT count(*) FROM appearances a" + where, values).fetchone()[0]
        rows = []
        for row in db.execute("SELECT a.*,f.pts,f.timestamp_us,f.end_us FROM appearances a JOIN frames f ON f.ordinal=a.ordinal" + where + " ORDER BY a.ordinal,a.embedding_row LIMIT ? OFFSET ?", [*values, limit, offset]):
            face = json.loads(row["native_json"])
            rows.append({"id": row["id"], "frameOrdinal": row["ordinal"], "pts": row["pts"], "startUs": row["timestamp_us"], "endUs": row["end_us"], "timingQuality": "native-presentation-range" if row["end_us"] is not None else "range-final-duration-unavailable", "faceId": row["face_id"], "trackId": row["track_id"], "groupId": row["group_id"], "personId": row["person_id"], "status": row["status"], "appearanceKey": row["appearance_key"], "geometry": {"coordinateSpace": "normalized-native-source", "boxFormat": "xywh", "bbox": face["bbox"], "landmarks": face["landmarks"], "width": metadata["width"], "height": metadata["height"], "rotationApplied": False}, "native": face})
        return {"schemaVersion": SCHEMA, "ok": True, "jobId": metadata["jobId"], "sourceSha256": metadata["sourceSha256"], "archiveSha256": receipt["archiveSha256"], "offset": offset, "limit": limit, "total": total, "appearances": rows, "nextOffset": offset + limit if offset + limit < total else None}


def preview_request(index, appearance_id):
    _require(_sha(appearance_id), "Choose a saved native face appearance")
    with _open_index(index) as (db, metadata, receipt):
        row = db.execute("SELECT a.*,f.pts,f.timestamp_us FROM appearances a JOIN frames f ON f.ordinal=a.ordinal WHERE a.id=?", (appearance_id,)).fetchone()
        _require(row is not None, "Unknown native face appearance")
        face = json.loads(row["native_json"])
        return {"schemaVersion": "vibeedit.facePreviewRequest.v1", "jobId": metadata["jobId"], "archiveSha256": receipt["archiveSha256"], "sourceSha256": metadata["sourceSha256"], "sourceByteLength": metadata["sourceByteLength"], "appearanceId": appearance_id, "groupId": row["group_id"], "personId": row["person_id"], "frameOrdinal": row["ordinal"], "pts": row["pts"], "timestampMicros": row["timestamp_us"], "timeBase": metadata["timeBase"], "width": metadata["width"], "height": metadata["height"], "bbox": face["bbox"], "boxFormat": "normalized-native-xywh", "landmarks": face["landmarks"], "purpose": "source-bound review preview; not an aligned crop hash or new identity inference"}


def render_preview(index, source, request, output, *, portrait=False, max_width=960):
    _require(isinstance(request, dict) and _json(request) == _json(preview_request(index, request.get("appearanceId"))), "Face preview request differs from saved native evidence")
    _require(type(portrait) is bool and type(max_width) is int and 32 <= max_width <= 2048, "Invalid face preview dimensions")
    source = Path(source).resolve(strict=True)
    output = Path(output).absolute()
    _require(source.stat().st_size == request["sourceByteLength"] and _digest(source) == request["sourceSha256"], "Relink the exact original source before requesting face previews")
    _require(not output.exists() and not output.is_symlink(), "Face preview output exists; preserve the original")
    probe = subprocess.run([ffprobe_path(), "-v", "error", "-select_streams", "V:0", "-show_entries", "stream=index,width,height,time_base", "-of", "json", str(source)], capture_output=True, text=True, check=True, timeout=30)
    stream = json.loads(probe.stdout)["streams"][0]
    _require((stream["width"], stream["height"], Fraction(stream["time_base"])) == (request["width"], request["height"], Fraction(request["timeBase"])), "Original source geometry/time base differs from native face package")
    crop = None
    filters = [f"select=eq(pts\\,{request['pts']})", "showinfo"]
    if portrait:
        x, y, width, height = request["bbox"]
        left = max(0, math.floor(x * stream["width"])); top = max(0, math.floor(y * stream["height"]))
        right = min(stream["width"], math.ceil((x + width) * stream["width"])); bottom = min(stream["height"], math.ceil((y + height) * stream["height"]))
        _require(right > left and bottom > top, "Native face box has no visible source intersection")
        crop = {"x": left, "y": top, "width": right - left, "height": bottom - top}
        filters.append(f"crop={right-left}:{bottom-top}:{left}:{top}")
    filters.append(f"scale=w='min({max_width},iw)':h=-1")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name("." + output.name + "." + uuid.uuid4().hex + ".png")
    try:
        seek = max(Fraction(0), request["pts"] * Fraction(request["timeBase"]) - 2)
        result = subprocess.run([ffmpeg_path(), "-nostdin", "-hide_banner", "-loglevel", "info", "-copyts", "-noautorotate", "-ss", f"{float(seek):.9f}", "-i", str(source), "-map", f"0:{stream['index']}", "-an", "-sn", "-dn", "-vf", ",".join(filters), "-fps_mode", "passthrough", "-frames:v", "1", "-update", "1", str(temporary)], capture_output=True, text=True, timeout=120)
        shown = re.findall(r"\[Parsed_showinfo_[^\]]+\].*?\bn:\s*\d+\s+pts:\s*(-?\d+)", result.stderr)
        _require(result.returncode == 0 and temporary.is_file() and temporary.stat().st_size > 0 and shown and int(shown[0]) == request["pts"], "Exact native face frame unavailable; no neighboring frame was substituted")
        _require(_digest(source) == request["sourceSha256"], "Original source changed while rendering face preview")
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"schemaVersion": "vibeedit.facePreview.v1", "ok": True, "request": request, "output": str(output), "sha256": _digest(output), "byteLength": output.stat().st_size, "cropNativePixels": crop, "maxWidth": max_width, "rotationApplied": False, "toneMappingApplied": False, "portraitMeaning": "source bbox preview; distinct from saved aligned native evidence cards"}


def prepare_library_command(index, *, operation_id, expected_revision_sha256, action, library_revision=None):
    """Return an immutable pending native API body. Caller persists before sending."""
    _require(_id(operation_id) and _sha(expected_revision_sha256) and isinstance(action, dict), "Cloud face draft requires operation ID and explicit authoritative library revision")
    with _open_index(index) as (db, metadata, receipt):
        library = metadata["library"]
        _require(isinstance(library, dict) and isinstance(library.get("libraryId"), str), "Native v1 package has no persistent cloud library")
        known = {row[0] for row in db.execute("SELECT id FROM people")}
        revision_reference = None
        if library_revision is not None:
            _require(isinstance(library_revision, dict) and isinstance(library_revision.get("value"), dict) and isinstance(library_revision.get("reference"), dict), "Expected actual native library revision value/reference response")
            value, revision_reference = library_revision["value"], library_revision["reference"]
            _require(set(revision_reference) == {"bucket", "key", "versionId", "artifactSha256", "byteLength"} and all(isinstance(revision_reference[k], str) and revision_reference[k] for k in ("bucket", "key", "versionId")), "Expected exact versioned native library revision reference")
            raw = (_json(value) + "\n").encode()
            _require(value.get("schemaVersion") == "myriograph.faceLibraryRevision.v1" and value.get("libraryId") == library["libraryId"] and value.get("embeddingSpaceSha256") == library["embeddingSpaceSha256"] and all(metadata.get(k) is None or value.get(k) == metadata[k] for k in ("organizationId", "projectId")) and hashlib.sha256(raw).hexdigest() == expected_revision_sha256 == revision_reference.get("artifactSha256") and revision_reference.get("byteLength") == len(raw) and revision_reference.get("versionId") not in {None, "", "null"} and revision_reference.get("bucket") == library["revision"]["bucket"], "Native library revision scope/hash/length changed")
            _require(isinstance(value.get("identityIds"), list) and len(value["identityIds"]) <= 100_000 and len(set(value["identityIds"])) == len(value["identityIds"]) and all(_person(p) for p in value["identityIds"]), "Native library identity census changed")
            known = set(value["identityIds"])
        kind = action.get("kind")
        if kind == "merge":
            _require(set(action) == {"kind", "fromPersonId", "toPersonId"} and action["fromPersonId"] in known and action["toPersonId"] in known and action["fromPersonId"] != action["toPersonId"], "Merge requires two known library/package person IDs")
            native_operation = dict(action)
        elif kind in {"split", "assign"}:
            expected_fields = {"kind", "groupIds", "fromPersonId" if kind == "split" else "personId"}
            _require(set(action) == expected_fields and isinstance(action["groupIds"], list) and 0 < len(action["groupIds"]) <= 1000 and all(_id(g) for g in action["groupIds"]) and len(set(action["groupIds"])) == len(action["groupIds"]), "Choose 1–1000 unique saved appearance groups")
            keys = []
            for group in action["groupIds"]:
                row = db.execute("SELECT appearance_key,person_id FROM groups WHERE id=?", (group,)).fetchone()
                _require(row is not None and row[0] is not None, "Authoritative native appearance mapping unavailable; do not synthesize a key from displayed group IDs")
                if kind == "split":
                    _require(action["fromPersonId"] in known and row[1] == action["fromPersonId"], "Split group does not belong to that saved person; rebase explicitly after remote corrections")
                keys.append(row[0])
            if kind == "split":
                native_operation = {"kind": "split", "fromPersonId": action["fromPersonId"], "appearanceKeys": keys}
            else:
                _require(action["personId"] is None or action["personId"] in known, "Choose a known library/package person or unresolved null")
                native_operation = {"kind": "assign", "personId": action["personId"], "appearanceKeys": keys}
        elif kind == "restore":
            _require(set(action) == {"kind", "revisionSha256"} and _sha(action["revisionSha256"]), "Restore requires an explicit committed ancestor hash; authority validates ancestry")
            native_operation = dict(action)
        else:
            raise ValueError("Native cloud library supports merge/split/assign/restore; portrait changes are local review overlays")
        body = {"expectedRevisionSha256": expected_revision_sha256, "operation": native_operation}
        result = {"schemaVersion": "vibeedit.faceLibraryPendingCommand.v1", "operationId": operation_id, "state": "pending", "jobId": metadata["jobId"], "sourceSha256": metadata["sourceSha256"], "archiveSha256": receipt["archiveSha256"], "libraryId": library["libraryId"], "packageInputLibrary": library, "libraryRevisionReference": revision_reference, "expectedRevisionSha256": expected_revision_sha256, "method": "POST", "relativePath": "/v1/faces/libraries/" + library["libraryId"] + "/corrections", "body": body, "scope": "Whole authoritative appearance groups; never a single-frame identity change", "acknowledgement": "Remain pending until authoritative appliedRevisionSha256 acknowledgement; preserve this exact body on uncertain sends"}
        result["commandSha256"] = hashlib.sha256(_json(result).encode()).hexdigest()
        return result
