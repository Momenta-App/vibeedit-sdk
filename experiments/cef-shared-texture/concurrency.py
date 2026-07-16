#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress concurrent CEF-to-Rust-to-Metal surface consumers")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("concurrency-output"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = [run_case(args, workers) for workers in (1, 2, 4)]
    report = {
        "schemaVersion": "vibeedit.cef-gpu-concurrency.v1",
        "resolution": {"width": args.width, "height": args.height},
        "framesPerConsumer": args.frames,
        "cases": cases,
        "recommendedMaxIsolatedWorkers": max(value["workers"] for value in cases if value["allPassed"]),
        "scope": "Each worker is an isolated CEF process and Rust/Metal consumer. This measures safe aggregate pressure; production should share one CEF process and compositor device.",
    }
    destination = args.output / "report.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def run_case(args: argparse.Namespace, workers: int) -> dict:
    directory = args.output / f"workers-{workers}"
    directory.mkdir(exist_ok=True)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        reports = list(executor.map(lambda index: run_consumer(args, directory / f"consumer-{index}.json"), range(workers)))
    elapsed = time.perf_counter() - started
    frames = sum(report["acceleratedPaintCallbacks"] for report in reports)
    return {
        "workers": workers,
        "wallSeconds": round(elapsed, 3),
        "endToEndAggregateFramesPerSecond": round(frames / elapsed, 2),
        "steadyStateAggregateCallbackFps": round(sum(report["steadyStateCallbackFps"] or 0 for report in reports), 2),
        "perConsumerCallbackFps": [report["steadyStateCallbackFps"] for report in reports],
        "averageGpuSubmitMilliseconds": round(sum(report["rustGpuStats"]["averageSubmitMilliseconds"] for report in reports if report["rustGpuStats"]) / max(1, sum(1 for report in reports if report["rustGpuStats"])), 3),
        "allPassed": all(report["status"] == "passed" for report in reports),
        "failures": [
            {
                "consumer": index,
                "callbacks": report["acceleratedPaintCallbacks"],
                "reason": report.get("lifecycle", {}).get("failureReason"),
            }
            for index, report in enumerate(reports)
            if report["status"] != "passed"
        ],
    }


def run_consumer(args: argparse.Namespace, destination: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("probe.py")),
            "--skip-build",
            "--rust-gpu",
            "--rust-gpu-mode",
            "composite",
            "--deterministic",
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
