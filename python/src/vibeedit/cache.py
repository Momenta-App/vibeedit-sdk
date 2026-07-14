from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from vibeedit.spec import JSONObject
from vibeedit.validation import canonical_json


def cache_root() -> Path:
    configured = os.environ.get("VIBEEDIT_CACHE_DIR")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "VibeEdit" / "Cache"
    if sys_platform() == "darwin":
        return Path.home() / "Library" / "Caches" / "VibeEdit"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "vibeedit"


def sys_platform() -> str:
    import sys

    return sys.platform


def cache_key(operation: str, inputs: JSONObject, *, implementation_version: str, runtime_versions: dict[str, str] | None = None) -> str:
    value = {
        "operation": operation,
        "inputs": inputs,
        "implementationVersion": implementation_version,
        "runtimeVersions": runtime_versions or {},
        "schemaVersion": "1.0.0",
    }
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def write_artifact_provenance(path: str | Path, provenance: JSONObject) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def restore_cached_artifact(operation: str, key: str, destination: str | Path) -> bool:
    target = Path(destination)
    cached = cache_root() / "artifacts" / Path(*operation.split(".")) / f"{key}{target.suffix}"
    checksum = cached.with_suffix(cached.suffix + ".sha256")
    if not cached.is_file() or not checksum.is_file() or checksum.read_text(encoding="utf-8").strip() != hashlib.sha256(cached.read_bytes()).hexdigest():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached, target)
    return True


def store_cached_artifact(operation: str, key: str, source: str | Path) -> Path:
    artifact = Path(source)
    cached = cache_root() / "artifacts" / Path(*operation.split(".")) / f"{key}{artifact.suffix}"
    cached.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact, cached)
    cached.with_suffix(cached.suffix + ".sha256").write_text(hashlib.sha256(cached.read_bytes()).hexdigest() + "\n", encoding="utf-8")
    return cached
