#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="vibeedit-cef-reliability-") as temporary:
        directory = Path(temporary)
        cases = [
            run_case(directory, "normal", 20, True),
            run_case(directory, "webgpu-error", 3, False),
            run_case(directory, "hang", 3, False),
        ]
    passed = (
        cases[0]["probeStatus"] == "passed"
        and all(value["probeStatus"] == "incomplete" for value in cases[1:])
        and all(value["runtimeCacheRemoved"] for value in cases)
        and all(value["boundedFailure"] for value in cases[1:])
    )
    report = {
        "schemaVersion": "vibeedit.cef-reliability.v1",
        "status": "passed" if passed else "failed",
        "cases": cases,
        "wallSeconds": round(time.perf_counter() - started, 3),
        "scope": "Validates success, bounded renderer script failure, bounded page-not-ready failure, process-group shutdown, and runtime-cache cleanup.",
    }
    destination = Path(__file__).with_name("reliability-report.json")
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


def run_case(directory: Path, mode: str, timeout: int, should_pass: bool) -> dict:
    started = time.perf_counter()
    destination = directory / f"{mode}.json"
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
            "10",
            "--width",
            "640",
            "--height",
            "360",
            "--timeout",
            str(timeout),
            "--page-mode",
            mode,
            "--report",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout + 15,
    )
    value = json.loads(destination.read_text(encoding="utf-8"))
    wall_seconds = time.perf_counter() - started
    if should_pass and result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    if not should_pass and result.returncode == 0:
        raise RuntimeError(f"{mode} unexpectedly passed")
    return {
        "mode": mode,
        "probeStatus": value["status"],
        "returnCode": result.returncode,
        "callbacks": value["acceleratedPaintCallbacks"],
        "webgpuReady": value["webgpuReady"],
        "timedOut": value["lifecycle"]["timedOut"],
        "failureReason": value["lifecycle"]["failureReason"],
        "boundedFailure": wall_seconds < timeout + 10,
        "wallSeconds": round(wall_seconds, 3),
        "runtimeCacheRemoved": value["lifecycle"]["runtimeCacheRemoved"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
