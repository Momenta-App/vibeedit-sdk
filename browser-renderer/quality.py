#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, load_job, render_browser_job

p = argparse.ArgumentParser()
p.add_argument("job", type=Path)
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/quality.json")
)
args = p.parse_args()
manifest, root, entry, fps, frames = load_job(args.job)
w, h = manifest["width"], manifest["height"]
report = {
    "job": str(args.job),
    "threshold": {"minimumPSNRdB": 32, "meanPSNRdB": 35},
    "exports": [],
}
with (
    CEFService() as service,
    tempfile.TemporaryDirectory(prefix="vibeedit-quality-") as directory,
):
    directory = Path(directory)
    raw = directory / "reference.bgra"
    for backend in ["cef", "screenshot"]:
        movie = directory / f"{backend}.mp4"
        result = render_browser_job(
            args.job,
            movie,
            service=service,
            backend=backend,
            raw=raw if backend == "cef" else None,
        )
        decoded = directory / f"{backend}.rgb"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(movie),
                "-map",
                "0:v:0",
                "-fps_mode",
                "passthrough",
                "-pix_fmt",
                "rgb24",
                "-f",
                "rawvideo",
                str(decoded),
            ],
            check=True,
        )
        assert decoded.stat().st_size == w * h * 3 * frames
        reference = np.memmap(raw, mode="r", dtype=np.uint8, shape=(frames, h, w, 4))
        pixels = np.memmap(decoded, mode="r", dtype=np.uint8, shape=(frames, h, w, 3))
        scores = []
        for frame in range(frames):
            error = pixels[frame].astype("float32") - reference[frame][
                :, :, [2, 1, 0]
            ].astype("float32")
            mse = float(np.mean(error * error))
            scores.append(float(10 * np.log10(255**2 / max(mse, 1e-9))))
        score = {
            "backend": backend,
            "meanPSNRdB": float(np.mean(scores)),
            "minimumPSNRdB": min(scores),
            "bytes": movie.stat().st_size,
            "render": result,
        }
        score["passed"] = score["meanPSNRdB"] >= 35 and score["minimumPSNRdB"] >= 32
        report["exports"].append(score)
        print(json.dumps(score), flush=True)
report["passed"] = all(export["passed"] for export in report["exports"])
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, indent=2) + "\n")
raise SystemExit(0 if report["passed"] else 1)
