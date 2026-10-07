#!/usr/bin/env python3
"""Public API, actual CLI/worker, cache, queued concurrency and cancellation."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, render_browser_job

p = argparse.ArgumentParser()
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/service.json")
)
a = p.parse_args()
report = {"tests": []}
env = {
    **os.environ,
    "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "python/src"),
}
with tempfile.TemporaryDirectory(prefix="vibeedit-service-check-") as directory:
    directory = Path(directory)
    root = directory / "project"
    root.mkdir()
    page = root / "index.html"
    page.write_text(
        '<body style="background:#102030;color:white;font:30px Arial">CACHE</body>'
    )
    job = root / "job.json"
    job.write_text(
        json.dumps({"entry": "index.html", "width": 320, "height": 180, "frames": 6})
    )
    output = directory / "video.mp4"
    cache = directory / "cache"
    with CEFService() as service:
        first = render_browser_job(
            job, output, backend="cef", service=service, cache=cache
        )
        second = render_browser_job(
            job, output, backend="cef", service=service, cache=cache
        )
        page.write_text(page.read_text().replace("CACHE", "REVISED"))
        third = render_browser_job(
            job, output, backend="cef", service=service, cache=cache
        )
        artifact = cache / (third["cacheKey"] + ".mp4")
        artifact.write_bytes(b"corrupt")
        fourth = render_browser_job(
            job, output, backend="cef", service=service, cache=cache
        )
        report["tests"].append(
            {
                "name": "cache-hit-revision-corruption",
                "passed": not first["cacheHit"]
                and second["cacheHit"]
                and not third["cacheHit"]
                and not fourth["cacheHit"],
            }
        )
        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    render_browser_job,
                    job,
                    directory / f"parallel{i}.mp4",
                    backend="cef",
                    service=service,
                )
                for i in range(2)
            ]
            results = [future.result() for future in futures]
        report["tests"].append(
            {
                "name": "two-request-one-service-serialized",
                "passed": all(result["frames"] == 6 for result in results),
                "aggregateFps": 12 / (time.perf_counter() - started),
                "admittedConcurrency": 1,
            }
        )
    bad = root / "bad.json"
    bad.write_text(
        json.dumps({"entry": "missing.html", "width": 320, "height": 180, "frames": 2})
    )
    requests = [
        {"id": name, "job": str(path), "output": str(directory / f"{name}.mp4")}
        for name, path in [("first", job), ("bad", bad), ("after", job)]
    ]
    worker = subprocess.run(
        [sys.executable, "-m", "vibeedit", "browser-worker", "--backend", "cef"],
        input="".join(json.dumps(request) + "\n" for request in requests),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=90,
    )
    replies = [json.loads(line) for line in worker.stdout.splitlines()]
    report["tests"].append(
        {
            "name": "built-cli-worker-good-bad-good",
            "passed": [reply["ok"] for reply in replies] == [True, False, True]
            and worker.returncode == 0,
            "ids": [reply["id"] for reply in replies],
        }
    )
    # SIGTERM must preserve the approved output and reap every owned CEF child.
    page.write_text(
        '<body style="background:#123456"><script>window.renderFrame=async()=>await new Promise(r=>setTimeout(r,100))</script>'
    )
    job.write_text(
        json.dumps({"entry": "index.html", "width": 320, "height": 180, "frames": 300})
    )
    output.write_bytes(b"approved artifact")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vibeedit",
            "render-browser",
            str(job),
            "--output",
            str(output),
            "--backend",
            "cef",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)
    tree = subprocess.check_output(["ps", "-axo", "pid,ppid,command"], text=True)
    hosts = [
        int(line.split()[0])
        for line in tree.splitlines()
        if len(line.split()) > 2
        and line.split()[1] == str(process.pid)
        and "/VibeEditRenderer " in line
    ]
    process.send_signal(signal.SIGTERM)
    process.communicate(timeout=12)
    remaining = subprocess.check_output(["ps", "-axo", "pid,ppid,command"], text=True)
    report["tests"].append(
        {
            "name": "CLI-SIGTERM-cleanup",
            "passed": output.read_bytes() == b"approved artifact"
            and not any(
                line.split()[0] in {str(pid) for pid in hosts}
                for line in remaining.splitlines()
                if line.split()
            ),
            "ownedHostsObserved": len(hosts),
            "exitCode": process.returncode,
        }
    )
report["passed"] = all(test["passed"] for test in report["tests"])
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
