# Chromium/CEF Shared-Texture MVP

This experiment keeps Chromium's Blink/Skia HTML and CSS rendering, runs an
optional WebGPU scene inside the browser, and receives the composited result as
a GPU-backed shared surface instead of a PNG screenshot.

On macOS ARM64 the probe pins CEF `144.0.30` / Chromium `144.0.7559.257`,
verifies the published archive SHA-1, builds the maintained `cefclient`
off-screen sample, instruments `OnAcceleratedPaint`, and confirms that CEF
delivers an IOSurface while the page reports an active WebGPU adapter. The MVP
probe fixes the logical browser viewport at the composition's 640x360 size;
Retina systems may expose a 1280x720 backing IOSurface.

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
- CEF requires the client to copy the temporary surface during the callback.
- The probe can copy that surface to raw BGRA and encode a complete H.264 review
  video. It deliberately keeps this CPU-copy path visible in its evidence.

The remaining production steps are deterministic external frame scheduling and
importing the IOSurface into a Rust/wgpu-owned texture for native composition
and texture-native hardware encoding. This MVP does not claim that final GPU
handoff yet.
