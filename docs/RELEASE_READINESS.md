# Release readiness report

Date: 2026-07-13  
Candidate: VibeEdit 0.1.0  
Decision: **NOT READY FOR PUBLICATION**

The candidate is a functional local package, not a scaffold. It now includes
the expanded reusable VibeEdit inventory and locally verified production
workflows. Publication remains withheld because Windows, Linux x86_64, and
macOS Intel jobs have not actually run and the custom license/model notices
have not been reviewed by qualified counsel. Pose support in 0.1 is explicitly macOS-native;
SAM 3.1 remains quarantined rather than claimed. No npm/PyPI publication,
website deployment, GitHub release, or production rollout occurred.

## Candidate inventory

| Surface | Included and verified |
| --- | --- |
| Media presets | 333: 200 filters, 112 effects, 21 transitions |
| Motion runtime | 74 tracked text/caption/MOGRT adaptations plus the two baseline components |
| Skills | 44 byte-identical clones selected from the canonical tracked tree; 23 rejected/quarantined |
| Examples | 13 executable examples; 12 render locally or are baseline recipes, 1 is capability-gated SAM |
| Catalog | 467 searchable items with stable IDs, prompts, code, compatibility, provenance, and validation |
| Assets | 13 generated, hash-bound, decodable preview/audio assets |
| Tooling | Python and Node CLIs, four-harness skill lifecycle, static site, and 10-tool local MCP adapter |

The Python API owns composition, media rendering, external audio mixing, beat
analysis, masks, effects, transitions, tracking, sound design, caching,
verification, catalog, skills, and setup. The JavaScript package owns the same
schema, catalog identifiers, skill data, deterministic seekable HTML motion
runtime, tracking-keyframe interpolation, browser frame renderer, and Node CLI.
No MoviePy or HyperFrames object is public API.

## Rendering and workflow evidence

- FFmpeg renders generated media and one/two-source timelines with integer-frame
  trim, seeded stutter, crossfade, external audio clips, gain, pan, fades,
  procedural SFX, constant-frame-rate normalization, and deterministic metadata.
- Chromium renders seekable local HTML with escaped content and no network
  dependencies. Mixed source-video/HTML and VP9 alpha-overlay examples pass.
- All 333 preset implementations execute deterministic RGBA frames. The
  aggregate canonical-runtime SHA-256 is
  `0950fc8ce189dd897b35bb4f5f9da5f8d9466c315c5a273cb91622a5e8e7bad7`.
- Representative cinematic-filter, invert, cross-dissolve, film-burn, and
  push-transition frames match fixed pixel goldens and exceed perceptual-delta
  floors against their inputs.
- All 74 portable motion adaptations seek at two frames in Python and
  JavaScript with aggregate cross-runtime SHA-256
  `1cf1537e50444f0499e07384eeaaaed27ba9bcd2a1947ef66870c22dc55bedb1`.
- Clean-copy examples pass for fan editing, beat analysis/synchronization,
  layered sound design, mask-confined subject treatment, face-following text,
  multiple transitions, and transparent overlays. Talking-head captions,
  kinetic typography, effect/transition, generated assembly, and mixed
  Python/HTML examples also pass.
- The conditional SAM example writes an actionable unavailable report when no
  provider is configured. With the clean-installed public provider it produced
  60 mask frames and a verified 320×180, 30 fps, 60-frame MP4 with zero drift.

## Vision and models

Verified lightweight providers:

- OpenCV Haar face detection.
- Deterministic normalized face tracking with stable centroid IDs.
- OpenCV HOG person/body detection.
- Packaged VibeEdit-owned Swift/Apple Vision runner for face, body, and pose.
- Portable SSD-MobileNetV1-12/ONNX Runtime general-object detection.
- Capability-declared external Apple-runner contract for general objects.
- Checksum-declared external SAM provider execution and rejection of incomplete
manifests.

The Apple runner builds from the wheel's bundled Swift source during explicit
`setup --vision` on supported macOS. A real release build, isolated-cache CLI
setup, capability probe, and blank decoded-image face/body/pose requests passed
on macOS Apple Silicon. Setup records the compiled executable SHA-256 and its
declared `face`, `body`, and `pose` list. The bundled runner does not claim
general-object detection, so that request falls through to the portable ONNX
provider.

Explicit `setup --vision` also downloads the 29,461,455-byte SSD-MobileNetV1-12
checkpoint pinned to commit
`019281f3fcb151a90e491f3b2f0273f9f31bd6be`, SHA-256
`b8fba5e404077d4048d27fcd1667e85e27e192eb9bf51e696c46a3acd7d21058`.
ONNX Runtime 1.27 detected normalized `person` and `chair` boxes on the natural
validation image; the person confidence was 0.879. Setup and inference evidence
is retained in `docs/evidence/object-onnx-proof.json`. The model card states MIT,
the repository metadata states Apache-2.0, and COCO dataset terms apply, so the
notice remains a legal-review item. The checkpoint is not in release archives.

