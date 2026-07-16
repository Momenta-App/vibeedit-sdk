#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deterministic Rust/Metal compositor output")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("compositor-conformance-report.json"))
    args = parser.parse_args()
    if args.runs < 2:
        raise SystemExit("--runs must be at least two")
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="vibeedit-cef-compositor-") as temporary:
        results = [run_probe(args, Path(temporary), index) for index in range(args.runs)]
    hashes = [result["gpuQaCapture"]["sha256"] for result in results]
    report = {
        "schemaVersion": "vibeedit.cef-compositor-conformance.v1",
        "resolution": {"width": args.width, "height": args.height},
        "fps": args.fps,
        "frames": args.frames,
        "runs": args.runs,
        "allRunsPassed": all(result["status"] == "passed" for result in results),
        "exactFinalFrameReplay": len(set(hashes)) == 1,
        "finalFrameSha256": hashes[0],
        "exactFrameSequences": all(result["frameScheduling"]["exactSequence"] for result in results),
        "steadyStateCallbackFps": [result["steadyStateCallbackFps"] for result in results],
        "averageGpuSubmitMilliseconds": [result["rustGpuStats"]["averageSubmitMilliseconds"] for result in results],
        "wallSeconds": round(time.perf_counter() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["allRunsPassed"] and report["exactFinalFrameReplay"] and report["exactFrameSequences"] else 1


def run_probe(args: argparse.Namespace, temporary: Path, index: int) -> dict:
    capture = temporary / f"run-{index}.bgra"
    report = temporary / f"run-{index}.json"
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("probe.py")),
            "--skip-build",
            "--deterministic",
            "--rust-gpu",
            "--rust-gpu-mode",
            "composite",
            "--frames",
            str(args.frames),
            "--fps",
            str(args.fps),
            "--width",
            str(args.width),
            "--height",
            str(args.height),
            "--timeout",
            "60",
            "--gpu-qa-output",
            str(capture),
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
