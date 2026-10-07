#!/usr/bin/env python3
"""Compare every application-owned lossless frame with the pinned CEF screenshot."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, load_job, render_browser_job

p = argparse.ArgumentParser()
p.add_argument("jobs", nargs="+", type=Path)
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/conformance.json")
)
args = p.parse_args()
report = {
    "reference": "CEF 144.0.7559.257 Page.captureScreenshot",
    "losslessThreshold": {"maxChannelError": 0},
    "runs": [],
}
with CEFService() as service:
    for job in args.jobs:
        manifest, root, entry, fps, frames = load_job(job)
        width, height = manifest["width"], manifest["height"]
        with tempfile.TemporaryDirectory(prefix="vibeedit-conformance-") as directory:
            directory = Path(directory)
            raw = directory / "frames.bgra"
            images = directory / "screenshots"
            output = directory / "video.mp4"
            rendered = render_browser_job(
                job, output, backend="cef", service=service, raw=raw, screenshots=images
            )
            assert raw.stat().st_size == frames * width * height * 4
            pixels = np.memmap(
                raw, dtype=np.uint8, mode="r", shape=(frames, height, width, 4)
            )
            checks = []
            for frame in range(frames):
                reference = np.array(
                    Image.open(images / f"{frame:06d}.png").convert("RGBA")
                )
                actual = pixels[frame][:, :, [2, 1, 0, 3]]
                # IOSurface stores premultiplied alpha, screenshots store straight alpha.
                # Opaque exports must remain byte-exact. Transparent capture has its own gate.
                difference = np.abs(actual.astype("int16") - reference.astype("int16"))
                checks.append(
                    {
                        "frame": frame,
                        "maxChannelError": int(difference.max()),
                        "meanChannelError": float(difference.mean()),
                    }
                )
            metadata = json.loads(
                subprocess.check_output(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-select_streams",
                        "v:0",
                        "-show_frames",
                        "-show_entries",
                        "frame=pts_time",
                        "-of",
                        "json",
                        str(output),
                    ]
                )
            )
            timestamps = [float(frame["pts_time"]) for frame in metadata["frames"]]
            drift = max(
                abs(timestamp - float(index / fps))
                for index, timestamp in enumerate(timestamps)
            )
            run = {
                "job": str(job),
                "render": rendered,
                "frames": checks,
                "timestampMaxDriftSeconds": drift,
                "passed": all(check["maxChannelError"] == 0 for check in checks)
                and len(timestamps) == frames
                and drift <= 0.000001,
            }
            report["runs"].append(run)
            print(
                json.dumps({k: v for k, v in run.items() if k != "frames"}), flush=True
            )
report["passed"] = all(run["passed"] for run in report["runs"])
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, indent=2) + "\n")
raise SystemExit(0 if report["passed"] else 1)
