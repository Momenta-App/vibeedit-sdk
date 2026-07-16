#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "src"))

from vibeedit.effects import register_video_effect_filter
from vibeedit.ffmpeg import render_media


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark bounded concurrency in VibeEdit's Python/FFmpeg media stage")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments" / "render-concurrency" / "output")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sources = create_sources(args.output, args.width, args.height, args.frames)
    register_video_effect_filter(
        "vibeedit://effect/concurrency-stress",
        lambda _: "eq=contrast=1.12:saturation=1.18:brightness=0.02,unsharp=5:5:0.75:3:3:0.2,gblur=sigma=0.45",
        replace=True,
    )
    cases = [
        {"workers": 1, "threads": 1},
        {"workers": 1, "threads": 0},
        {"workers": 2, "threads": 1},
        {"workers": 2, "threads": max(1, (os.cpu_count() or 1) // 2)},
        {"workers": 4, "threads": 1},
        {"workers": 4, "threads": max(1, (os.cpu_count() or 1) // 4)},
    ]
    results = [run_case(args.output, sources, args.width, args.height, args.frames, args.jobs, case) for case in cases]
    report = {
        "schemaVersion": "vibeedit.render-concurrency.v1",
        "machineLogicalCpus": os.cpu_count(),
        "resolution": {"width": args.width, "height": args.height},
        "framesPerRender": args.frames * 2 - 30,
        "rendersPerCase": args.jobs,
        "results": results,
        "note": "Python selects trusted filters and launches FFmpeg; FFmpeg performs the pixel work in native code.",
    }
    destination = args.output / "report.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def create_sources(output: Path, width: int, height: int, frames: int) -> tuple[Path, Path]:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    duration = frames / 30
    sources = (output / "source-a.mp4", output / "source-b.mp4")
    filters = (f"testsrc2=size={width}x{height}:rate=30:duration={duration}", f"smptebars=size={width}x{height}:rate=30:duration={duration}")
    for destination, source_filter in zip(sources, filters, strict=True):
        if destination.is_file():
            continue
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source_filter, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", str(destination)],
            check=True,
        )
    return sources


def run_case(output: Path, sources: tuple[Path, Path], width: int, height: int, frames: int, jobs: int, case: dict[str, int]) -> dict[str, int | float]:
    directory = output / f"workers-{case['workers']}-threads-{case['threads']}"
    directory.mkdir(exist_ok=True)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=case["workers"]) as executor:
        outputs = list(executor.map(lambda index: render_media(composition(sources, width, height, frames, case["threads"], index), directory / f"render-{index}.mp4"), range(jobs)))
    elapsed = time.perf_counter() - started
    total_frames = jobs * (frames * 2 - 30)
    return {
        **case,
        "wallSeconds": round(elapsed, 3),
        "aggregateFramesPerSecond": round(total_frames / elapsed, 2),
        "megapixelsPerSecond": round(total_frames * width * height / elapsed / 1_000_000, 2),
        "outputBytes": sum(path.stat().st_size for path in outputs),
    }


def composition(sources: tuple[Path, Path], width: int, height: int, frames: int, threads: int, index: int) -> dict:
    duration = frames * 2 - 30
    return {
        "canvas": {"width": width, "height": height, "frameRate": {"numerator": 30, "denominator": 1}, "audioSampleRate": 48000},
        "durationFrames": duration,
        "sources": [
            {"id": "a", "kind": "video", "uri": str(sources[0])},
            {"id": "b", "kind": "video", "uri": str(sources[1])},
        ],
        "timeline": {
            "tracks": [
                {
                    "id": "V1",
                    "kind": "video",
                    "order": 0,
                    "items": [
                        {"id": "a", "kind": "video", "placement": {"startFrame": 0, "durationFrames": frames}, "source": {"sourceId": "a", "inFrame": 0, "durationFrames": frames}, "effects": [{"effectId": "vibeedit://effect/concurrency-stress", "params": {"variation": index}, "enabled": True}]},
                        {"id": "b", "kind": "video", "placement": {"startFrame": frames - 30, "durationFrames": frames}, "source": {"sourceId": "b", "inFrame": 0, "durationFrames": frames}, "effects": [{"effectId": "vibeedit://effect/random-frame-stutter", "params": {"seed": index + 1, "windowFrames": 4, "intensity": .5}, "enabled": True}]},
                        {"id": "fade", "kind": "transition", "placement": {"startFrame": frames - 30, "durationFrames": 30}, "transitionId": "vibeedit://transition/crossfade", "params": {}},
                    ],
                }
            ]
        },
        "render": {"threads": threads, "output": {"uri": "ignored.mp4", "container": "mp4", "videoCodec": "h264", "pixelFormat": "yuv420p"}},
    }


if __name__ == "__main__":
    raise SystemExit(main())
