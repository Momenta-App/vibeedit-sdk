from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from vibeedit.cache import cache_key, cache_root, write_artifact_provenance
from vibeedit.ffmpeg import render_generated, render_media
from vibeedit.spec import JSONObject
from vibeedit.validation import canonical_json, validate_composition
from vibeedit.version import VERSION


def render(spec: JSONObject | str | Path, output: str | Path | None = None) -> Path:
    base = Path(spec).parent if isinstance(spec, (str, Path)) else Path.cwd()
    composition = json.loads(Path(spec).read_text(encoding="utf-8")) if isinstance(spec, (str, Path)) else spec
    validate_composition(composition)
    backend = composition["render"]["backend"]
    destination = Path(output or composition["render"]["output"]["uri"])
    normalized = json.loads(json.dumps(composition))
    normalized["render"]["output"]["uri"] = "<output>"
    versions = _runtime_versions(backend)
    key = cache_key("render", normalized, implementation_version=VERSION, runtime_versions=versions)
    cached = cache_root() / "renders" / f"{key}{destination.suffix}"
    if composition.get("cache", {}).get("enabled", False) and cached.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached, destination)
        _write_render_provenance(destination, composition, key, versions, cache_hit=True, work={"framesRendered": 0, "framesReused": composition["durationFrames"], "reuseKind": "final-render"})
        return destination
    work = {"framesRendered": composition["durationFrames"], "framesReused": 0, "reuseKind": "none"}
    if backend in {"auto", "ffmpeg", "python"}:
        if any(item["kind"] == "video" for track in composition["timeline"]["tracks"] for item in track["items"]):
            result = render_media(composition, destination, base)
        else:
            result = render_generated(composition, destination)
    elif backend in {"html", "mixed"}:
        from vibeedit.motion import render_mixed

        result = render_mixed(composition, destination, base, metrics=work)
    else:
        raise NotImplementedError(f"render backend {backend!r} is not available in the lightweight installation")
    if composition.get("cache", {}).get("enabled", False):
        cached.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result, cached)
    _write_render_provenance(result, composition, key, versions, cache_hit=False, work=work)
    return result


def _runtime_versions(backend: str) -> dict[str, str]:
    executable = shutil.which("ffmpeg")
    result = subprocess.run([executable, "-version"], capture_output=True, text=True, check=False) if executable else None
    versions = {"ffmpeg": (result.stdout or result.stderr).splitlines()[0] if result and result.returncode == 0 else "unavailable"}
    if backend not in {"html", "mixed"}:
        return versions
    try:
        versions["playwright"] = version("playwright")
    except PackageNotFoundError:
        versions["playwright"] = "unavailable"
    return versions


def _write_render_provenance(output: Path, spec: JSONObject, key: str, versions: dict[str, str], *, cache_hit: bool, work: JSONObject) -> None:
    write_artifact_provenance(
        output.with_suffix(output.suffix + ".vibeedit.json"),
        {
            "schemaVersion": "1.0.0",
            "compositionId": spec["id"],
            "compositionSha256": hashlib.sha256(canonical_json(spec).encode()).hexdigest(),
            "sourceIdentities": [source["identity"] for source in spec["sources"]],
            "implementationVersion": VERSION,
            "runtimeVersions": versions,
            "cacheKey": key,
            "cacheHit": cache_hit,
            "work": work,
            "output": {"path": output.name, "bytes": output.stat().st_size, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()},
        },
    )
