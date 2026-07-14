# Legal review handoff

Status: **qualified counsel decision required**

This document organizes the engineering evidence for legal review. It does not
provide legal advice, change `LICENSE.md`, or assert rights that have not been
verified. Public registry publication, a GitHub Release, catalog deployment,
and commercial release remain withheld pending the decisions below and
separate product approval.

## Review scope

The candidate is VibeEdit 0.1.0 in the public
`Momenta-App/vibeedit-sdk` source repository. It contains a Python package, an
npm package, a shared schema and catalog, generated preview assets, and
byte-identical selections from the canonical VibeEdit skill and media-preset
trees. Optional browser and model payloads are downloaded only after an
explicit setup command; they are not included in the package archives.

Counsel should review the exact source revision and build artifacts supplied
with the release handoff. GitHub Actions produces SHA-256 sums, an archive
audit, and build-provenance attestations for the wheel, Python source archive,
and npm archive.

## Decisions requested

1. **VibeEdit terms.** Approve `LICENSE.md` or provide replacement wording for
   public inspection/download, personal evaluation, grants made in writing,
   commercial licensing, warranty/liability, termination, governing law, and
   contact language as applicable.
2. **Existing public-source state.** Confirm whether the current public GitHub
   source repository may remain available while registry, GitHub Release,
   catalog deployment, and commercial-release actions stay withheld.
3. **Canonical VibeEdit material.** Confirm Attention Engine's right to
   distribute the 44 byte-identical skill packages and 16 byte-identical
   media-preset source files identified by `skills/migration-report.json` and
   the package provenance audit. Engineering has not rewritten or relicensed
   those files.
4. **Preset provenance.** Review the disclosure that VibeEdit-owned preset
   implementations use public effect vocabulary and that some names/default
   concepts were informed by the MIT-licensed FreeCut project. No FreeCut
   WebGPU source is bundled.
5. **Optional runtimes and models.** Determine whether the notices and explicit
   download flow are sufficient for Playwright/Chromium, the ONNX Model Zoo
   SSD-MobileNetV1-12 checkpoint and COCO terms, and Meta SAM 2.1 source and
   weights. In particular, resolve the SSD-MobileNet model card's MIT statement
   against the model repository's Apache-2.0 metadata. SAM 3.1 is quarantined
   and is not claimed or downloaded.
6. **Generated assets and excluded media.** Confirm the proposed treatment of
   the 13 VibeEdit-generated, hash-bound preview/audio assets. No movie clips,
   music, dialogue, downloaded SFX, model weights, or other third-party
   recorded media are included in the release archives.
7. **Notices and inventory.** Confirm that `THIRD_PARTY_NOTICES.md`,
   `SBOM.spdx.json`, package metadata, model manifests, and asset provenance are
   sufficient, and identify any license texts, attribution, source-offer, or
   distribution obligations that must be added.

## Evidence index

| Evidence | Purpose |
| --- | --- |
| `LICENSE.md` | Current unapproved VibeEdit custom-license draft |
| `THIRD_PARTY_NOTICES.md` | Human-readable dependency, runtime, model, and provenance notices |
| `SBOM.spdx.json` | SPDX 2.3 package/dependency inventory and license expressions |
| `runtime-models/manifest.json` | Optional download URLs, versions, sizes, SHA-256 values, and license notes |
| `catalog/assets.json` | Source, license, hash, decode, duration, loudness, and usage data for packaged assets |
| `skills/migration-report.json` | Canonical source revision, selection/quarantine decisions, and skill-tree hashes |
| `catalog/preset-validation.json` | Canonical preset-source hashes and deterministic execution evidence |
| `docs/AUDIT.md` | Source ownership, canonicality, exclusions, and migration approach |
| `docs/GAPS.md` | Quarantined material and explicit unsupported claims |
| `docs/RELEASE_READINESS.md` | Platform, package, validation, and definition-of-success evidence |
| `docs/evidence/` | Hash-bound setup, vision, SAM, and cross-platform proof records |
| `.github/workflows/vibeedit-package.yml` | Build, clean-install, archive-audit, checksum, and attestation procedure |

The archive audit separately proves that all packaged skills and preset-source
files match their pinned canonical digests and that forbidden media, model
weights, developer paths, key material, and unapproved file types are absent.

## Requested decision record

The release owner should retain a written record containing:

- review date, reviewer, firm or organization, and jurisdictions considered;
- exact Git commit and artifact SHA-256 values reviewed;
- disposition of each numbered decision above;
- approved `LICENSE.md` and notice revisions, if any;
- whether public source, npm, PyPI, GitHub Release, static-site deployment, and
  commercial distribution are separately permitted;
- restrictions or required attribution for optional browser, vision, and SAM
  setup flows; and
- unresolved items, expiry/re-review conditions, and the person authorized to
  approve release.

Engineering should apply counsel-provided text exactly, regenerate the SBOM if
package metadata changes, rebuild all artifacts, rerun the public workflow,
and retain the resulting checksums and attestations before changing the release
decision.
