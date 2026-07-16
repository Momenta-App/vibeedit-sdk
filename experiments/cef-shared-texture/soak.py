#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sequential CEF/Rust/Metal compositor soak checks")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("soak-report.json"))
    args = parser.parse_args()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="vibeedit-cef-soak-") as temporary:
        results = [run_probe(args, Path(temporary), index) for index in range(args.runs)]
    report = {
        "schemaVersion": "vibeedit.cef-soak.v1",
        "resolution": {"width": args.width, "height": args.height},
        "runs": args.runs,
        "framesPerRun": args.frames,
        "allPassed": all(value["status"] == "passed" for value in results),
        "exactFrameSequences": all(value["frameScheduling"]["exactSequence"] for value in results),
        "steadyStateCallbackFps": [value["steadyStateCallbackFps"] for value in results],
        "averageGpuSubmitMilliseconds": [value["rustGpuStats"]["averageSubmitMilliseconds"] for value in results],
        "maximumChildResidentBytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "wallSeconds": round(time.perf_counter() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["allPassed"] and report["exactFrameSequences"] else 1


def run_probe(args: argparse.Namespace, temporary: Path, index: int) -> dict:
    destination = temporary / f"run-{index}.json"
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
            "--width",
            str(args.width),
            "--height",
            str(args.height),
            "--timeout",
            "60",
            "--report",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if not destination.is_file():
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(destination.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
