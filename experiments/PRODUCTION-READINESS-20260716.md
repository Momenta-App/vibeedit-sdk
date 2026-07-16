# Experimental renderer production-readiness review

## Decision

Keep HTML, CSS, JavaScript, and optional WebGPU/WGSL as the primary agent
authoring surface. Chromium remains responsible for standards-compatible DOM,
layout, font shaping, CSS painting, filters, and web-library execution. Rust is
the scheduler and native compositor; it must consume Chromium's finished GPU
surface rather than attempting to reproduce Blink/Skia's pixels.

Python remains a trusted extension and orchestration surface for effects,
transitions, analysis, and filter construction. In the current SDK those
builders return FFmpeg filter graphs; FFmpeg's native C/C++ implementation does
the pixel processing. Python is not looping over video pixels.

## What this round proved

| Test | Result | Interpretation |
|---|---:|---|
| CEF only, 1080p | 60.33 callback fps | Chromium can paint the test document at the 60 fps cap. |
| CEF → Rust → Metal, 1080p | 52.02 callback fps; 1.551 ms average submit | Direct GPU import and GPU-private blit work without CPU readback. |
| CEF → Rust → Metal, 4K | 35.03 callback fps; 2.657 ms average submit | The direct path remains faster than real time at 30 fps. |
| CEF synchronous 4K CPU copy | 12.45 callback fps | CPU readback and file I/O are unacceptable as the production boundary. |
| CEF Rust queued 4K CPU copy | 14.44 callback fps | Moving the copy helps callbacks slightly but wall time and memory remain poor. |
| Two concurrent CEF/Metal processes | all passed | Isolated consumers are safe, but separate-process startup and GPU contention are expensive. |
| Four concurrent CEF/Metal processes | all passed, worse end-to-end throughput | Four heavy Chromium processes oversubscribe this 10-core machine. |
| Python/FFmpeg, one worker/one thread | 6.99 aggregate fps | This was the effective old behavior because the SDK ignored `render.threads`. |
| Python/FFmpeg, one auto-threaded worker | 23.08 aggregate fps | Respecting native encoder/filter concurrency gives 3.30× throughput. |
| Python/FFmpeg, two workers/five threads | 44.29 aggregate fps | Best tested throughput: 6.34× the old behavior. |
| Python/FFmpeg, four workers/two threads | 43.29 aggregate fps | More jobs do not improve this machine. |
| Three web bands, sequential vs concurrent | 10.175 s vs 3.231 s | Parallel web-band production was 3.15× faster. |

The 4K direct-GPU path is 2.81× faster at the callback boundary than the
synchronous CPU-copy path and avoids writing roughly 995 MB for only 30 raw 4K
frames. The interleaved review validates this order:

1. native/Python media base;
2. transparent Chromium text;
3. native screen-blend video;
4. transparent Chromium text;
5. circularly masked, partially transparent native video;
6. transparent Chromium text.

The review still uses the current PNG capture fallback for its web bands. The
new CEF/Rust/Metal route proves how to remove that boundary, but it is not yet
wired into the final multi-layer compositor.

## Defects found and fixed

- `render.threads` was present in the public schema but ignored by every Python
  FFmpeg path. The implementation now passes it to the encoder and complex
  filter scheduler while preserving one thread as the default.
- A frame-count-only Rust queue could hide hundreds of megabytes or gigabytes
  of pending 4K buffers. The probe now derives effective depth from a memory
  budget and reports capacity, copy time, queue wait, and buffer allocation.
- Concurrent CEF clients originally collided because they shared a runtime
  cache. Every probe now receives an isolated temporary CEF cache.
- CPU copying was incorrectly treated as the likely Rust boundary. A real
  Rust-to-Metal surface submission path now imports and blits the IOSurface on
  the GPU with a three-frame in-flight limit.

## Determinism finding

H.264 outputs produced with different encoder thread counts did not have equal
decoded-frame hashes. Therefore production deterministic mode should parallelize
lossless intermediate layer/segment generation, then perform one controlled
final encode. Fast preview mode may use multi-threaded or hardware encoding and
must not promise byte- or pixel-identical output across concurrency settings.

CEF benchmarking currently uses live wall-clock animation. Production rendering
still needs a host-controlled protocol:

1. wait for document, fonts, and web libraries to report ready;
2. seek all CSS, WAAPI, JavaScript, and WebGPU state to an exact rational frame;
3. call CEF external begin-frame;
4. accept exactly one matching accelerated-paint surface;
5. submit it to the Rust compositor and apply bounded backpressure;
6. advance only after the compositor accepts the frame.

Until that handshake exists, the shared-texture path is a validated transport
prototype, not a deterministic production renderer.

## Production architecture

```text
Agent code (HTML/CSS/JS, optional WGSL)
                    │
                    ▼
         Chromium / Blink / Skia
       exact web layout and painting
                    │ IOSurface / shared handle / dma-buf
                    ▼
          Rust scheduler + compositor
     transforms, masks, blend, color, cache
           │                    │
           │                    └── native video textures
           ▼
      hardware encoder

Python/Rust/other-language extension
        └── validates and emits composition nodes,
            FFmpeg graphs, native kernels, or WGSL
```

Alternate text/video/text/video ordering should create one transparent Chromium
surface per contiguous web z-band. Native media stays as native textures between
those bands. This avoids one Chromium instance per text item and preserves exact
track ordering.

Agents may author extensions in any language only through a stable process or
WASM ABI with declared inputs, outputs, determinism, resource limits, and cache
identity. Arbitrary code cannot safely become an unconstrained in-process plugin.
The lowest-token path remains a declarative composition plus reusable atoms;
raw HTML/CSS/JS is the escape hatch for designs that need it.

## Remaining gate before production

1. Build the deterministic CEF seek/begin-frame/paint handshake.
2. Replace the discarded Metal blit destination with the real Rust compositor
   texture graph and add transforms, masks, blend modes, and color tests.
3. Connect the compositor texture directly to VideoToolbox on macOS; add D3D11/
   Media Foundation on Windows and dma-buf/Vulkan/VA-API on Linux.
4. Run one persistent CEF process with pooled browser views. Start with two
   concurrent heavy web bands on a 10-core/32 GB machine and adapt from measured
   CPU/GPU/memory pressure.
5. Split deterministic final rendering from fast preview policy.
6. Add crash isolation, watchdogs, cancellation, memory budgets, font/package
   pinning, cache invalidation, golden-frame conformance, and soak tests.

This round did not establish a 10× end-to-end win. It established the correct
zero-readback boundary, a 6.34× media-stage throughput improvement, and a 3.15×
web-band concurrency improvement. A 10× claim should wait until deterministic
CEF scheduling, native compositing, and texture-native encoding are connected
and measured as one pipeline.
