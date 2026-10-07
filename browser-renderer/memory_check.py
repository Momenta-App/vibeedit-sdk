#!/usr/bin/env python3
"""Check independent warm jobs do not retain prior Chromium media documents."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, render_browser_job

p = argparse.ArgumentParser()
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/memory.json")
)
a = p.parse_args()
root = Path(__file__).resolve().parent / "examples/corpus"
report = {"runs": [], "scope": "owned CEF process tree after completed jobs"}
with CEFService() as service, tempfile.TemporaryDirectory() as directory:
    directory = Path(directory)
    job = json.loads((root / "job.json").read_text())
    job.update(root=str(root), width=1280, height=720, frames=6)
    (directory / "job.json").write_text(json.dumps(job))
    for index in range(12):
        result = render_browser_job(
            directory / "job.json",
            directory / "video.mp4",
            backend="cef",
            service=service,
        )
        time.sleep(0.1)
        rows = [
            row.split(None, 3)
            for row in subprocess.check_output(
                ["ps", "-axo", "pid,ppid,rss,command"], text=True
            ).splitlines()[1:]
        ]
        family = {service.process.pid}
        while True:
            descendants = family | {
                int(row[0]) for row in rows if int(row[1]) in family
            }
            if descendants == family:
                break
            family = descendants
        report["runs"].append(
            {
                "job": index,
                "rssMiB": sum(int(row[2]) for row in rows if int(row[0]) in family)
                / 1024,
                "renderers": sum(
                    "--type=renderer" in row[3] for row in rows if int(row[0]) in family
                ),
                "historyEntries": len(
                    service.call("Page.getNavigationHistory")["entries"]
                ),
                "implementationSha256": result["implementationSha256"],
                "hostSha256": result["hostSha256"],
            }
        )
report["growthMiB"] = report["runs"][-1]["rssMiB"] - report["runs"][0]["rssMiB"]
report["passed"] = report["growthMiB"] < 128 and all(
    run["renderers"] <= 3 and run["historyEntries"] == 1 for run in report["runs"]
)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
