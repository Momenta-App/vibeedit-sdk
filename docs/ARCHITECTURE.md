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
4. **HTML runtime** — a persistent deterministic `frame -> visual state`
   contract for unrestricted local HTML/CSS/JavaScript projects, CSS, SVG,
   Canvas, WebGL, and WebGPU components.
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

Built-in components and explicitly selected local web projects run in a pinned,
persistent Chromium document. The renderer loads each project once, waits for
fonts and libraries, seeks CSS/WAAPI plus recognized animation runtimes to an
integer frame, and captures the resulting compositor surface. Project assets
are served from a traversal-safe loopback server. External network requests are
blocked during rendering. Catalog HTML remains data; selecting a local web
project is an explicit executable-code trust boundary.

The browser path is the compatibility reference. Native Rust/WGPU routing is
per-layer and conformance-gated: a layer remains in Chromium unless the native
compiler proves that every operation it uses is supported and visually
conformant. WebGPU/WGSL is also available inside custom projects as an advanced
escape hatch; agents are not required to author shaders for ordinary text.

The preferred agent surface is narrower than the unrestricted project path:
`vibeedit://motion/html-css` accepts raw Chromium HTML and CSS, automatically
seeks CSS animations, and forbids authored JavaScript. Its optional VibeEdit
Motion Atoms stylesheet is a composable vocabulary of layout, text, material,
transform, animation, and blend primitives. The atoms are browser-reference
CSS today and carry stable native-primitive names for future conformance-gated
Rust/WGPU lowering; they do not replace or mutate the source-preserved preset
catalog.

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

Output URIs are destinations rather than pixel or sample inputs. Render and
revision hashes therefore exclude the URI while retaining container and codec
settings. Hybrid renders also cache the lossless Python/FFmpeg media base
separately from browser motion overlays, so a bounded text revision does not
rebuild unchanged source clips, effects, transitions, or audio before final
assembly.

Incremental revision planning compares two canonical CompositionSpecs and emits
changed fields, dirty video/audio ranges, changed and reusable artifacts,
dependency reasons, required jobs, a stitch strategy, and expected reuse. The
dependency graph gives sources, analysis/mask/tracking artifacts, timeline
layers, video composites, audio mixes, and final output stable content hashes.
Invalidation follows artifact dependencies transitively: a changed tracking
artifact invalidates masks derived from it and every layer referencing those
masks. Dependency-invalidated artifacts and layers are excluded from reusable
claims even when their own serialized objects are unchanged. Analysis
`sourceIds` also contribute source hashes and explicit source-to-artifact graph
edges, so replacing media invalidates derived analysis even if its artifact
declaration was not manually edited.
Execution support remains explicit per revision class: bounded browser-motion
changes use content-addressed composite-frame reuse, compatible container-only
changes stream-copy encoded packets, and explicit audio-clip/SFX parameter
changes remix audio while stream-copying video. Scene-tail removal stream-copies
an exact packet-counted video prefix only when the previous artifact and its
provenance digest match, all retained visual layers are unchanged or safely
trimmed at the new boundary, and removed visual layers begin at or beyond the
new end. Retained explicit music/SFX is rebuilt from the revised timeline and
encoded once rather than packet-truncated. The output frame count and clean
audio sample count are independently verified before reuse is reported.
Planned transition, mid-scene, and segmentation-dependent range replacement is
not reported as executable.

No-op or destination-only revisions copy only a provenance-verified prior
artifact. Audio and container revision executors also require the previous
composition hash and output digest before reuse. Cross-family AAC container
changes (for example MP4 to Matroska) do not blindly stream-copy audio because
that can lose encoder-delay metadata; VibeEdit stream-copies video while
rebuilding and encoding the audio mix directly into the target container.

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
- 30 selected HTML/CSS/JS effects plus 20 dependency-free fallback
  Python/JavaScript motion components and two baseline effects.
- 44 byte-identical canonical skill packages with four-harness lifecycle support.
- External audio-clip mixing, beat analysis, mask compositing, procedural SFX,
  OpenCV face/body providers, tracking artifacts, and optional SAM routing.
- 13 executable examples and 65 generated, hash-bound preview/audio assets,
  including one verified browser render for every registered text effect.
- One 467-item catalog and static site generated from the same manifests.

Generated imports retain tracked source revision, per-file hashes, aggregate
execution hashes, validation reports, and explicit quarantine records.
