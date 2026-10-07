# Acceptance audit — 2026-10-05

The source backend implements the handoff's ordinary browser-project workflow: Python/FFmpeg-generated media and transparent effects enter normal HTML/CSS/JS, CEF owns the complete browser composition, and callback-scoped IOSurfaces are copied into application-owned Metal resources for GPU conversion and hardware VideoToolbox encoding. CLI, Python API and a warm background JSON-lines worker are available. No creative DSL or timeline editor was introduced. This is an opt-in source backend, not a release or universal device qualification.

Both SDK checkouts and their history were inspected. The clean `vibeedit-sdk` checkout at `ccbb7da` contained the newer prototype; unrelated changes in `vibeedit-sdk-package-ux` were preserved. Existing experimental sources and creative assets remain intact. The maintained CEF host, recovered Rust/Metal bridge and qualification tools live under `browser-renderer/`. Job orchestration and the shared logical-time adapter live in `python/src/vibeedit/browser_render.py`, `browser_media.py`, and `browser_frame.js`. Setup and runnable examples are in [README.md](README.md).

## Correctness and service qualification

All results below are from actual built artifacts and exported media. Current implementation identity is `3e3631ad4699a89624a019630d31328411c13684a52cd048f991cae40f21faf2`; adapter identity is `35b2cae3e44c114954efd5cc8ecd6729bd16c4013c0dc796d6dd8f441036eaa5`. Native host and bridge identities are recorded in every report. The CEF archive is checksum-pinned to Chromium 144.0.7559.257.

| Gate | Evidence in `evidence/` | Result |
|---|---|---|
| Integration/regression | `integration-entry.log` | 23 passed: actual native static/async/warm capture, dynamic WAAPI, independent GSAP timing/delay/repeat truth, hook-created images/fonts, original-byte fetches, actual portable transport deadline, nested module/font/graphics entry, existing CLI/render behavior |
| Browser composition | `conformance-entry.json` | Four projects byte-exact against identical CEF screenshots: ordinary JS/modules/CSP, GSAP, CSS/WAAPI, overlapping real video and Python alpha effects, SVG, Canvas, WebGL2/WebGPU, clip/blend/backdrop/perspective |
| Typography | Conformance and platform reports | Arabic/RTL, Indic, CJK, ligatures, variable Roboto, bundled Poppins, fallback and emoji; font readiness and actual Chromium platform-font usage recorded |
| Equal requested bitrate quality | `quality-accepted.json` | Native min/mean PSNR 41.58/43.09 dB; screenshot 41.17/43.34 dB at 12 Mbps; both exceed 32/35 dB gates. Encoders and actual file sizes differ |
| Media timing | `media-accepted.json` | Independent VFR colors, two videos with loop/offset/rate, repeated frames and 24 fps input to 30000/1001 output: zero channel error; orientation/color error 1 |
| Unsupported codec normalization | `normalized-media-accepted.json` | H.264 inputs converted to cached VP9 with preserved decoded-YUV pixels and source PTS; VFR, fractional boundaries and rotation error at most 1 |
| Audio | Media reports | Requested 0.25 s onset measured at 0.2500417 s; 5 ms gate. AAC duration verified within one 48 kHz sample; exact output frame counts and rational MP4 times checked |
| Browser playback/color | `browser-color-accepted.json` | Independent six-frame export/decode plus CEF/Playwright playback of cold/warm static exports; maximum channel error 1; sRGB transfer metadata preserved |
| Alpha | `alpha-accepted.json` | Explicit VP9 screenshot fallback; independent libvpx alpha decode, maximum alpha error 3 and center RGBA error 1 (threshold 4) |
| Failures/device recovery | `reliability-accepted.json`, `gpu-recovery-accepted.json` | Script failure, never-ready promise, owned renderer/GPU process failures, bounded failure or correct continuation, fresh 1080p/4K recovery, no partial publication |
| Public worker/cache/concurrency | `service-entry.json` | Actual CLI good/bad/good, cache hit/revision/corruption, serialized concurrent requests, SIGTERM cleanup and preservation of prior output |
| Warm memory | `memory-accepted.json` | Twelve independent media jobs: 4.7 MiB final growth, two renderer processes. Job-boundary pressure evicts old cached documents; history resets without changing frame composition |
| Windows fallback | `windows-fallback-entry.json` | Actual Windows 10 AMD64 PC, pinned Playwright 1.61/Chromium 149: four exports including a nested entry, stalled CDP closed in 2.05 s, fresh-browser recovery |
| Linux fallback | `linux-fallback-entry.json` | Linux ARM64 pinned Playwright container: same exports, stalled CDP closed in 2.10 s, fresh-browser recovery. Container requires documented init/shared IPC settings |