Optional SAM 2.1 setup declares and verifies:

| Payload | Bytes | SHA-256 |
| --- | ---: | --- |
| Official source revision `2b90b9f5ceec907a1c18123530e92e794ad901a4` | 55,645,345 | `1f2fbfad3ffa38110368abac76c6ef9df9c282a66d5c2807bc94abf4d2fb30f8` |
| Official Hiera Tiny checkpoint | 156,008,466 | `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69` |

Both official payloads are Apache-2.0 and total 211,653,811 bytes before the
pinned Python inference dependencies. They are downloaded only by explicit
`setup --sam`/`setup --all`, safely extracted into the VibeEdit cache, and never
included in release archives. The runner selects CUDA, MPS, then CPU and emits
frame-indexed RLE masks with model/source/prompt/cache provenance.

A fresh exact-wheel proof now passes for SHA-256
`07c3e08e3e85b8880c2a681b1d40c44dabac2f043617782f25abfeafc0eb554e`.
After reclaiming only generated temporary files and package caches, the host
met the 25 GiB safety gate. Standalone
`vibeedit[sam]` installation, exact `setup --sam`, a controlled 30-frame
180-high clip, a natural 30-frame 180-high person clip, and the packaged
60-frame example all ran through Torch 2.12/MPS. Visual review accepted both
30-frame masks with zero empty frames; the controlled clip reached IoU,
precision, and recall of 1.0 against its known target. Repeating the natural
run with identical parameters produced a true cache hit and byte-identical
mask. Each model process reported zero swaps. Runtime/device versions enter
both mask provenance and cache keys. The hash-bound evidence record is
`docs/evidence/sam21-public-proof.json`. SAM 3.1 remains quarantined.

A fresh `[all]` environment with an empty VibeEdit cache also passes unified
`setup --all` with `complete: true`. It prepares effects, the compiled Apple
runner, the portable object model, and SAM, and verifies the host-global pinned
Chromium payload. Doctor then reports every intended 0.1 capability above as
available and only SAM 3.1 as quarantined. The browser payload already existed
in Playwright's host-global cache, so this run is not mislabeled as a clean-host
Chromium download. Missing-browser installation remains covered by setup tests.
The two declared model payloads total 241,115,266 bytes, excluding Chromium and
Python wheels. The sanitized ledger is
`docs/evidence/full-setup-proof.json`.

## Verified platforms

| Platform | Status | Evidence |
| --- | --- | --- |
| macOS Apple Silicon | Locally verified | Source tests, exact wheel/npm clean installs, FFmpeg 8.1.1, Chromium/Playwright 1.61.0, OpenCV providers, native Apple Vision build/setup/requests, portable ONNX object inference, clean SAM 2.1 setup/inference/visual review, examples, and artifact audits passed. |
| Linux ARM64 | Locally verified in Docker | Debian 12/aarch64, Python 3.11.2, Node 22.23.1, FFmpeg 5.1.9, pinned portable vision wheels, Playwright 1.61.0/Chromium 1228, 17 Node tests, 60 Python tests, exact wheel/npm installs, and core/mixed renders passed. The sole Python skip was the intentionally macOS-only Apple Vision build. |
| macOS Intel | Workflow declared, not executed | Portable matrix job exists but has no recorded run. |
| Linux x86_64 | Emulated artifact smoke passed; native workflow not executed | Under Docker `--platform linux/amd64`, the exact wheel/npm installed, doctor reported `linux/x86_64`, and a 60-frame audio/video render passed with zero drift. Native matrix jobs for Python 3.11/3.12/3.13 still have no recorded run. |
| Windows | Workflow declared, not executed | Portable matrix job exists but has no recorded run. |

The Linux ARM64 proof is retained in
`docs/evidence/linux-arm64-proof.json`; the explicitly limited x86_64 emulation
proof is in `docs/evidence/linux-amd64-emulated-proof.json`. The workflow was
corrected to reference real test files, install its test and browser extras,
install pinned Chromium on every matrix OS, and use GitHub's current
`macos-15-intel` label alongside the Apple-Silicon `macos-latest` job. Emulation
and unexecuted workflows are still not native proof for the remaining matrix
targets.

## Local publishable artifacts

The wheel, source distribution, and npm tarball are built locally, then
clean-installed and extracted for audit. Final sizes, entry counts, and SHA-256
values belong in the external build handoff beside the archives rather than
inside a packaged document that would make its own hashes stale.

