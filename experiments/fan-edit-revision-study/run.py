from __future__ import annotations

import array
import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path

from vibeedit import plan_revision, render, render_revision, verify_output
from vibeedit.data import data_path
from vibeedit.examples import render_example


ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "review"
SOURCES = ROOT / "sources"
EXECUTABLE = {
    "verified-frame-cache",
    "verified-audio-remix",
    "verified-stream-copy-remux",
    "verified-stream-copy-video-audio-remix",
    "verified-stream-copy-tail",
    "verified-stream-copy-tail-audio-remix",
    "no-work",
}


def main() -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    _materialize_sources()
    revisions = _revisions()
    report = {"schemaVersion": "1.0.0", "test": "vibeedit-fan-edit-revision-study", "revisions": []}
    previous_spec = None
    previous_output = None
    for index, revision in enumerate(revisions):
        spec = revision["spec"]
        stem = f"r{index:02d}-{revision['slug']}"
        output = REVIEW / f"{stem}.mp4"
        spec["render"]["output"]["uri"] = output.name
        spec_path = REVIEW / f"{stem}.composition.json"
        spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        plan = plan_revision(previous_spec, spec) if previous_spec else None
        started = time.perf_counter()
        if previous_spec is None:
            mode = "full-initial"
            render(spec_path, output)
        elif plan["executionStatus"] in EXECUTABLE:
            mode = "incremental"
            render_revision(previous_spec, spec, previous_output, output)
        else:
            mode = "clean-fallback"
            render(spec_path, output)
        elapsed = time.perf_counter() - started
        clean = copy.deepcopy(spec)
        clean["cache"] = {"enabled": False, "namespace": f"fan-study-clean-{index}"}
        clean_output = ROOT / f".{stem}-clean.mp4"
        clean_started = time.perf_counter()
        render(clean, clean_output)
        clean_elapsed = time.perf_counter() - clean_started
        verification = verify_output(output, spec["verification"])
        provenance = json.loads(output.with_suffix(".mp4.vibeedit.json").read_text(encoding="utf-8"))
        report["revisions"].append({
            "index": index,
            "id": stem,
            "label": revision["label"],
            "changeClasses": revision["changeClasses"],
            "renderMode": mode,
            "elapsedSeconds": round(elapsed, 6),
            "cleanRenderSeconds": round(clean_elapsed, 6),
            "plan": plan,
            "work": provenance.get("work"),
            "verification": {"passed": verification.passed, "errors": verification.errors, "warnings": verification.warnings},
            "cleanComparison": _compare(output, clean_output, previous_output, plan),
            "output": {"file": output.name, "bytes": output.stat().st_size, "sha256": _sha256(output)},
        })
        _remove_artifact(clean_output)
        previous_spec = copy.deepcopy(spec)
        previous_output = output
    report["benchmarks"] = _benchmarks(revisions)
    (REVIEW / "fan-edit-study-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (REVIEW / "REVIEW_NOTES.md").write_text(_review_notes(report), encoding="utf-8")
    outputs = [REVIEW / item["output"]["file"] for item in report["revisions"]]
    _contact_sheet(outputs, 0.18, "contact-sheet-build.jpg")
    _contact_sheet(outputs, 0.68, "contact-sheet-drop.jpg")
    print(json.dumps({"reviewFolder": str(REVIEW), "revisions": len(outputs), "failures": [item["id"] for item in report["revisions"] if not item["verification"]["passed"] or not item["cleanComparison"]["passed"]]}, indent=2))


def _materialize_sources() -> None:
    if SOURCES.exists():
        shutil.rmtree(SOURCES)
    shutil.copytree(data_path("examples", "fan-edit"), SOURCES)
    prime = ROOT / ".source-prime.mp4"
    render_example(SOURCES, prime)
    _remove_artifact(prime)


def _base_spec() -> dict:
    spec = json.loads((SOURCES / "composition.json").read_text(encoding="utf-8"))
    for source in spec["sources"]:
        source["uri"] = str(SOURCES / source["uri"])
        source["identity"] = {"algorithm": "sha256", "value": _sha256(Path(source["uri"]))}
    spec["cache"] = {"enabled": False, "namespace": "fan-edit-revision-study"}
    spec["provenance"]["generator"] = "vibeedit-fan-edit-revision-study"
    return spec


def _revisions() -> list[dict]:
    current = _base_spec()
    revisions = [_revision("baseline", "Five-moment hook/setup/build/drop/aftershock baseline", ["baseline"], current)]

    current = copy.deepcopy(current)
    _item(current, "hook")["effects"] = [_stutter("hook-stutter", 21, 2, 0.25)]
    revisions.append(_revision("hook-punch", "Add a restrained two-frame hook stutter", ["effect-add", "hook"], current))

    current = copy.deepcopy(current)
    setup = _item(current, "setup")
    setup["placement"]["durationFrames"] = 40
    setup["source"]["durationFrames"] = 40
    build = _item(current, "build")
    build["placement"]["startFrame"] = 74
    build["placement"]["durationFrames"] = 40
    build["source"]["durationFrames"] = 40
    bridge = _item(current, "build-bridge")
    bridge["placement"] = {"startFrame": 74, "durationFrames": 2}
    bridge["params"]["curve"] = "faster"
    revisions.append(_revision("tighter-bridge", "Tighten the setup-to-build bridge from six frames to two", ["transition-change", "timing"], current))

    current = copy.deepcopy(current)
    _item(current, "build")["effects"][0]["params"].update({"windowFrames": 2, "intensity": 0.58})
    _item(current, "drop")["effects"] = []
    revisions.append(_revision("effect-contrast", "Increase build instability and remove drop stutter", ["effect-change", "effect-remove"], current))

    current = copy.deepcopy(current)
    _track(current, "A1")["items"].append(_sfx("pre-drop-tick", 104, 4, 132, -18, 31))
    revisions.append(_revision("add-pre-drop-sfx", "Add one selective pre-drop accent", ["audio-add", "sfx"], current))

    current = copy.deepcopy(current)
    _item(current, "music-bed").update({"gainDb": -15, "pan": -0.12, "fadeInFrames": 6, "fadeOutFrames": 14})
    _item(current, "drop-hit")["gainDb"] = -6
    revisions.append(_revision("rebalance-audio", "Lower and pan music while increasing drop impact", ["audio-change", "mix"], current))

    current = copy.deepcopy(current)
    _track(current, "A1")["items"] = [item for item in _track(current, "A1")["items"] if item["id"] != "pre-drop-tick"]
    revisions.append(_revision("remove-pre-drop-sfx", "Remove the extra accent after review", ["audio-remove", "sfx"], current))

    current = copy.deepcopy(current)
    current["durationFrames"] = 150
    current["verification"]["durationFrames"] = 150
    _track(current, "V1")["items"] = [item for item in _track(current, "V1")["items"] if item["id"] != "aftershock"]
    _track(current, "A1")["items"] = [item for item in _track(current, "A1")["items"] if item["id"] != "aftershock-hit"]
    music = _item(current, "music-bed")
    music["placement"]["durationFrames"] = 150
    music["source"]["durationFrames"] = 150
    current["timeline"]["markers"] = [marker for marker in current["timeline"]["markers"] if marker["id"] != "aftershock"]
    current["metadata"]["fanEdit"]["structure"] = ["hook", "setup", "build", "drop"]
    revisions.append(_revision("remove-aftershock", "Remove the ending beat while retaining the approved video prefix", ["scene-remove", "audio-change"], current))

    current = copy.deepcopy(current)
    revisions.append(_revision("no-op", "Resubmit the approved composition without semantic changes", ["no-op"], current))
    return revisions


def _revision(slug: str, label: str, change_classes: list[str], spec: dict) -> dict:
    return {"slug": slug, "label": label, "changeClasses": change_classes, "spec": copy.deepcopy(spec)}


def _stutter(identifier: str, seed: int, window: int, intensity: float) -> dict:
    return {"id": identifier, "effectId": "vibeedit://effect/random-frame-stutter", "enabled": True, "params": {"seed": seed, "windowFrames": window, "intensity": intensity}, "implementationVersion": "0.1.0"}


def _sfx(identifier: str, start: int, duration: int, frequency: int, gain: int, seed: int) -> dict:
    return {"id": identifier, "kind": "sound_effect", "placement": {"startFrame": start, "durationFrames": duration}, "soundEffectId": "vibeedit://sfx/impact-procedural", "params": {"frequency": frequency}, "gainDb": gain, "variationSeed": seed, "avoidImmediateRepeat": True}


def _track(spec: dict, identifier: str) -> dict:
    return next(track for track in spec["timeline"]["tracks"] if track["id"] == identifier)


def _item(spec: dict, identifier: str) -> dict:
    return next(item for track in spec["timeline"]["tracks"] for item in track["items"] if item["id"] == identifier)


def _compare(output: Path, reference: Path, previous_output: Path | None, plan: dict | None) -> dict:
    video_exact = _decoded_md5(output, "0:v:0") == _decoded_md5(reference, "0:v:0")
    approved_video_exact = False
    if previous_output and plan and plan["executionStatus"] == "verified-stream-copy-tail-audio-remix":
        approved_video_exact = _decoded_md5(output, "0:v:0") == _decoded_md5(previous_output, "0:v:0", plan["expectedReuse"]["reusedFrames"])
    if previous_output and plan and plan["executionStatus"] == "no-work":
        approved_video_exact = _decoded_md5(output, "0:v:0") == _decoded_md5(previous_output, "0:v:0")
    left = _decoded_pcm(output)
    right = _decoded_pcm(reference)
    count = min(len(left), len(right))
    dot = sum(int(left[index]) * int(right[index]) for index in range(count))
    left_energy = sum(int(left[index]) ** 2 for index in range(count))
    right_energy = sum(int(right[index]) ** 2 for index in range(count))
    correlation = dot / math.sqrt(left_energy * right_energy) if left_energy and right_energy else 1.0
    return {"videoExact": video_exact, "approvedVideoExact": approved_video_exact, "videoSsim": _video_ssim(output, reference), "audioExact": left == right, "audioSampleDelta": len(left) - len(right), "audioCorrelation": correlation, "passed": (video_exact or approved_video_exact) and len(left) == len(right) and correlation >= 0.9999}


def _decoded_md5(path: Path, stream: str, frames: int | None = None) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", stream, *(["-frames:v", str(frames)] if frames else []), "-f", "md5", "-"], capture_output=True, text=True, check=True).stdout.strip()


def _video_ssim(output: Path, reference: Path) -> float:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(output), "-i", str(reference), "-lavfi", "[0:v][1:v]ssim", "-f", "null", "-"], capture_output=True, text=True, check=True)
    match = re.search(r"All:([0-9.]+)", result.stderr)
    if not match:
        raise RuntimeError("FFmpeg did not report an SSIM score")
    return float(match.group(1))


