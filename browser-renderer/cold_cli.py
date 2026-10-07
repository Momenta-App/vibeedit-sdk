#!/usr/bin/env python3
"""Measure complete cold CLI exports, including interpreter and service startup."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/cold-cli.json")
)
a = p.parse_args()
root = Path(__file__).resolve().parent / "examples/corpus"
report = {
    "scope": "cold Python CLI process, CEF startup, preparation, 30-frame export, audio and verification",
    "runs": [],
}
with tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    for width, height in [(1280, 720), (1920, 1080), (3840, 2160)]:
        job = json.loads((root / "job.json").read_text())
        job.update(root=str(root), width=width, height=height, frames=30)
        job["export"]["bitrate"] = max(12_000_000, width * height * 10)
        (directory / "job.json").write_text(json.dumps(job))
        for backend in ["cef", "screenshot"]:
            started = time.monotonic()
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "vibeedit",
                    "render-browser",
                    str(directory / "job.json"),
                    "--output",
                    str(directory / "video.mp4"),
                    "--backend",
                    backend,
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=90,
                check=True,
            )
            result = json.loads(completed.stdout)
            report["runs"].append(
                {
                    "dimensions": [width, height],
                    "backend": backend,
                    "coldProcessSeconds": time.monotonic() - started,
                    "render": result,
                }
            )
report["passed"] = len(report["runs"]) == 6 and all(
    run["render"]["frames"] == 30 for run in report["runs"]
)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
