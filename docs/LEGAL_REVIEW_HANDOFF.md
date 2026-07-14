# Release-owner rights and review record

Status: **public beta approved on 2026-07-14**

This document records the release-owner determination supplied for the public
beta and organizes the supporting engineering evidence. It does not claim
ownership of third-party projects or expand their licenses. Production and
commercial-release decisions remain separate from this testing release.

## Review scope

The candidate is VibeEdit 0.1.0 beta 1 in the public
`Momenta-App/vibeedit-sdk` source repository. It contains a Python package, an
npm package, a shared schema and catalog, generated preview assets, and
byte-identical selections from the canonical VibeEdit skill and media-preset
trees. Optional browser and model payloads are downloaded only after an
explicit setup command; they are not included in the package archives.

Counsel should review the exact source revision and build artifacts supplied
with the release handoff. GitHub Actions produces SHA-256 sums, an archive
audit, and build-provenance attestations for the wheel, Python source archive,
and npm archive.

## Release-owner determinations

1. Public beta publication is approved for testing and community review.
2. The 13 hash-bound preview/audio assets are entirely VibeEdit-generated and
   contain no third-party movie clips, music, dialogue, images, or recordings.
3. The 44 included canonical VibeEdit skills and 16 canonical media-preset
   source files are approved for distribution and remain byte-identical.
4. The named external projects are approved open-source integrations or
   suggested workflows. VibeEdit does not claim ownership of them, and their
   upstream terms remain in effect.
5. Optional Chromium, SSD-MobileNet, and SAM 2.1 payloads are not shipped in
   the package archives; explicit setup downloads pinned payloads and preserves
   their notices. SAM 3.1 remains quarantined.
6. `LICENSE.md` remains the controlling VibeEdit-owned-material terms;
   commercial use requires a separate commercial license.

## Evidence index

| Evidence | Purpose |
| --- | --- |
| `LICENSE.md` | VibeEdit terms for public beta evaluation and community testing |
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

## Release record

The release owner should retain a written record containing:

- review date, reviewer, firm or organization, and jurisdictions considered;
- exact Git commit and artifact SHA-256 values reviewed;
- the release-owner determinations above;
- approved `LICENSE.md` and notice revisions, if any;
- whether public source, npm, PyPI, GitHub Release, static-site deployment, and
  commercial distribution are separately permitted;
- restrictions or required attribution for optional browser, vision, and SAM
  setup flows; and
- unresolved items, expiry/re-review conditions, and the person authorized to
  approve release.

Engineering must regenerate the SBOM if dependency or license metadata changes,
rebuild all artifacts, rerun the public workflow, and retain the resulting
checksums and attestations for every beta revision.