def _decoded_pcm(path: Path) -> array.array:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", "0:a:0", "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "2", "-ar", "48000", "-"], capture_output=True, check=True)
    samples = array.array("h")
    samples.frombytes(result.stdout)
    return samples


def _benchmarks(revisions: list[dict]) -> list[dict]:
    results = []
    for name, previous_index, revised_index in (("audio-rebalance", 4, 5), ("retained-audio-tail-removal", 6, 7)):
        incremental_samples = []
        clean_samples = []
        for trial in range(3):
            previous = copy.deepcopy(revisions[previous_index]["spec"])
            revised = copy.deepcopy(revisions[revised_index]["spec"])
            previous["render"]["output"]["uri"] = f"benchmark-{name}-{trial}-previous.mp4"
            revised["render"]["output"]["uri"] = f"benchmark-{name}-{trial}-revised.mp4"
            previous_output = ROOT / f".benchmark-{name}-{trial}-previous.mp4"
            incremental_output = ROOT / f".benchmark-{name}-{trial}-incremental.mp4"
            clean_output = ROOT / f".benchmark-{name}-{trial}-clean.mp4"
            render(previous, previous_output)
            started = time.perf_counter()
            render_revision(previous, revised, previous_output, incremental_output)
            incremental_samples.append(time.perf_counter() - started)
            started = time.perf_counter()
            render(revised, clean_output)
            clean_samples.append(time.perf_counter() - started)
            for output in (previous_output, incremental_output, clean_output):
                _remove_artifact(output)
        incremental_mean = sum(incremental_samples) / 3
        clean_mean = sum(clean_samples) / 3
        results.append({"name": name, "incrementalSamplesSeconds": incremental_samples, "cleanSamplesSeconds": clean_samples, "incrementalMeanSeconds": incremental_mean, "cleanMeanSeconds": clean_mean, "speedup": clean_mean / incremental_mean})
    return results


