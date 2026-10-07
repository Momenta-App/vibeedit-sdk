#!/usr/bin/env python3
"""Cold service startup, warm previews and small text revisions with stage metrics."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, render_browser_job

p = argparse.ArgumentParser()
p.add_argument(
    "--report",
    type=Path,
    default=Path("browser-renderer/evidence/preview-revisions.json"),
)
a = p.parse_args()
base = Path(__file__).resolve().parent
report = {"machine": platform.platform(), "runs": [], "startupSamplesSeconds": []}
for repeat in range(3):
    started = time.perf_counter()
    with CEFService() as service:
        report["startupSamplesSeconds"].append(time.perf_counter() - started)
with (
    CEFService() as service,
    tempfile.TemporaryDirectory(prefix="vibeedit-preview-") as directory,
):
    root = Path(directory) / "project"
    shutil.copytree(base / "examples/corpus", root)
    page = root / "index.html"
    original = page.read_text()
    for width, height in [(1280, 720), (1920, 1080), (3840, 2160)]:
        job = json.loads((root / "job.json").read_text())
        job.update(width=width, height=height, frames=30, profile=True)
        path = root / "job.json"
        path.write_text(json.dumps(job))
        for repeat in range(2):
            for backend in (
                ["cef", "screenshot"] if repeat == 0 else ["screenshot", "cef"]
            ):
                page.write_text(
                    original.replace("Tools make media.", f"Text revision {repeat}.")
                )
                result = render_browser_job(
                    path,
                    Path(directory) / "preview.mp4",
                    backend=backend,
                    service=service,
                )
                report["runs"].append(
                    {
                        "size": f"{width}x{height}",
                        "repeat": repeat,
                        "textRevision": repeat,
                        **result,
                    }
                )
                a.report.parent.mkdir(parents=True, exist_ok=True)
                a.report.write_text(json.dumps(report, indent=2) + "\n")
                print(
                    f"{width}x{height} {backend} revision {repeat}: {result['elapsedSeconds']:.3f}s",
                    flush=True,
                )
report["passed"] = len(report["runs"]) == 12
a.report.write_text(json.dumps(report, indent=2) + "\n")
