"""Verified data-only project transfers. Restores never start work or import credentials."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

import jsonschema

from vibeedit.data import data_path
from vibeedit.project import Project, atomic_json, canonical, file_digest, within
from vibeedit.validation import validate_composition

SCHEMA = "vibeedit.projectBundle.v1"
MAX_BYTES = 64 * 1024**3


def _relative(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError("Invalid portable member path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {".", ".."} for part in name.split("/")) or str(path) != name:
        raise ValueError("Noncanonical portable member path")
    return name


def _validated_project(value):
    jsonschema.validate(value, json.loads(data_path("schema", "project.schema.json").read_text()))
    return value


def bundle_project(project, output, *, include_media=True, max_bytes=MAX_BYTES):
    project = Project(project)
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(project.root):
        raise ValueError("Bundle output must be a new file outside the project")
    # One SQLite snapshot binds document and correction history to one revision.
    with project.connect() as db:
        db.execute("BEGIN")
        state = _validated_project(json.loads(db.execute("SELECT document FROM project WHERE singleton=1").fetchone()[0]))
        events = [json.loads(row[0]) for row in db.execute("SELECT document FROM correction ORDER BY revision")]
    files = {}
    omitted = []

    def add(relative, digest=None, size=None):
        _relative(relative)
        if relative.startswith(".vibeedit/") or relative == "project.vibeedit.json":
            raise ValueError("Private runtime state is not a transferable asset")
        path = within(project.root, relative)
        if not path.is_file():
            raise ValueError(f"Registered asset missing: {relative}")
        actual = file_digest(path)
        if digest is not None and actual != digest or size is not None and path.stat().st_size != size:
            raise ValueError(f"Registered asset changed: {relative}")
        files[relative] = {"path": relative, "sha256": actual, "byteLength": path.stat().st_size}

    source_paths = {source["path"]: source for source in state["sources"]}
    for source in state["sources"]:
        add(source["clock"], source["clockSha256"])
        if include_media:
            add(source["path"], source["sha256"], source["byteLength"])
        else:
            omitted.append({key: source[key] for key in ("id", "path", "sha256", "byteLength")})
    for group in ("analysis", "beats", "masks", "reviews", "renders"):
        for artifact in state[group]:
            if artifact.get("files"):
                for member in artifact["files"]:
                    add(member["path"], member["sha256"], member["byteLength"])
            elif artifact.get("path"):
                add(artifact["path"], artifact.get("sha256"), artifact.get("byteLength"))
    pending = [state["composition"]]
    seen = set()
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        seen.add(relative)
        add(relative)
        spec = json.loads(within(project.root, relative).read_text())
        validate_composition(spec)
        parent = spec.get("metadata", {}).get("reviewApplication", {})
        if parent.get("parentComposition"):
            ancestor = parent["parentComposition"]
            add(ancestor, parent["parentCompositionSha256"])
            pending.append(ancestor)
        # Composition URIs are resolved relative to their containing file, as by render.
        for source in spec.get("sources", []):
            uri = source["uri"]
            if "://" in uri or Path(uri).is_absolute():
                raise ValueError("Portable compositions require registered relative sources")
            asset = within(project.root, (PurePosixPath(relative).parent / uri).as_posix()).relative_to(project.root).as_posix()
            if asset in source_paths and not include_media:
                continue
            add(asset, source.get("identity", {}).get("value") if source.get("identity", {}).get("algorithm") == "sha256" else None)
        for group in ("masks", "tracking", "analysis"):
            for artifact in spec.get("artifacts", {}).get(group, []):
                asset = within(project.root, (PurePosixPath(relative).parent / artifact["artifactUri"]).as_posix()).relative_to(project.root).as_posix()
                add(asset)
    total = sum(item["byteLength"] for item in files.values())
    if total > max_bytes:
        raise ValueError("Project exceeds bundle byte ceiling; select a larger explicit ceiling or omit source media")
    recovery = {}
    if within(project.root, ".vibeedit/companion.sqlite3").is_file():
        from vibeedit.goals import export_recovery
        recovery["companion"] = export_recovery(project.root)
    if within(project.root, ".vibeedit/myriograph.sqlite3").is_file():
        from vibeedit.myriograph import export_recovery
        recovery["myriograph"] = export_recovery(project.root)
    manifest = {"schemaVersion": SCHEMA, "project": state, "corrections": events, "files": list(files.values()), "omittedSources": omitted, "recovery": recovery, "privacy": "Contains project media, prompts and analysis selected for transfer. Credentials, browser tokens and Pi conversations are excluded. Restored execution requires explicit resume."}
    if len(canonical(manifest).encode()) > 64 * 1024**2:
        raise ValueError("Bundle metadata exceeds 64 MiB; retain a project directory backup instead")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            archive.writestr("vibeedit.bundle.json", canonical(manifest))
            for relative, record in files.items():
                archive.write(within(project.root, relative), "project/" + relative)
                # Refuse publication if the source was edited while streaming.
                if file_digest(within(project.root, relative)) != record["sha256"]:
                    raise ValueError(f"Asset changed during bundle: {relative}")
        # A race must not overwrite a user's output created after preflight.
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"schemaVersion": SCHEMA, "ok": True, "path": str(output), "sha256": file_digest(output), "byteLength": output.stat().st_size, "projectId": state["id"], "revision": state["revision"], "files": len(files), "omittedSources": omitted}


def restore_project(archive, destination, *, expected_sha256=None, max_bytes=MAX_BYTES):
    archive = Path(archive).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Restore requires a new destination; existing work is preserved")
    if expected_sha256 and file_digest(archive) != expected_sha256:
        raise ValueError("Bundle checksum differs from expected SHA256")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".vibeedit-restore-", dir=destination.parent))
    try:
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            names = [item.filename for item in members]
            if len(names) != len(set(names)) or len(names) > 100_000:
                raise ValueError("Duplicate or excessive bundle members")
            for item in members:
                _relative(item.filename)
                kind = stat.S_IFMT(item.external_attr >> 16)
                if kind not in (0, stat.S_IFREG) or item.flag_bits & 1:
                    raise ValueError("Only unencrypted regular data files are supported")
            info = bundle.getinfo("vibeedit.bundle.json")
            if info.file_size > 64 * 1024**2:
                raise ValueError("Excessive bundle metadata")
            value = json.loads(bundle.read(info))
            if value["schemaVersion"] != SCHEMA:
                raise ValueError("Unsupported project bundle")
            state = _validated_project(value["project"])
            records = value["files"]
            wanted = {"project/" + _relative(record["path"]): record for record in records}
            if len(wanted) != len(records) or set(names) != {*wanted, "vibeedit.bundle.json"}:
                raise ValueError("Bundle membership differs from manifest")
            if sum(item.file_size for item in members) > max_bytes:
                raise ValueError("Bundle exceeds restore byte ceiling")
            for name, record in wanted.items():
                relative = record["path"]
                if relative.startswith(".vibeedit/") or relative == "project.vibeedit.json":
                    raise ValueError("Bundle contains private executable runtime state")
                item = bundle.getinfo(name)
                if item.file_size != record["byteLength"]:
                    raise ValueError("Bundle asset length mismatch")
                target = within(staging, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with bundle.open(item) as source, target.open("xb") as output:
                    while block := source.read(1024**2):
                        digest.update(block)
                        output.write(block)
                if digest.hexdigest() != record["sha256"]:
                    raise ValueError("Bundle asset checksum mismatch")
            for source in state["sources"]:
                if file_digest(within(staging, source["clock"])) != source["clockSha256"]:
                    raise ValueError("Source clock mismatch")
                if not any(s["id"] == source["id"] for s in value["omittedSources"]):
                    path = within(staging, source["path"])
                    if file_digest(path) != source["sha256"] or path.stat().st_size != source["byteLength"]:
                        raise ValueError("Source identity mismatch")
            validate_composition(json.loads(within(staging, state["composition"]).read_text()))
            atomic_json(staging / "project.vibeedit.json", state)
            project = Project(staging)
            correction_schema = json.loads(data_path("schema", "correction.schema.json").read_text())
            identities = {source["id"]: source["sha256"] for source in state["sources"]}
            seen = set()
            prior = 0
            with project.connect() as db:
                for event in value["corrections"]:
                    jsonschema.validate(event, correction_schema)
                    if event["operationId"] in seen or not prior < event["revision"] <= state["revision"] or identities.get(event["sourceId"]) != event["sourceSha256"]:
                        raise ValueError("Invalid correction lineage")
                    prior = event["revision"]
                    seen.add(event["operationId"])
                    command = {k: v for k, v in event.items() if k not in {"revision", "schemaVersion", "remoteStatus"}}
                    db.execute("INSERT INTO correction VALUES (?,?,?,?)", (event["revision"], event["operationId"], canonical(command), canonical(event)))
            if value.get("recovery", {}).get("companion"):
                from vibeedit.goals import import_recovery
                import_recovery(staging, value["recovery"]["companion"])
            if value.get("recovery", {}).get("myriograph"):
                from vibeedit.myriograph import import_recovery
                import_recovery(staging, value["recovery"]["myriograph"])
            atomic_json(staging / ".vibeedit" / "restore.json", {"schemaVersion": SCHEMA, "archiveSha256": file_digest(archive), "projectId": state["id"], "revision": state["revision"], "omittedSources": value["omittedSources"], "execution": "paused; inspect original jobs and explicitly resume"})
        # A user-created destination wins over this operation.
        if destination.exists():
            raise ValueError("Restore destination was created concurrently")
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"schemaVersion": SCHEMA, "ok": True, "path": str(destination), "projectId": state["id"], "revision": state["revision"], "omittedSources": value["omittedSources"], "execution": "explicit-resume-required"}