def _contact_sheet(outputs: list[Path], ratio: float, name: str) -> None:
    thumbnails = []
    for index, output in enumerate(outputs):
        thumbnail = ROOT / f".thumb-{index:02d}.jpg"
        duration = float(json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(output)], capture_output=True, text=True, check=True).stdout)["format"]["duration"])
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{duration * ratio:.6f}", "-i", str(output), "-frames:v", "1", "-vf", "scale=320:180", str(thumbnail)], check=True)
        thumbnails.append(thumbnail)
    inputs = [part for thumbnail in thumbnails for part in ("-i", str(thumbnail))]
    layout = "|".join(f"{(index % 3) * 320}_{(index // 3) * 180}" for index in range(len(thumbnails)))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", f"xstack=inputs={len(thumbnails)}:layout={layout}", "-frames:v", "1", str(REVIEW / name)], check=True)
    for thumbnail in thumbnails:
        thumbnail.unlink(missing_ok=True)


def _review_notes(report: dict) -> str:
    rows = ["| Rev | Change | Mode | Time | Reused/rendered | Clean match |", "|---|---|---:|---:|---:|---:|"]
    for item in report["revisions"]:
        work = item.get("work") or {}
        comparison = item["cleanComparison"]
        rows.append(f"| {item['id']} | {item['label']} | {item['renderMode']} | {item['elapsedSeconds']:.3f}s | {work.get('framesReused', '?')}/{work.get('framesRendered', '?')} | clean V {comparison['videoExact']}, approved V {comparison['approvedVideoExact']}, SSIM {comparison['videoSsim']:.6f} / A {comparison['audioExact']} ({comparison['audioCorrelation']:.6f}) |")
    rows.extend(["", "## Three-trial latency benchmarks", "", "| Class | Incremental mean | Clean mean | Speedup |", "|---|---:|---:|---:|"])
    rows.extend(f"| {item['name']} | {item['incrementalMeanSeconds']:.3f}s | {item['cleanMeanSeconds']:.3f}s | {item['speedup']:.2f}x |" for item in report["benchmarks"])
    return "# Fan-edit revision review\n\nOpen the numbered videos in order. Specs, provenance, two contact sheets, and the JSON report are in this same flat folder. The companion general stress sequence covers text add/change/move/remove; this sequence preserves the fan-edit no-text default.\n\n" + "\n".join(rows) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_artifact(path: Path) -> None:
    path.unlink(missing_ok=True)
    path.with_suffix(path.suffix + ".vibeedit.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
