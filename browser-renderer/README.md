# Accelerated Chromium browser projects

This backend accepts ordinary bundled HTML/CSS/JS. Chromium owns typography, video blending, filters, SVG, Canvas and browser graphics. Python/FFmpeg/Blender/Rust tools create assets beforehand. No CompositionSpec or creative DSL is required.

Status: implemented macOS ARM64 fast path; acceptance audit in `REPORT.md`. This is an opt-in backend included in beta.4. The existing SDK render APIs remain available.

## Build and run

Requirements: macOS 15+ ARM64, Python 3.12+, FFmpeg/ffprobe, Xcode command-line tools, CMake/Ninja and Rust. From the SDK checkout:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[browser,effects,test]'
vibeedit setup --cef
.venv/bin/python -m playwright install chromium
.venv/bin/python -m vibeedit render-browser browser-renderer/examples/basic/job.json --output /tmp/basic.mp4 --backend cef --json
```

Setup explicitly downloads the checksum-pinned CEF 144 archive and builds a maintained CEF host plus the recovered Rust/Metal bridge. Renders do not download dependencies. No application window opens. The native binaries are source build artifacts, not distribution packages.

For a real-media project, supply your own footage:

```sh
.venv/bin/python browser-renderer/examples/corpus/prepare.py --footage /absolute/path/footage.mp4 --start 2
.venv/bin/python -m vibeedit render-browser browser-renderer/examples/corpus/job.json --output /tmp/corpus.mp4 --backend cef --json
```

Preparation reports the source hash and explicit VP9/geometry normalization. It generates transparent effects with ordinary Python/Pillow and FFmpeg, WAV audio, a local font and pinned GSAP. The Roboto variable-font example includes its OFL license and pinned source identity.

## Execution manifest

```json
{
  "root": ".",
  "entry": "index.html",
  "width": 1920,
  "height": 1080,
  "frameRate": {"numerator": 30000, "denominator": 1001},
  "frames": 900,
  "timing": "seek",
  "audio": [{"path": "music.wav", "start": 0, "sourceStart": 0, "volume": 0.7}],
  "export": {"codec": "h264", "bitrate": 20000000}
}
```

`duration` can replace `frames` when it resolves to an exact integer frame count. Entry, videos, audio and dependencies must live inside the root. Local modules/framework bundles work normally; bundle remote dependencies during preparation. Missing resources and script failures fail the job. The pinned CEF build lacks H.264 decoding: opaque 8-bit SDR MP4/MOV inputs are converted to cached, lossless-in-decoded-YUV VP9/MP4 with preserved source timestamps and reported provenance. Unsupported codec hints on local video source elements are removed and reported. Alpha/high-bit-depth/HDR inputs require explicit preparation rather than an automatic lossy conversion. Preparation has a 120-second subprocess deadline and document loading has a 30-second deadline; prepare large unsupported assets to a supported codec beforehand. Interactive dialogs and popup windows are unsupported and produce explicit failures without showing UI. Paths cannot escape through symlinks. Byte-range serving preserves browser media seeking.

CSS/WAAPI and a global GSAP timeline are paused and sought to logical time. Initial GSAP creation time is removed while authored delays remain intact; dynamically created WAAPI animations start at their creation frame. Local video elements select exact decoded source PTS and retain repeated source frames; `data-source-offset`, `data-source-rate` and `loop` control mapping. Use `data-vibeedit-timing="manual"` for a custom media adapter. Custom code can supply:

```js
window.renderFrame = async (frame, time, context) => {
  await preparedGraphicsReady;
  // Update normal DOM, Canvas, WebGL or WebGPU at this logical time.
  // Await asynchronous GPU submission when needed.
};
```

Existing `vibeedit.seek(time, context)` and `__vibeeditSeek(frame, context)` contracts are also recognized. `timing: "sequential"` guarantees ordered calls from frame zero and disables export reuse. Arbitrary wall-clock programs need an adapter; random/stateful code must manage deterministic state. Automatic adapters currently traverse the main document; iframe/shadow-root animations need custom adapters. Anime requires a custom timing adapter. Set `window.__vibeeditManualAnimationTiming = true` when custom code owns CSS/WAAPI/GSAP clocks. Automatic video timing exposes requested/mapped time and the selected source PTS in `context.media`; the paused element’s `currentTime` represents the decoded frame, rather than a continuously advancing output clock. Nonzero source start PTS needs explicit zero-based preparation or manual timing. Images and fonts introduced by a hook are awaited before capture. Custom hooks remain responsible for their asynchronous tasks and GPU submissions. Dynamic video sources/elements need explicit preparation and a manual timing adapter.

## API and warm worker

```python
from pathlib import Path
from vibeedit.browser_render import CEFService, render_browser_job
with CEFService() as service:
    report = render_browser_job(Path('job.json'), Path('/tmp/movie.mp4'),
                                backend='cef', service=service)
