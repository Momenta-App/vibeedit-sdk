# Release readiness report

Date: 2026-07-16
Candidate: VibeEdit 0.1.0 beta 2 (unreleased)
Decision: **PUBLIC BETA APPROVED FOR TESTING AND COMMUNITY REVIEW**

The candidate is a functional package, not a scaffold. It includes
the expanded reusable VibeEdit inventory and locally and GitHub-hosted verified
production workflows. The release owner approved public beta publication and
confirmed that the generated previews contain no third-party material, the
included canonical VibeEdit material is authorized, and optional open-source
integrations retain their own ownership and terms. Pose support in 0.1 is
explicitly macOS-native; SAM 3.1 remains quarantined rather than claimed.

## Current branch candidate verification

Commit `1244d0ac02272204d84247cd3a8a371ae5db7612` was rebuilt as the distinct
Python `0.1.0b2` and npm `0.1.0-beta.2` candidate after the Chromium/CEF
renderer hardening and text-catalog refinements. This is candidate verification
only; no new registry or GitHub release was published. The already-public
beta.1 remains immutable and retains its original artifacts.

The exact archives pass byte-level comparison against the pinned canonical
VibeEdit Git source: 44 skills and 16 preset source files match, and the archive
scanner found zero forbidden entries. A fresh Python 3.12 environment installed
the exact wheel with its browser extra, completed browser setup, initialized the
10-tool MCP server, resolved the packaged catalog site, and installed/checked a
Codex skill without modification. It rendered the generated 60-frame example
and the mixed source-video/Chromium/SFX 90-frame example with zero duration
drift. A fresh Node project installed the exact npm tarball, imported the API,
constructed and validated a CompositionSpec, searched the catalog, and reported
zero production vulnerabilities. The hash-bound record is
[current-candidate-proof.json](evidence/current-candidate-proof.json).
The same clean-artifact sequence is now implemented by
`scripts/smoke_release_artifacts.py` and runs in every portable workflow job,
so future Linux, Windows, Intel Mac, and Apple Silicon candidates must exercise
the exact wheel and npm archive rather than only report their version strings.

