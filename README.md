# VibeEdit

VibeEdit is a frame-accurate video-production library for AI coding harnesses.
It provides a VibeEdit-owned Python media API, a deterministic JavaScript/HTML
motion runtime, one shared CompositionSpec, a searchable local catalog, safe
skill installation, rendering, and output verification.

The qualification candidate is Python **0.2.0b1** / npm **0.2.0-beta.1**.
It adds portable projects and corrections, focused local review tools, explicit
model packs, source-acquisition receipts and an optional Pi companion. It is
**not yet qualified as the complete launch**. Its exact archives are public in
[v0.2.0-beta.1](https://github.com/Momenta-App/vibeedit-sdk/releases/tag/v0.2.0-beta.1).
Registry publication and complete customer journeys remain pending. Archive
source is pinned to `7ff8ff1a9caf1f53d7f8cba7fbbfec97d0dd61e1`; these updated
guides are a documentation supplement and do not rebuild those archives.

VibeEdit-owned code is MIT licensed. Optional models and fonts have their own
terms in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Myriograph owns the
three paid intelligence services and metered companion access. Ordinary local
editing requires no account or Pi companion.

## Install

Give your agent the [pinned setup skill](https://raw.githubusercontent.com/Momenta-App/vibeedit-sdk/v0.2.0-beta.1/skills/vibeedit-setup/SKILL.md):
"Read this VibeEdit setup skill, install it for this project, verify it, and help
me make a video."

The agent verifies the release manifest, checksums and matching skill before
installing exact archives into isolated environments. Registry versions are not
published yet. For manual installation, first download and verify the files from
that same prerelease; the commands below use those verified local files.

Lightweight Python CLI and media orchestration:

```bash
uv tool install ./vibeedit-0.2.0b1-py3-none-any.whl
vibeedit doctor
```

For a manual installation inside a Python virtual environment, choose only the
needed extras below. These pip commands do not modify an existing `uv tool`
environment; the setup skill handles isolated optional-runtime installation.

```bash
pip install "./vibeedit-0.2.0b1-py3-none-any.whl[effects]"
pip install "./vibeedit-0.2.0b1-py3-none-any.whl[browser]"
pip install "./vibeedit-0.2.0b1-py3-none-any.whl[vision]"
pip install "./vibeedit-0.2.0b1-py3-none-any.whl[sam]"
pip install "./vibeedit-0.2.0b1-py3-none-any.whl[all]"
vibeedit setup --effects
vibeedit setup --browser
vibeedit setup --sam
vibeedit doctor --json
```

The effects extra activates 333 reviewed deterministic frame presets: 200
filters, 112 effects, and 21 transitions. Every preset has a stable catalog ID,
bounded parameters, source hashes, and an exhaustive execution result in
`catalog/preset-validation.json`.

```python
from vibeedit import apply_media_preset, render_transition_preset

graded = apply_media_preset(
    rgba_frame,
    "vibeedit://effect/filters-cinematic-teal-orange",
    parameter_overrides={"intensity": 0.42},
    progress=0.4,
)
transition = render_transition_preset(
    graded,
    next_rgba_frame,
    "vibeedit://transition/transitions-core-film-burn",
    progress=0.5,
)
```

The vision extra exposes real OpenCV face detection, person/body detection, and
deterministic temporal face tracking through `CapabilityRouter`. Tracking writes
a normalized JSON artifact and returns a public `TrackingArtifact` with source,
runtime, and cache-key provenance. On macOS, `vibeedit setup --vision` builds the
packaged VibeEdit-owned Swift runner and enables its explicitly declared face,
body, and pose requests. The same explicit setup downloads a checksum-pinned
29.5 MB SSD-MobileNetV1 ONNX model for portable general-object detection where
ONNX Runtime publishes a wheel. ONNX Runtime 1.27 has no macOS Intel wheel, so
that platform retains OpenCV face/body tracking and Apple Vision while reporting
the portable object provider as unsupported. Unsupported providers remain
explicit in `doctor`; they are never inferred merely from the operating system.

`vibeedit setup --sam` is an explicit 211.7 MB optional download. It installs a
checksum-pinned official SAM 2.1 source revision and tiny checkpoint in the
VibeEdit cache; the source and weights are Apache-2.0. The runner uses
Torch/CUDA, Torch/MPS, or CPU in that order and records the model version,
checkpoint digest, prompt, source identity, actual device/runtime versions, and
cache key. A clean-wheel Torch/MPS proof with controlled and natural masks is
recorded in `docs/evidence/sam21-public-proof.json` for an earlier release. The new model-pack command supports pinned TransNet, SAM 2.1 and SAM 3.1 MLX setup. Fresh inference qualification for this candidate is pending; setup availability is not model accuracy evidence.
No model weight is part of the base wheel or npm archive.

Node SDK, HTML motion runtime, and Node-facing CLI:

```bash
npm install ./vibeedit-0.2.0-beta.1.tgz
npx vibeedit doctor --json
```

The Node package owns CompositionSpec, catalog, skills, and HTML motion APIs.
Media rendering commands bridge to an installed Python VibeEdit package. Run
`npx vibeedit doctor --json` to see both capabilities and exact next actions.

Agent-package guides: [projects/review](docs/PROJECTS.md),
[models and reviewed effects](docs/MODELS.md), [Pi workers/goals](docs/COMPANION.md),
[Myriograph funding/services](docs/MYRIOGRAPH.md), and
[operations/rollback](docs/OPERATIONS.md). [Launch state](docs/launch/STATE.md)
keeps actual qualification separate from supported command contracts.

## Agent quick start

Use this sequence when an agent has no prior VibeEdit context:

```bash
vibeedit doctor --json
vibeedit examples list --details --json
vibeedit catalog search kinetic --compact --limit 5 --json
vibeedit examples create basic-generated ./vibeedit-work --json
vibeedit render ./vibeedit-work/basic-generated/composition.json --json
```

`ready: true` means the core FFmpeg renderer is ready. It does not claim every
optional model or browser capability is installed; inspect the `readiness` and
`capabilities` fields for those distinctions. Compact catalog search is intended
for low-token agent discovery. Omit `--compact` when the full parameter,
provenance, prompt, and validation contract is needed.

Compact results are ranked deterministically and include the selected stable ID,
intent, required capability, backend, determinism, parameter count, platform
compatibility, setup cost, confidence, and reason. Search does not load skill
bodies; inspect only the selected result when more detail is needed.

Before a human revision, inspect the dependency-aware invalidation plan:

```python
from vibeedit import plan_revision, render_revision

plan = plan_revision(previous_spec, revised_spec)
print(plan["dirtyFrameRanges"], plan["expectedReuse"])
render_revision(previous_spec, revised_spec, "previous.mp4", "revised.mkv")
```

The same preflight is available without Python code:

```bash
vibeedit revision plan previous.json revised.json --json
```

For bounded browser-text changes with caching enabled, VibeEdit reuses
content-addressed composite frames outside the changed layer's placement. The
render provenance sidecar reports `work.framesRendered`, `work.framesReused`,
and the reuse kind. Compatible container-only changes use stream-copy remuxing
without decoding video. Audio-clip and procedural-SFX parameter revisions remix
audio and stream-copy the encoded video. Bounded browser-text changes still
encode the complete final frame sequence; transition-range replacement is
planned but not yet claimed as executable. A conservative scene-tail removal
can stream-copy an exact number of approved prior video frames when all
remaining visual layers are unchanged and every removed visual layer begins at
or after the new end. If explicit music or SFX remain, VibeEdit rebuilds the
revised audio mix instead of cutting AAC packets, then verifies the exact video
frame count and prior artifact provenance. Mid-scene removal remains planned.

Install the Python beta directly from its GitHub release asset:

```bash
uv tool install https://github.com/Momenta-App/vibeedit-sdk/releases/download/v0.1.0-beta.4/vibeedit-0.1.0b4-py3-none-any.whl
```

Install the Node beta tarball in a project:

```bash
npm install https://github.com/Momenta-App/vibeedit-sdk/releases/download/v0.1.0-beta.4/vibeedit-0.1.0-beta.4.tgz
```

When downloading an existing release, use the checksum manifest distributed with that exact release:

```bash
shasum -a 256 -c SHA256SUMS
```

The build workflow emits future flat release manifests as `SHA256SUMS`.

Or clone and install the public source:

```bash
git clone https://github.com/Momenta-App/vibeedit-sdk.git
cd vibeedit-sdk
uv tool install .
```

From a Node project:

```bash
npm install github:Momenta-App/vibeedit-sdk
```

Or build and install the exact local artifacts:

```bash
uv build --out-dir dist/python
uv tool install dist/python/vibeedit-0.2.0b1-py3-none-any.whl
npm pack --pack-destination dist/npm
npm install ./dist/npm/vibeedit-0.2.0-beta.1.tgz
```

`setup` performs only explicitly requested work. It installs pinned browser and
vision wheels into the current VibeEdit tool environment when missing. Browser
setup then installs Playwright's pinned Chromium revision, records the resolved
executable and SHA-256, and writes its manifest to the VibeEdit cache. On macOS,
vision setup compiles the bundled Swift source with Apple Vision, records the
binary SHA-256 and declared capability list, then downloads the exact portable
object model declared in `runtime-models/manifest.json`. SAM setup downloads
only its separately declared exact URLs, sizes, and SHA-256 values. No runtime
model is included in the base wheel or npm archive.

## Accelerated ordinary browser compositions

The Python package accepts normal bundled HTML/CSS/JS with local media. Chromium owns fonts, layout, graphics and composition. No CompositionSpec is needed for this workflow. On macOS 15+ ARM64, the CEF backend captures GPU surfaces, converts on Metal, and encodes opaque H.264 with VideoToolbox.

Install an exact qualified release wheel with the browser extra. Native setup requires FFmpeg, Xcode command-line tools, CMake, Ninja and Rust; it explicitly downloads the checksum-pinned CEF runtime and builds the bundled sources into the user cache:

```bash
vibeedit setup --cef --json
vibeedit examples create browser-composition ./projects
vibeedit render-browser ./projects/browser-composition/job.json --output ./movie.mp4 --backend cef --json
```

For portable Windows/Linux/macOS screenshot rendering:

```bash
vibeedit setup --browser --json
vibeedit render-browser ./projects/browser-composition/job.json --output ./movie.mp4 --backend screenshot --json
```

`vibeedit browser-worker --backend cef` accepts JSON lines containing `id`, `job`, and `output` to reuse a warm background browser. Python callers can import `CEFService` and `render_browser_job` from `vibeedit.browser_render`. The Node CLI delegates these commands to an installed Python package. Rendering does not download dependencies. Alpha exports use the screenshot fallback; native acceleration is currently macOS ARM64 only. See [the renderer guide](browser-renderer/README.md) for media preparation, timing adapters and performance evidence.

## One composition contract

All public APIs use `schema/composition.schema.json`. Timeline values are integer
frames and frame rates are rational numbers.

```python
from vibeedit import Canvas, Composition, FrameRate, MotionComponent, Placement, Track

composition = Composition(
    "title-card",
    Canvas(1920, 1080, FrameRate(30000, 1001)),
    90,
)
motion = composition.timeline.add_track(Track("M1", "motion", 10))
motion.add(
    MotionComponent(
        "title",
        Placement(0, 90),
        "vibeedit://text/negative",
        {"text": "NO EXCUSES"},
    )
)
composition.write("composition.json")
```

```js
import { Canvas, Composition, FrameRate, MotionComponent, Placement, Timeline, Track } from "vibeedit";

const timeline = new Timeline();
const motion = timeline.addTrack(new Track({ id: "M1", kind: "motion", order: 10 }));
motion.add(new MotionComponent({
  id: "title",
  placement: new Placement(0, 90),
  componentId: "vibeedit://text/negative",
  props: { text: "NO EXCUSES" },
}));
const composition = new Composition({
  id: "title-card",
  canvas: new Canvas({ width: 1920, height: 1080, frameRate: new FrameRate(30000, 1001) }),
  durationFrames: 90,
  timeline,
});
composition.validate();
```

MoviePy, FFmpeg, Playwright, OpenCV, ONNX, Torch, MLX, and platform APIs are
backend details. Their native objects never enter the public CompositionSpec.

Agents may supply raw HTML/CSS fragments or full documents through
`vibeedit://motion/html-css`. This preferred contract loads local fonts/assets,
automatically seeks CSS animations, rejects authored JavaScript, and includes a
composable Motion Atoms vocabulary. The broader executable path accepts an
inline HTML/CSS/JavaScript fragment or a complete locally bundled React, Vue,
Svelte, Three.js, PixiJS, Canvas, WebGL, or WebGPU project through
`vibeedit://motion/html` and
`vibeedit://motion/web-project`. The persistent Chromium renderer loads the
project once, waits for bundled fonts, and seeks it by integer frame. Run
`vibeedit inspect composition.json --json` to see routing and library details.
The complete authoring and deterministic-seek contract is documented in
[`docs/HTML_MOTION_RUNTIME.md`](docs/HTML_MOTION_RUNTIME.md).

## CLI

```text
vibeedit init
vibeedit setup
vibeedit doctor
vibeedit inspect
vibeedit catalog list|search|open
vibeedit motion atoms
vibeedit examples list|create
vibeedit skills list|install|check|update|remove
vibeedit validate
vibeedit preview
vibeedit render
vibeedit verify
vibeedit clean
vibeedit mcp
```

Commands return actionable errors and support `--json` where automation
benefits. Run a verified example with:

```bash
vibeedit examples create effect-transition
python effect-transition/render.py

vibeedit examples create mixed-python-html
python mixed-python-html/render.py

vibeedit examples create fan-edit
python fan-edit/render.py

vibeedit examples create face-follow-text
python face-follow-text/render.py
```

The local catalog stays in the background by default:

```bash
vibeedit catalog open --json           # resolve its packaged path; no tab
vibeedit catalog open --browser        # explicitly open a visible browser tab
```

The same example inventory is available without shell orchestration:

```python
from vibeedit import create_example, render_example

directory = create_example("fan-edit")
render_example(directory)
```

```javascript
import { createExample } from "vibeedit";

createExample("portable-motion-showcase");
```

Sixteen packaged examples cover generated assembly, effects/transitions,
talking-head captions, portable kinetic typography, mixed media/HTML, a fan
edit, beat analysis, layered sound design, a generated elliptical mask effect,
tracking-driven face-follow text, multiple transitions, a VP9 alpha overlay,
and conditional SAM 2.1 candidate review. Generated examples demonstrate
rendering and composition; they do not establish real footage segmentation or
editorial quality. The SAM example stops for candidate review and writes
actionable evidence when its runtime is unavailable. Actual SAM 2.1 and SAM 3.1
MLX model runs, persisted mask corrections, and reviewed subject-effect renders
use the separate `vibeedit models` workflow; their inference qualification
remains open.

## Catalog and skills

All 445 shipped capabilities have a stable `vibeedit://` identifier, parameter
schema, platforms/backends, provenance, validation evidence, example code,
agent prompts, and an explicit preview state.

```bash
vibeedit catalog search stutter --json
vibeedit catalog open                 # print the local catalog path; no browser tab
vibeedit catalog open --browser       # explicitly open the catalog in a browser
vibeedit skills install vibeedit-workspace --harness codex
```

Skill install/update/remove operations track versions and checksums. They refuse
to overwrite or remove user-modified skill files. The bundle contains 44 public
skills adapted for the portable SDK from pinned canonical Git sources and records 23
rejected source skill packages with quarantine reasons in
`skills/migration-report.json`. Packaging metadata remains outside the cloned
skill directories. Each adaptation records its original source identity and
the checksum of the adapted package.

## Local tool server

`vibeedit mcp` starts a local stdio JSON-RPC/MCP-compatible adapter exposing
catalog search, media inspection, composition creation, effects, transitions,
motion, SFX placement, render, and verification. It calls the same library used
by the CLI; it is not a separate implementation.

## Reproducibility and security

Rendering uses integer-frame plans, normalized constant-frame-rate inputs,
deterministic seeded effects, explicit runtime capability checks, safe subprocess
argument arrays, content-based cache keys, and output probes. HTML components
run locally with no network requirement. Catalog data is never executed as code.

See `docs/SECURITY.md`, `docs/ARCHITECTURE.md`, `SBOM.spdx.json`, and
`THIRD_PARTY_NOTICES.md` for boundaries and inventories.

## License

VibeEdit's owned package code, skills and templates use the MIT license in
`LICENSE.md`. Fonts, optional model weights and third-party runtimes retain their
own terms, recorded in `THIRD_PARTY_NOTICES.md` and `SBOM.spdx.json`.
Myriograph is a separately metered service; package installation includes no paid
inference credit. Earlier release legal records are historical evidence.
