# Chromium/CEF Shared-Texture MVP

This experiment keeps Chromium's Blink/Skia HTML and CSS rendering, runs an
optional WebGPU scene inside the browser, and receives the composited result as
a GPU-backed shared surface instead of a PNG screenshot.

On macOS ARM64 the probe pins CEF `144.0.30` / Chromium `144.0.7559.257`,
verifies the published archive SHA-1, builds the maintained `cefclient`
off-screen sample, instruments `OnAcceleratedPaint`, and confirms that CEF
delivers an IOSurface while the page reports an active WebGPU adapter. The MVP
probe accepts an explicit logical viewport and fixes the device scale at one.

```bash
python3 experiments/cef-shared-texture/probe.py \
  --report docs/evidence/cef-shared-texture-mvp.json
```

Capture the callback-scoped IOSurfaces as raw BGRA frames and encode a review
video without PNG screenshots:

```bash
python3 experiments/cef-shared-texture/probe.py --frames 90 \
  --raw-output /tmp/vibeedit-cef.bgra \
  --video-output /tmp/vibeedit-cef.mp4 \
  --report /tmp/vibeedit-cef-raw.json
```

The first run downloads about 256 MB into the user cache and builds the sample.
Later runs may use `--skip-build`. The CEF archive and build are intentionally
not committed to the SDK.

Import the IOSurface through Rust into Metal and perform a bounded, asynchronous
GPU-private blit without CPU pixel readback:

```bash
python3 experiments/cef-shared-texture/probe.py --skip-build --rust-gpu \
  --width 1920 --height 1080 --frames 60 \
  --report experiments/cef-shared-texture/rust-metal-1080p.json
```

Stress isolated consumers at one, two, and four workers:

```bash
python3 experiments/cef-shared-texture/concurrency.py
```

Render the same deterministic page through the current production-compatible
browser path:

```bash
PYTHONPATH=python/src .venv/bin/python -m vibeedit.cli render \
  experiments/cef-shared-texture/composition.json \
  --output /tmp/cef-shared-texture-webgpu-mvp.mp4
```

## Proven boundary

- Chromium parses, lays out, shapes, paints, and composites the HTML/CSS.
- A WebGPU canvas can participate in the same browser composition.
- CEF delivers the composited frame through `OnAcceleratedPaint` as an
  IOSurface on macOS, without PNG capture.
- The Rust bridge imports that IOSurface directly as a Metal texture and blits
  it into private GPU memory without CPU pixel readback.
- A separate bounded CPU-copy mode remains available to quantify why a native
  shared-texture path is necessary. Its queue is capped by bytes, not only by
  frames, to prevent hidden multi-gigabyte buffering at 4K.

The remaining production steps are deterministic external frame scheduling,
using one persistent CEF process with multiple browser views, connecting the
imported texture to the real Rust layer compositor, and texture-native hardware
encoding. macOS uses a small Metal platform adapter because stable high-level
wgpu does not expose this IOSurface-import contract. Windows and Linux need
equivalent D3D shared-handle and dma-buf/Vulkan adapters.
