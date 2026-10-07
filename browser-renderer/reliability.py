#!/usr/bin/env python3
"""Real built-host failure and clean-process recovery gates."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import BrowserRenderError, CEFService, render_browser_job

p = argparse.ArgumentParser()
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/reliability.json")
)
args = p.parse_args()
report = {"tests": []}
with tempfile.TemporaryDirectory(prefix="vibeedit-recovery-") as directory:
    directory = Path(directory)
    page = directory / "index.html"
    job = directory / "job.json"
    output = directory / "video.mp4"
    job.write_text(
        json.dumps({"entry": "index.html", "width": 640, "height": 360, "frames": 4})
    )
    output.write_bytes(b"previous approved artifact")
    for name, script in [
        ("script-error", 'throw new Error("INTENTIONAL_FAILURE")'),
        ("never-ready", "await new Promise(()=>{})"),
    ]:
        page.write_text(
            '<body style="background:#16343e"><script>window.renderFrame=async()=>{'
            + script
            + "}</script>"
        )
        service = CEFService(timeout=2)
        started = time.perf_counter()
        try:
            render_browser_job(job, output, backend="cef", service=service)
            raise AssertionError("fault was accepted")
        except BrowserRenderError as error:
            assert service.closed and not service.cache.exists()
            assert output.read_bytes() == b"previous approved artifact"
            report["tests"].append(
                {
                    "test": name,
                    "passed": True,
                    "seconds": time.perf_counter() - started,
                    "failure": str(error),
                    "cacheRemoved": True,
                    "processExited": service.process.poll() is not None,
                }
            )
        finally:
            service.close()
    # Kill an owned renderer helper mid-render. The user desktop is never targeted.
    page.write_text(
        '<body style="background:#183840"><script>window.renderFrame=async()=>{await new Promise(r=>setTimeout(r,80))}</script>'
    )
    job.write_text(
        json.dumps({"entry": "index.html", "width": 640, "height": 360, "frames": 60})
    )
    service = CEFService(timeout=4)

    def interrupt():
        time.sleep(1)
        tree = subprocess.check_output(["ps", "-axo", "pid,ppid,command"], text=True)
        targets = [
            int(line.split()[0])
            for line in tree.splitlines()
            if len(line.split()) > 2
            and line.split()[1] == str(service.process.pid)
            and "--type=renderer" in line
        ]
        for pid in targets:
            os.kill(pid, signal.SIGKILL)

    thread = threading.Thread(target=interrupt)
    thread.start()
    try:
        render_browser_job(job, output, backend="cef", service=service)
        raise AssertionError("crashed renderer was accepted")
    except BrowserRenderError as error:
        report["tests"].append(
            {
                "test": "renderer-crash",
                "passed": service.closed and service.process.poll() is not None,
                "failure": str(error),
            }
        )
    finally:
        thread.join()
        service.close()
    page.write_text(
        '<body style="margin:0;background:#16343e;color:white;font:6vw Arial">RECOVERED<script>window.renderFrame=(f)=>document.body.dataset.frame=f</script>'
    )
    for w, h in [(1920, 1080), (3840, 2160)]:
        job.write_text(
            json.dumps({"entry": "index.html", "width": w, "height": h, "frames": 30})
        )
        rendered = render_browser_job(job, output, backend="cef")
        report["tests"].append(
            {
                "test": f"fresh-{w}x{h}-after-failure",
                "passed": rendered["frames"] == 30,
                "render": rendered,
            }
        )
report["passed"] = all(test["passed"] for test in report["tests"])
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
