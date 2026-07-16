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
import tempfile
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
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--raw-output", type=Path)
    parser.add_argument("--video-output", type=Path)
    parser.add_argument("--rust-bridge", action="store_true")
    parser.add_argument("--rust-gpu", action="store_true")
    parser.add_argument("--rust-gpu-mode", choices=("blit", "composite"), default="blit")
    parser.add_argument("--gpu-qa-output", type=Path)
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--page-mode", choices=("normal", "webgpu-error", "hang"), default="normal")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--channel-depth", type=int, default=4)
    parser.add_argument("--max-inflight-mb", type=int, default=128)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.frames <= 120:
        raise SystemExit("--frames must be between 1 and 120")
    if args.video_output and not args.raw_output:
        raise SystemExit("--video-output requires --raw-output")
    if args.gpu_qa_output and not args.rust_gpu:
        raise SystemExit("--gpu-qa-output requires --rust-gpu")
    if args.width < 1 or args.height < 1:
        raise SystemExit("--width and --height must be positive")
    if not 1 <= args.channel_depth <= 64:
        raise SystemExit("--channel-depth must be between 1 and 64")
    if args.max_inflight_mb < 1:
        raise SystemExit("--max-inflight-mb must be positive")
    if args.fps < 1:
        raise SystemExit("--fps must be positive")
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
    parameters = [] if args.deterministic else ["live=1"]
    if args.page_mode != "normal":
        parameters.append(f"failure={args.page_mode}")
    url = f"http://127.0.0.1:{server.server_port}/experiments/cef-shared-texture/webgpu-html-css.html"
    if parameters:
        url += "?" + "&".join(parameters)
    runtime_cache = Path(tempfile.mkdtemp(prefix="vibeedit-cef-runtime-"))
    command = [
        str(app),
        "--off-screen-rendering-enabled",
        "--shared-texture-enabled",
        "--enable-gpu",
        "--enable-unsafe-webgpu",
        "--off-screen-frame-rate=60",
        "--force-device-scale-factor=1",
        f"--window-size={args.width},{args.height}",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        f"--cache-path={runtime_cache}",
        f"--url={url}",
        "--enable-logging=stderr",
        "--v=1",
        "--no-sandbox",
    ]
    if args.deterministic:
        command.append("--external-begin-frame-enabled")
    environment = os.environ.copy()
    environment.update({"VIBEEDIT_CEF_WIDTH": str(args.width), "VIBEEDIT_CEF_HEIGHT": str(args.height), "VIBEEDIT_CEF_HEADLESS_CAPTURE": "1", "VIBEEDIT_CEF_BACKGROUND": "1"})
    if args.deterministic:
        environment.update({"VIBEEDIT_CEF_DETERMINISTIC_FRAMES": str(args.frames), "VIBEEDIT_CEF_DETERMINISTIC_FPS": str(args.fps)})
    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.unlink(missing_ok=True)
        environment.update({"VIBEEDIT_CEF_RAW_OUTPUT": str(args.raw_output), "VIBEEDIT_CEF_RAW_FRAMES": str(args.frames)})
    frame_bytes = args.width * args.height * 4
    effective_channel_depth = min(args.channel_depth, max(1, args.max_inflight_mb * 1024 * 1024 // frame_bytes))
    if args.rust_bridge or args.rust_gpu:
        environment.update({"VIBEEDIT_RUST_BRIDGE": str(prepare_rust_bridge(root, skip_build=args.skip_build)), "VIBEEDIT_RUST_CHANNEL_DEPTH": str(effective_channel_depth)})
    if args.rust_gpu:
        environment.update({"VIBEEDIT_CEF_GPU_FRAMES": str(args.frames), "VIBEEDIT_RUST_GPU_MODE": args.rust_gpu_mode})
    if args.gpu_qa_output:
        args.gpu_qa_output.parent.mkdir(parents=True, exist_ok=True)
        args.gpu_qa_output.unlink(missing_ok=True)
        environment["VIBEEDIT_METAL_QA_OUTPUT"] = str(args.gpu_qa_output)
    process = subprocess.Popen(
        command,
        cwd=root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    lines: queue.Queue[tuple[float, str]] = queue.Queue()
    reader = threading.Thread(target=read_lines, args=(process.stderr, lines), daemon=True)
    reader.start()
    callbacks: list[float] = []
    callback_frames: list[int] = []
    first_surface = None
    webgpu_ready = False
    errors = []
    rust_stats = None
    rust_gpu_stats = None
    timed_out = False
    process_running_at_cleanup = False
    deadline = time.monotonic() + args.timeout
    try:
        while time.monotonic() < deadline:
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
            if "VIBEEDIT_RUST_SURFACE_STATS" in line:
                rust_stats = parse_values(line)
            if "VIBEEDIT_RUST_GPU_STATS" in line:
                rust_gpu_stats = parse_values(line)
            if MARKER not in line:
                continue
            callbacks.append(timestamp)
            values = dict(part.split("=", 1) for part in line.split() if "=" in part)
            callback_frames.append(int(values.get("requested_frame", -1)))
            if first_surface is None:
                first_surface = {"width": int(values["width"]), "height": int(values["height"]), "kind": "IOSurface"}
            if len(callbacks) >= args.frames and webgpu_ready:
                break
        timed_out = time.monotonic() >= deadline and not (len(callbacks) >= args.frames and webgpu_ready)
        if args.raw_output and args.raw_output != Path("/dev/null") and first_surface:
            expected = first_surface["width"] * first_surface["height"] * 4 * len(callbacks)
            write_deadline = time.monotonic() + 10
            while time.monotonic() < write_deadline and (not args.raw_output.is_file() or args.raw_output.stat().st_size < expected):
                time.sleep(.01)
        if args.rust_gpu and rust_gpu_stats is None:
            stats_deadline = time.monotonic() + 5
            while time.monotonic() < stats_deadline and rust_gpu_stats is None:
                try:
                    _, line = lines.get(timeout=.05)
                except queue.Empty:
                    continue
                if "VIBEEDIT_RUST_GPU_STATS" in line:
                    rust_gpu_stats = parse_values(line)
        while not lines.empty():
            _, line = lines.get_nowait()
            if "VIBEEDIT_RUST_SURFACE_STATS" in line:
                rust_stats = parse_values(line)
            if "VIBEEDIT_RUST_GPU_STATS" in line:
                rust_gpu_stats = parse_values(line)
    finally:
        process_running_at_cleanup = process.poll() is None
        terminate_process_group(process)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        shutil.rmtree(runtime_cache, ignore_errors=True)

    elapsed = callbacks[-1] - callbacks[0] if len(callbacks) > 1 else 0
    steady_elapsed = callbacks[-1] - callbacks[2] if len(callbacks) > 3 else 0
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
    deterministic_sequence = callback_frames == list(range(args.frames)) if args.deterministic else None
    gpu_qa_bytes = args.gpu_qa_output.stat().st_size if args.gpu_qa_output and args.gpu_qa_output.is_file() else 0
    gpu_qa_expected = args.width * args.height * 4 if args.gpu_qa_output else 0
    passed = len(callbacks) >= args.frames and webgpu_ready and deterministic_sequence is not False and (not args.rust_gpu or bool(rust_gpu_stats and rust_gpu_stats.get("submitted") == args.frames)) and (not args.gpu_qa_output or gpu_qa_bytes == gpu_qa_expected)
    report = {
        "schemaVersion": "vibeedit.cef-shared-texture-mvp.v1",
        "status": "passed" if passed else "incomplete",
        "platform": "macos-arm64",
        "cefVersion": CEF_VERSION,
        "chromiumVersion": CHROMIUM_VERSION,
        "htmlCssEngine": "Blink/Skia",
        "browserGpu": "WebGPU",
        "surfaceTransport": "CEF OnAcceleratedPaint IOSurface",
        "backgroundMode": True,
        "pngBoundaryUsed": False,
        "webgpuReady": webgpu_ready,
        "acceleratedPaintCallbacks": len(callbacks),
        "callbackFps": round((len(callbacks) - 1) / elapsed, 2) if elapsed > 0 else None,
        "steadyStateCallbackFps": round((len(callbacks) - 3) / steady_elapsed, 2) if steady_elapsed > 0 else None,
        "frameScheduling": {
            "mode": "external-begin-frame" if args.deterministic else "live-wall-clock",
            "fps": args.fps,
            "requestedFrames": callback_frames,
            "exactSequence": deterministic_sequence,
        },
        "firstSurface": first_surface,
        "logicalViewport": {"width": args.width, "height": args.height},
        "surfaceConsumer": "rust-metal-gpu-import" if args.rust_gpu else "rust-concurrent-copy" if args.rust_bridge else "cpp-synchronous-copy" if args.raw_output else "none",
        "channelDepth": {
            "requested": args.channel_depth,
            "effective": effective_channel_depth,
            "maxInflightMiB": args.max_inflight_mb,
            "effectiveCapacityMiB": round(effective_channel_depth * frame_bytes / 1024 / 1024, 2),
        } if args.rust_bridge else None,
        "rustSurfaceStats": normalize_rust_stats(rust_stats) if rust_stats else None,
        "rustGpuStats": normalize_gpu_stats(rust_gpu_stats) if rust_gpu_stats else None,
        "rustGpuMode": args.rust_gpu_mode if args.rust_gpu else None,
        "gpuQaCapture": {
            "enabled": bool(args.gpu_qa_output),
            "bytes": gpu_qa_bytes,
            "expectedBytes": gpu_qa_expected,
            "sha256": file_sha256(args.gpu_qa_output) if args.gpu_qa_output and gpu_qa_bytes == gpu_qa_expected else None,
        },
        "rawCapture": {"enabled": bool(args.raw_output), "bytes": raw_bytes, "expectedBytes": expected_raw_bytes if args.raw_output else 0, "complete": bool(args.raw_output) and raw_bytes == expected_raw_bytes},
        "videoOutput": args.video_output.name if args.video_output and args.video_output.is_file() else None,
        "lifecycle": {
            "pageMode": args.page_mode,
            "timedOut": timed_out,
            "processWasRunningAtCleanup": process_running_at_cleanup,
            "processExitCode": process.returncode,
            "runtimeCacheRemoved": not runtime_cache.exists(),
            "failureReason": "timeout" if timed_out else "page-not-ready" if not webgpu_ready else None,
        },
        "errors": errors,
        "claimBoundary": "Deterministic CEF external-begin-frame scheduling and macOS Rust/Metal IOSurface compositing primitives are proven for this fixture. A real multi-input media texture graph, hardware encoding, pooled browser views, crash isolation, and Windows/Linux adapters remain production gates.",
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
    instrument_background_window(cef / "tests" / "cefclient" / "browser" / "root_window_manager.cc")
    instrument_background_app(cef / "tests" / "cefclient" / "cefclient_mac.mm")
    if skip_build:
        return cef
    build = cef / "build"
    subprocess.run([shutil.which("cmake") or "cmake", "-G", "Ninja", "-S", str(cef), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release", "-DUSE_SANDBOX=OFF"], check=True)
    subprocess.run([shutil.which("cmake") or "cmake", "--build", str(build), "--target", "cefclient", "-j", str(max(1, min(8, os.cpu_count() or 1)))], check=True)
    return cef


def prepare_rust_bridge(root: Path, *, skip_build: bool) -> Path:
    manifest = root / "experiments" / "cef-shared-texture" / "rust-surface-bridge" / "Cargo.toml"
    library = manifest.parent / "target" / "release" / "libvibeedit_cef_surface_bridge.dylib"
    if skip_build and library.is_file():
        return library
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo" / "bin" / "cargo")
    subprocess.run([cargo, "build", "--release", "--manifest-path", str(manifest)], check=True)
    if not library.is_file():
        raise SystemExit(f"Rust surface bridge was not built: {library}")
    return library


def instrument_background_window(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if "#include <cstdlib>" not in source:
        source = source.replace("#include <sstream>\n", "#include <cstdlib>\n#include <sstream>\n")
    marker = "  // VIBEEDIT_CEF_BACKGROUND_WINDOW\n"
    needle = "scoped_refptr<RootWindow> RootWindowManager::CreateRootWindow(\n    std::unique_ptr<RootWindowConfig> config) {\n"
    if marker not in source:
        if source.count(needle) != 1:
            raise SystemExit("CEF background-window patch no longer applies cleanly")
        source = source.replace(needle, needle + marker + "  if (std::getenv(\"VIBEEDIT_CEF_BACKGROUND\")) config->initially_hidden = true;\n")
    path.write_text(source, encoding="utf-8")


def instrument_background_app(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if "#include <cstdlib>" not in source:
        source = source.replace("#import <Cocoa/Cocoa.h>\n", "#import <Cocoa/Cocoa.h>\n\n#include <cstdlib>\n")
    marker = "    // VIBEEDIT_CEF_BACKGROUND_APP\n"
    needle = "    // Create the application delegate and window.\n"
    if marker not in source:
        if source.count(needle) != 1:
            raise SystemExit("CEF background-app patch no longer applies cleanly")
        source = source.replace(
            needle,
            marker + "    if (std::getenv(\"VIBEEDIT_CEF_BACKGROUND\"))\n      [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];\n\n" + needle,
        )
    source = source.replace("      [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];\n      [NSApp hide:nil];", "      [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];")
    path.write_text(source, encoding="utf-8")


def instrument(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if "#include <dlfcn.h>" not in source:
        source = source.replace("#include <optional>\n", "#include <dlfcn.h>\n#include <optional>\n")
    if "#include <cstdio>" not in source:
        source = source.replace("#include <optional>\n", "#include <cstdio>\n#include <cstdlib>\n#include <optional>\n")
    scheduler_marker = "// VIBEEDIT_CEF_DETERMINISTIC_SCHEDULER\n"
    scheduler_needle = "class ScopedGLContext {\n"
    if scheduler_marker not in source:
        scheduler = scheduler_marker + "int vibeedit_requested_frame = -1;\n\nvoid VibeEditBeginFrame(CefRefPtr<CefBrowser> browser) {\n  CEF_REQUIRE_UI_THREAD();\n  browser->GetHost()->SendExternalBeginFrame();\n}\n\nvoid VibeEditRequestFrame(CefRefPtr<CefBrowser> browser, int frame, int fps) {\n  CEF_REQUIRE_UI_THREAD();\n  vibeedit_requested_frame = frame;\n  const double seconds = static_cast<double>(frame) / static_cast<double>(fps);\n  const std::string script = \"globalThis.vibeedit?.seek(\" + std::to_string(seconds) + \")\";\n  browser->GetMainFrame()->ExecuteJavaScript(script, browser->GetMainFrame()->GetURL(), 0);\n  const int render_budget_ms = fps > 0 && 1000 / fps > 0 ? 1000 / fps : 1;\n  CefPostDelayedTask(TID_UI, base::BindOnce(&VibeEditBeginFrame, browser), render_budget_ms);\n  LOG(INFO) << \"VIBEEDIT_CEF_FRAME_REQUEST frame=\" << frame << \" time=\" << seconds;\n}\n\n" + scheduler_needle
        if source.count(scheduler_needle) != 1:
            raise SystemExit("CEF deterministic scheduler patch no longer applies cleanly")
        source = source.replace(scheduler_needle, scheduler)
    if scheduler_marker in source and "render_budget_ms" not in source:
        source = source.replace(
            "  CefPostDelayedTask(TID_UI, base::BindOnce(&VibeEditBeginFrame, browser), 8);",
            "  const int render_budget_ms = fps > 0 && 1000 / fps > 0 ? 1000 / fps : 1;\n  CefPostDelayedTask(TID_UI, base::BindOnce(&VibeEditBeginFrame, browser), render_budget_ms);",
        )
    after_created_marker = "  // VIBEEDIT_CEF_DETERMINISTIC_START\n"
    after_created_needle = "void BrowserWindowOsrMacImpl::OnAfterCreated(CefRefPtr<CefBrowser> browser) {\n  CEF_REQUIRE_UI_THREAD();\n"
    if after_created_marker not in source:
        after_created = after_created_needle + after_created_marker + "  // VIBEEDIT_CEF_RUST_PREPARE\n  if (const char* bridge = std::getenv(\"VIBEEDIT_RUST_BRIDGE\")) {\n    if (void* library = dlopen(bridge, RTLD_NOW | RTLD_LOCAL)) {\n      using VibeEditPrepareGpu = int (*)();\n      if (auto prepare = reinterpret_cast<VibeEditPrepareGpu>(dlsym(library, \"vibeedit_rust_prepare_gpu\"))) {\n        LOG(INFO) << \"VIBEEDIT_CEF_RUST_PREPARED ready=\" << prepare();\n      }\n    }\n  }\n  if (const char* frames = std::getenv(\"VIBEEDIT_CEF_DETERMINISTIC_FRAMES\")) {\n    const char* fps_value = std::getenv(\"VIBEEDIT_CEF_DETERMINISTIC_FPS\");\n    const int fps = fps_value ? std::atoi(fps_value) : 30;\n    if (std::atoi(frames) > 0) CefPostDelayedTask(TID_UI, base::BindOnce(&VibeEditRequestFrame, browser, 0, fps), 1000);\n  }\n"
        if source.count(after_created_needle) != 1:
            raise SystemExit("CEF deterministic start patch no longer applies cleanly")
        source = source.replace(after_created_needle, after_created)
    if after_created_marker in source and "VIBEEDIT_CEF_RUST_PREPARE" not in source:
        source = source.replace(
            after_created_marker,
            after_created_marker + "  // VIBEEDIT_CEF_RUST_PREPARE\n  if (const char* bridge = std::getenv(\"VIBEEDIT_RUST_BRIDGE\")) {\n    if (void* library = dlopen(bridge, RTLD_NOW | RTLD_LOCAL)) {\n      using VibeEditPrepareGpu = int (*)();\n      if (auto prepare = reinterpret_cast<VibeEditPrepareGpu>(dlsym(library, \"vibeedit_rust_prepare_gpu\"))) {\n        LOG(INFO) << \"VIBEEDIT_CEF_RUST_PREPARED ready=\" << prepare();\n      }\n    }\n  }\n",
        )
    if MARKER in source and "<= 120" not in source:
        source = source.replace("<= 8", "<= 120")
    if MARKER in source and "requested_frame=" not in source:
        source = source.replace(
            '              << vibeedit_accelerated_paint_count << " width=" << width\n              << " height=" << height << " io_surface=" << io_surface;',
            '              << vibeedit_accelerated_paint_count << " requested_frame="\n              << vibeedit_requested_frame << " width=" << width\n              << " height=" << height << " io_surface=" << io_surface;',
        )
    if MARKER not in source:
        needle = "  GLsizei height = (GLsizei)IOSurfaceGetHeight(io_surface);\n"
        insertion = needle + "\n  static int vibeedit_accelerated_paint_count = 0;\n  if (++vibeedit_accelerated_paint_count <= 120) {\n    LOG(INFO) << \"VIBEEDIT_CEF_ACCELERATED_PAINT frame=\"\n              << vibeedit_accelerated_paint_count << \" requested_frame=\"\n              << vibeedit_requested_frame << \" width=\" << width\n              << \" height=\" << height << \" io_surface=\" << io_surface;\n  }\n"
        if source.count(needle) != 1:
            raise SystemExit("CEF accelerated-paint probe patch no longer applies cleanly")
        source = source.replace(needle, insertion)
    raw_marker = "  // VIBEEDIT_CEF_RAW_CAPTURE\n"
    needle = "  CGLTexImageIOSurface2D(cgl_context, GL_TEXTURE_RECTANGLE_ARB, GL_RGBA8, width,\n"
    if raw_marker not in source:
        if source.count(needle) != 1:
            raise SystemExit("CEF raw-capture probe patch no longer applies cleanly")
        source = source.replace(needle, raw_marker + needle)
    raw_start = source.find(raw_marker)
    raw_end = source.find(needle, raw_start)
    if raw_start < 0 or raw_end < 0:
        raise SystemExit("CEF raw-capture probe patch no longer applies cleanly")
    insertion = raw_marker + "  const char* vibeedit_raw_output = std::getenv(\"VIBEEDIT_CEF_RAW_OUTPUT\");\n  const char* vibeedit_raw_frames_value = std::getenv(\"VIBEEDIT_CEF_RAW_FRAMES\");\n  const int vibeedit_raw_frames = vibeedit_raw_frames_value ? std::atoi(vibeedit_raw_frames_value) : 0;\n  if (vibeedit_raw_output && vibeedit_accelerated_paint_count <= vibeedit_raw_frames) {\n    uint32_t seed = 0;\n    if (IOSurfaceLock(io_surface, kIOSurfaceLockReadOnly, &seed) == 0) {\n      const auto* bytes = static_cast<const uint8_t*>(IOSurfaceGetBaseAddress(io_surface));\n      const size_t stride = IOSurfaceGetBytesPerRow(io_surface);\n      using VibeEditSubmitFrame = int (*)(const uint8_t*, size_t, size_t, size_t);\n      static bool vibeedit_rust_initialized = false;\n      static VibeEditSubmitFrame vibeedit_rust_submit = nullptr;\n      if (!vibeedit_rust_initialized) {\n        vibeedit_rust_initialized = true;\n        if (const char* bridge = std::getenv(\"VIBEEDIT_RUST_BRIDGE\")) {\n          if (void* library = dlopen(bridge, RTLD_NOW | RTLD_LOCAL)) {\n            vibeedit_rust_submit = reinterpret_cast<VibeEditSubmitFrame>(dlsym(library, \"vibeedit_rust_submit_frame\"));\n          }\n        }\n        LOG(INFO) << \"VIBEEDIT_CEF_RUST_BRIDGE loaded=\" << (vibeedit_rust_submit != nullptr);\n      }\n      if (vibeedit_rust_submit) {\n        vibeedit_rust_submit(bytes, stride, static_cast<size_t>(width), static_cast<size_t>(height));\n      } else {\n        static FILE* vibeedit_raw_file = std::fopen(vibeedit_raw_output, \"ab\");\n        if (vibeedit_raw_file) {\n          for (GLsizei row = 0; row < height; ++row) {\n            std::fwrite(bytes + row * stride, 1, static_cast<size_t>(width) * 4, vibeedit_raw_file);\n          }\n          std::fflush(vibeedit_raw_file);\n        }\n      }\n      IOSurfaceUnlock(io_surface, kIOSurfaceLockReadOnly, &seed);\n    }\n  }\n\n"
    gpu = raw_marker + "  const char* vibeedit_gpu_frames_value = std::getenv(\"VIBEEDIT_CEF_GPU_FRAMES\");\n  const int vibeedit_gpu_frames = vibeedit_gpu_frames_value ? std::atoi(vibeedit_gpu_frames_value) : 0;\n  if (vibeedit_gpu_frames > 0 && vibeedit_accelerated_paint_count <= vibeedit_gpu_frames) {\n    using VibeEditSubmitSurface = int (*)(void*, size_t, size_t);\n    static bool vibeedit_gpu_initialized = false;\n    static VibeEditSubmitSurface vibeedit_gpu_submit = nullptr;\n    if (!vibeedit_gpu_initialized) {\n      vibeedit_gpu_initialized = true;\n      if (const char* bridge = std::getenv(\"VIBEEDIT_RUST_BRIDGE\")) {\n        if (void* library = dlopen(bridge, RTLD_NOW | RTLD_LOCAL)) {\n          vibeedit_gpu_submit = reinterpret_cast<VibeEditSubmitSurface>(dlsym(library, \"vibeedit_rust_submit_surface\"));\n        }\n      }\n      LOG(INFO) << \"VIBEEDIT_CEF_RUST_GPU loaded=\" << (vibeedit_gpu_submit != nullptr);\n    }\n    if (vibeedit_gpu_submit) vibeedit_gpu_submit(io_surface, static_cast<size_t>(width), static_cast<size_t>(height));\n  }\n\n"
    insertion = gpu + insertion.removeprefix(raw_marker)
    source = source[:raw_start] + insertion + source[raw_end:]
    advance_marker = "  // VIBEEDIT_CEF_DETERMINISTIC_ADVANCE\n"
    advance_needle = "  renderer_.OnAcceleratedPaint(browser, type, dirtyRects, rectTexture, width,\n                               height);\n  renderer_.Render();\n"
    if advance_marker not in source:
        advance = "  renderer_.OnAcceleratedPaint(browser, type, dirtyRects, rectTexture, width,\n                               height);\n  if (!std::getenv(\"VIBEEDIT_CEF_HEADLESS_CAPTURE\")) renderer_.Render();\n" + advance_marker + "  if (const char* frames_value = std::getenv(\"VIBEEDIT_CEF_DETERMINISTIC_FRAMES\")) {\n    const int frames = std::atoi(frames_value);\n    const char* fps_value = std::getenv(\"VIBEEDIT_CEF_DETERMINISTIC_FPS\");\n    const int fps = fps_value ? std::atoi(fps_value) : 30;\n    if (vibeedit_requested_frame >= 0 && vibeedit_requested_frame + 1 < frames) {\n      CefPostDelayedTask(TID_UI, base::BindOnce(&VibeEditRequestFrame, browser, vibeedit_requested_frame + 1, fps), 1);\n    }\n  }\n"
        if source.count(advance_needle) != 1:
            raise SystemExit("CEF deterministic advance patch no longer applies cleanly")
        source = source.replace(advance_needle, advance)
    if advance_marker in source and "VIBEEDIT_CEF_HEADLESS_CAPTURE" not in source:
        source = source.replace("  renderer_.Render();\n" + advance_marker, "  if (!std::getenv(\"VIBEEDIT_CEF_HEADLESS_CAPTURE\")) renderer_.Render();\n" + advance_marker)
    if advance_marker in source and "vibeedit_frame_delay" in source:
        source = source.replace(
            "      const int vibeedit_frame_delay = fps > 0 && 1000 / fps > 8 ? 1000 / fps - 8 : 1;\n      CefPostDelayedTask(TID_UI, base::BindOnce(&VibeEditRequestFrame, browser, vibeedit_requested_frame + 1, fps), vibeedit_frame_delay);",
            "      CefPostDelayedTask(TID_UI, base::BindOnce(&VibeEditRequestFrame, browser, vibeedit_requested_frame + 1, fps), 1);",
        )
    viewport_marker = "  // VIBEEDIT_CEF_FIXED_VIEWPORT\n"
    if viewport_marker not in source:
        needle = "  REQUIRE_MAIN_THREAD();\n\n  // Keep (0,0) origin for proper layout on macOS.\n"
        if source.count(needle) != 1:
            raise SystemExit("CEF viewport probe patch no longer applies cleanly")
        source = source.replace(needle, "  REQUIRE_MAIN_THREAD();\n\n" + viewport_marker + "  // Keep (0,0) origin for proper layout on macOS.\n")
    viewport_start = source.find(viewport_marker)
    viewport_end = source.find("  // Keep (0,0) origin for proper layout on macOS.\n", viewport_start)
    if viewport_start < 0 or viewport_end < 0:
        raise SystemExit("CEF viewport probe patch no longer applies cleanly")
    viewport = viewport_marker + "  const char* vibeedit_width = std::getenv(\"VIBEEDIT_CEF_WIDTH\");\n  const char* vibeedit_height = std::getenv(\"VIBEEDIT_CEF_HEIGHT\");\n  rect = CefRect(0, 0, vibeedit_width ? std::atoi(vibeedit_width) : 640,\n                 vibeedit_height ? std::atoi(vibeedit_height) : 360);\n  return;\n\n"
    source = source[:viewport_start] + viewport + source[viewport_end:]
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


def terminate_process_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    for current_signal, timeout in ((signal.SIGINT, 3), (signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        try:
            os.killpg(process.pid, current_signal)
            process.wait(timeout=timeout)
            return
        except PermissionError:
            try:
                process.send_signal(current_signal)
                process.wait(timeout=timeout)
                return
            except ProcessLookupError:
                return
            except subprocess.TimeoutExpired:
                continue
        except ProcessLookupError:
            return
        except subprocess.TimeoutExpired:
            continue


def parse_values(line: str) -> dict[str, int]:
    return {key: int(value) for part in line.split() if "=" in part for key, value in [part.split("=", 1)] if value.isdigit()}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_rust_stats(values: dict[str, int]) -> dict[str, int | float]:
    frames = values["frames"]
    return {
        "frames": frames,
        "averageCopyMilliseconds": round(values["copy_nanos"] / frames / 1_000_000, 3),
        "averageQueueWaitMilliseconds": round(values["queue_wait_nanos"] / frames / 1_000_000, 3),
        "allocatedBuffers": values["allocated_buffers"],
    }


def normalize_gpu_stats(values: dict[str, int]) -> dict[str, int | float]:
    submitted = values["submitted"]
    return {
        "submittedFrames": submitted,
        "completedWhenReported": values["completed"],
        "averageSubmitMilliseconds": round(values["submit_nanos"] / submitted / 1_000_000, 3),
        "cpuReadback": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
