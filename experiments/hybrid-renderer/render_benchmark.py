#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from vibeedit import register_transition_filter, register_video_effect_filter, render, verify_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Python effect/transition plus Chromium motion benchmark")
    parser.add_argument("output", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be positive")
    root = Path(__file__).resolve().parents[2]
    args.output.mkdir(parents=True, exist_ok=True)
    sources = args.output / "sources"
    sources.mkdir(exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required")
    for name, source in (
        ("a.mp4", "testsrc2=size=640x360:rate=30:duration=2"),
        ("b.mp4", "smptebars=size=640x360:rate=30:duration=2"),
    ):
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(sources / name)], check=True)

    spec = json.loads((root / "examples" / "effect-transition" / "composition.json").read_text(encoding="utf-8"))
    spec["id"] = "hybrid-python-web-benchmark"
    spec["canvas"].update({"width": 640, "height": 360})
    spec["sources"][0]["uri"] = str(sources / "a.mp4")
    spec["sources"][1]["uri"] = str(sources / "b.mp4")
    spec["render"]["backend"] = "mixed"
    spec["render"]["output"].update({"uri": "hybrid-review.mp4", "quality": {"crf": 18}})
    spec["verification"].update({"width": 640, "height": 360})
    spec["timeline"]["tracks"][0]["items"][0]["effects"][0].update({"effectId": "vibeedit://effect/agent-color-punch", "params": {"contrast": 1.12, "saturation": 1.18}})
    spec["timeline"]["tracks"][0]["items"][2].update({"transitionId": "vibeedit://transition/agent-wipe-left", "params": {"direction": "left"}})
    spec["timeline"]["tracks"].append(
        {
            "id": "M1",
            "kind": "motion",
            "order": 10,
            "items": [
                {
                    "id": "agent-web-title",
                    "kind": "motion",
                    "placement": {"startFrame": 0, "durationFrames": 108},
                    "componentId": "vibeedit://motion/html",
                    "props": {
                        "html": '<main><p>PYTHON EFFECTS</p><h1>WEB MOTION</h1><i></i></main>',
                        "css": "html,body{background:transparent}body{display:grid;place-items:center;margin:0;overflow:hidden;color:white;font-family:Inter,Arial,sans-serif}main{text-align:center;transform:perspective(700px) rotateX(-7deg);animation:enter .8s cubic-bezier(.2,.8,.2,1) both}p{margin:0 0 8px;font:800 14px/1 Arial;letter-spacing:.34em;color:#99f6e4}h1{margin:0;font:950 62px/.85 Arial;letter-spacing:-.07em;text-shadow:0 8px 22px #000;background:linear-gradient(100deg,#fff 20%,#5eead4 45%,#fff 60%);background-size:240% 100%;color:transparent;background-clip:text;animation:shine 1.3s linear infinite}i{display:block;width:84%;height:2px;margin:14px auto;background:#5eead4;box-shadow:0 0 16px #5eead4}@keyframes enter{from{opacity:0;transform:translateY(90px) scale(.9);filter:blur(16px)}to{opacity:1;transform:none;filter:none}}@keyframes shine{from{background-position:120%}to{background-position:-60%}}",
                        "javascript": "addEventListener('vibeedit:frame',({detail})=>document.documentElement.dataset.frame=detail.frame)",
                    },
                    "renderer": "html",
                    "transparent": True,
                }
            ],
        }
    )
    (args.output / "composition.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

    register_video_effect_filter(
        "vibeedit://effect/agent-color-punch",
        lambda params: f"eq=contrast={float(params.get('contrast', 1.1)):.3f}:saturation={float(params.get('saturation', 1.1)):.3f}",
    )
    register_transition_filter(
        "vibeedit://transition/agent-wipe-left",
        lambda *, params, duration_frames, offset_frames, numerator, denominator: f"xfade=transition=wipeleft:duration={duration_frames * denominator / numerator:.9f}:offset={offset_frames * denominator / numerator:.9f}",
    )
    runs = []
    for index in range(args.runs):
        output = args.output / f"hybrid-review-{index + 1}.mp4"
        started = time.perf_counter()
        render(spec, output)
        elapsed = time.perf_counter() - started
        verification = verify_output(output, spec["verification"])
        runs.append({"run": index + 1, "seconds": round(elapsed, 4), "framesPerSecond": round(spec["durationFrames"] / elapsed, 2), "bytes": output.stat().st_size, "verified": verification.passed, "errors": verification.errors})
    report = {"schemaVersion": "vibeedit.hybrid-render-benchmark.v1", "composition": "composition.json", "frames": spec["durationFrames"], "runs": runs, "bestFramesPerSecond": max(run["framesPerSecond"] for run in runs)}
    (args.output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all(run["verified"] for run in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
