from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from vibeedit.cache import cache_key, cache_root, write_artifact_provenance
from vibeedit.ffmpeg import ffmpeg_path, ffprobe_path, render_audio_mix, render_generated, render_media
from vibeedit.revision import plan_revision
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


def render_revision(previous: JSONObject | str | Path, revised: JSONObject | str | Path, previous_output: str | Path, output: str | Path | None = None) -> Path:
    previous_spec = json.loads(Path(previous).read_text(encoding="utf-8")) if isinstance(previous, (str, Path)) else previous
    revised_spec = json.loads(Path(revised).read_text(encoding="utf-8")) if isinstance(revised, (str, Path)) else revised
    plan = plan_revision(previous_spec, revised_spec)
    if plan["revisionKind"] == "motion":
        return render(revised, output)
    if plan["revisionKind"] == "audio":
        return _render_audio_revision(revised_spec, Path(previous_output), Path(output or revised_spec["render"]["output"]["uri"]), plan, Path(revised).parent if isinstance(revised, (str, Path)) else Path.cwd())
    if plan["executionStatus"] == "verified-stream-copy-tail":
        return _render_scene_tail_revision(revised_spec, Path(previous_output), Path(output or revised_spec["render"]["output"]["uri"]), plan)
    if plan["revisionKind"] != "container":
        raise NotImplementedError(f"incremental execution for {plan['revisionKind']} revisions is planned but not yet verified; inspect plan_revision(...) before rendering")
    source = Path(previous_output)
    if not source.is_file():
        raise FileNotFoundError(f"previous rendered output does not exist: {source}")
    destination = Path(output or revised_spec["render"]["output"]["uri"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-map", "0", "-c", "copy", "-map_metadata", "-1", str(destination)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"FFmpeg remux failed with exit code {result.returncode}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg remux returned success without a non-empty output")
    write_artifact_provenance(
        destination.with_suffix(destination.suffix + ".vibeedit.json"),
        {
            "schemaVersion": "1.0.0",
            "compositionId": revised_spec["id"],
            "compositionSha256": hashlib.sha256(canonical_json(revised_spec).encode()).hexdigest(),
            "implementationVersion": VERSION,
            "revisionPlan": plan,
            "work": {"framesRendered": 0, "framesReused": revised_spec["durationFrames"], "encodedVideoBytesReused": _packet_bytes(source, "v:0"), "decodeWorkAvoided": plan["decodeWorkAvoided"], "reuseKind": "stream-copy-remux"},
            "output": {"path": destination.name, "bytes": destination.stat().st_size, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()},
        },
    )
    return destination


def _render_scene_tail_revision(spec: JSONObject, previous_output: Path, destination: Path, plan: JSONObject) -> Path:
    if not previous_output.is_file():
        raise FileNotFoundError(f"previous rendered output does not exist: {previous_output}")
    _verify_previous_revision_input(previous_output, plan)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(previous_output), "-map", "0:v:0", "-an", "-c", "copy", "-frames:v", str(spec["durationFrames"]), "-map_metadata", "-1"]
    if spec["render"]["output"]["container"] == "mp4":
        command.extend(["-movflags", "+faststart"])
    command.append(str(destination))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"FFmpeg tail truncation failed with exit code {result.returncode}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg tail truncation returned success without a non-empty output")
    if _video_frames(destination) != spec["durationFrames"]:
        raise RuntimeError(f"FFmpeg tail truncation did not produce exactly {spec['durationFrames']} video frames")
    work = {
        "framesRendered": 0,
        "framesReused": spec["durationFrames"],
        "encodedVideoBytesReused": _packet_bytes(destination, "v:0"),
        "encodedAudioBytesReused": 0,
        "decodeWorkAvoided": plan["decodeWorkAvoided"],
        "reuseKind": "stream-copy-tail-truncation",
    }
    write_artifact_provenance(
        destination.with_suffix(destination.suffix + ".vibeedit.json"),
        {
            "schemaVersion": "1.0.0",
            "compositionId": spec["id"],
            "compositionSha256": hashlib.sha256(canonical_json(spec).encode()).hexdigest(),
            "implementationVersion": VERSION,
            "revisionPlan": plan,
            "work": work,
            "output": {"path": destination.name, "bytes": destination.stat().st_size, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()},
        },
    )
    return destination


def _verify_previous_revision_input(previous_output: Path, plan: JSONObject) -> None:
    provenance = previous_output.with_suffix(previous_output.suffix + ".vibeedit.json")
    if not provenance.is_file():
        raise ValueError(f"previous rendered output provenance does not exist: {provenance}")
    record = json.loads(provenance.read_text(encoding="utf-8"))
    if record.get("compositionSha256") != plan["previousCompositionHash"]:
        raise ValueError("previous rendered output provenance does not match the previous composition")
    if record.get("output", {}).get("sha256") != hashlib.sha256(previous_output.read_bytes()).hexdigest():
        raise ValueError("previous rendered output does not match its provenance digest")


def _video_frames(path: Path) -> int:
    result = subprocess.run(
        [ffprobe_path(), "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"FFprobe frame count failed with exit code {result.returncode}")
    streams = json.loads(result.stdout).get("streams", [])
    if not streams or not str(streams[0].get("nb_read_frames", "")).isdigit():
        raise RuntimeError("FFprobe did not report a video frame count")
    return int(streams[0]["nb_read_frames"])


def _render_audio_revision(spec: JSONObject, previous_output: Path, destination: Path, plan: JSONObject, base: Path) -> Path:
    if not previous_output.is_file():
        raise FileNotFoundError(f"previous rendered output does not exist: {previous_output}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vibeedit-audio-revision-") as temporary:
        settings = spec["render"]["output"]
        audio_codec = settings.get("audioCodec", "aac")
        audio = render_audio_mix(spec, Path(temporary) / ("audio.m4a" if audio_codec == "aac" else "audio.mka"), base, audio_codec=audio_codec)
        result = subprocess.run(
            [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(previous_output), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-map_metadata", "-1", *(["-movflags", "+faststart"] if settings["container"] == "mp4" else []), str(destination)],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"FFmpeg audio revision failed with exit code {result.returncode}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("FFmpeg audio revision returned success without a non-empty output")
    write_artifact_provenance(
        destination.with_suffix(destination.suffix + ".vibeedit.json"),
        {
            "schemaVersion": "1.0.0",
            "compositionId": spec["id"],
            "compositionSha256": hashlib.sha256(canonical_json(spec).encode()).hexdigest(),
            "implementationVersion": VERSION,
            "revisionPlan": plan,
            "work": {"framesRendered": 0, "framesReused": spec["durationFrames"], "encodedVideoBytesReused": _packet_bytes(previous_output, "v:0"), "audioRangesRemixed": plan["dirtyAudioRanges"], "decodeWorkAvoided": plan["decodeWorkAvoided"], "reuseKind": "audio-only-remix"},
            "output": {"path": destination.name, "bytes": destination.stat().st_size, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()},
        },
    )
    return destination


def _packet_bytes(path: Path, stream: str) -> int:
    result = subprocess.run(
        [ffprobe_path(), "-v", "error", "-select_streams", stream, "-show_entries", "packet=size", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"FFprobe packet inspection failed with exit code {result.returncode}")
    return sum(int(packet["size"]) for packet in json.loads(result.stdout).get("packets", []))


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
