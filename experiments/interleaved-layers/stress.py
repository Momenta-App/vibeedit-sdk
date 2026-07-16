#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


DOCUMENTS = (
    """<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}.title{position:absolute;top:9%;left:7%;font:900 72px/0.9 Arial;color:white;letter-spacing:-5px;text-shadow:0 10px 28px #000;animation:a 2s ease-in-out infinite alternate paused}@keyframes a{from{transform:translateX(-140px) rotate(-6deg);filter:blur(14px);opacity:.1}to{transform:translateX(0) rotate(1deg);filter:blur(0);opacity:1}}.title i{color:#bdf4ff}</style><div class=title>WEB <i>OVER</i><br>VIDEO</div>""",
    """<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}.rail{position:absolute;top:44%;left:10%;right:10%;display:flex;justify-content:space-between;mix-blend-mode:difference}.rail span{font:800 34px Arial;color:white;padding:12px 18px;border:2px solid white;backdrop-filter:blur(8px);animation:b 1.4s cubic-bezier(.2,.9,.2,1) infinite alternate paused}@keyframes b{from{transform:translateY(90px) scale(.8);opacity:0}to{transform:none;opacity:1}}</style><div class=rail><span>PYTHON FX</span><span>SCREEN BLEND</span><span>45% ALPHA</span></div>""",
    """<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}.copy{position:absolute;bottom:8%;left:0;right:0;text-align:center;font:900 52px Arial;color:#f5f5f5;letter-spacing:10px;filter:drop-shadow(0 5px 2px #000);animation:c 1.8s ease-in-out infinite alternate paused}.copy:after{content:'';position:absolute;inset:-10px 20%;background:linear-gradient(105deg,transparent 35%,#fff8 50%,transparent 65%);mix-blend-mode:screen;animation:s 1s linear infinite paused}@keyframes c{from{transform:perspective(700px) rotateX(50deg) translateY(80px);opacity:.15}to{transform:perspective(700px) rotateX(0);opacity:1}}@keyframes s{from{transform:translateX(-120%)}to{transform:translateX(120%)}}</style><div class=copy>MASKED · INTERLEAVED</div>""",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress alternating Chromium text and native media layers")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("output"))
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--frames", type=int, default=60)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sequential = render_layers(args, args.output / "sequential", 1)
    concurrent = render_layers(args, args.output / "concurrent", len(DOCUMENTS))
    review = compose(args, concurrent["outputs"], args.output / "interleaved-review.mp4")
    report = {
        "schemaVersion": "vibeedit.interleaved-layer-stress.v1",
        "resolution": {"width": args.width, "height": args.height},
        "frames": args.frames,
        "stackBottomToTop": ["Python/native base video", "Chromium text A", "Python/native screen-blend video", "Chromium text B", "Python/native circular alpha-mask video", "Chromium text C"],
        "sequentialWebSeconds": sequential["seconds"],
        "concurrentWebSeconds": concurrent["seconds"],
        "webConcurrencySpeedup": round(sequential["seconds"] / concurrent["seconds"], 2),
        "finalCompositeSeconds": review["seconds"],
        "reviewVideo": str(review["path"]),
        "boundary": "This validates ordering, blend, mask, opacity, and parallel web-band production through the current PNG fallback. The CEF Rust/Metal experiment removes that PNG boundary but is not yet connected to this final compositor.",
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def render_layers(args: argparse.Namespace, output: Path, workers: int) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        outputs = list(executor.map(lambda value: render_web_layer(args, output / f"web-{value[0]}.mkv", value[1]), enumerate(DOCUMENTS)))
    return {"seconds": round(time.perf_counter() - started, 3), "outputs": outputs}


def render_web_layer(args: argparse.Namespace, output: Path, document: str) -> Path:
    from playwright.sync_api import sync_playwright

    ffmpeg = subprocess.Popen(
        [shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", "30", "-vcodec", "png", "-i", "pipe:0", "-frames:v", str(args.frames), "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgra", "-threads", "2", str(output)],
        stdin=subprocess.PIPE,
    )
    if ffmpeg.stdin is None:
        raise RuntimeError("FFmpeg did not open its image pipe")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": args.width, "height": args.height}, device_scale_factor=1)
        page = context.new_page()
        page.set_content(document, wait_until="load")
        session = context.new_cdp_session(page)
        session.send("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
        for frame in range(args.frames):
            page.evaluate("milliseconds => document.getAnimations({subtree:true}).forEach(animation => animation.currentTime = milliseconds)", frame * 1000 / 30)
            ffmpeg.stdin.write(base64.b64decode(session.send("Page.captureScreenshot", {"format": "png", "fromSurface": True, "captureBeyondViewport": False})["data"]))
        context.close()
        browser.close()
    ffmpeg.stdin.close()
    if ffmpeg.wait() != 0:
        raise RuntimeError("FFmpeg failed to encode a web layer")
    return output


def compose(args: argparse.Namespace, web: list[Path], output: Path) -> dict:
    duration = args.frames / 30
    command = [shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    command.extend(["-f", "lavfi", "-i", f"testsrc2=size={args.width}x{args.height}:rate=30:duration={duration}"])
    command.extend(["-i", str(web[0])])
    command.extend(["-f", "lavfi", "-i", f"smptebars=size={args.width}x{args.height}:rate=30:duration={duration}"])
    command.extend(["-i", str(web[1])])
    command.extend(["-f", "lavfi", "-i", f"testsrc=size={args.width}x{args.height}:rate=30:duration={duration}"])
    command.extend(["-i", str(web[2])])
    radius = min(args.width, args.height) * .34
    graph = ";".join(
        [
            "[0:v]eq=contrast=1.12:saturation=1.25,unsharp=5:5:.55,format=rgba[base]",
            "[base][1:v]overlay=0:0:format=auto[s1]",
            "[2:v]eq=saturation=1.5,format=rgba[blend]",
            "[s1][blend]blend=all_mode=screen:all_opacity=.28[s2]",
            "[s2][3:v]overlay=0:0:format=auto[s3]",
            f"[4:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lt(hypot(X-W/2,Y-H/2),{radius:.3f}),92,0)'[masked]",
            "[s3][masked]overlay=0:0:format=auto[s4]",
            "[s4][5:v]overlay=0:0:format=auto,format=yuv420p[video]",
        ]
    )
    command.extend(["-filter_complex", graph, "-map", "[video]", "-an", "-frames:v", str(args.frames), "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-threads", "0", str(output)])
    started = time.perf_counter()
    subprocess.run(command, check=True)
    return {"seconds": round(time.perf_counter() - started, 3), "path": output}


if __name__ == "__main__":
    raise SystemExit(main())
