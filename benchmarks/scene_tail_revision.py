from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from vibeedit import render, render_revision
from vibeedit.data import data_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark exact stream-copy scene-tail removal")
    parser.add_argument("workdir")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--cut-frame", type=int, default=210)
    args = parser.parse_args()
    if args.iterations < 3:
        raise ValueError("timing evidence requires at least three iterations")
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    previous, revised = _spec(workdir, args.width, args.height, args.frames, args.cut_frame)
    full_samples = []
    prime_samples = []
    revision_samples = []
    similarities = []
    records = []
    for index in range(args.iterations):
        with tempfile.TemporaryDirectory(prefix="vibeedit-scene-tail-") as cache:
            os.environ["VIBEEDIT_CACHE_DIR"] = cache
            started = time.perf_counter()
            reference = render(revised, workdir / f"reference-{index}.mp4")
            full_samples.append(time.perf_counter() - started)
            started = time.perf_counter()
            previous_output = render(previous, workdir / f"previous-{index}.mp4")
            prime_samples.append(time.perf_counter() - started)
            started = time.perf_counter()
            incremental = render_revision(previous, revised, previous_output, workdir / f"incremental-{index}.mp4")
            revision_samples.append(time.perf_counter() - started)
            if _decoded_hash(incremental, "0:v:0", ["-frames:v", str(args.cut_frame)]) != _decoded_hash(previous_output, "0:v:0", ["-frames:v", str(args.cut_frame)]):
                raise RuntimeError(f"incremental video {index} does not preserve the exact approved prefix")
            similarities.append(_ssim(incremental, reference))
            records.append(json.loads(incremental.with_suffix(".mp4.vibeedit.json").read_text(encoding="utf-8"))["work"])
    result = {
        "schemaVersion": "1.0.0",
        "task": "scene-tail-stream-copy-truncation",
        "canvas": {"width": args.width, "height": args.height, "frameRate": 30},
        "previousDurationFrames": args.frames,
        "revisedDurationFrames": args.cut_frame,
        "fullSamplesSeconds": [round(value, 6) for value in full_samples],
        "primeSamplesSeconds": [round(value, 6) for value in prime_samples],
        "revisionSamplesSeconds": [round(value, 6) for value in revision_samples],
        "fullMeanSeconds": round(sum(full_samples) / len(full_samples), 6),
        "revisionMeanSeconds": round(sum(revision_samples) / len(revision_samples), 6),
        "speedup": round(sum(full_samples) / sum(revision_samples), 6),
        "cleanRenderSsim": [round(value, 6) for value in similarities],
        "work": records,
        "equivalence": "exact-decoded-video-prefix-from-approved-render",
    }
    (workdir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


def _spec(workdir: Path, width: int, height: int, frames: int, cut_frame: int) -> tuple[dict, dict]:
    transition_frames = 30
    if not transition_frames < cut_frame < frames:
        raise ValueError("cut frame must leave a prefix and a removable tail")
    first_frames = cut_frame + transition_frames
    second_frames = frames - cut_frame
    _generate_sources(workdir, width, height, first_frames, second_frames)
    previous = json.loads(data_path("examples", "effect-transition", "composition.json").read_text(encoding="utf-8"))
    previous["canvas"].update({"width": width, "height": height})
    previous["durationFrames"] = frames
    previous["cache"] = {"enabled": False}
    previous["sources"][0].update({"uri": str(workdir / "a.mp4"), "durationFrames": first_frames})
    previous["sources"][1].update({"uri": str(workdir / "b.mp4"), "durationFrames": second_frames})
    items = previous["timeline"]["tracks"][0]["items"]
    items[0]["placement"]["durationFrames"] = first_frames
    items[0]["source"]["durationFrames"] = first_frames
    items[1]["placement"].update({"startFrame": cut_frame, "durationFrames": second_frames})
    items[1]["source"]["durationFrames"] = second_frames
    items[2]["placement"].update({"startFrame": cut_frame, "durationFrames": transition_frames})
    previous["timeline"]["tracks"][1]["items"][0]["placement"] = {"startFrame": cut_frame, "durationFrames": transition_frames}
    previous["verification"].update({"durationFrames": frames, "width": width, "height": height})
    revised = json.loads(json.dumps(previous))
    revised["durationFrames"] = cut_frame
    revised["timeline"]["tracks"][0]["items"] = [revised["timeline"]["tracks"][0]["items"][0]]
    revised["timeline"]["tracks"][1]["items"] = []
    revised["verification"].update({"durationFrames": cut_frame, "hasAudio": False})
    return previous, revised


def _generate_sources(workdir: Path, width: int, height: int, first_frames: int, second_frames: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    for name, source in (("a.mp4", f"testsrc2=size={width}x{height}:rate=30:duration={first_frames / 30:.9f}"), ("b.mp4", f"smptebars=size={width}x{height}:rate=30:duration={second_frames / 30:.9f}")):
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-threads", "1", str(workdir / name)], check=True)


def _decoded_hash(path: Path, stream: str, limit: list[str]) -> str:
    result = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", stream, *limit, "-f", "framemd5", "-"], capture_output=True, text=True, check=True)
    return "\n".join(line for line in result.stdout.splitlines() if not line.startswith("#"))


def _ssim(incremental: Path, reference: Path) -> float:
    result = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-i", str(incremental), "-i", str(reference), "-lavfi", "ssim", "-f", "null", "-"], capture_output=True, text=True, check=True)
    match = re.search(r"All:([0-9.]+)", result.stderr)
    if not match:
        raise RuntimeError("FFmpeg did not report SSIM")
    return float(match.group(1))


if __name__ == "__main__":
    raise SystemExit(main())
