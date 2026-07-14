from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from vibeedit.data import data_path
from vibeedit.spec import JSONObject


HARNESS_DIRECTORIES = {"agents": ".agents/skills", "codex": ".codex/skills", "claude": ".claude/skills", "opencode": ".opencode/skills"}


def list_skills() -> list[JSONObject]:
    return json.loads(data_path("skills", "index.json").read_text(encoding="utf-8"))["skills"]


def install_skill(identifier: str, *, harness: str, scope: str = "project", root: str | Path | None = None) -> JSONObject:
    skill = _skill(identifier, harness)
    source = data_path("skills", skill["path"])
    destination = _destination(skill, harness, scope, root)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing skill: {destination}")
    shutil.copytree(source, destination)
    _write_tracker(destination, skill, harness, _checksum(source))
    return {"action": "installed", "id": skill["id"], "version": skill["version"], "destination": str(destination)}


def check_skill(identifier: str, *, harness: str, scope: str = "project", root: str | Path | None = None) -> JSONObject:
    skill = _skill(identifier, harness)
    destination = _destination(skill, harness, scope, root)
    tracker = destination / ".vibeedit-install.json"
    if not tracker.is_file():
        return {"action": "check", "id": skill["id"], "installed": False, "destination": str(destination)}
    record = json.loads(tracker.read_text(encoding="utf-8"))
    return {
        "action": "check",
        "id": skill["id"],
        "installed": True,
        "modified": _checksum(destination, {".vibeedit-install.json"}) != record["checksum"],
        "version": record["version"],
        "currentVersion": skill["version"],
        "destination": str(destination),
    }


def update_skill(identifier: str, *, harness: str, scope: str = "project", root: str | Path | None = None) -> JSONObject:
    status = check_skill(identifier, harness=harness, scope=scope, root=root)
    if not status["installed"]:
        return install_skill(identifier, harness=harness, scope=scope, root=root)
    if status["modified"]:
        raise RuntimeError(f"refusing to overwrite a user-modified skill: {status['destination']}")
    destination = Path(status["destination"])
    shutil.rmtree(destination)
    result = install_skill(identifier, harness=harness, scope=scope, root=root)
    result["action"] = "updated"
    return result


def remove_skill(identifier: str, *, harness: str, scope: str = "project", root: str | Path | None = None) -> JSONObject:
    status = check_skill(identifier, harness=harness, scope=scope, root=root)
    if not status["installed"]:
        return {"action": "remove", "id": status["id"], "removed": False, "destination": status["destination"]}
    if status["modified"]:
        raise RuntimeError(f"refusing to remove a user-modified skill: {status['destination']}")
    shutil.rmtree(status["destination"])
    return {"action": "remove", "id": status["id"], "removed": True, "destination": status["destination"]}


def _skill(identifier: str, harness: str) -> JSONObject:
    skill = next((item for item in list_skills() if identifier in {item["id"], item["name"]}), None)
    if not skill:
        raise ValueError(f"unknown skill: {identifier}")
    if harness not in HARNESS_DIRECTORIES or harness not in skill["harnesses"]:
        raise ValueError(f"skill {skill['id']} does not support harness {harness}")
    return skill


def _destination(skill: JSONObject, harness: str, scope: str, root: str | Path | None) -> Path:
    base = Path.home() if scope == "user" else Path(root or Path.cwd())
    return base / HARNESS_DIRECTORIES[harness] / skill["name"]


def _checksum(root: Path, excluded: set[str] | None = None) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file() and path.name not in (excluded or set())):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _write_tracker(destination: Path, skill: JSONObject, harness: str, checksum: str) -> None:
    (destination / ".vibeedit-install.json").write_text(json.dumps({"schemaVersion": 1, "id": skill["id"], "version": skill["version"], "harness": harness, "checksum": checksum}, indent=2) + "\n", encoding="utf-8")

