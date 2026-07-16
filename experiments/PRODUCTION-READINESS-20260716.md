# Experimental renderer production-readiness review

## Decision

Keep the SDK's persistent Playwright/Chromium renderer as the production-safe
HTML fallback. Keep HTML, CSS, JavaScript, and optional WebGPU/WGSL as the agent
authoring surface. Chromium remains responsible for standards-compatible DOM,
layout, font shaping, CSS painting, filters, and web-library execution.

The CEF/Rust/Metal path is now a deterministic, background, zero-CPU-readback
prototype. It is not yet safe to replace the fallback because high-resolution
jobs can stop producing frames after multi-process GPU stress. Production must
fall back to the current persistent Chromium path on readiness or frame timeout.

Python remains the trusted orchestration and extension surface for effects,
transitions, analysis, and FFmpeg graph construction. Native FFmpeg code, not a
Python pixel loop, performs those media operations.

## Results from this round

| Test | Result | Meaning |
|---|---:|---|
| Three fresh 1080p Chromium runs, 30 frames | exact hashes for every frame | Host-controlled seeking is reproducible for the tested document. |
| Three fresh 720p CEF/Rust/Metal composite runs | identical final hash; exact sequences | The deterministic compositor output repeats across processes. |
| 720p native composite | 23.0–23.5 callback fps; 2.11–2.33 ms synchronous GPU work | Metal is not the primary callback bottleneck. |
| One isolated 4K composite before stress | exact 30-frame sequence; 21.61 steady callback fps; 4.944 ms GPU work | A clean single process can render 4K without CPU readback. |
| Five sequential 720p × 60-frame runs | 5/5 passed; exact sequences | Short sequential soak passed; maximum child RSS was about 203 MB. |
| One vs two isolated 720p processes | 3.42 vs 7.22 aggregate end-to-end fps | Two processes improve aggregate throughput by about 2.11×. |
| Four isolated 720p processes | 2/4 timed out | Four processes are unsafe and dramatically slower. |
| Post-stress 900p/1080p retry | stalled after zero or one paint | CEF/Chromium GPU lifecycle recovery is still a production blocker. |
| Script failure and never-ready page | bounded incomplete result and cache cleanup | Failure is reported instead of being mistaken for success. |
| Background-host check | `visible=false`, `frontmost=false`, zero windows | Rendering no longer opens a tab/window or steals focus. |

The accepted compositor fixture performs real Metal work: a procedural native
base, transformed and opacity-adjusted Chromium layer, circular mask, and native
screen-blend overlay. It does not yet contain decoded video textures or the
final encoder.

## Defects found and fixed

- CSS/WAAPI/WebGPU state now seeks to exact rational frame time. CEF external
  begin-frame requests are numbered and validated as an exact sequence.
- The browser frame request now allows a full frame budget before requesting a
  paint. This avoids asking CEF to paint before asynchronous WebGPU work has had
  an opportunity to finish.
- The Metal adapter now waits for GPU completion before returning the IOSurface
  to CEF's reuse pool. Returning earlier was an invalid ownership assumption.
- Native compositor QA now captures the final GPU result and verifies its hash.
- The probe terminates the complete process group with escalation, records the
  lifecycle outcome, and always removes its temporary browser cache.
- Renderer errors and never-ready pages now fail explicitly.
- The sample host's redundant OpenGL preview draw is disabled in capture mode.
- The macOS host is an accessory process with an initially hidden window, so
  all rendering happens in the background.
- Concurrency tests retain partial failures instead of aborting and losing the
  evidence.

## Production policy now

1. Default to the existing persistent Chromium renderer.
2. Keep CEF/Rust/Metal behind an experimental capability flag.
3. Admit at most two isolated CEF jobs on the tested 10-core/32 GB Apple Silicon
   machine; use one under memory or GPU pressure.
4. Apply a readiness deadline and a per-frame deadline. On failure, terminate
   the process group, discard its runtime cache, and retry through the persistent
   Chromium fallback without lowering resolution or changing pixels silently.
5. Use one controlled final encode for deterministic delivery. Preview mode may
   use more aggressive FFmpeg threads or hardware encoding.

## Architecture

```text
Agent HTML/CSS/JS (optional WGSL)
              │
              ▼
     Chromium / Blink / Skia
 exact web layout, text, and paint
              │ IOSurface
              ▼
     Rust scheduler + Metal
 transforms, masks, blend, color
              │
              ├── native video textures (next gate)
              ▼
       hardware encoder (next gate)

Python extension
  └── validates composition nodes and emits FFmpeg/native work
```

Agents should never author raw Metal or WGPU for ordinary typography. Reusable
declarative atoms are the lowest-token path; arbitrary HTML/CSS/JS remains the
compatibility escape hatch.

## Remaining gates

1. Replace the modified `cefclient` sample with a small VibeEdit-owned CEF host
   and one persistent browser process containing pooled off-screen views.
2. Find and fix the high-resolution post-stress paint stall. Add GPU-process
   crash/restart telemetry and a clean-process recovery test at 1080p and 4K.
3. Feed decoded media textures into the compositor and validate multiple real
   video layers, masks, transforms, opacity, blend modes, color, blur, and
   distortion against canonical output.
4. Connect the final texture to VideoToolbox. Add D3D11/Media Foundation for
   Windows and dma-buf/Vulkan/VA-API for Linux.
5. Expand soak from five short jobs to hours, including cancellation, cache
   invalidation, font/library matrices, device loss, and memory-pressure tests.
6. Add golden/perceptual thresholds for the complete browser → native media →
   encoder pipeline.

This round closes deterministic scheduling, compositor repeatability, bounded
failure handling, and background operation for the tested fixture. It does not
justify a production-ready or 10× end-to-end claim yet.
