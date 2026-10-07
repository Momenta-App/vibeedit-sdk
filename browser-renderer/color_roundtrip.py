#!/usr/bin/env python3
"""Independent static frame-zero and browser-presented color qualification."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, ScreenshotService, render_browser_job

parser = argparse.ArgumentParser()
parser.add_argument(
    "--report",
    type=Path,
    default=Path("browser-renderer/evidence/browser-color-roundtrip.json"),
)
args = parser.parse_args()
root = args.report.parent.joinpath("media", args.report.stem).resolve()
root.mkdir(parents=True, exist_ok=True)
levels = [16, 32, 64, 96, 128, 160, 192, 224]
(root / "index.html").write_text(
    "<style>body{margin:0;display:flex;background:black}div{width:80px;height:360px}</style>"
    + "".join(f'<div style="background:rgb({v},{v},{v})"></div>' for v in levels)
)
job = root / "job.json"
job.write_text(
    json.dumps(
        {
            "entry": "index.html",
            "width": 640,
            "height": 360,
            "frames": 6,
            "export": {"bitrate": 12000000},
        }
    )
)
report = {"runs": []}
# Actual production path: no raw readback and no reference screenshots.
for cold in range(3):
    with CEFService() as native:
        for warm in range(2):
            movie = root / f"static-{cold}-{warm}.mp4"
            result = render_browser_job(job, movie, backend="cef", service=native)
            decoded = np.frombuffer(
                subprocess.check_output(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(movie),
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "-",
                    ]
                ),
                dtype=np.uint8,
            ).reshape(6, 360, 640, 3)
            measured = decoded[:, 180, [40 + i * 80 for i in range(8)]].astype(int)
            error = int(np.abs(measured - np.array(levels)[None, :, None]).max())
            report["runs"].append(
                {
                    "name": f"static-cold-{cold}-warm-{warm}",
                    "maximumChannelError": error,
                    "threshold": 4,
                    "passed": error <= 4,
                    "render": result,
                }
            )
(root / "playback.html").write_text(
    "<style>body{margin:0;background:black}video{width:640px;height:360px}</style>"
    '<video muted preload="auto"><source src="static-2-1.mp4" type=\'video/mp4; codecs="avc1.42E01E"\'></video>'
)
job.write_text(
    json.dumps({"entry": "playback.html", "width": 640, "height": 360, "frames": 6})
)
for name, constructor in [("CEF144", CEFService), ("Playwright149", ScreenshotService)]:
    with constructor() as service:
        shots = root / name
        render = render_browser_job(
            job,
            root / f"{name}.mp4",
            backend="screenshot",
            service=service,
            screenshots=shots,
        )
        measured = np.array(
            [
                np.array(Image.open(shots / f"{frame:06d}.png").convert("RGB"))[
                    180, [40 + i * 80 for i in range(8)]
                ]
                for frame in range(6)
            ]
        ).astype(int)
        error = int(np.abs(measured - np.array(levels)[None, :, None]).max())
        report["runs"].append(
            {
                "name": f"playback-{name}",
                "maximumChannelError": error,
                "threshold": 4,
                "passed": error <= 4,
                "render": render,
            }
        )
report["passed"] = all(run["passed"] for run in report["runs"])
args.report.write_text(json.dumps(report, indent=2) + "\n")
print(
    json.dumps(
        {
            "passed": report["passed"],
            "runs": [
                (run["name"], run["maximumChannelError"]) for run in report["runs"]
            ],
        }
    )
)
raise SystemExit(0 if report["passed"] else 1)
