"""Ordinary browser-project rendering. CEF stays warm across serial jobs.

No CompositionSpec, presets, or creative schema is needed. The manifest only
describes execution. Native capture is opt-in until the qualification gates pass.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import http.server
import json
import os
import platform
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from collections import deque
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

from vibeedit.data import package_root
from vibeedit.browser_setup import native_paths

ROOT = package_root()
HOST, BRIDGE = native_paths()
ADAPTER = Path(__file__).with_name("browser_frame.js").read_text()
IMPLEMENTATION_SHA = hashlib.sha256(
    Path(__file__).read_bytes()
    + Path(__file__).with_name("browser_media.py").read_bytes()
).hexdigest()


class BrowserRenderError(RuntimeError):
    pass


class CEFService:
    def __init__(self, executable: Path = HOST, *, timeout: float = 30):
        if sys.platform != "darwin" or not executable.is_file():
            raise BrowserRenderError(
                "CEF host unavailable; run vibeedit setup --cef or choose screenshot fallback"
            )
        if int(platform.mac_ver()[0].split(".")[0]) < 15:
            raise BrowserRenderError(
                "Native sRGB VideoToolbox export requires macOS 15 or newer; use screenshot fallback"
            )
        import fcntl

        self.timeout = timeout
        self.executable = executable
        self.host_sha = _sha256(executable)
        self.bridge_sha = None
        self.closed = False
        self.job_lock = threading.RLock()
        # Conservative process admission replaces the prototype's unsafe four-
        # process fanout. A warm service retains its slot until explicitly closed.
        self.admission = (Path("/private/var/tmp") / "vibeedit-cef-render.lock").open(
            "a"
        )
        admitted = time.monotonic() + 120
        while True:
            try:
                fcntl.flock(self.admission, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= admitted:
                    self.admission.close()
                    raise BrowserRenderError(
                        "CEF admission deadline exceeded; one service is already rendering"
                    )
                time.sleep(0.05)
        self.cache = Path(
            tempfile.mkdtemp(prefix="vibeedit-browser-", dir="/private/var/tmp")
        )
        self.responses = queue.Queue(maxsize=8)
        self.logs = deque(maxlen=100)
        self.sequence = 0
        try:
            self.process = subprocess.Popen(
                [
                    str(executable),
                    f"--cache-path={self.cache}",
                    "--no-sandbox",
                    "--enable-gpu",
                    "--enable-unsafe-webgpu",
                    "--force-device-scale-factor=1",
                    "--force-color-profile=srgb",
                    "--disable-background-networking",
                    "--disable-component-update",
                    "--disable-sync",
                    "--disable-gpu-vsync",
                    "--use-mock-keychain",
                    "--password-store=basic",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except BaseException:
            shutil.rmtree(self.cache)
            self.admission.close()
            raise
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._log, daemon=True).start()
        try:
            self.capabilities = self._response(0)
            self.version = self.call("Browser.getVersion")
            self.call("Runtime.enable", params={})
            self.call("Page.enable", params={})
            self.call("Network.enable", params={})
        except BaseException:
            self.close()
            raise

    def _read(self):
        for line in self.process.stdout:
            if line.startswith("{"):
                self.responses.put(json.loads(line))

    def _log(self):
        for line in self.process.stderr:
            self.logs.append(line.strip())

    def _response(self, expected: int):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise BrowserRenderError(
                    f"CEF exited ({self.process.returncode}): {list(self.logs)[-5:]}"
                )
            try:
                response = self.responses.get(
                    timeout=min(0.1, max(0.001, deadline - time.monotonic()))
                )
            except queue.Empty:
                continue
            if response["id"] != expected:
                raise BrowserRenderError(
                    f"Unexpected CEF reply: {response['id']} != {expected}"
                )
            if response.get("error"):
                raise BrowserRenderError(response["error"])
            result = response.get("result", {})
            if result.get("exceptionDetails"):
                raise BrowserRenderError(json.dumps(result["exceptionDetails"]))
            return result
        raise BrowserRenderError(
            f"CEF command {expected} exceeded {self.timeout}s: {list(self.logs)[-8:]}"
        )

    def call(self, method: str, **values):
        self.sequence += 1
        self.process.stdin.write(
            json.dumps({"id": self.sequence, "method": method, **values}) + "\n"
        )
        self.process.stdin.flush()
        return self._response(self.sequence)

    def evaluate(self, expression: str):
        return self.call(
            "Runtime.evaluate",
            params={
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )

    def close(self):
        if getattr(self, "closed", False):
            return
        self.closed = True
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._signal(signal.SIGTERM)
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._signal(signal.SIGKILL)
                    self.process.wait(timeout=5)
        # Children can outlive an already-exited host; reap its owned group too.
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        shutil.rmtree(self.cache)
        self.admission.close()

    def _signal(self, current_signal):
        try:
            os.killpg(self.process.pid, current_signal)
        except PermissionError:
            self.process.send_signal(current_signal)
        except ProcessLookupError:
            return

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class ScreenshotService:
    """Portable existing Chromium-reference fallback; never a native capability claim."""

    def __init__(self, *, timeout=30):
        self.timeout = timeout
        self.closed = False
        self.job_lock = threading.RLock()
        self.errors = []
        self.trace = {"complete": False, "events": {}}
        self.origin = "about:blank"
        self.capabilities = {
            "backend": "playwright-screenshot",
            "platformQualified": False,
        }
        # CDP send has no action timeout in Playwright's synchronous API. Keep
        # the async transport on its own loop so every request has a deadline,
        # including a target that disappears without resolving its promise.
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        try:
            self._submit(self._start())
        except BaseException:
            self.close()
            raise

    async def _start(self):
        from playwright.async_api import async_playwright

        self.runtime = await async_playwright().start()
        self.browser = await self.runtime.chromium.launch(
            headless=True,
            timeout=self.timeout * 1000,
            args=["--enable-unsafe-webgpu", "--force-color-profile=srgb"],
        )
        self.page = await self.browser.new_page(device_scale_factor=1)
        self.page.set_default_timeout(self.timeout * 1000)
        self.session = await self.page.context.new_cdp_session(self.page)
        await self.page.route("**/*", self._route)
        self.page.on("pageerror", lambda error: self._error(str(error)))
        self.page.on("response", self._response_error)
        self.page.on("dialog", self._dialog)
        self.page.on("popup", self._popup)
        self.session.on("Tracing.dataCollected", self._trace_data)
        self.session.on(
            "Tracing.tracingComplete", lambda _: self.trace.update(complete=True)
        )

    def _submit(self, operation):
        async def bounded():
            return await asyncio.wait_for(operation, self.timeout)

        future = asyncio.run_coroutine_threadsafe(bounded(), self.loop)
        try:
            return future.result(timeout=self.timeout + 2)
        except TimeoutError as error:
            future.cancel()
            self.close()
            raise BrowserRenderError(
                f"Screenshot browser request exceeded {self.timeout}s"
            ) from error

    def _trace_data(self, event):
        for item in event["value"]:
            if item.get("ph") != "X" or "dur" not in item:
                continue
            name = item["name"]
            if len(self.trace["events"]) >= 256 and name not in self.trace["events"]:
                continue
            current = self.trace["events"].setdefault(
                name, {"durationSeconds": 0.0, "count": 0}
            )
            current["durationSeconds"] += item["dur"] / 1_000_000
            current["count"] += 1

    async def _dialog(self, dialog):
        self._error("Interactive JavaScript dialog unsupported by background renderer")
        await dialog.dismiss()

    async def _popup(self, popup):
        self._error("Popup windows unsupported by background renderer")
        await popup.close()

    def _error(self, message):
        if len(self.errors) < 100:
            self.errors.append(message)

    async def _route(self, route):
        if route.request.url.startswith((self.origin, "data:", "blob:")):
            await route.continue_()
            return
        self._error(f"Unbundled resource blocked: {route.request.url}")
        await route.abort()

    def _response_error(self, response):
        if response.status >= 400 and not response.url.endswith("/favicon.ico"):
            self._error(f"Resource load failed: {response.status} {response.url}")

    def call(self, method, **values):
        if self.closed:
            raise BrowserRenderError("Screenshot service is closed")
        return self._submit(self._call(method, values))

    async def _call(self, method, values):
        if method == "trace.reset":
            self.trace = {"complete": False, "events": {}}
            return {}
        if method == "trace.read":
            return self.trace
        if method == "load":
            self.errors.clear()
            parsed = urllib.parse.urlparse(values["url"])
            self.origin = f"{parsed.scheme}://{parsed.netloc}/"
            await self.page.set_viewport_size(
                {"width": values["width"], "height": values["height"]}
            )
            await self.page.goto(values["url"], wait_until="load")
            return {}
        if method == "diagnostics":
            return {"errors": self.errors[:]}
        return await self.session.send(method, values.get("params", {}))

    def evaluate(self, expression):
        # CDP awaitPromise has no Playwright action timeout. Bound the promise
        # in the page too, clearing the timer for every successful frame.
        bounded = f"(async()=>{{let timer;try{{return await Promise.race([Promise.resolve().then(()=>eval({json.dumps(expression)})),new Promise((_,reject)=>{{timer=setTimeout(()=>reject(new Error('frame readiness deadline exceeded')),{self.timeout * 1000})}})])}}finally{{clearTimeout(timer)}}}})()"
        result = self.call(
            "Runtime.evaluate",
            params={"expression": bounded, "awaitPromise": True, "returnByValue": True},
        )
        if result.get("exceptionDetails"):
            raise BrowserRenderError(json.dumps(result["exceptionDetails"]))
        return result

    def close(self):
        if self.closed:
            return
        self.closed = True

        async def shutdown():
            try:
                if hasattr(self, "browser"):
                    await asyncio.wait_for(self.browser.close(), 5)
            finally:
                if hasattr(self, "runtime"):
                    await asyncio.wait_for(self.runtime.stop(), 5)

        future = asyncio.run_coroutine_threadsafe(shutdown(), self.loop)
        try:
            future.result(timeout=12)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=2)
            if not self.thread.is_alive():
                self.loop.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


@contextmanager
def project_server(
    root: Path,
    *,
    identities=None,
    normalize=False,
    browser_version=None,
    conversions=None,
    prepared_sources=None,
):
    from vibeedit.browser_media import prepare_cef_media

    conversion_lock = threading.Lock()
    preparing = set()
    canceled = threading.Event()
    failures = []
    converted = {}

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def translate_path(self, path):
            result = Path(super().translate_path(path)).resolve()
            return (
                str(result) if result.is_relative_to(root) else str(root / ".forbidden")
            )

        def log_message(self, *_):
            pass

        def send_head(self):
            target = Path(self.translate_path(self.path))
            if not target.is_file():
                self.send_error(404)
                return None
            if identities is not None:
                name = str(target.relative_to(root))
                if name not in identities:
                    identities[name] = _sha256(target)
            if (
                normalize
                and self.headers.get("Sec-Fetch-Dest") == "video"
                and target.suffix.lower()
                in {
                    ".mp4",
                    ".m4v",
                    ".mov",
                    ".mkv",
                    ".avi",
                    ".mts",
                    ".ts",
                    ".mxf",
                }
            ):
                with conversion_lock:
                    if target not in converted:
                        try:
                            result, record = prepare_cef_media(
                                target, browser_version, preparing, canceled
                            )
                        except (
                            BrowserRenderError,
                            OSError,
                            subprocess.SubprocessError,
                        ) as error:
                            failures.append(str(error))
                            self.send_error(422, "Media preparation failed")
                            return None
                        converted[target] = result
                        if prepared_sources is not None:
                            prepared_sources[target] = result
                        if record and conversions is not None:
                            conversions[str(target.relative_to(root))] = record
                    target = converted[target]
            size = target.stat().st_size
            requested = self.headers.get("Range")
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested or "")
            if requested and (not match or not any(match.groups())):
                self.send_error(416)
                return None
            start = (
                (int(match[1]) if match[1] else max(0, size - int(match[2])))
                if match
                else 0
            )
            end = min(
                size - 1, int(match[2]) if match and match[1] and match[2] else size - 1
            )
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return None
            self.send_response(206 if match else 200)
            self.send_header("Content-Type", self.guess_type(str(target)))
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-cache")
            if match:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            stream = target.open("rb")
            stream.seek(start)
            self.remaining = end - start + 1
            return stream

        def copyfile(self, source, outputfile):
            while self.remaining:
                chunk = source.read(min(1024 * 1024, self.remaining))
                if not chunk:
                    return
                outputfile.write(chunk)
                self.remaining -= len(chunk)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
        if failures:
            raise BrowserRenderError(f"Media preparation failed: {failures[:5]}")
    except Exception as error:
        if failures:
            raise BrowserRenderError(f"Media preparation failed: {failures[:5]}") from error
        raise
    finally:
        canceled.set()
        for process in preparing.copy():
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join()


def load_job(path: Path):
    manifest = json.loads(path.read_text())
    root = (path.parent / manifest.get("root", ".")).resolve()
    entry = (root / manifest["entry"]).resolve()
    if not entry.is_file() or not entry.is_relative_to(root):
        raise BrowserRenderError(
            "entry must be an existing HTML file inside the project root"
        )
    rate = manifest.get("frameRate", {"numerator": 30, "denominator": 1})
    fps = Fraction(rate["numerator"], rate["denominator"])
    frames = manifest.get("frames")
    if frames is None:
        duration = Fraction(str(manifest["duration"])) * fps
        if duration.denominator != 1:
            raise BrowserRenderError(
                "duration must resolve to an exact integer frame count; specify frames"
            )
        frames = duration.numerator
    width, height = manifest["width"], manifest["height"]
    if (
        any(type(value) is not int or value < 1 for value in (frames, width, height))
        or fps <= 0
    ):
        raise BrowserRenderError(
            "dimensions, frames, and rational frame rate must be positive"
        )
    if manifest.get("timing", "seek") not in {"seek", "sequential"}:
        raise BrowserRenderError(
            "wall-clock programs need a seek adapter or sequential renderFrame"
        )
    return manifest, root, entry, fps, frames


def render_browser_job(
    path: Path,
    output: Path,
    *,
    backend="screenshot",
    service=None,
    raw: Path | None = None,
    screenshots: Path | None = None,
    cache: Path | None = None,
):
    """Render with an explicit backend, or opt into recovery with backend='auto'.

    A cache is optional and must live outside the authoring root. Every bundled
    dependency and installed font participates; stateful sequential jobs cannot
    reuse exports. Native failures retry once in a fresh screenshot service.
    """
    if backend == "auto":
        try:
            return render_browser_job(
                path,
                output,
                backend="cef",
                service=service,
                raw=raw,
                screenshots=screenshots,
                cache=cache,
            )
        except (BrowserRenderError, OSError) as error:
            with ScreenshotService() as fallback:
                report = render_browser_job(
                    path,
                    output,
                    backend="screenshot",
                    service=fallback,
                    screenshots=screenshots,
                    cache=cache,
                )
            report["fallback"] = {"requestedBackend": "cef", "reason": str(error)}
            output.with_suffix(output.suffix + ".browser.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
            return report
    if cache is None:
        if service is None:
            return _render_browser_job(
                path, output, backend=backend, raw=raw, screenshots=screenshots
            )
        with service.job_lock:
            return _render_browser_job(
                path,
                output,
                backend=backend,
                service=service,
                raw=raw,
                screenshots=screenshots,
            )
    manifest, root, _entry, _fps, _frames = load_job(path)
    if (
        cache.resolve().is_relative_to(root)
        or manifest.get("timing") == "sequential"
        or raw
        or screenshots
    ):
        raise BrowserRenderError(
            "Export cache requires seekable jobs, no QA readback, and a directory outside the project root"
        )
    started = time.perf_counter()
    owned = service is None
    service = service or (CEFService() if HOST.is_file() else ScreenshotService())
    service.job_lock.acquire()
    try:
        fonts = (
            [
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library/Fonts",
            ]
            if sys.platform == "darwin"
            else [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]
            if sys.platform == "win32"
            else [Path("/usr/share/fonts"), Path.home() / ".local/share/fonts"]
        )
        identities = {
            str(file.relative_to(root)): _sha256(file)
            for file in sorted(root.rglob("*"))
            if file.is_file()
            and file.resolve().is_relative_to(root)
            and file.resolve()
            not in {
                output.resolve(),
                output.with_suffix(output.suffix + ".browser.json").resolve(),
            }
        }
        font_identities = {
            str(file): _sha256(file)
            for directory in fonts
            if directory.is_dir()
            for file in sorted(directory.rglob("*"))
            if file.is_file()
        }
        settings = {
            "manifest": manifest,
            "platform": [platform.platform(), platform.version(), platform.machine()],
            "dependencies": identities,
            "fonts": font_identities,
            "browser": service.call("Browser.getVersion"),
            "adapter": hashlib.sha256(ADAPTER.encode()).hexdigest(),
            "implementation": IMPLEMENTATION_SHA,
            "backend": backend,
            "host": _sha256(service.executable)
            if isinstance(service, CEFService)
            else None,
            "bridge": _sha256(BRIDGE) if backend == "cef" else None,
            "ffmpeg": subprocess.check_output(
                ["ffmpeg", "-version"], text=True
            ).splitlines()[0],
            "scale": 1,
            "color": "srgb-transfer-bt709-matrix-limited",
        }
        key = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
        artifact = cache / (key + output.suffix.lower())
        provenance = artifact.with_suffix(".json")
        cached = json.loads(provenance.read_text()) if provenance.is_file() else None
        if artifact.is_file() and cached and _sha256(artifact) == cached["sha256"]:
            output.parent.mkdir(parents=True, exist_ok=True)
            _publish(artifact, output)
            report = {
                **cached,
                "cacheHit": True,
                "output": str(output.resolve()),
                "elapsedSeconds": time.perf_counter() - started,
            }
        else:
            report = _render_browser_job(path, output, backend=backend, service=service)
            # Do not reuse a render if an input changed while it was being read.
            if any(
                not (root / name).is_file() or _sha256(root / name) != digest
                for name, digest in identities.items()
            ):
                raise BrowserRenderError(
                    "Project dependency changed during rendering; result was not cached"
                )
            cache.mkdir(parents=True, exist_ok=True)
            report.update(cacheHit=False, cacheKey=key)
            _publish(output, artifact)
            provenance.write_text(json.dumps(report, indent=2) + "\n")
        output.with_suffix(output.suffix + ".browser.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        return report
    finally:
        service.job_lock.release()
        if owned:
            service.close()


def _write_png(stream, png):
    stream.write(png)
    stream.flush()


def _font_diagnostics(service):
    service.call("DOM.enable", params={})
    service.call("CSS.enable", params={})
    document = service.call("DOM.getDocument", params={"depth": 1})["root"]["nodeId"]
    nodes = service.call(
        "DOM.querySelectorAll", params={"nodeId": document, "selector": "body,body *"}
    )["nodeIds"]
    used = {}
    for node in nodes[:100]:
        for font in service.call(
            "CSS.getPlatformFontsForNode", params={"nodeId": node}
        )["fonts"]:
            name = font["familyName"]
            if "lastresort" in name.replace(" ", "").lower():
                raise BrowserRenderError(f"Missing glyph fallback detected: {name}")
            used[name] = {
                "family": name,
                "custom": font["isCustomFont"],
                "glyphCount": font["glyphCount"],
            }
    return {
        "platformFonts": list(used.values()),
        "nodesExamined": min(100, len(nodes)),
        "truncated": len(nodes) > 100,
        "coverage": "Chromium platform-font usage; LastResort rejected; full codepoint coverage not proven",
    }


def _publish(source: Path, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent, prefix=".vibeedit-", delete=False
        ) as target:
            staged = Path(target.name)
            with source.open("rb") as stream:
                shutil.copyfileobj(stream, target)
            target.flush()
            os.fsync(target.fileno())
        os.replace(staged, output)
    finally:
        if staged:
            staged.unlink(missing_ok=True)


def _sha256(path: Path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


@contextmanager
def browser_signals():
    """CLI termination enters normal cleanup; never installs handlers in API threads."""

    def cancel(*_):
        raise KeyboardInterrupt("browser export canceled")

    previous = signal.signal(signal.SIGTERM, cancel)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def serve_browser_jobs(
    *, backend="cef", input_stream=sys.stdin, output_stream=sys.stdout
):
    """A bounded JSON-lines worker suitable for agent process orchestration."""
    service = None
    try:
        while line := input_stream.readline(65537):
            request = None
            try:
                if len(line) > 65536:
                    while not line.endswith("\n"):
                        line = input_stream.readline(65537)
                        if not line:
                            break
                    raise BrowserRenderError(
                        "job request exceeds 64 KiB; pass a manifest path"
                    )
                request = json.loads(line)
                if service is None or service.closed:
                    service = (
                        CEFService()
                        if backend == "cef" or HOST.is_file()
                        else ScreenshotService()
                    )
                result = render_browser_job(
                    Path(request["job"]),
                    Path(request["output"]),
                    backend=backend,
                    service=service,
                )
                response = {"id": request.get("id"), "ok": True, "report": result}
            except (BrowserRenderError, OSError, ValueError, KeyError) as error:
                response = {
                    "id": request.get("id") if isinstance(request, dict) else None,
                    "ok": False,
                    "error": str(error),
                }
            output_stream.write(json.dumps(response) + "\n")
            output_stream.flush()
    finally:
        if service:
            service.close()


def _render_browser_job(
    path: Path,
    output: Path,
    *,
    backend="screenshot",
    service: CEFService | ScreenshotService | None = None,
    raw: Path | None = None,
    screenshots: Path | None = None,
):
    started = time.perf_counter()
    manifest, root, entry, fps, frames = load_job(path)
    if backend not in {"cef", "screenshot"}:
        raise BrowserRenderError("backend must be cef or screenshot")
    if manifest["width"] % 2 or manifest["height"] % 2:
        raise BrowserRenderError("H.264 4:2:0 export requires even dimensions")
    settings = manifest.get("export", {})
    unsupported = set(settings) - {"codec", "alpha", "bitrate", "color"}
    if unsupported or settings.get("color", "bt709") != "bt709":
        raise BrowserRenderError(
            f"Unsupported export settings: {settings}; only SDR BT.709 is qualified"
        )
    if "bitrate" in settings and (
        type(settings["bitrate"]) is not int
        or not 1 <= settings["bitrate"] <= 2147483647
    ):
        raise BrowserRenderError("bitrate must be a positive 32-bit integer")
    if type(settings.get("alpha", False)) is not bool:
        raise BrowserRenderError("alpha must be an explicit boolean")
    codec = settings.get("codec", "h264")
    alpha = settings.get("alpha", False)
    if codec not in {"h264", "vp9"} or (alpha and codec != "vp9"):
        raise BrowserRenderError(
            "supported exports: opaque H.264/MP4, or explicit VP9/WebM alpha via screenshot fallback"
        )
    if backend == "cef" and codec != "h264":
        raise BrowserRenderError(
            "accelerated encoder currently supports opaque H.264; choose screenshot for VP9/alpha"
        )
    if output.suffix.lower() != (".mp4" if codec == "h264" else ".webm"):
        raise BrowserRenderError(
            "output extension must match the export codec (.mp4 for H.264, .webm for VP9)"
        )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    timings = {"seek": 0.0, "captureEncode": 0.0, "mux": 0.0}
    prepared = time.perf_counter()
    dependencies = {}
    audio_verification = None
    browser_profile = None
    source_hints = []
    conversions = {}
    prepared_sources = {}
    owned_service = service is None
    service = service or (CEFService() if HOST.is_file() else ScreenshotService())
    if backend == "cef" and isinstance(service, ScreenshotService):
        service.close()
        raise BrowserRenderError(
            "CEF accelerated capability unavailable; choose the explicit screenshot fallback"
        )
    try:
        normalize = False
        if isinstance(service, CEFService):
            service.call(
                "load",
                width=manifest["width"],
                height=manifest["height"],
                url="about:blank",
            )
            normalize = not bool(
                service.evaluate(
                    "document.createElement('video').canPlayType('video/mp4; codecs=\"avc1.42E01E\"')"
                )["result"]["value"]
            )
        with (
            project_server(
                root,
                identities=dependencies,
                normalize=normalize,
                browser_version=service.call("Browser.getVersion"),
                conversions=conversions,
                prepared_sources=prepared_sources,
            ) as url,
            tempfile.TemporaryDirectory(prefix="vibeedit-export-") as scratch,
        ):
            scratch = Path(scratch)
            from vibeedit.browser_media import SOURCE_HINT_ADAPTER

            hint_script = (
                service.call(
                    "Page.addScriptToEvaluateOnNewDocument",
                    params={"source": SOURCE_HINT_ADAPTER},
                )["identifier"]
                if normalize
                else None
            )
            # Previous jobs may remain in Chromium's back/forward cache even
            # after their history entries are removed. Evict them at the boundary.
            service.call(
                "Memory.simulatePressureNotification", params={"level": "critical"}
            )
            try:
                service.call(
                    "load",
                    width=manifest["width"],
                    height=manifest["height"],
                    url=url + urllib.parse.quote(entry.relative_to(root).as_posix()),
                )
            finally:
                if hint_script and service.process.poll() is None:
                    service.call(
                        "Page.removeScriptToEvaluateOnNewDocument",
                        params={"identifier": hint_script},
                    )
            # Each job begins with its own document history.
            service.call("Page.resetNavigationHistory")
            service.call(
                "Emulation.setDefaultBackgroundColorOverride",
                params={"color": {"r": 0, "g": 0, "b": 0, "a": 0}},
            )
            if manifest.get("profile", False):
                service.call("trace.reset")
                service.call(
                    "Tracing.start",
                    params={
                        "categories": "devtools.timeline,blink,cc,media,gpu",
                        "options": "record-continuously",
                        "transferMode": "ReportEvents",
                    },
                )
            if normalize:
                service.evaluate(SOURCE_HINT_ADAPTER)
                service.evaluate("__veNormalizeSourceHints()")
            service.evaluate(ADAPTER)
            service.evaluate("document.fonts.ready")
            service.evaluate("""Promise.all([...document.querySelectorAll('video')].filter(video => video.dataset.vibeeditTiming !== 'manual').map(video => {
              if (video.error) throw new Error(`Media decode failed: ${video.error.message}`);
              if (video.readyState >= 1) return;
              return new Promise((resolve, reject) => {
                video.addEventListener('loadedmetadata', resolve, {once:true});
                video.addEventListener('error', () => reject(new Error(`Media metadata failed: ${video.error?.message}`)), {once:true});
              });
            }))""")
            font_diagnostics = _font_diagnostics(service)
            videos = service.evaluate(
                "[...document.querySelectorAll('video')].filter(video => video.dataset.vibeeditTiming !== 'manual').map(video => video.currentSrc || video.src)"
            )["result"]["value"]
            media_timeline = {}
            for source in set(videos):
                parsed = urllib.parse.urlparse(source)
                local = (root / urllib.parse.unquote(parsed.path).lstrip("/")).resolve()
                if (
                    not source.startswith(url)
                    or not local.is_relative_to(root)
                    or not local.is_file()
                ):
                    raise BrowserRenderError(
                        f"Automatic video timing requires local media: {source}"
                    )
                local = prepared_sources.get(local, local)
                inspected = json.loads(
                    subprocess.check_output(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            "-select_streams",
                            "v:0",
                            "-show_frames",
                            "-show_streams",
                            "-show_entries",
                            "frame=best_effort_timestamp:stream=time_base",
                            "-of",
                            "json",
                            str(local),
                        ],
                        timeout=120,
                    )
                )
                timestamps = [
                    float(
                        int(frame["best_effort_timestamp"])
                        * Fraction(inspected["streams"][0]["time_base"])
                    )
                    for frame in inspected["frames"]
                ]
                if not timestamps:
                    raise BrowserRenderError(f"No decoded video frames: {source}")
                if abs(timestamps[0]) > 0.000001:
                    raise BrowserRenderError(
                        f"Nonzero source start PTS needs explicit zero-based preparation or manual timing: {source}"
                    )
                media_timeline[source] = [
                    timestamp - timestamps[0] for timestamp in timestamps
                ]
            service.evaluate(
                f"globalThis.__veMediaTimeline = {json.dumps(media_timeline)}"
            )
            diagnostics = service.call("diagnostics")
            if diagnostics["errors"]:
                raise BrowserRenderError(
                    f"Project resource/runtime failure: {diagnostics['errors']}"
                )
            browser_version = service.call("Browser.getVersion")
            if isinstance(service, CEFService):
                # CDP forces the initial compositor submission for static pages;
                # CEF Invalidate alone can refresh the old blank cached surface.
                # Discard this startup readback; output frames use only the GPU path.
                service.call(
                    "Page.captureScreenshot",
                    params={
                        "format": "png",
                        "fromSurface": True,
                        "captureBeyondViewport": False,
                    },
                )
            timings["preparation"] = time.perf_counter() - prepared
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
            movie = scratch / (
                "video.mov"
                if backend == "cef"
                else "video.mp4"
                if codec == "h264"
                else "video.webm"
            )
            if backend == "cef":
                if _sha256(service.executable) != service.host_sha:
                    raise BrowserRenderError(
                        "Native host changed; restart the warm service"
                    )
                bridge_sha = _sha256(BRIDGE)
                if service.bridge_sha is not None and bridge_sha != service.bridge_sha:
                    raise BrowserRenderError(
                        "Native bridge changed; restart the warm service"
                    )
                service.call(
                    "begin",
                    bridge=str(BRIDGE),
                    output=str(movie),
                    raw=str(raw.resolve()) if raw else "",
                    numerator=fps.numerator,
                    denominator=fps.denominator,
                    bitrate=manifest.get("export", {}).get(
                        "bitrate",
                        max(2_000_000, manifest["width"] * manifest["height"] * 8),
                    ),
                )
                service.bridge_sha = bridge_sha
            encoder = None
            writer = None
            if backend == "screenshot":
                from concurrent.futures import ThreadPoolExecutor

                writer = ThreadPoolExecutor(max_workers=1)
                options = (
                    [
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                    ]
                    if codec == "h264"
                    else [
                        "-c:v",
                        "libvpx-vp9",
                        "-b:v",
                        "0",
                        "-crf",
                        "18",
                        "-auto-alt-ref",
                        "0",
                        "-pix_fmt",
                        "yuva420p" if alpha else "yuv420p",
                    ]
                )
                if "bitrate" in settings:
                    if "-crf" in options:
                        index = options.index("-crf")
                        del options[index : index + 2]
                    if "-b:v" in options:
                        options[options.index("-b:v") + 1] = str(settings["bitrate"])
                    else:
                        options += ["-b:v", str(settings["bitrate"])]
                encoder = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-y",
                        "-f",
                        "image2pipe",
                        "-framerate",
                        str(fps),
                        "-i",
                        "pipe:0",
                        "-frames:v",
                        str(frames),
                        *options,
                        "-vf",
                        (
                            "premultiply=inplace=1,scale=out_color_matrix=bt709"
                            if not alpha
                            else "scale=out_color_matrix=bt709"
                        ),
                        "-colorspace",
                        "bt709",
                        "-color_primaries",
                        "bt709",
                        "-color_trc",
                        "iec61966-2-1",
                        str(movie),
                    ],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
            try:
                for frame in range(frames):
                    before = time.perf_counter()
                    context = {
                        "frame": frame,
                        "time": float(Fraction(frame, 1) / fps),
                        "fps": float(fps),
                        "durationFrames": frames,
                        "absoluteFrame": frame,
                        "progress": frame / max(1, frames - 1),
                    }
                    ready = service.evaluate(f"__veRenderFrame({json.dumps(context)})")[
                        "result"
                    ].get("value", {})
                    for key, value in ready.get("metrics", {}).items():
                        timings[key] = timings.get(key, 0.0) + value
                    timings["seek"] += time.perf_counter() - before
                    before = time.perf_counter()
                    if backend == "cef":
                        native = service.call("frame", frame=frame)
                        for key in (
                            "gpuTransferConversionSeconds",
                            "nativeWaitSeconds",
                            "encoderAppendSeconds",
                        ):
                            timings[key] = timings.get(key, 0.0) + native.get(key, 0.0)
                    if backend == "screenshot" and isinstance(service, CEFService):
                        service.call("settle", frame=frame)
                    if backend == "screenshot" or screenshots:
                        png = base64.b64decode(
                            service.call(
                                "Page.captureScreenshot",
                                params={
                                    "format": "png",
                                    "fromSurface": True,
                                    "captureBeyondViewport": False,
                                    "optimizeForSpeed": True,
                                },
                            )["data"]
                        )
                        if screenshots:
                            (screenshots / f"{frame:06d}.png").write_bytes(png)
                        if encoder:
                            try:
                                writer.submit(encoder.stdin.write, png).result(
                                    timeout=30
                                )
                            except TimeoutError as error:
                                raise BrowserRenderError(
                                    "Screenshot encoding frame exceeded 30s"
                                ) from error
                    timings["captureEncode"] += time.perf_counter() - before
                if backend == "cef":
                    timings["encoderFlushSeconds"] = service.call("finish").get(
                        "encoderFlushSeconds", 0.0
                    )
                if encoder:
                    encoder.stdin.close()
                    if encoder.wait(timeout=60):
                        raise BrowserRenderError("screenshot encoder failed")
                font_diagnostics = _font_diagnostics(service)
                diagnostics = service.call("diagnostics")
                if diagnostics["errors"]:
                    raise BrowserRenderError(
                        f"Project resource/runtime failure: {diagnostics['errors']}"
                    )
            finally:
                if encoder and encoder.poll() is None:
                    encoder.kill()
                    encoder.wait()
                if writer:
                    writer.shutdown(wait=True)
            source_hints = (
                service.evaluate("globalThis.__veSourceHints || []")["result"]["value"]
                if normalize
                else []
            )
            if manifest.get("profile", False):
                service.call("Tracing.end")
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    service.call("Runtime.evaluate", params={"expression": "0"})
                    browser_profile = service.call("trace.read")
                    if browser_profile["complete"]:
                        break
                    time.sleep(0.01)
                if not browser_profile["complete"]:
                    raise BrowserRenderError(
                        "Browser tracing completion deadline exceeded"
                    )
            before = time.perf_counter()
            command = ["ffmpeg", "-v", "error", "-y", "-i", str(movie)]
            audio = manifest.get("audio", [])
            for item in audio:
                source = (root / item["path"]).resolve()
                if not source.is_relative_to(root) or not source.is_file():
                    raise BrowserRenderError("audio must be a local project asset")
                dependencies[str(source.relative_to(root))] = _sha256(source)
                command += ["-i", str(source)]
            command += ["-map", "0:v:0", "-c:v", "copy"]
            if audio:
                samples = round(Fraction(frames * 48000, 1) / fps)
                filters = [
                    f"[{index + 1}:a]atrim=start={item.get('sourceStart', 0)},asetpts=PTS-STARTPTS,"
                    f"aresample=48000,volume={item.get('volume', 1)},adelay={round(Fraction(str(item.get('start', 0))) * 48000)}S:all=1[a{index}]"
                    for index, item in enumerate(audio)
                ]
                filters += [
                    "".join(f"[a{index}]" for index in range(len(audio)))
                    + f"amix=inputs={len(audio)}:normalize=0,apad,atrim=end_sample={samples}[audio]"
                ]
                command += [
                    "-filter_complex",
                    ";".join(filters),
                    "-map",
                    "[audio]",
                    "-c:a",
                    "aac" if codec == "h264" else "libopus",
                    "-ar",
                    "48000",
                    "-b:a",
                    "192k",
                ]
            final = scratch / ("final.mp4" if codec == "h264" else "final.webm")
            command += (
                [
                    "-movflags",
                    "+faststart",
                    "-movie_timescale",
                    str(fps.numerator),
                    str(final),
                ]
                if codec == "h264"
                else [str(final)]
            )
            subprocess.run(command, check=True, timeout=120)
            verification = json.loads(
                subprocess.check_output(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-count_frames",
                        "-show_streams",
                        "-of",
                        "json",
                        str(final),
                    ],
                    timeout=120,
                )
            )
            video = next(
                stream
                for stream in verification["streams"]
                if stream["codec_type"] == "video"
            )
            if (
                int(video["nb_read_frames"]) != frames
                or Fraction(video["avg_frame_rate"]) != fps
            ):
                raise BrowserRenderError(
                    "encoded frame count/rate did not match the job"
                )
            if audio and not any(
                stream["codec_type"] == "audio" for stream in verification["streams"]
            ):
                raise BrowserRenderError("requested audio is absent")
            if audio and codec == "h264":
                packets = json.loads(
                    subprocess.check_output(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            "-select_streams",
                            "a:0",
                            "-show_packets",
                            "-show_entries",
                            "packet=pts,duration",
                            "-of",
                            "json",
                            str(final),
                        ],
                        timeout=120,
                    )
                )["packets"]
                clean_samples = sum(
                    max(0, int(packet["pts"]) + int(packet["duration"]))
                    - max(0, int(packet["pts"]))
                    for packet in packets
                )
                audio_verification = {
                    "requestedSamples": samples,
                    "packetSamples": clean_samples,
                    "roundingDriftSamples": clean_samples - samples,
                    "toleranceSamples": 1,
                    "sampleRate": 48000,
                }
                # AAC edit-list/container rounding differs by one sample across FFmpeg builds.
                if abs(clean_samples - samples) > 1:
                    raise BrowserRenderError(
                        f"audio sample count drift: {clean_samples} != {samples}"
                    )
            # Publish only a completed and independently probed export.
            if any(
                not (root / name).is_file() or _sha256(root / name) != digest
                for name, digest in dependencies.items()
            ):
                raise BrowserRenderError("Project dependency changed during rendering")
            _publish(final, output)
            timings["mux"] = time.perf_counter() - before
    except BaseException:
        # A stalled/device-lost host cannot be reused. No partial result is published.
        service.close()
        raise
    finally:
        if owned_service and not service.closed:
            service.close()
    elapsed = time.perf_counter() - started
    report = {
        "backend": backend,
        "browser": browser_version,
        "platform": [platform.platform(), platform.version(), platform.machine()],
        "mediaTiming": "Exact decoded source PTS; repeated source frames are retained; requested times are supplied in context.media",
        "frames": frames,
        "dimensions": [manifest["width"], manifest["height"]],
        "bootstrapReadbackPixels": manifest["width"] * manifest["height"]
        if isinstance(service, CEFService)
        else 0,
        "frameRate": str(fps),
        "export": {
            "codec": codec,
            "alpha": alpha,
            "color": {
                "primaries": "bt709",
                "transfer": "iec61966-2-1",
                "matrix": "bt709",
                "range": "limited",
            },
            "bitrate": settings.get(
                "bitrate",
                max(2_000_000, manifest["width"] * manifest["height"] * 8)
                if backend == "cef"
                else None,
            ),
            "nativeHardwareRequired": backend == "cef",
            "matte": None if alpha else "black",
        },
        "audioVerification": audio_verification,
        "mediaConversions": conversions,
        "normalizedSourceTypeHints": source_hints,
        "browserProfile": browser_profile,
        "fontDiagnostics": font_diagnostics,
        "dependencyIdentities": dependencies,
        "hostSha256": service.host_sha if isinstance(service, CEFService) else None,
        "bridgeSha256": service.bridge_sha if backend == "cef" else None,
        "implementationSha256": IMPLEMENTATION_SHA,
        "mediaPreparationSha256": _sha256(Path(__file__).with_name("browser_media.py")),
        "adapterSha256": hashlib.sha256(ADAPTER.encode()).hexdigest(),
        "elapsedSeconds": elapsed,
        "endToEndFps": frames / elapsed,
        "timingsSeconds": timings,
        "output": str(output),
        "sha256": _sha256(output),
    }
    output.with_suffix(output.suffix + ".browser.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Render ordinary bundled HTML/CSS/JS projects"
    )
    parser.add_argument("job", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--backend", choices=("cef", "screenshot", "auto"), default="screenshot"
    )
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            render_browser_job(
                args.job,
                args.output,
                backend=args.backend,
                raw=args.raw,
                screenshots=args.screenshots,
                cache=args.cache,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
