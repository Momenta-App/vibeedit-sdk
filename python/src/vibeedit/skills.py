from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path

from vibeedit.data import data_path
from vibeedit.spec import JSONObject


HARNESS_DIRECTORIES = {"agents": ".agents/skills", "codex": ".codex/skills", "claude": ".claude/skills", "opencode": ".opencode/skills"}
_TRACKER = ".vibeedit-install.json"


def list_skills() -> list[JSONObject]:
    return [skill for name in ("index.json", "owned.json") for skill in json.loads(data_path("skills", name).read_text(encoding="utf-8"))["skills"]]


def install_skill(identifier: str, *, harness: str, scope: str = "project", root: str | Path | None = None) -> JSONObject:
    return _operate(identifier, harness, scope, root, "install")


def check_skill(identifier: str, *, harness: str, scope: str = "project", root: str | Path | None = None) -> JSONObject:
    return _operate(identifier, harness, scope, root, "check")


def update_skill(identifier: str, *, harness: str, scope: str = "project", root: str | Path | None = None) -> JSONObject:
    return _operate(identifier, harness, scope, root, "update")


def remove_skill(identifier: str, *, harness: str, scope: str = "project", root: str | Path | None = None) -> JSONObject:
    return _operate(identifier, harness, scope, root, "remove")


def _operate(identifier: str, harness: str, scope: str, root: str | Path | None, action: str) -> JSONObject:
    skill = _skill(identifier, harness)
    destination = _destination(skill, harness, scope, root)
    with _lock(destination):
        _recover(destination, skill, harness)
        record = _record(destination, skill, harness)
        modified = record is not None and _checksum(destination, {_TRACKER}) != record["checksum"]
        result = {"id": skill["id"], "destination": str(destination)}
        if action == "check":
            return {**result, "action": "check", "installed": record is not None, **({"modified": modified, "version": record["version"], "currentVersion": skill["version"]} if record else {})}
        if modified:
            raise RuntimeError(f"refusing to {action} a user-modified skill: {destination}")
        if destination.exists() and record is None:
            raise FileExistsError(f"refusing to overwrite unmanaged existing skill: {destination}")
        if action == "remove":
            if record is None:
                return {**result, "action": "remove", "removed": False}
            _transaction(destination, skill, harness, record, None)
            return {**result, "action": "remove", "removed": True}
        source = data_path("skills", skill["path"])
        if (source / _TRACKER).exists() or _checksum(source) != skill["checksum"]:
            raise RuntimeError(f"bundled skill checksum mismatch: {skill['id']}")
        if action == "install" and record is not None:
            if record["version"] == skill["version"] and record["checksum"] == skill["checksum"]:
                return {**result, "action": "reused", "version": skill["version"]}
            raise FileExistsError(f"existing managed skill requires update: {destination}")
        _transaction(destination, skill, harness, record, source)
        return {**result, "action": "updated" if record else "installed", "version": skill["version"]}


def _paths(destination: Path) -> dict[str, Path]:
    return {name: destination.parent / f".{destination.name}.vibeedit-{suffix}" for name, suffix in {"stage": "stage", "previous": "previous", "journal": "operation.json", "lock": "lock"}.items()}


