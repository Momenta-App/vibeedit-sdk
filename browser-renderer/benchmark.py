#!/usr/bin/env python3
"""Built-artifact benchmark; identical pages, adapter, browser, geometry, color."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, render_browser_job

p = argparse.ArgumentParser()
p.add_argument("--frames", type=int, default=900)
p.add_argument("--sizes", default="1280x720,1920x1080,3840x2160")
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/benchmark.json")
)
p.add_argument("--repeats", type=int, default=1)
a = p.parse_args()
base = Path(__file__).resolve().parent
root = base / "examples/corpus"
outputs = (
    Path(os.environ.get("VIBEEDIT_RENDER_ARTIFACTS", str(base / "evidence/media")))
    / a.report.stem
)
outputs.mkdir(parents=True, exist_ok=True)
report = {
    "machine": platform.platform(),
    "architecture": platform.machine(),
    "loadAverageAtStart": os.getloadavg(),
    "frames": a.frames,
    "runs": [],
    "qualification": "macOS ARM64 only; identical CEF 144 screenshot reference",
}
with CEFService(timeout=30) as service:
    report["capabilities"] = service.capabilities
    for size in a.sizes.split(","):
        width, height = map(int, size.split("x"))
        job = json.loads((root / "job.json").read_text())
        job.update(width=width, height=height, frames=a.frames)
        job["export"]["bitrate"] = max(12_000_000, width * height * 10)
        path = root / "benchmark-job.json"
        path.write_text(json.dumps(job))
        try:
            for repeat in range(a.repeats):
                results = {}
                for backend in (
                    ["cef", "screenshot"] if repeat % 2 == 0 else ["screenshot", "cef"]
                ):
                    print(f"{size} {backend} repeat {repeat} started", flush=True)
                    result = render_browser_job(
                        path,
                        outputs / f"{size}-{backend}-{repeat}.mp4",
                        backend=backend,
                        service=service,
                    )
                    results[backend] = result
                    print(json.dumps(result), flush=True)
                    report["runs"].append({"size": size, "repeat": repeat, **result})
                    a.report.parent.mkdir(parents=True, exist_ok=True)
                    a.report.write_text(json.dumps(report, indent=2) + "\n")
                print(
                    f"{size}: {results['screenshot']['elapsedSeconds'] / results['cef']['elapsedSeconds']:.3f}x end-to-end",
                    flush=True,
                )
        finally:
            path.unlink()