The native service has no application windows and remains inactive. One service is admitted per machine and jobs serialize; measured safe concurrency is one. GPU pixel-buffer allocation is capped at six, protocol and diagnostics storage is bounded, and readiness/GPU/encoder/shutdown have deadlines. A GPU hang terminates the owned service before a borrowed surface can be returned while still in use. Outputs publish atomically after verification. Export reuse includes dependency/font/browser/platform/timing/settings/core/native identities and validates cached bytes; sequential simulations cannot use export reuse.

## Performance and sustained operation

The full built-artifact suite passed all 14 gates (`verification-accepted.json`). Supplemental complete cold CLI exports, 90-frame high-resolution quality checks and final-loader native regression/conformance/worker checks also passed (`post-acceptance.json`, `entry-verification.json`). The runtime snapshot used by the full matrix/soak is `b67134255b986f21c534e6ecb68cbda38a662702829c55e862f5c57341231c00`; its exact sources are preserved in `benchmark-source-b671/`. The final loader differs by one entry-URL expression: `Path.as_posix()` replaces `str()` to fix Windows nested entries. That expression produces identical URLs for these macOS benchmark projects. The frame adapter and native binaries are identical. `entry-path-fix.json` records provenance, and the corrected loader was exercised on all three fallback platforms, current native conformance/worker/integration, cold CLI and high-resolution quality.

`benchmark-accepted.json` compares 900 frames at 30000/1001 (30.03 seconds), using the same CEF build, fonts, viewport, device scale, active GSAP/CSS/custom adapter, readiness barrier and color handling for both backends. Backend order reverses for the second repeat. Both use the same requested bitrate at each resolution. Every complete export includes preparation, audio mux, final decode/timestamp verification and publication on the external artifact volume.

| Size | Repeat | GPU seconds | Screenshot seconds | Improvement |
|---|---:|---:|---:|---:|
| 1280x720 | 1 | 43.32 | 96.91 | 2.24× |
| 1280x720 | 2 | 42.29 | 94.89 | 2.24× |
| 1920x1080 | 1 | 46.29 | 129.58 | 2.80× |
| 1920x1080 | 2 | 46.36 | 128.16 | 2.76× |
| 3840x2160 | 1 | 67.94 | 289.91 | 4.27× |
| 3840x2160 | 2 | 67.95 | 289.30 | 4.26× |

These are measured results on one macOS ARM64 machine, with normal load variation. They do not promise faster-than-real-time exports. At 4K, seek/readiness and final decode verification remain substantial; the report's `mux` bucket includes audio mux, verification and publication. Detailed GPU conversion/wait, encoder append/flush and browser timing are recorded; overlapping spans must not be summed as independent work.

Cold CEF service startup measured 0.41–0.69 seconds, excluding Python imports (`profile-accepted.json`). Complete cold Python CLI processes exporting 30 frames took 4.17/3.43/5.91 seconds through the GPU backend at 720p/1080p/4K, versus 4.97/6.99/16.16 seconds for screenshots (`cold-cli-accepted.json`). Two warm short previews and small text revisions at each size and bounded Blink/layout/paint/decoder trace aggregates are in `profile-accepted.json`.