def _transaction(destination: Path, skill: JSONObject, harness: str, previous: JSONObject | None, source: Path | None) -> None:
    paths = _paths(destination)
    operation = {"schemaVersion": "vibeedit.skill-operation.v1", "id": skill["id"], "harness": harness, "operationId": uuid.uuid4().hex, "action": "replace" if source else "remove", "previousChecksum": previous["checksum"] if previous else None, "newChecksum": skill["checksum"] if source else None, "phase": "preparing"}
    _atomic_json(paths["journal"], operation)
    if source is not None:
        paths["stage"].mkdir()
        _atomic_json(paths["stage"] / _TRACKER, {"schemaVersion": 1, "id": skill["id"], "version": skill["version"], "harness": harness, "checksum": skill["checksum"], "operationId": operation["operationId"]})
        shutil.copytree(source, paths["stage"], dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if _checksum(paths["stage"], {_TRACKER}) != operation["newChecksum"]:
            raise RuntimeError("staged skill checksum mismatch; previous installation preserved")
    operation["phase"] = "ready"
    _atomic_json(paths["journal"], operation)
    _recover(destination, skill, harness)


def _recover(destination: Path, skill: JSONObject, harness: str) -> None:
    paths = _paths(destination)
    for path in paths.values():
        _no_symlink(path)
    if not paths["journal"].exists():
        if paths["stage"].exists() or paths["previous"].exists():
            raise RuntimeError(f"unowned skill recovery artifacts; preserve and inspect: {destination}")
        return
    operation = json.loads(paths["journal"].read_text(encoding="utf-8"))
    if operation.get("schemaVersion") != "vibeedit.skill-operation.v1" or operation.get("id") != skill["id"] or operation.get("harness") != harness or operation.get("action") not in {"replace", "remove"} or operation.get("phase") not in {"preparing", "ready", "committed"} or not isinstance(operation.get("operationId"), str) or len(operation["operationId"]) != 32 or any(c not in "0123456789abcdef" for c in operation["operationId"]):
        raise RuntimeError("invalid skill operation journal; preserve and inspect")
    for key in ("previousChecksum", "newChecksum"):
        if operation.get(key) is not None and (not isinstance(operation[key], str) or len(operation[key]) != 64 or any(c not in "0123456789abcdef" for c in operation[key])):
            raise RuntimeError("invalid skill operation checksum; preserve and inspect")
    old = operation["previousChecksum"]
    new = operation["newChecksum"]
    if (operation["action"] == "replace") != (new is not None):
        raise RuntimeError("invalid skill operation action; preserve and inspect")

    def matches(path: Path, checksum: str | None, *, current: bool = False) -> bool:
        if not path.exists() or checksum is None:
            return False
        record = _record(path, skill, harness)
        return record is not None and record["checksum"] == checksum and (not current or record.get("operationId") == operation["operationId"]) and _checksum(path, {_TRACKER}) == checksum

    if paths["previous"].exists() and not matches(paths["previous"], old):
        raise RuntimeError("user-modified skill backup; preserve and inspect")
    if destination.exists() and not (matches(destination, new, current=True) or (not paths["previous"].exists() and matches(destination, old))):
        raise RuntimeError("conflicting or user-modified skill during recovery; preserve and inspect")
    ready = matches(paths["stage"], new, current=True)
    if new is not None and not matches(destination, new, current=True) and not ready:
        # A failed/partial copy cannot destroy the old install. Retain partial data for inspection.
        if paths["stage"].exists():
            quarantine = paths["stage"].with_name(paths["stage"].name + ".aborted-" + operation["operationId"])
            if quarantine.exists() or quarantine.is_symlink():
                raise RuntimeError("skill quarantine already exists; preserve and inspect")
            os.replace(paths["stage"], quarantine)
        if paths["previous"].exists() and not destination.exists():
            os.replace(paths["previous"], destination)
        if old is not None and not matches(destination, old):
            raise RuntimeError("previous skill missing; preserve recovery journal")
        paths["journal"].unlink()
        return
    if not matches(destination, new, current=True) and operation["phase"] != "committed":
        if destination.exists():
            os.replace(destination, paths["previous"])
        if new is not None:
            os.replace(paths["stage"], destination)
    if new is not None and not matches(destination, new, current=True):
        raise RuntimeError("committed skill is missing; preserve recovery journal")
    if new is None and destination.exists():
        raise RuntimeError("removed skill still exists; preserve recovery journal")
    operation["phase"] = "committed"
    _atomic_json(paths["journal"], operation)
    if paths["stage"].exists():
        if not matches(paths["stage"], new, current=True):
            raise RuntimeError("modified redundant skill stage; preserve and inspect")
        shutil.rmtree(paths["stage"])
    if paths["previous"].exists():
        shutil.rmtree(paths["previous"])
    paths["journal"].unlink()


@contextmanager
def _lock(destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock = _paths(destination)["lock"]
    _no_symlink(lock)
    try:
        lock.mkdir()
    except FileExistsError:
        _no_symlink(lock / "owner.json")
        if not (lock / "owner.json").is_file():
            raise RuntimeError(f"incomplete skill lock; preserve and inspect: {lock}")
        owner = json.loads((lock / "owner.json").read_text(encoding="utf-8"))
        pid = owner.get("pid")
        if owner.get("schemaVersion") != 1 or not isinstance(owner.get("nonce"), str) or len(owner["nonce"]) != 32 or any(c not in "0123456789abcdef" for c in owner["nonce"]) or not isinstance(pid, int) or isinstance(pid, bool) or not 0 < pid < 2 ** 31 or _alive(pid):
            raise RuntimeError(f"skill operation locked; preserve active or unknown owner: {lock}")
        # A separate mkdir prevents two stale-lock reclaimers from deleting a new owner's lock.
        reclaim = lock.with_name(lock.name + ".reclaim")
        _no_symlink(reclaim)
        try:
            reclaim.mkdir()
        except FileExistsError:
            raise RuntimeError(f"skill lock recovery already in progress: {reclaim}")
        try:
            if json.loads((lock / "owner.json").read_text(encoding="utf-8")) != owner or _alive(pid):
                raise RuntimeError("skill lock owner changed during recovery")
            shutil.rmtree(lock)
            lock.mkdir()
        finally:
            reclaim.rmdir()
    nonce = uuid.uuid4().hex
    _atomic_json(lock / "owner.json", {"schemaVersion": 1, "pid": os.getpid(), "nonce": nonce})
    try:
        yield
    finally:
        _no_symlink(lock)
        _no_symlink(lock / "owner.json")
        if json.loads((lock / "owner.json").read_text(encoding="utf-8")).get("nonce") != nonce:
            raise RuntimeError("skill lock ownership changed; preserve and inspect")
        shutil.rmtree(lock)


def _alive(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(["powershell", "-NoProfile", "-Command", f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 3 }}"], capture_output=True, timeout=10)
        return result.returncode != 3
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _atomic_json(path: Path, value: JSONObject) -> None:
    _no_symlink(path)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _sync_parent(path)


def _sync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _skill(identifier: str, harness: str) -> JSONObject:
    skill = next((item for item in list_skills() if identifier in {item["id"], item["name"]}), None)
    if not skill:
        raise ValueError(f"unknown skill: {identifier}")
    if harness not in HARNESS_DIRECTORIES or harness not in skill["harnesses"]:
        raise ValueError(f"skill {skill['id']} does not support harness {harness}")
    name = skill["name"]
    if not isinstance(name, str) or name in {"", ".", ".."} or any(character in name for character in "/\\"):
        raise ValueError("unsafe skill name")
    return skill


def _destination(skill: JSONObject, harness: str, scope: str, root: str | Path | None) -> Path:
    if scope not in {"project", "user"}:
        raise ValueError("skill scope must be project or user")
    base = (Path.home() if scope == "user" else Path(root or Path.cwd())).resolve()
    destination = base / HARNESS_DIRECTORIES[harness] / skill["name"]
    for path in (destination.parent.parent, destination.parent, destination):
        _no_symlink(path)
    return destination


def _no_symlink(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"refusing skill symlink: {path}")


def _checksum(root: Path, excluded: set[str] | None = None) -> str:
    _no_symlink(root)
    digest = hashlib.sha256()
    files = []
    for directory, directories, names in os.walk(root, followlinks=False):
        for name in directories + names:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise RuntimeError(f"refusing skill symlink or special file: {path}")
            if stat.S_ISREG(mode) and path.relative_to(root).as_posix() not in (excluded or set()):
                if "__pycache__" not in path.relative_to(root).parts and path.suffix != ".pyc":
                    files.append(path)
        # Wheel installation and script execution can compile caches. They are
        # derived interpreter state, never part of the installed skill payload.
        directories[:] = [name for name in directories if name != "__pycache__"]
    for path in sorted(files, key=lambda path: path.relative_to(root).as_posix().encode()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _record(destination: Path, skill: JSONObject, harness: str) -> JSONObject | None:
    _no_symlink(destination)
    tracker = destination / _TRACKER
    _no_symlink(tracker)
    if not tracker.is_file():
        return None
    record = json.loads(tracker.read_text(encoding="utf-8"))
    if record.get("schemaVersion") != 1 or record.get("id") != skill["id"] or record.get("harness") != harness or not isinstance(record.get("version"), str) or not isinstance(record.get("checksum"), str) or len(record["checksum"]) != 64 or any(c not in "0123456789abcdef" for c in record["checksum"]):
        raise RuntimeError(f"invalid skill install tracker; preserve and inspect: {destination}")
    return record
