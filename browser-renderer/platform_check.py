#!/usr/bin/env python3
"""Actual portable fallback qualification, independent of the macOS native host."""

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
from vibeedit.browser_render import (
    BrowserRenderError,
    ScreenshotService,
    render_browser_job,
)

p = argparse.ArgumentParser()
p.add_argument("--report", type=Path, required=True)
args = p.parse_args()
root = Path(__file__).resolve().parent
report = {
    "platform": platform.platform(),
    "architecture": platform.machine(),
    "adapter": "Playwright screenshot/FFmpeg",
    "nativeAccelerated": False,
    "runs": [],
}
with ScreenshotService() as service, tempfile.TemporaryDirectory() as directory:
    for name in ["basic", "corpus", "features"]:
        result = render_browser_job(
            root / "examples" / name / "job.json",
            Path(directory) / f"{name}.mp4",
            backend="screenshot",
            service=service,
        )
        report["runs"].append({"example": name, "render": result})
    directory = Path(directory)
    shutil.copytree(root / "examples/features", directory / "nested/site")
    job = json.loads((root / "examples/features/job.json").read_text())
    job.update(root=str(directory), entry="nested/site/index.html", frames=3)
    (directory / "nested-job.json").write_text(json.dumps(job))
    report["runs"].append(
        {
            "example": "nested-entry",
            "render": render_browser_job(
                directory / "nested-job.json",
                directory / "nested.mp4",
                backend="screenshot",
                service=service,
            ),
        }
    )
with ScreenshotService(timeout=2) as service:
    started = time.monotonic()
    try:
        service.call(
            "Runtime.evaluate",
            params={"expression": "new Promise(()=>{})", "awaitPromise": True},
        )
    except BrowserRenderError:
        report["deadlineRecovery"] = {
            "seconds": time.monotonic() - started,
            "closed": service.closed,
            "loopStopped": not service.thread.is_alive(),
        }
with ScreenshotService() as service:
    report["freshBrowserAfterDeadline"] = (
        service.evaluate("1+1")["result"]["value"] == 2
    )
report["passed"] = (
    len(report["runs"]) == 4
    and report["deadlineRecovery"]["seconds"] < 6
    and report["deadlineRecovery"]["closed"]
    and report["deadlineRecovery"]["loopStopped"]
    and report["freshBrowserAfterDeadline"]
)
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
