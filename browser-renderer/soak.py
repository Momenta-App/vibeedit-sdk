#!/usr/bin/env python3
"""Bounded real-media soak, sampled process-tree RSS, long jobs and revisions."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, render_browser_job

p = argparse.ArgumentParser()
p.add_argument("--seconds", type=float, default=600)
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/soak.json")
)
a = p.parse_args()
base = Path(__file__).resolve().parent
root = base / "examples/corpus"
report = {
    "machine": platform.platform(),
    "requestedSeconds": a.seconds,
    "runs": [],
    "memorySamples": [],
    "memoryLimitMiB": 4096,
    "qualifiedConcurrency": 1,
    "memoryScope": "orchestrator and all owned descendants, including CEF and FFmpeg",
}
started = time.perf_counter()
stop = threading.Event()
with (
    CEFService() as service,
    tempfile.TemporaryDirectory(prefix="vibeedit-soak-") as directory,
):
    report["startupSeconds"] = time.perf_counter() - started
    directory = Path(directory)

    def sample():
        while not stop.wait(1):
            rows = [
                row.split(None, 3)
                for row in subprocess.check_output(
                    ["ps", "-axo", "pid,ppid,rss,command"], text=True
                ).splitlines()[1:]
            ]
            family = {os.getpid()}
            previous = set()
            while previous != family:
                previous = set(family)
                family.update(int(row[0]) for row in rows if int(row[1]) in family)
            rss = sum(int(row[2]) for row in rows if int(row[0]) in family) / 1024
            report["memorySamples"].append(
                {"seconds": time.perf_counter() - started, "rssMiB": rss}
            )

    thread = threading.Thread(target=sample)
    thread.start()
    try:
        index = 0
        while time.perf_counter() - started < a.seconds:
            width, height = [(1920, 1080), (3840, 2160), (1280, 720)][index % 3]
            job = json.loads((root / "job.json").read_text())
            job.update(
                root=str(root),
                width=width,
                height=height,
                frames=3600 if index == 0 else 1800,
            )
            path = directory / "job.json"
            path.write_text(json.dumps(job))
            result = render_browser_job(
                path, directory / "video.mp4", backend="cef", service=service
            )
            report["runs"].append(result)
            report["elapsedSeconds"] = time.perf_counter() - started
            a.report.parent.mkdir(parents=True, exist_ok=True)
            a.report.write_text(json.dumps(report, indent=2) + "\n")
            index += 1
    finally:
        stop.set()
        thread.join()
report["peakRSSMiB"] = max(sample["rssMiB"] for sample in report["memorySamples"])
report["passed"] = (
    report["elapsedSeconds"] >= a.seconds
    and report["peakRSSMiB"] < report["memoryLimitMiB"]
)
a.report.write_text(json.dumps(report, indent=2) + "\n")
print(
    json.dumps({k: v for k, v in report.items() if k not in {"memorySamples", "runs"}})
)
raise SystemExit(0 if report["passed"] else 1)
