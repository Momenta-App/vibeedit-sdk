# Changelog

## 0.1.0 beta 2 - Unreleased

- Give the materially changed post-beta.1 candidate a distinct npm/Python
  package identity so it cannot be confused with or overwrite the existing
  public beta.1 artifacts.

- Add a pinned Chromium/CEF shared-texture MVP proving HTML/CSS plus browser
  WebGPU composition can reach native code as a macOS IOSurface without PNG
  capture.
- Stream mixed Chromium overlay frames directly into FFmpeg, support two-clip
  Python effect/transition bases, and expose trusted process-local Python filter
  registration for agent-authored effects and transitions.
- Added `vibeedit://motion/html-css`, a deterministic raw HTML/CSS-only authoring
  contract with full pinned-Chromium CSS rendering, automatic animation seeking,
  local assets/fonts, and no authored JavaScript.
- Added VibeEdit Motion Atoms v1, a reusable CSS/manifest vocabulary designed for
  concise agent composition and future conformance-gated Rust/WGPU lowering.

- Replace per-frame Chromium document reloads with a persistent deterministic
  seek runtime and faster lossless compositor capture.
- Stream browser-only frame sequences directly into FFmpeg instead of writing
  and rereading temporary PNG directories.
- Add explicit local HTML/CSS/JavaScript project components, bundled font and
  asset loading, CSS/WAAPI/GSAP/Anime.js seeking, framework guidance, and
  actionable network/font failures.
- Add secure-loopback WebGPU/WGSL execution, native-eligibility inspection, and
  conformance-gated routing that keeps unverified layers on Chromium.

## 0.1.0 beta 1 - 2026-07-14

- Publish the first public beta for evaluation, testing, and community review.
- Centralize runtime version reporting and use ecosystem-native prerelease
  versions: npm `0.1.0-beta.1` and Python `0.1.0b1`.
- Add beta feedback intake and installable, attested GitHub release artifacts.
- Update the pinned setup-python action and beta-aware artifact validation.

- Clone the canonical 333 reviewed deterministic media presets byte-for-byte
  behind VibeEdit-owned public adapters, stable catalog identifiers, provenance,
  and exhaustive tests.
- Add the lightweight `effects` extra plus `vibeedit setup --effects` and
  `media.presets` doctor reporting.
- Adapt 74 tracked text/motion components into a dependency-free deterministic
  Python/JavaScript runtime, including real tracking-keyframe interpolation.
- Clone 44 release-safe production skills byte-for-byte, quarantine 23 rejected
  packages, and validate every clone across four harness layouts.
- Add beat analysis, external audio-clip mixing, mask compositing, procedural
  synthesis, face/body providers, and checksum-pinned optional SAM 2.1 setup.
- Add an auditable Swift/Apple Vision runner that explicit macOS setup compiles,
  hashes, and probes for face, body, and pose capabilities.
- Add checksum-pinned SSD-MobileNetV1/ONNX Runtime general-object detection with
  normalized COCO-labeled boxes and explicit cross-platform vision setup.
- Add and render fan-edit, beat-sync, layered-sound, mask-subject, face-follow,
  multiple-transition, transparent-overlay, and conditional-SAM examples.

- Added CompositionSpec 1.0.0 with integer-frame/rational-rate timing.
- Added Python composition, FFmpeg, HTML motion, SFX, verification, catalog,
  skill, capability, setup, and local tool APIs.
- Added npm runtime, deterministic motion seeking, Node CLI, declarations, and
  safe skill lifecycle management.
- Added verified generated-media, effect/transition, and mixed HTML examples.
- Added a static local production catalog, generated previews, custom license,
  provenance inventory, and SPDX SBOM.
