from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

from vibeedit import plan_revision, render, render_revision, verify_output
from vibeedit.data import data_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workdir")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    if args.iterations < 3:
        raise ValueError("competitive timing requires at least three iterations")
    workdir = Path(args.workdir)
    run_dir = Path(args.run_dir)
    if run_dir.exists():
        raise FileExistsError(f"immutable benchmark run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    previous = _spec(workdir, -12)
    revised = _spec(workdir, -6)
    started = time.perf_counter()
    previous_output = render(previous, run_dir / "vibeedit-initial.mp4")
    initial_seconds = time.perf_counter() - started
    plan = plan_revision(previous, revised)
    full_samples = []
    revision_samples = []
    for index in range(args.iterations):
        started = time.perf_counter()
        reference = render(revised, run_dir / f"vibeedit-full-{index}.mp4")
        full_samples.append(time.perf_counter() - started)
        started = time.perf_counter()
        incremental = render_revision(previous, revised, previous_output, run_dir / f"vibeedit-revision-{index}.mp4")
        revision_samples.append(time.perf_counter() - started)
    provenance = json.loads(incremental.with_suffix(".mp4.vibeedit.json").read_text(encoding="utf-8"))
    report = {
        "schemaVersion": "1.0.0",
        "system": "vibeedit",
        "task": "agent-video-revision-v1",
        "runDirectory": str(run_dir.resolve()),
        "source": _source_state(),
        "environment": {
            "platform": platform.platform(),
            "python": sys.version,
            "ffmpeg": subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0],
            "ordering": "initial, then each full revision immediately followed by its incremental revision",
            "cacheState": "VibeEdit composition cache disabled; operating-system and FFmpeg process caches not reset",
        },
        "initialRenderSeconds": round(initial_seconds, 6),
        "fullRenderSamplesSeconds": [round(value, 6) for value in full_samples],
        "revisionSamplesSeconds": [round(value, 6) for value in revision_samples],
        "fullRenderMeanSeconds": round(sum(full_samples) / len(full_samples), 6),
        "revisionMeanSeconds": round(sum(revision_samples) / len(revision_samples), 6),
        "revisionSpeedup": round(sum(full_samples) / sum(revision_samples), 6),
        "revisionPlan": plan,
        "work": provenance["work"],
        "outputVerification": verify_output(incremental, revised["verification"]).to_spec(),
        "decodedVideoEquivalent": _stream_md5(incremental, "0:v:0") == _stream_md5(reference, "0:v:0"),
        "decodedAudioEquivalent": _stream_md5(incremental, "0:a:0") == _stream_md5(reference, "0:a:0"),
        "agentMeasurements": {"setupSeconds": None, "inputTokens": None, "outputTokens": None, "toolCalls": None, "failedAttempts": None, "recoveryNotes": "Supervisor harness baseline; agent-experience telemetry is unavailable."},
    }
    payload = json.dumps(report, indent=2) + "\n"
    (run_dir / "result.json").write_text(payload, encoding="utf-8")
    files = [path for path in sorted(run_dir.rglob("*")) if path.is_file()]
    (run_dir / "sha256-manifest.json").write_text(json.dumps({
        "schemaVersion": "1.0.0",
        "files": [{"path": str(path.relative_to(run_dir)), "bytes": path.stat().st_size, "sha256": _sha256(path)} for path in files],
    }, indent=2) + "\n", encoding="utf-8")
    print(payload, end="")
    return 0 if report["outputVerification"]["passed"] and report["decodedVideoEquivalent"] and report["decodedAudioEquivalent"] else 1


def _spec(workdir: Path, gain_db: int) -> dict:
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
    spec["id"] = "competitive-audio-revision"
    spec["cache"] = {"enabled": False}
    spec["canvas"].update({"width": 1920, "height": 1080})
    spec["durationFrames"] = 300
    spec["sources"] = [
        {"id": "source", "kind": "video", "uri": str(workdir / "source.mp4"), "identity": {"algorithm": "sha256", "value": _sha256(workdir / "source.mp4")}, "durationFrames": 300},
        {"id": "music", "kind": "audio", "uri": str(workdir / "music.wav"), "identity": {"algorithm": "sha256", "value": _sha256(workdir / "music.wav")}, "durationFrames": 300},
    ]
    spec["timeline"]["tracks"] = [
        {"id": "V1", "kind": "video", "order": 0, "items": [{"id": "source", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 300}, "source": {"sourceId": "source", "inFrame": 0, "durationFrames": 300}, "effects": []}]},
        {"id": "A1", "kind": "audio", "order": 0, "items": [{"id": "music", "kind": "audio", "placement": {"startFrame": 0, "durationFrames": 300}, "source": {"sourceId": "music", "inFrame": 0, "durationFrames": 300}, "role": "music", "gainDb": gain_db, "pan": 0, "fadeInFrames": 0, "fadeOutFrames": 0, "effects": []}]},
    ]
    spec["verification"] = {"durationFrames": 300, "width": 1920, "height": 1080, "frameRate": {"numerator": 30, "denominator": 1}, "hasVideo": True, "hasAudio": True, "maxDurationDriftFrames": 1}
    return spec


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_state() -> dict:
    root = Path(__file__).resolve().parents[2]
    revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "-C", str(root), "status", "--short"], capture_output=True, text=True, check=True).stdout
    diff = subprocess.run(["git", "-C", str(root), "diff", "--binary", "HEAD"], capture_output=True, check=True).stdout
    return {
        "gitRevision": revision,
        "dirty": bool(status),
        "status": status.splitlines(),
        "trackedDiffSha256": hashlib.sha256(diff).hexdigest(),
        "benchmarkHarnessSha256": _sha256(Path(__file__)),
    }


def _stream_md5(path: Path, stream: str) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", stream, "-f", "framemd5", "-"], capture_output=True, text=True, check=True)
    return "\n".join(line for line in result.stdout.splitlines() if not line.startswith("#"))


if __name__ == "__main__":
    raise SystemExit(main())
