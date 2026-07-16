#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import platform
import queue
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from pathlib import Path


CEF_VERSION = "144.0.30+g9e70dde+chromium-144.0.7559.257"
CHROMIUM_VERSION = "144.0.7559.257"
ARCHIVE = f"cef_binary_{CEF_VERSION}_macosarm64.tar.bz2"
ARCHIVE_SHA1 = "52f7336a55a0bf54563675b81704e8d1d05bc14f"
MARKER = "VIBEEDIT_CEF_ACCELERATED_PAINT"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and probe Chromium/CEF IOSurface delivery for VibeEdit")
    parser.add_argument("--cache", type=Path, default=Path.home() / "Library" / "Caches" / "vibeedit" / "cef")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--raw-output", type=Path)
    parser.add_argument("--video-output", type=Path)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.frames <= 120:
        raise SystemExit("--frames must be between 1 and 120")
    if args.video_output and not args.raw_output:
        raise SystemExit("--video-output requires --raw-output")
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("this MVP currently pins the macOS ARM64 CEF distribution")

    root = Path(__file__).resolve().parents[2]
    cef = prepare_cef(args.cache, skip_build=args.skip_build)
    app = cef / "build" / "tests" / "cefclient" / "Release" / "cefclient.app" / "Contents" / "MacOS" / "cefclient"
    if not app.is_file():
        raise SystemExit(f"CEF probe application was not built: {app}")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), quiet_handler(root))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/experiments/cef-shared-texture/webgpu-html-css.html?live=1"
    command = [
        str(app),
        "--off-screen-rendering-enabled",
        "--shared-texture-enabled",
        "--enable-gpu",
        "--enable-unsafe-webgpu",
        "--off-screen-frame-rate=60",
        "--force-device-scale-factor=1",
        "--window-size=640,360",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        f"--url={url}",
        "--enable-logging=stderr",
        "--v=1",
        "--no-sandbox",
    ]
    environment = os.environ.copy()
    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.unlink(missing_ok=True)
        environment.update({"VIBEEDIT_CEF_RAW_OUTPUT": str(args.raw_output), "VIBEEDIT_CEF_RAW_FRAMES": str(args.frames)})
    process = subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, bufsize=1)
    lines: queue.Queue[tuple[float, str]] = queue.Queue()
    reader = threading.Thread(target=read_lines, args=(process.stderr, lines), daemon=True)
    reader.start()
    callbacks: list[float] = []
    first_surface = None
    webgpu_ready = False
    errors = []
    deadline = time.monotonic() + args.timeout
    try:
        while time.monotonic() < deadline and len(callbacks) < args.frames:
            try:
                timestamp, line = lines.get(timeout=.2)
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if "VIBEEDIT_WEBGPU_READY" in line:
                webgpu_ready = True
            if "VIBEEDIT_WEBGPU_ERROR" in line:
                errors.append(line.strip())
            if MARKER not in line:
                continue
            callbacks.append(timestamp)
            if first_surface is None:
                values = dict(part.split("=", 1) for part in line.split() if "=" in part)
                first_surface = {"width": int(values["width"]), "height": int(values["height"]), "kind": "IOSurface"}
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    elapsed = callbacks[-1] - callbacks[0] if len(callbacks) > 1 else 0
    raw_bytes = args.raw_output.stat().st_size if args.raw_output and args.raw_output.is_file() else 0
    expected_raw_bytes = first_surface["width"] * first_surface["height"] * 4 * len(callbacks) if first_surface else 0
    if args.video_output and first_surface and raw_bytes == expected_raw_bytes:
        args.video_output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                shutil.which("ffmpeg") or "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pixel_format",
                "bgra",
                "-video_size",
                f'{first_surface["width"]}x{first_surface["height"]}',
                "-framerate",
                "30",
                "-i",
                str(args.raw_output),
                "-frames:v",
                str(len(callbacks)),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                str(args.video_output),
            ],
            check=True,
        )
    report = {
        "schemaVersion": "vibeedit.cef-shared-texture-mvp.v1",
        "status": "passed" if len(callbacks) >= args.frames and webgpu_ready else "incomplete",
        "platform": "macos-arm64",
        "cefVersion": CEF_VERSION,
        "chromiumVersion": CHROMIUM_VERSION,
        "htmlCssEngine": "Blink/Skia",
        "browserGpu": "WebGPU",
        "surfaceTransport": "CEF OnAcceleratedPaint IOSurface",
        "pngBoundaryUsed": False,
        "webgpuReady": webgpu_ready,
        "acceleratedPaintCallbacks": len(callbacks),
        "callbackFps": round((len(callbacks) - 1) / elapsed, 2) if elapsed > 0 else None,
        "firstSurface": first_surface,
        "rawCapture": {"enabled": bool(args.raw_output), "bytes": raw_bytes, "expectedBytes": expected_raw_bytes, "complete": bool(args.raw_output) and raw_bytes == expected_raw_bytes},
        "videoOutput": args.video_output.name if args.video_output and args.video_output.is_file() else None,
        "errors": errors,
        "claimBoundary": "IOSurface-to-CPU raw BGRA capture and software H.264 encoding are proven; deterministic external frame scheduling, direct IOSurface-to-wgpu import, and texture-native hardware encoding are not implemented.",
    }
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["status"] == "passed" else 1