Matched-bitrate quality passed at every benchmark resolution: 720p native/screenshot mean PSNR 43.09/43.34 dB; 1080p 45.39/44.94 dB; 4K 47.08/47.25 dB. High-resolution comparisons cover 90 frames including the completed title entrance (`quality-1920x1080-accepted.json`, `quality-3840x2160-accepted.json`). Lossless capture is tested separately against the identical CEF reference, with zero channel error.

The final sustained soak passed 629.95 seconds across six jobs, including a 3,600-frame two-minute composition and 1,800-frame jobs at each size. Peak memory across Python and all owned CEF/FFmpeg descendants was 848.03 MiB, below the 4 GiB gate (`soak-accepted.json`). This supersedes the earlier retained-document growth; the independent 12-job memory gate validates eviction at job boundaries. GPU/renderer recovery and cancellation were exercised separately with fresh jobs after failure.

## Deliberate limits and remaining hardening

Native acceleration is macOS ARM64 opaque H.264 with hardware-required VideoToolbox, even dimensions and SDR sRGB transfer/BT.709 primaries and matrix/limited range. macOS 15 is the API minimum; the tested machine runs macOS 26.4. Alpha uses explicit VP9/PNG fallback. Windows/Linux are verified screenshot fallbacks, not native GPU adapters. They use Chromium 149 and platform-specific fallback fonts, so cross-platform or cross-version pixels are not certified identical to CEF 144.

One discarded full-frame Chromium snapshot initializes each document: CEF invalidation alone can otherwise return an old blank surface for static pages. Export frames still use shared surfaces and GPU encoding. The bootstrap is reported and timed; the complete service is not entirely readback-free.

Automatic timing covers finite local media and main-document CSS/WAAPI/global GSAP. Async hooks and ordered sequential calls handle custom simulations and graphics. Arbitrary wall-clock code, live sources, dynamic video sources, nonzero source start PTS, iframe/shadow-root clocks and unsupported library ownership require explicit preparation/manual adapters. Requested media time and selected decoded PTS are supplied separately in `context.media`; paused `video.currentTime` follows the decoded frame. Hooks must await their own asynchronous work/GPU submissions.

Repeated source frames reuse decoded browser frames. Distinct adjacent frames still use exact browser seeks and are the main remaining bottleneck. A lossless all-intra sequential-preparation experiment preserved every pixel but measured 0.999× speed (`decode-preparation-experiment.json`) and was rejected. A relaxed seek-readiness experiment produced only 1.017× improvement and was also rejected. No universal external decoder or live GPU plugin for every language is claimed.

Opaque 8-bit SDR unsupported media can be normalized with provenance and a validated cache. Alpha/HDR/high-bit-depth inputs need explicit preparation; large conversions must be prepared before the document-load deadline. Ordinary JavaScript fetches retain original file bytes. Resources, font errors and LastResort fallback fail explicitly. Font diagnostics inspect at most 100 main-document nodes; exhaustive Unicode coverage is not proven. HDR/wide-gamut output is unqualified. VP9/WebM alpha timestamps use millisecond container granularity; exact rational MP4 timing applies to opaque H.264.

Broader machine/driver coverage, native Windows/Linux adapters and multi-hour endurance are future qualification work. No 10× or arbitrary faster-than-real-time promise is made. The existing VibeEdit desktop app was not modified, packaged or released. Unrelated later catalog-preview changes were preserved.

Benchmark videos are stored on `the qualification artifact directory/artifacts/benchmark-accepted/`; the checksum-verified historical archive is recorded in `evidence/archive.json`. Current correctness artifacts and JSON/log evidence remain in this checkout.

## Published qualification evidence

The original source-backend acceptance reports, with local paths redacted and original report digests retained, are in `docs/evidence/accelerated-chromium/`. Beta.4 packaging and public-download checks are recorded separately in the release assets.