Artifact extraction scans found no developer-machine paths,
secret/private-key patterns, `.pt`/`.pth`/`.safetensors`/`.onnx` weights,
unapproved MP3 assets, Python bytecode, rewritten preset copies, or the removed
package-only skill. Every included asset manifest reports verified
redistribution and decoding. The npm archive preserves executable modes.

## Validation commands and results

Run from the repository root unless a path is absolute:

```bash
.venv/bin/pytest -q
# 61 passed

npm test
# 17 passed

npm run types:check
# passed

npm run validate
# {"ok":true,"version":"0.1.0","catalogItems":467,"skills":44,"assets":13}

.venv/bin/python -m build --outdir /tmp/vibeedit-python-release
# wheel and sdist built through isolated PEP 517 environments

npm pack --pack-destination /tmp/vibeedit-npm-release --json
# npm tarball built; no publication
```

Clean core wheel validation installed only the exact wheel and its base dependencies,
enumerated 467 catalog items, 44 skills, 74 motion components, 333 presets, and
13 examples, then rendered and verified the packaged generated example with
real audio/video and zero frame drift. The same clean wheel ran explicit vision
setup, compiled the packaged Swift source, and returned the exact
`face`/`body`/`pose` declaration. The exact wheel's standalone `sam` extra and
setup completed, reproduced the accepted natural mask byte-for-byte on MPS,
and retained a verified 60-frame example ledger. Clean optional-runtime validation installed
`[effects,browser]`, ran explicit setup, and rendered/verified the packaged mask
and face-follow examples. Clean npm validation imported the exact tarball,
validated CompositionSpec, searched catalog data, loaded all skills/motion
components, exercised tracking interpolation, and reported zero npm audit
vulnerabilities. MCP tests cover initialize, list, catalog invocation, and
composition editing over the underlying library.

## Definition-of-success audit

| # | Status | Evidence or remaining gate |
| ---: | --- | --- |
| 1 | Pass on verified platform | Lightweight wheel and npm tarball install in clean environments. |
| 2 | Pass on verified platform | Effects/browser/vision setup passes cleanly; standalone SAM setup downloads/verifies the exact payloads and controlled/natural inference passes through MPS. |
| 3 | Pass | Doctor reports exact installed/missing media, motion, face, tracking, body, pose, object, segmentation, and SAM capabilities. |
| 4 | Pass | Python users construct and render through VibeEdit-owned APIs. |
| 5 | Pass on verified platform | JavaScript/Python motion seeks deterministically and Chromium produces real outputs. |
| 6 | Pass on verified platform | One CompositionSpec combines source media, HTML overlay, source audio, and SFX with zero frame drift. |
| 7 | Pass on verified platform | Verified examples exist for every locally enabled major family, including fresh accepted public-runner SAM output. |
| 8 | Pass | Effects, transitions, text, SFX, skills, and templates share one 467-item catalog. |
| 9 | Pass | Packaged `catalog open --no-browser` resolves the generated local site. |
| 10 | Pass | Site copy controls use canonical IDs, prompts, Python, and JavaScript strings. |
| 11 | Pass | Forty-four byte-identical canonical skills install/check/update/remove across agent, Codex, Claude, and OpenCode layouts without overwriting user edits. |
| 12 | Pass | Ten MCP tools list and execute through the underlying library. |
| 13 | Pass on verified platform | Face/body/tracking, macOS-native pose, portable ONNX objects, SAM 2.1 setup/inference, and structured degradation all operate; 0.1 documents pose as macOS-native. |
| 14 | Pass for included assets | Included audio is VibeEdit-generated and hash/provenance/loudness/decode audited. |
| 15 | Partial | Local macOS ARM64 and Linux ARM64 builds, installs, renders, catalog, skills, assets, and license scans pass; Linux x86_64/Windows/macOS Intel execution and legal review remain. |
| 16 | Pass | npm/Python 0.1.0 share CompositionSpec 1.0.0 and catalog/skill compatibility policy. |
| 17 | Pass for audited artifacts | No secrets, absolute developer paths, bundled weights, unapproved media, or undocumented downloads were found. |
| 18 | Pass | This report records inventory, platforms, sizes, downloads, commands, gaps, and licensing concerns. |
| 19 | Pass | Nothing was published, deployed, or released. |

## Remaining release blockers

1. Execute and retain the Linux x86_64, Windows, and macOS Intel workflow
   results, plus hosted macOS Apple Silicon artifact builds and clean installs.
2. Obtain qualified legal review of `LICENSE.md`, commercial-license wording,
   SAM/SSD-MobileNet/COCO terms, Chromium notices, imported skill content, and
   third-party dependency notices. The current license remains an engineering
   draft.

Publication approval must remain withheld until these gates are resolved or
the initial support scope is explicitly reduced and approved.
