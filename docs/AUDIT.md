# VibeEdit Production Package Audit

Status: repository-grounded migration audit, updated 2026-07-13.

## Release ownership

This standalone repository is the release-package root for the existing
unscoped `vibeedit` npm package and the VibeEdit Python distribution. It was
prepared from the isolated package work in the legacy desktop repository
without rewriting or cleaning unrelated source-worktree changes.

The package root will contain both ecosystems:

- `package.json`, `src/`, and `bin/` for the Node/HTML runtime.
- `pyproject.toml` and `python/src/vibeedit/` for the Python distribution.
- `schema/` as the only hand-authored CompositionSpec source.
- `catalog/`, `skills/`, `examples/`, and `site/` as shared package data.

## Existing source inventory

### Python media API

The main VibeEdit repository contains a tracked, tested package at
`packages/sdk/python/vibeedit_media`. It is approximately 5,200 lines of Python
excluding generated data and includes:

- Canvas, project, section, transition, and timeline helpers.
- FFmpeg/FFprobe command execution and capability probes.
- Optional NumPy, Pillow, OpenCV, MoviePy, Manim, and Blender adapters.
- Deterministic image effects and transition-frame helpers.
- A generated preset catalog and tests.

It is also copied into the packaged desktop media runtime. Those copies are
derived artifacts, not canonical migration sources. Its current public timing
model uses floating-point seconds and integer FPS, so it does not become the new
public contract. The tracked package is instead vendored byte-for-byte under its
original `vibeedit_media` namespace, while the new frame-based `vibeedit` API
remains the public adapter and contract.

### Effect and transition catalogs

The main repository has one canonical 333-entry Python preset catalog mirrored
into the desktop app: 200 filters, 112 effects, and 21 transitions. Its
VibeEdit-owned NumPy implementations and source tests are the migration source;
the app JSON is a duplicate consumer. `scripts/import_media_presets.py` clones
all 16 tracked files from the canonical package without modifying them, verifies
their hashes, executes all 333 implementations, and only then records passing
validation evidence. Stable `vibeedit://` IDs and public examples are applied by
the separate `vibeedit.presets` and catalog adapters, not written into the
canonical preset files.

### HTML motion and text effects

The desktop app has 24 top-level text-effect component families under its
public text-effect catalog. The importer reads tracked revision
`2403e3f94cfabf7236d5401bd4beeadefde1d725`, not dirty working files. It adapts
20 caption/text vocabularies into dependency-free seekable components and
packages 30 selected VibeEdit HTML/CSS/JS motion-title renderers. Fifteen remain
source-identical apart from the text-override/transparent-compositing adapter;
fifteen contain approved beta refinements recorded in the runtime manifest.
Required local fonts and design assets are included; live CDNs, previews,
external media, and MOGRT binaries are not copied. A three-frame source
comparison passes all 15 unmodified canonical entries (13 pixel-identical, two
perceptually equivalent).

### Skills

The main repository currently has 33 top-level `.agents/skills` packages and
67 top-level `.codex/skills` packages, plus generated/imported OpenCode copies.
Names overlap but byte identity is not a reliable canonicality signal. The
tracked `.codex/skills` tree at revision
`57b5f4cb3381f72b5ba153bb90d171ba42945e3a` is the canonical source. The
importer selected 44 VibeEdit production skills without absolute paths or
unverified binary assets and rejected 23 aliases, unrelated packages,
absolute-path workflows, or unverified audio packages. Every selected directory
is copied byte-for-byte and retains its Git executable modes. Package manifests,
catalog entries, and install tracking remain outside the skill content.
`skills/migration-report.json` records every decision and matching source/package
checksum. No package-only replacement skill is included.

### Sound effects

Multiple workspaces contain WAV/MP3 assets and sound-design manifests, but most
media files do not yet have release-grade redistribution evidence. No ordinary
recording is included in the base package during the vertical slice. The first
SFX family is procedural and its manifest explicitly records that provenance.
Recorded audio remains quarantined until source, license, commercial-output
rights, checksum, duration, loudness, and decode validation are complete.

### Vision and segmentation

Existing sources include Apple Vision/Swift integration, portable Python
analysis workers, SAM 2.1 skills, SAM 3.1/MLX workflows, and local model
manifests. The public capability router now provides OpenCV face detection,
centroid face tracking, HOG person/body detection, a packaged VibeEdit-owned
Swift runner that explicitly declares Apple Vision face/body/pose operations,
the checksum-pinned portable SSD-MobileNetV1 ONNX object detector, and
checksum-declared segmentation providers. An external Apple runner can also
expose general objects only by declaring that capability; the bundled runner
does not. No local model is copied. Explicit setup downloads official SAM 2.1
source and tiny weights after exact size/SHA verification. SAM 3.1 remains
quarantined.

## Duplication policy

- Hand-authored CompositionSpec lives only in `schema/composition.schema.json`.
- Language types, documentation tables, and catalog indexes are generated or
  validated from canonical JSON data.
- Desktop runtime copies are build outputs.
- OpenCode skill-import mirrors are build outputs.
- Source effects keep a provenance record naming the original VibeEdit file,
  implementation version, and any third-party algorithm or dependency.
- Canonical preset clones retain matching source/package SHA-256 values and a
  deterministic aggregate output hash in `catalog/preset-validation.json`.
- No recorded media enters package files without a passing provenance audit.

## Worktree safety

Both migration-source repositories contain unrelated modified and untracked
files. This package does not rewrite or clean those changes. Migration tools
read from explicit allowlisted source paths and write only inside this
standalone repository.
