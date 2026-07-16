# Release Gap Register

This register distinguishes implemented claims from discovered source material.

| Area | Current state | Release gate |
| --- | --- | --- |
| CompositionSpec | Legacy projects use seconds and multiple shapes | Schema, compatibility tests, and cross-language fixtures pass |
| Python distribution | Reusable `vibeedit_media` exists under another public name | VibeEdit-owned API, CLI, wheel/sdist, clean install, and real render pass |
| npm runtime | Placeholder metadata package | Runtime exports, CLI, declarations, tests, and `npm pack --dry-run` pass |
| HTML rendering | 30 selected effects use their packaged VibeEdit HTML/CSS/JS renderer families; 20 use the portable runtime | Source comparison passes all 15 unmodified canonical entries; 15 approved refinements and all 52 registered effects pass browser conformance; fallback seek hashes, tracking interpolation, injection checks, pinned-Chromium video, and VP9-alpha example pass |
| Effects/transitions | 333 reviewed canonical presets are cloned byte-for-byte behind VibeEdit-owned adapters | Stable IDs, separate manifests, matching source/package hashes, exhaustive frame execution, and effect/transition/mask examples pass |
| Skills | 67 tracked canonical skill directories were audited | 44 byte-identical release-safe clones install into four harness layouts; 23 rejected packages remain recorded/quarantined |
| SFX | Many local recordings with incomplete rights evidence | Exclude/quarantine until license, rights, decode, loudness, and checksum pass |
| Vision | OpenCV providers, a packaged VibeEdit-owned Apple Vision runner, and a pinned portable ONNX object detector exist | Face/body/pose pass on macOS Apple Silicon; portable OpenCV/ONNX dependencies and degradation behavior pass on Linux ARM64 and hosted Linux x86_64/Windows; 0.1 documents pose as macOS-native; macOS Intel returns a tested structured unsupported result for the unavailable ONNX Runtime wheel while its remaining portable checks pass |
| SAM 2.1 | Official source and tiny weights are approved as an optional setup download | Exact URL/size/SHA, clean standalone `sam` extra, safe extraction, provider routing, controlled/natural 30-frame Torch/MPS visual proofs, and the verified 60-frame packaged example pass; evidence is retained in `docs/evidence/sam21-public-proof.json` |
| SAM 3.1 | Local research workflows/models exist | Remains quarantined until source, weights, redistribution, setup, and independent inference proof pass |
| MCP | Existing product MCP infrastructure is unrelated | Adapter over the library passes typed tool smoke tests |
| Catalog site | Desktop catalog UI/data exists | Static generation, search/filter/copy, local open, and missing-preview states pass |
| Licensing | The legacy npm placeholder says `UNLICENSED`; earlier Python source said MIT | The standalone beta uses explicit custom terms; the release owner approved included VibeEdit material and confirmed open-source integrations retain their own terms and ownership |
| Platform proof | macOS Apple Silicon and Dockerized Linux ARM64 have clean exact-artifact proofs; native GitHub-hosted Linux x86_64 on Python 3.11/3.12/3.13, Windows, macOS Intel, and macOS Apple Silicon portable suites and package smoke installs pass | Retain the hosted run, archive checksums, and exact clone/preset audit with the release handoff |
| Public access | GitHub repository is public; unauthenticated API access, credential-disabled clone, and branch-archive download pass | Retain `scripts/check_public_access.py` and public clone/archive checks in release evidence |
| Registry publication | GitHub prerelease is public and validated; the guarded OIDC workflow and protected `registry-beta` environment are ready; PyPI currently has no `vibeedit` project and npm `latest` remains the legacy `0.0.1` placeholder | An owner must configure the PyPI and npm trusted publishers; then publish and clean-install `vibeedit` from PyPI and `vibeedit@beta` from npm |

## Immediate quarantine list

- Recorded music, dialogue, movie clips, reference-corpus extracts, downloaded
  SFX, and model weights in release archives. The approved SAM 2.1 tiny weight
  is downloaded only by explicit setup into the user cache.
- Source with unclear ownership or a third-party noncommercial license.
- Modified source-tree HTML components until their intended revision is known.
- Absolute developer-machine paths and private service URLs.
