# VibeEdit Production Library Architecture

## Contract first

CompositionSpec is a strict, versioned JSON document. Integer frames are the
only timeline unit. Frame rate is a reduced rational `{numerator, denominator}`.
Sources may report seconds, samples, beats, or timecode, but those values must
be converted at admission and the conversion provenance retained.

The public object model is VibeEdit-owned:

`Composition`, `Canvas`, `Timeline`, `Track`, `VideoClip`, `AudioClip`,
`ImageClip`, `MotionComponent`, `Effect`, `Transition`, `Mask`,
`TrackingArtifact`, `AnalysisArtifact`, `SoundEffect`, `RenderJob`,
`VerificationReport`, `CatalogItem`, and `SkillPackage`.

MoviePy, browser automation, FFmpeg, OpenCV, ML frameworks, and GPU libraries
are backend details. Backend-native objects never appear in serialized specs or
public constructor signatures.

## Package layers

1. **Spec** — schema, version compatibility, deterministic canonical JSON, and
   cross-language fixtures.
2. **Catalog** — stable identifiers, parameter schemas, provenance, platforms,
   backends, examples, previews, and validation cases.
3. **Python API** — composition builders, media inspection, analysis artifacts,
   cache/provenance, render dispatch, audio mixing, and verification.
4. **HTML runtime** — a deterministic `frame -> visual state` contract for CSS,
   SVG, Canvas, and isolated WebGL components.
5. **Render dispatcher** — plans media-domain work and HTML overlay work, renders
   intermediates, and assembles them with FFmpeg.
6. **Adapters** — CLI, Node API, MCP, skills installer, and static catalog site.

## Rendering domains

The media engine owns source decoding, trim, speed, transforms, sequencing,
effects, transitions, audio, masks, analysis, final assembly, and verification.
The HTML engine owns kinetic typography, captions, lower thirds, graphics, and
seekable transparent overlays. A render plan is deterministic when its spec,
source identities, implementation versions, model versions, and runtime
versions are fixed.

HTML components run in a restricted local document with explicit assets and no
network access by default. Catalog HTML is data, not executable code. A future
third-party component loader requires a separate trust boundary.

### Hybrid renderer boundary

VibeEdit keeps browser-authored paint and native media work separate. HTML,
CSS, Canvas, and WebGL remain responsible for the exact visual surface that an
agent authored; the backend does not reinterpret DOM layout, glyph shaping,
shadows, gradients, or blend behavior. Native code owns source decoding,
surface transforms, alpha compositing, effects, transitions, audio, caching,
and encoding. This preserves browser appearance while leaving a stable boundary
for a future Rust/WGPU compositor.

A 50-edit adversarial gauntlet exercised existing VibeEdit motion components,
effects, transitions, transparent surfaces, blend modes, fractional affine
transforms, one through eight layers, overlapping motion, and odd frame sizes.
It did not introduce a replacement skill or a second public object model. The
native compositor matched its canonical reference across all 35 routed cases;
the remaining 15 cases stayed on the browser fallback because they depended on
browser paint semantics that were not safely portable.

The package does not currently ship the experimental Rust compositor. The test
runtime proved that a native accelerator must probe for an adapter and fall back
without crashing, use 256-byte GPU row alignment, accept straight RGBA textures,
composite in premultiplied alpha, and convert readback to straight alpha before
encoding. Those contracts are prerequisites for promotion into a cross-platform
release artifact.

Subsampled output formats also have geometric constraints. VibeEdit preserves
exact odd dimensions through a 4:4:4 working surface and supports them with
`yuv444p`. A requested 4:2:0 or 4:2:2 output whose dimensions violate chroma
subsampling now fails before FFmpeg with an actionable message; VibeEdit never
silently changes composition size.

## Backends and capability routing

The lightweight installation requires Python and system FFmpeg/FFprobe. Optional
extras add browser rendering, portable vision, and SAM. Capability selection is
registry-based:

- macOS builds the packaged VibeEdit-owned Swift/Apple Vision runner during
  explicit vision setup and prefers its declared face, body, and pose providers.
- Windows and Linux prefer portable OpenCV/ONNX/Torch providers.
- Missing optional runtimes produce structured unavailable results and setup
  instructions, never import-time failures.

`vibeedit setup` owns pinned runtime/model downloads, checksums, cache location,
licenses, and removal. No provider downloads during import or render.

The Apple Vision runner is bundled as auditable Swift source, not as a universal
binary. On supported macOS, setup compiles it into the user cache, probes its
capability declaration, and records the executable SHA-256. The router never
infers support from platform or executable presence alone; because the bundled
runner does not declare general objects, that request falls through to ONNX.

General objects use the portable SSD-MobileNetV1-12 ONNX provider after explicit
vision setup. The 29,461,455-byte checkpoint is pinned to a model-repository
commit, byte count, and SHA-256 and stays outside release archives. The router
prefers an explicitly capable Apple runner if one is configured, then ONNX.
Because ONNX Runtime 1.27 does not publish macOS Intel wheels, setup skips that
model on Intel Macs and reports the provider as unsupported while preserving
OpenCV and Apple Vision capabilities. Pose support in 0.1 is intentionally
macOS-native; other platforms receive a structured unavailable result instead
of a platform-derived claim.

SAM 2.1 is an optional adapter, never part of the lightweight wheel. Explicit
setup streams a pinned official source archive and Hiera Tiny checkpoint into
the VibeEdit cache, verifies exact size/SHA-256, safely extracts source, and
creates a local runner manifest. The runner chooses CUDA, MPS, then CPU and
emits frame-indexed lossless RLE masks. An external provider may be registered
only with an executable and a manifest declaring capability, version, license,
and a 64-character weight digest. SAM 3.1 remains quarantined.

## Cache and provenance

Cache keys hash canonical JSON containing source identity, operation parameters,
VibeEdit implementation version, backend/runtime version, model version, and
schema version. Artifacts store the same inputs plus creation time and output
hash. Users can inspect or invalidate any cached item.

## Versioning

CompositionSpec starts at `1.0.0`. Readers reject unknown major versions and may
accept newer minor versions only when all unfamiliar fields are optional under
the declared compatibility policy. Writers emit the current version. Migration
is explicit and never silently changes timing.

The npm and Python packages share the same release version. Their compatibility
metadata records schema, catalog, and skill-bundle versions. Catalog item IDs
are stable; behavior changes require an item version bump, while replacement
uses `supersedes` rather than reassigning an ID.

## Expanded candidate

The verified vertical slice was expanded mechanically from canonical sources:

- 333 deterministic media presets behind the VibeEdit-owned frame API.
- 74 dependency-free, seekable Python/JavaScript motion components.
- 44 byte-identical canonical skill packages with four-harness lifecycle support.
- External audio-clip mixing, beat analysis, mask compositing, procedural SFX,
  OpenCV face/body providers, tracking artifacts, and optional SAM routing.
- 13 executable examples and 13 generated preview/audio assets.
- One 467-item catalog and static site generated from the same manifests.

Generated imports retain tracked source revision, per-file hashes, aggregate
execution hashes, validation reports, and explicit quarantine records.
