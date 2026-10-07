#!/usr/bin/env python3
"""Kill only an owned CEF GPU process; bounded failure or verified continuation."""

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

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import BrowserRenderError, CEFService, render_browser_job

p = argparse.ArgumentParser()
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/gpu-recovery.json")
)
a = p.parse_args()
report = {}
with tempfile.TemporaryDirectory(prefix="vibeedit-gpu-failure-") as directory:
    root = Path(directory)
    (root / "index.html").write_text(
        '<style>body{margin:0;background:#16343e}</style><canvas width="320" height="180"></canvas><script>window.renderFrame=async(frame)=>{await new Promise(r=>setTimeout(r,60));const c=document.querySelector("canvas").getContext("2d");c.fillStyle=`rgb(${frame},100,180)`;c.fillRect(0,0,320,180)}</script>'
    )
    job = root / "job.json"
    job.write_text(
        json.dumps({"entry": "index.html", "width": 320, "height": 180, "frames": 60})
    )
    service = CEFService(timeout=8)
    targets = []

    def kill_gpu():
        time.sleep(1)
        rows = subprocess.check_output(
            ["ps", "-axo", "pid,ppid,command"], text=True
        ).splitlines()
        targets.extend(
            int(row.split()[0])
            for row in rows
            if len(row.split()) > 2
            and row.split()[1] == str(service.process.pid)
            and "--type=gpu-process" in row
        )
        for pid in targets:
            os.kill(pid, signal.SIGKILL)

    thread = threading.Thread(target=kill_gpu)
    thread.start()
    try:
        render_browser_job(
            job,
            root / "failed.mp4",
            backend="cef",
            service=service,
            raw=root / "frames.bgra",
            screenshots=root / "shots",
        )
        pixels = np.memmap(
            root / "frames.bgra", mode="r", dtype=np.uint8, shape=(60, 180, 320, 4)
        )
        parity = all(
            np.array_equal(
                pixels[i][:, :, [2, 1, 0, 3]],
                np.array(Image.open(root / "shots" / f"{i:06d}.png").convert("RGBA")),
            )
            for i in range(60)
        )
        logical = all(
            tuple(pixels[i, 90, 160, [2, 1, 0]]) == (i, 100, 180) for i in range(60)
        )
        report.update(
            outcome="continued",
            losslessParity=parity,
            logicalFramePixels=logical,
            passed=parity and logical,
        )
    except BrowserRenderError as error:
        report.update(
            outcome="bounded-failure", failure=str(error), passed=service.closed
        )
    finally:
        thread.join()
        service.close()
    report["ownedGPUProcessesKilled"] = len(targets)
    report["passed"] = report["passed"] and len(targets) == 1
    recovery = render_browser_job(job, root / "recovered.mp4", backend="cef")
    report["freshJob"] = recovery
    report["passed"] = report["passed"] and recovery["frames"] == 60
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