def prepare_cef(cache: Path, *, skip_build: bool) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / ARCHIVE
    cef = cache / ARCHIVE.removesuffix(".tar.bz2")
    if not archive.is_file():
        urllib.request.urlretrieve(f"https://cef-builds.spotifycdn.com/{ARCHIVE}", archive)
    digest = hashlib.sha1()
    with archive.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != ARCHIVE_SHA1:
        archive.unlink(missing_ok=True)
        raise SystemExit("downloaded CEF archive did not match the pinned SHA-1")
    if not cef.is_dir():
        with tarfile.open(archive, "r:bz2") as bundle:
            for member in bundle.getmembers():
                if not (cache / member.name).resolve().is_relative_to(cache.resolve()):
                    raise SystemExit("CEF archive contains an unsafe path")
            bundle.extractall(cache)
    instrument(cef / "tests" / "cefclient" / "browser" / "browser_window_osr_mac.mm")
    if skip_build:
        return cef
    build = cef / "build"
    subprocess.run([shutil.which("cmake") or "cmake", "-G", "Ninja", "-S", str(cef), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release", "-DUSE_SANDBOX=OFF"], check=True)
    subprocess.run([shutil.which("cmake") or "cmake", "--build", str(build), "--target", "cefclient", "-j", str(max(1, min(8, os.cpu_count() or 1)))], check=True)
    return cef


def instrument(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if "#include <cstdio>" not in source:
        source = source.replace("#include <optional>\n", "#include <cstdio>\n#include <cstdlib>\n#include <optional>\n")
    if MARKER in source and "<= 120" not in source:
        source = source.replace("<= 8", "<= 120")
    if MARKER not in source:
        needle = "  GLsizei height = (GLsizei)IOSurfaceGetHeight(io_surface);\n"
        insertion = needle + "\n  static int vibeedit_accelerated_paint_count = 0;\n  if (++vibeedit_accelerated_paint_count <= 120) {\n    LOG(INFO) << \"VIBEEDIT_CEF_ACCELERATED_PAINT frame=\"\n              << vibeedit_accelerated_paint_count << \" width=\" << width\n              << \" height=\" << height << \" io_surface=\" << io_surface;\n  }\n"
        if source.count(needle) != 1:
            raise SystemExit("CEF accelerated-paint probe patch no longer applies cleanly")
        source = source.replace(needle, insertion)
    raw_marker = "  // VIBEEDIT_CEF_RAW_CAPTURE\n"
    if raw_marker not in source:
        needle = "  CGLTexImageIOSurface2D(cgl_context, GL_TEXTURE_RECTANGLE_ARB, GL_RGBA8, width,\n"
        insertion = raw_marker + "  const char* vibeedit_raw_output = std::getenv(\"VIBEEDIT_CEF_RAW_OUTPUT\");\n  const char* vibeedit_raw_frames_value = std::getenv(\"VIBEEDIT_CEF_RAW_FRAMES\");\n  const int vibeedit_raw_frames = vibeedit_raw_frames_value ? std::atoi(vibeedit_raw_frames_value) : 0;\n  if (vibeedit_raw_output && vibeedit_accelerated_paint_count <= vibeedit_raw_frames) {\n    static FILE* vibeedit_raw_file = std::fopen(vibeedit_raw_output, \"ab\");\n    uint32_t seed = 0;\n    if (vibeedit_raw_file && IOSurfaceLock(io_surface, kIOSurfaceLockReadOnly, &seed) == 0) {\n      const auto* bytes = static_cast<const uint8_t*>(IOSurfaceGetBaseAddress(io_surface));\n      const size_t stride = IOSurfaceGetBytesPerRow(io_surface);\n      for (GLsizei row = 0; row < height; ++row) {\n        std::fwrite(bytes + row * stride, 1, static_cast<size_t>(width) * 4, vibeedit_raw_file);\n      }\n      std::fflush(vibeedit_raw_file);\n      IOSurfaceUnlock(io_surface, kIOSurfaceLockReadOnly, &seed);\n    }\n  }\n\n" + needle
        if source.count(needle) != 1:
            raise SystemExit("CEF raw-capture probe patch no longer applies cleanly")
        source = source.replace(needle, insertion)
    viewport_marker = "  // VIBEEDIT_CEF_FIXED_VIEWPORT\n"
    if viewport_marker not in source:
        needle = "  REQUIRE_MAIN_THREAD();\n\n  // Keep (0,0) origin for proper layout on macOS.\n"
        insertion = "  REQUIRE_MAIN_THREAD();\n\n" + viewport_marker + "  rect = CefRect(0, 0, 640, 360);\n  return;\n\n  // Keep (0,0) origin for proper layout on macOS.\n"
        if source.count(needle) != 1:
            raise SystemExit("CEF viewport probe patch no longer applies cleanly")
        source = source.replace(needle, insertion)
    path.write_text(source, encoding="utf-8")


def quiet_handler(root: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=root, **kwargs)

        def log_message(self, format, *args):
            return

    return Handler


def read_lines(stream, output: queue.Queue[tuple[float, str]]) -> None:
    for line in stream:
        output.put((time.perf_counter(), line))


if __name__ == "__main__":
    raise SystemExit(main())