```

```sh
.venv/bin/python -m vibeedit browser-worker --backend cef
```

Send one JSON line per request: `{"id":"a","job":"/absolute/job.json","output":"/absolute/movie.mp4"}`. Responses preserve the ID and contain a report or explicit failure. The browser stays warm; documents load once per job, never once per frame. Requests serialize, and a failed service is replaced for the next job. Between independent jobs, Chromium memory pressure evicts old cached documents and navigation history resets; this keeps previous media decoders from accumulating. One native service is admitted per machine to avoid the prototype's unsafe fanout. Readiness, GPU completion, encoder backpressure and shutdown have deadlines. Portable fallback CDP requests run on an async transport with bounded waits, including missing target replies. SIGINT/SIGTERM enter normal CLI cleanup. API callers should close services with a context manager.

An optional `--cache /outside/project/cache` uses identities of all bundled dependencies, installed fonts, browser, adapter, implementation, native binaries and export settings. It requires seekable jobs and no QA readback. Outputs publish atomically after frame/audio verification. Changed dependencies and corrupt cached artifacts invalidate reuse.

## Export profiles and fallback

`--backend cef` uses CEF IOSurface → callback-scoped Metal copy into owned BGRA → GPU BT.709 NV12 → hardware-required VideoToolbox H.264. It requires even dimensions; transparent browser pixels flatten over black. Queues/pixel pools are bounded. Output frames use GPU transfer and hardware encoding. One full Chromium snapshot is discarded during document initialization: CEF invalidation alone can otherwise refresh an old blank surface on static pages. That startup readback is reported and included in preparation time; this is not a completely readback-free service. QA adds optional raw readback and reference screenshots.

`--backend screenshot` uses the same CEF build on this Mac when built, with the same readiness barrier, or pinned Playwright 1.61 Chromium 149 on Windows/Linux. It uses PNG/FFmpeg and reports its actual browser version. This is an explicit portable fallback; cross-version/cross-platform typography and GPU pixels are not promised to be identical. `--backend auto` attempts native once and reports the failure reason if a fresh screenshot service is required.

Transparent output is explicit: `"export":{"codec":"vp9","alpha":true}`, `.webm`, screenshot backend. Opaque exports flatten over black and do not preserve alpha. Color handling retains the sRGB transfer curve with BT.709 primaries/matrix and limited-range video; HDR/wide-gamut export is not qualified. VP9/WebM alpha uses the container’s millisecond timestamp granularity; the exact rational MP4 timestamp qualification applies to opaque H.264. Native quality and screenshot quality use different encoders; compare decoded quality as well as speed and file size.

## Reproduce verification

Run Python tests from `python/`, not the checkout root:

```sh
cd python
VIBEEDIT_CEF_INTEGRATION=1 ../.venv/bin/python -m pytest tests/test_browser_render.py -q
cd ..
.venv/bin/python browser-renderer/conformance.py browser-renderer/examples/basic/job.json browser-renderer/examples/corpus/job.json browser-renderer/examples/features/job.json browser-renderer/examples/gpu/job.json
.venv/bin/python browser-renderer/quality.py browser-renderer/examples/corpus/job.json
.venv/bin/python browser-renderer/media_check.py
.venv/bin/python browser-renderer/media_check.py --h264 --report /tmp/normalized-media.json
.venv/bin/python browser-renderer/color_roundtrip.py
.venv/bin/python browser-renderer/reliability.py
.venv/bin/python browser-renderer/benchmark.py --frames 900 --repeats 2
.venv/bin/python browser-renderer/soak.py --seconds 600
.venv/bin/python browser-renderer/platform_check.py --report /tmp/platform.json
.venv/bin/python browser-renderer/memory_check.py
.venv/bin/python browser-renderer/cold_cli.py
.venv/bin/python browser-renderer/verify.py --full --label accepted
```

QA lossless BGRA is compared to the same CEF screenshots at identical logical times with zero channel error for opaque compositions. Lossy exports require minimum 32 dB and mean 35 dB PSNR, separately from lossless capture. These thresholds permit expected 4:2:0/encoding loss and are not claims of archival fidelity. Reports check frame count, rational timestamps, AAC duration within one 48 kHz sample and independent audio pulse onset within 5 ms. Reports include native binary and dependency identities. GPU timing and native wait overlap; do not sum them as independent stages. `"profile":true` optionally collects bounded Chromium trace aggregates for Blink paint/layout, script and decoder events. Complete-duration trace events and nested spans overlap; trace sampling and instrumentation add overhead.

Benchmark videos default to `browser-renderer/evidence/media/<report-stem>`. Set `VIBEEDIT_RENDER_ARTIFACTS=/absolute/artifact-directory` to store them on another volume. Current full-run artifacts and the verified historical archive are on `the qualification artifact directory`; `evidence/archive.json` records the archived file hashes. CEF profiles and native admission locks stay on a local Unix filesystem.

Windows qualification used an isolated directory on the supplied Windows 10 AMD64 PC. Linux qualification used `mcr.microsoft.com/playwright/python:v1.61.0-noble` on ARM64, with FFmpeg and the recorded fonts, `--init` and `--ipc=host`. Docker 4.16 also required `--security-opt seccomp=unconfined` for this Ubuntu image. The same `platform_check.py` runs real exports, a stalled-CDP deadline, and fresh-browser recovery; reports record the actual browser and fonts. Qualification containers and temporary images were removed after testing.

## Published qualification evidence

The original source-backend acceptance reports, with local paths redacted and original report digests retained, are in `docs/evidence/accelerated-chromium/`. Beta.4 packaging and public-download checks are recorded separately in the release assets.