Hosted workflow run
[`29535644613`](https://github.com/Momenta-App/vibeedit-sdk/actions/runs/29535644613)
passed this exact-artifact gate for commit
`1244d0ac02272204d84247cd3a8a371ae5db7612` on Windows, Intel macOS, Apple
Silicon macOS, and Linux with Python 3.11, 3.12, and 3.13. The downstream
build-and-attest job also passed. Its uploaded wheel, source distribution, and
npm archive were downloaded again, re-audited against the canonical VibeEdit
Git source, and replayed through the clean-artifact smoke script locally. The
archive hashes and hosted job matrix are retained in
[current-candidate-proof.json](evidence/current-candidate-proof.json).

The accelerated CEF/Rust/Metal path remains experimental and is not the package
default. Its archive download is now pinned with SHA-256 and its background,
deterministic three-frame probe passes. Persistent Playwright/Chromium remains
the production fallback while high-resolution post-stress recovery is still
being developed.

## Public access gate

The package source is publicly downloadable from
`https://github.com/Momenta-App/vibeedit-sdk`. An unauthenticated GitHub API
request returns HTTP 200 with `visibility=public`; a credential-disabled Git
clone and the unauthenticated `main` branch archive download both pass. This is
distinct from npm or PyPI publication, which has not occurred.

Recheck the goal-wide access requirement without credentials:

```bash
python3 scripts/check_public_access.py --repo Momenta-App/vibeedit-sdk
# exit 0; publiclyDownloadable=true; status=public; httpStatus=200
```

The `0.1.0-beta.1` GitHub prerelease is explicitly approved. npm/PyPI registry
publication is also authorized as a beta when package-owner credentials are
available; catalog deployment and production rollout are separate actions.

On 2026-07-15, the exact GitHub release wheel, source distribution, and npm
tarball were downloaded without repository credentials and installed in clean
Python and Node environments. Python doctor reported core rendering ready and
the packaged generated example produced a verified 640×360, 30 fps, 60-frame
H.264/AAC MP4. Node doctor passed, catalog search and CompositionSpec validation
passed, and the production dependency audit reported zero vulnerabilities. The
flat and workflow-relative checksum layouts both verified. The hash-bound
record is [public-beta-install-proof.json](evidence/public-beta-install-proof.json).

## Candidate inventory

| Surface | Included and verified |
| --- | --- |
| Media presets | 333: 200 filters, 112 effects, 21 transitions |
| Motion runtime | 30 selected VibeEdit HTML/CSS/JS effects, 20 portable-runtime text/caption effects, and two baseline components |
| Skills | 44 byte-identical clones selected from the canonical tracked tree; 23 rejected/quarantined |
| Examples | 13 executable examples; 12 render locally or are baseline recipes, 1 is capability-gated SAM |
| Catalog | 443 searchable items with stable IDs, prompts, code, compatibility, provenance, and validation |
| Assets | 65 generated, hash-bound, decodable preview/audio assets: the original 13 plus 52 text-effect previews |
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
- All 50 imported motion implementations seek at two frames in Python and
  JavaScript with aggregate cross-runtime SHA-256
  `c096094e8e9a2f75097dacc96d9d84a1099a57170de7408ea8d4169fe338cedf`.
- All 15 unmodified packaged canonical HTML/CSS/JS effects were compared to the
  tracked source at three timeline points: 13 are pixel-identical and two are
  perceptually equivalent browser-font rasterizations above SSIM 0.95. Fifteen
  approved refinements intentionally diverge and pass browser conformance.
- All 52 registered text effects (50 imported components plus the two
  baseline components) have verified, hash-bound, decodable MP4 previews. The
  browser suite checks deterministic frames, visible pixels, expected DOM
  text, in-frame geometry, temporal motion where required, blocked networking,
  browser errors, and full 48-frame decode. The visual evidence is retained in
  `docs/evidence/text-effects/`.
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
| macOS Apple Silicon | Locally and GitHub-hosted verified | Source tests, exact wheel/npm clean installs, FFmpeg 8.1.1, Chromium/Playwright 1.61.0, OpenCV providers, native Apple Vision build/setup/requests, portable ONNX object inference, clean SAM 2.1 setup/inference/visual review, examples, and artifact audits passed. The hosted Python 3.12 portable checks and package smoke installs also pass. |
| Linux ARM64 | Locally verified in Docker | Debian 12/aarch64, Python 3.11.2, Node 22.23.1, FFmpeg 5.1.9, pinned portable vision wheels, Playwright 1.61.0/Chromium 1228, 17 Node tests, 60 Python tests, exact wheel/npm installs, and core/mixed renders passed. The sole Python skip was the intentionally macOS-only Apple Vision build. |
| macOS Intel | GitHub-hosted verified | Python 3.12, Node 22, FFmpeg, Chromium, 78 Python tests with 1 intentional skip, 23 Node tests, type declarations, catalog validation, and exact wheel/npm workflow smoke pass. ONNX Runtime 1.27 has no macOS x86_64 wheel, so object-model setup returns a tested structured unsupported-platform result while the rest of the portable package remains available. |
| Linux x86_64 | Native GitHub-hosted verified | Python 3.11/3.12/3.13 jobs each pass 78 Python tests with 1 intentional skip, 23 Node tests, type declarations, catalog validation, Chromium rendering, and exact wheel/npm workflow smoke. The earlier emulated exact-artifact render also passed with zero drift. |
| Windows | GitHub-hosted verified | Python 3.12, Node 22, FFmpeg, Chromium, 77 Python tests with 2 intentional skips, 23 Node tests, canonical skill checksum validation, catalog validation, and exact wheel/npm workflow smoke pass. |

The Linux ARM64 proof is retained in
`docs/evidence/linux-arm64-proof.json`; the explicitly limited x86_64 emulation
proof is in `docs/evidence/linux-amd64-emulated-proof.json`. GitHub-hosted run
[`29305221241`](https://github.com/Momenta-App/vibeedit-sdk/actions/runs/29305221241)
retains the successful six-job portable matrix for commit `6d7bcc0`: native
Linux x86_64 on three Python versions, Windows, macOS Intel, and macOS Apple
Silicon. The workflow installs FFmpeg and pinned Chromium, runs both language
suites, and smoke-installs newly built wheel and npm archives on every target.
The build job also audits the final wheel, source distribution, and npm tarball
against the pinned canonical skill-tree and preset-file digests before upload;
an optional `--source-root` comparison retains the stronger byte-level check
against a canonical VibeEdit Git checkout when one is available.
The current exact-artifact matrix and build-and-attest proof is hosted in run
[`29535644613`](https://github.com/Momenta-App/vibeedit-sdk/actions/runs/29535644613).
Public workflow dispatches are configured to generate GitHub build-provenance
attestations. Every build also retains flat GitHub-release SHA-256 sums,
artifact-relative SHA-256 sums, and the uploaded workflow artifact.

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
# 76 passed, 3 skipped on the local macOS host

npm test
# 23 passed

npm run types:check
# passed

npm run validate
# {"ok":true,"version":"0.1.0-beta.2","catalogItems":443,"skills":44,"assets":65}

.venv/bin/python -m build --outdir /tmp/vibeedit-python-release
# wheel and sdist built through isolated PEP 517 environments

npm pack --pack-destination /tmp/vibeedit-npm-release --json
# npm tarball built; no publication
```

Clean core wheel validation installed only the exact wheel and its base dependencies,
enumerated 443 catalog items, 44 skills, 50 imported motion components, 333 presets, and
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
| 8 | Pass | Effects, transitions, text, SFX, skills, and templates share one 443-item catalog. |
| 9 | Pass | Packaged `catalog open --no-browser` resolves the generated local site. |
| 10 | Pass | Site copy controls use canonical IDs, prompts, Python, and JavaScript strings. |
| 11 | Pass | Forty-four byte-identical canonical skills install/check/update/remove across agent, Codex, Claude, and OpenCode layouts without overwriting user edits. |
| 12 | Pass | Ten MCP tools list and execute through the underlying library. |
| 13 | Pass on verified platform | Face/body/tracking, macOS-native pose, portable ONNX objects, SAM 2.1 setup/inference, and structured degradation all operate; 0.1 documents pose as macOS-native. |
| 14 | Pass for included assets | Included audio is VibeEdit-generated and hash/provenance/loudness/decode audited. |
| 15 | Pass | Local macOS ARM64/Linux ARM64 and hosted Linux x86_64/Windows/macOS builds, installs, renders, catalog, skills, assets, license scans, and release-owner rights review pass. |
| 16 | Pass | The unreleased npm `0.1.0-beta.2` and Python `0.1.0b2` identify the same candidate and share CompositionSpec 1.0.0 plus the catalog/skill compatibility policy. The existing public beta.1 retains its original immutable versions and artifacts. |
| 17 | Pass for audited artifacts | No secrets, absolute developer paths, bundled weights, unapproved media, or undocumented downloads were found. |
| 18 | Pass | This report records inventory, platforms, sizes, downloads, commands, gaps, and licensing concerns. |
| 19 | Pass | The source repository is public and public beta publication is explicitly approved; website deployment and production rollout remain separate actions. |

The objective's public-access requirement now passes through the public GitHub
source repository. Registry publication remains a separate withheld action.

The registry engineering path is now checked in as the manual, protected
`.github/workflows/vibeedit-registry-beta.yml` workflow. It republishes only the
already-attested GitHub prerelease archives after verifying their tag-bound
package identities, flat checksums, archive audit, and GitHub attestations. It
uses OIDC trusted publishing and accepts no long-lived registry token. As of
2026-07-15, PyPI still returns 404 for `vibeedit`, npm `latest` is the legacy
`0.0.1`, and this machine has neither registry credential. Registry install
commands therefore remain unproven. The protected `registry-beta` GitHub
environment now exists with a required reviewer and protected-branch policy;
an owner must still configure the two registry-side trusted publishers, approve
the environment, and run the separate dispatches. Each dispatch now waits for
the exact published version to become publicly resolvable and proves a clean
temporary install plus CLI version check before it can pass; an independent
`uv tool install`/`npm install` verification remains the final handoff check.

## Beta release gates

No content-rights or engineering blocker remains for the approved public beta.
The GitHub prerelease must use exact artifacts from a successful public
workflow run and retain its checksums, archive audit, and attestations. npm and
PyPI publication require package-owner credentials; final production or
commercial release remains a separate decision under `LICENSE.md`.
