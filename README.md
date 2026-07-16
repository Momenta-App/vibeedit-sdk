# VibeEdit

VibeEdit is a frame-accurate video-production library for AI coding harnesses.
It provides a VibeEdit-owned Python media API, a deterministic JavaScript/HTML
motion runtime, one shared CompositionSpec, a searchable local catalog, safe
skill installation, rendering, and output verification.

This public repository contains the unreleased VibeEdit 0.1.0 beta 2 source
candidate. The latest downloadable GitHub prerelease is the immutable beta 1.
Both have been validated locally and on GitHub-hosted Linux, Windows, and macOS
runners. These betas are for evaluation, testing, and community review; they are
not production-stability or commercial-use claims. Source, GitHub release assets,
and registry publication are separate channels with separate version identities.

## Install

The registry commands below are the intended registry experience. Until a
registry beta is published, install the attested GitHub prerelease artifacts or
the public source checkout instead.

Lightweight Python CLI and media orchestration:

```bash
uv tool install vibeedit
vibeedit doctor
```

Optional local runtimes:

```bash
pip install "vibeedit[effects]"
pip install "vibeedit[browser]"
pip install "vibeedit[vision]"
pip install "vibeedit[sam]"
pip install "vibeedit[all]"
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
recorded in `docs/evidence/sam21-public-proof.json`. SAM 3.1 remains quarantined.
No model weight is part of the base wheel or npm archive.

Node SDK, HTML motion runtime, and Node-facing CLI:

```bash
npm install vibeedit
npx vibeedit doctor --json
```

The Node package owns CompositionSpec, catalog, skills, and HTML motion APIs.
Media rendering commands bridge to an installed Python VibeEdit package. Run
`npx vibeedit doctor --json` to see both capabilities and exact next actions.

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

Install the Python beta directly from its GitHub release asset:

```bash
uv tool install https://github.com/Momenta-App/vibeedit-sdk/releases/download/v0.1.0-beta.1/vibeedit-0.1.0b1-py3-none-any.whl
```

Install the Node beta tarball in a project:

```bash
npm install https://github.com/Momenta-App/vibeedit-sdk/releases/download/v0.1.0-beta.1/vibeedit-0.1.0-beta.1.tgz
```

When downloading all three beta-1 release archives manually, place them beside
`SHA256SUMS.release` and verify before installing:

```bash
shasum -a 256 -c SHA256SUMS.release
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
uv tool install dist/python/vibeedit-0.1.0b2-py3-none-any.whl
npm pack --pack-destination dist/npm
npm install ./dist/npm/vibeedit-0.1.0-beta.2.tgz
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

Thirteen packaged examples cover generated assembly, effects/transitions,
talking-head captions, portable kinetic typography, mixed media/HTML, a fan
edit, beat analysis, layered sound design, a mask-confined subject effect,
tracking-driven face-follow text, multiple transitions, a VP9 alpha overlay,
and capability-gated SAM segmentation. Every non-SAM recipe renders from a
clean copy in the test suite; the SAM recipe writes actionable evidence when no
approved runtime is installed.

## Catalog and skills

All 467 shipped capabilities have a stable `vibeedit://` identifier, parameter
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
skills copied byte-for-byte from pinned canonical Git sources and records 23
rejected source skill packages with quarantine reasons in
`skills/migration-report.json`. Packaging metadata remains outside the cloned
skill directories.

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

`LICENSE.md` defines the terms for this publicly inspectable and downloadable
beta. Commercial use requires a separate license from Attention Engine Inc.
Third-party components remain under their own licenses and are not claimed as
VibeEdit property. The release-owner provenance determination and evidence are
recorded in `docs/LEGAL_REVIEW_HANDOFF.md`.
