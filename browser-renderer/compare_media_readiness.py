#!/usr/bin/env python3
"""Explore removing redundant presentation waits, using actual built renderer.

The candidate still awaits decoded seek completion, async creative code, two
Blink frames, and the corresponding drained/refreshed CEF surface. It is never
selected by the shipping backend unless lossless conformance and speed pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit import browser_render

p = argparse.ArgumentParser()
p.add_argument("--frames", type=int, default=120)
p.add_argument(
    "--report",
    type=Path,
    default=Path("browser-renderer/evidence/media-readiness-experiment.json"),
)
a = p.parse_args()
base = Path(__file__).resolve().parent
original = browser_render.ADAPTER
candidate = original.replace(
    "const repeated = decodedIndex(video.currentTime) === decodedIndex(target);",
    "const repeated = true;",
)
assert candidate != original
report = {
    "frames": a.frames,
    "reference": "requested video frame callback + Blink/surface barriers",
    "candidate": "decoded seek completion + Blink/surface barriers",
    "runs": [],
    "threshold": {"maximumChannelError": 0},
}
with (
    browser_render.CEFService() as service,
    tempfile.TemporaryDirectory(prefix="vibeedit-media-experiment-") as temporary,
):
    directory = Path(temporary)
    job = json.loads((base / "examples/corpus/job.json").read_text())
    job.update(
        root=str(base / "examples/corpus"), width=1280, height=720, frames=a.frames
    )
    path = directory / "job.json"
    path.write_text(json.dumps(job))
    for name, adapter in [("presented", original), ("seeked", candidate)]:
        browser_render.ADAPTER = adapter
        result = browser_render.render_browser_job(
            path,
            directory / f"{name}.mp4",
            backend="cef",
            service=service,
            raw=directory / f"{name}.bgra",
        )
        report["runs"].append(
            {
                "name": name,
                "adapterSha256": hashlib.sha256(adapter.encode()).hexdigest(),
                "render": result,
            }
        )
    reference = np.memmap(
        directory / "presented.bgra",
        mode="r",
        dtype=np.uint8,
        shape=(a.frames, 720, 1280, 4),
    )
    actual = np.memmap(
        directory / "seeked.bgra",
        mode="r",
        dtype=np.uint8,
        shape=(a.frames, 720, 1280, 4),
    )
    errors = [
        int(np.abs(actual[i].astype("int16") - reference[i].astype("int16")).max())
        for i in range(a.frames)
    ]
    report["maximumChannelError"] = max(errors)
    report["differingFrames"] = [i for i, value in enumerate(errors) if value]
    report["speedup"] = (
        report["runs"][0]["render"]["elapsedSeconds"]
        / report["runs"][1]["render"]["elapsedSeconds"]
    )
    report["passed"] = max(errors) == 0 and report["speedup"] > 1.05
browser_render.ADAPTER = original
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
