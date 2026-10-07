#!/usr/bin/env python3
"""Explicit alpha fallback via actual CLI; independent libvpx alpha decode."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/alpha.json")
)
a = p.parse_args()
base = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="vibeedit-alpha-") as directory:
    root = Path(directory)
    (root / "index.html").write_text(
        "<style>body{margin:0;background:transparent}div{position:absolute;left:40px;top:30px;width:80px;height:80px;background:#ff886680;border-radius:50%}</style><div></div>"
    )
    job = root / "job.json"
    job.write_text(
        json.dumps(
            {
                "entry": "index.html",
                "width": 320,
                "height": 180,
                "frames": 6,
                "export": {"codec": "vp9", "alpha": True},
            }
        )
    )
    movie = root / "alpha.webm"
    screens = root / "shots"
    command = [
        sys.executable,
        "-m",
        "vibeedit",
        "render-browser",
        str(job),
        "--output",
        str(movie),
        "--backend",
        "auto",
        "--screenshots",
        str(screens),
        "--json",
    ]
    completed = subprocess.run(
        command,
        env={**os.environ, "PYTHONPATH": str(base / "python/src")},
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    render = json.loads(completed.stdout)
    decoded = root / "frames.rgba"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-c:v",
            "libvpx-vp9",
            "-i",
            str(movie),
            "-pix_fmt",
            "rgba",
            "-f",
            "rawvideo",
            str(decoded),
        ],
        check=True,
    )
    pixels = np.memmap(decoded, dtype=np.uint8, mode="r", shape=(6, 180, 320, 4))
    reference = np.array(Image.open(screens / "000000.png").convert("RGBA"))
    assert reference[0, 0, 3] == 0 and 125 <= reference[70, 80, 3] <= 130
    alpha_error = int(
        np.abs(
            pixels[:, :, :, 3].astype("int16") - reference[:, :, 3].astype("int16")
        ).max()
    )
    center_error = int(
        np.abs(
            pixels[0, 70, 80].astype("int16") - reference[70, 80].astype("int16")
        ).max()
    )
    report = {
        "passed": alpha_error <= 4 and center_error <= 4,
        "alphaMaximumChannelError": alpha_error,
        "centerMaximumChannelError": center_error,
        "threshold": 4,
        "render": render,
    }
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
