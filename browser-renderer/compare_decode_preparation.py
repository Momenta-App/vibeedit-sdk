#!/usr/bin/env python3
"""Measure lossless all-intra source preparation against ordinary video seeks."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, render_browser_job

report = {"runs": []}
with tempfile.TemporaryDirectory(prefix="vibeedit-decode-preparation-") as temporary:
    root = Path(temporary)
    source = Path("browser-renderer/examples/corpus").resolve()
    prepared = root / "prepared"
    shutil.copytree(source, prepared)
    before = time.perf_counter()
    footage = prepared / "media/footage.webm"
    original = root / "original.webm"
    shutil.copyfile(footage, original)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-copyts",
            "-i",
            str(original),
            "-an",
            "-c:v",
            "libvpx-vp9",
            "-lossless",
            "1",
            "-g",
            "1",
            "-deadline",
            "realtime",
            "-cpu-used",
            "6",
            "-row-mt",
            "1",
            "-threads",
            "4",
            "-fps_mode",
            "passthrough",
            "-enc_time_base:v",
            "-1",
            str(footage),
        ],
        check=True,
    )
    report["sourceFrameHashes"] = [
        subprocess.check_output(
            ["ffmpeg", "-v", "error", "-i", str(file), "-an", "-f", "framemd5", "-"]
        ).decode()
        for file in [original, footage]
    ]
    report["preparationSeconds"] = time.perf_counter() - before
    reports = {}
    with CEFService() as service:
        for variant, directory in [("original", source), ("independent", prepared)]:
            manifest = {
                **json.loads((directory / "job.json").read_text()),
                "root": str(directory),
                "frames": 120,
            }
            job = root / (variant + ".json")
            job.write_text(json.dumps(manifest))
            reports[variant] = render_browser_job(
                job,
                root / (variant + ".mp4"),
                backend="cef",
                service=service,
                raw=root / (variant + ".bgra"),
            )
            report["runs"].append({"variant": variant, "render": reports[variant]})
    arrays = [
        np.memmap(
            root / (name + ".bgra"), mode="r", dtype=np.uint8, shape=(120, 720, 1280, 4)
        )
        for name in ["original", "independent"]
    ]
    report["maximumChannelErrorByFrame"] = [
        int(
            np.abs(
                arrays[0][frame].astype(np.int16) - arrays[1][frame].astype(np.int16)
            ).max()
        )
        for frame in range(120)
    ]
    report["maximumChannelError"] = max(
        int(
            np.abs(
                arrays[0][frame].astype(np.int16) - arrays[1][frame].astype(np.int16)
            ).max()
        )
        for frame in range(120)
    )
    report["speedup"] = (
        reports["original"]["elapsedSeconds"] / reports["independent"]["elapsedSeconds"]
    )
    report["accepted"] = report["maximumChannelError"] == 0 and report["speedup"] > 1.05
Path("browser-renderer/evidence/decode-preparation-experiment.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(
    json.dumps(
        {
            key: value
            for key, value in report.items()
            if key not in {"runs", "sourceFrameHashes", "maximumChannelErrorByFrame"}
        }
    )
)
