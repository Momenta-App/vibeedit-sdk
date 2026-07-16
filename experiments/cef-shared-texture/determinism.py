#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify exact CEF frame replay across fresh processes")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("determinism-report.json"))
    args = parser.parse_args()
    if args.runs < 2:
        raise SystemExit("--runs must be at least two")
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="vibeedit-cef-determinism-") as temporary:
        results = [run_probe(args, Path(temporary), index) for index in range(args.runs)]
    hashes = [result["frameHashes"] for result in results]
    report = {
        "schemaVersion": "vibeedit.cef-determinism.v1",
        "resolution": {"width": args.width, "height": args.height},
        "fps": args.fps,
        "frames": args.frames,
        "runs": args.runs,
        "allRunsPassed": all(result["status"] == "passed" for result in results),
        "exactReplay": all(value == hashes[0] for value in hashes[1:]),
        "allFramesDistinct": len(set(hashes[0])) == args.frames,
        "frameHashes": hashes[0],
        "callbackFps": [result["callbackFps"] for result in results],
        "wallSeconds": round(time.perf_counter() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["allRunsPassed"] and report["exactReplay"] and report["allFramesDistinct"] else 1


def run_probe(args: argparse.Namespace, temporary: Path, index: int) -> dict:
    raw = temporary / f"run-{index}.bgra"
    report = temporary / f"run-{index}.json"
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("probe.py")),
            "--skip-build",
            "--deterministic",
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
            "--raw-output",
            str(raw),
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    frame_bytes = args.width * args.height * 4
    hashes = []
    with raw.open("rb") as source:
        for _ in range(args.frames):
            frame = source.read(frame_bytes)
            if len(frame) != frame_bytes:
                raise RuntimeError(f"run {index} ended with an incomplete raw frame")
            hashes.append(hashlib.sha256(frame).hexdigest())
        if source.read(1):
            raise RuntimeError(f"run {index} produced unexpected extra raw bytes")
    value = json.loads(report.read_text(encoding="utf-8"))
    return {**value, "frameHashes": hashes}


if __name__ == "__main__":
    raise SystemExit(main())
