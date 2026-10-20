---
name: vibeedit-python-analysis-rendering
description: Use Python and local analysis models to find fan-edit content, produce timing data, build masks, render A/B/C tests, and preserve reproducible VibeEdit artifacts.
---

# VibeEdit Python Analysis Rendering

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill when implementing a repeatable fan-edit formula with Python analysis and render scripts.

## Analysis Stack

Prefer local tools and models when possible:

- `ffprobe`/`ffmpeg` for metadata, audio extraction, frame extraction, transcodes, and muxing.
- `opencv-python` for frame IO, motion, optical flow, crops, transforms, overlays, and masks.
- `librosa` for beat, onset, RMS, and tempo analysis.
- `Pillow` for typography masks, strokes, shadows, and perspective text assets.
- Apple Vision for OCR, faces, people, rectangles, and layout checks on macOS.
- SAM 2.1/SAM 3.1 or available local segmentation for cutouts and object masks.
- the Myriograph public `analyze speakers` service (with an explicitly authorized retail ceiling) for transcript/dialogue/lyric timing when speech or lyrics matter.

Do not run Qwen embedding when the project constraint forbids it.

## Artifact Contract

For each formula or test, persist:

- `ffprobe.json`
- beat/onset map with seconds and frame numbers
- transcript alignment when available
- shot detection data
- OCR/face/person/object summaries
- render manifest
- QA notes and known gaps

## Render Pattern

- A: reference recreation using original assets/audio as closely as feasible.
- B: same audio/style using substitute source footage.
- C: same style using substitute source footage and synthetic beat/song.

Keep renders deterministic. Store source ranges, text events, effect events, masks, and audio decisions in JSON or code constants that another agent can inspect.

## Content Search Pattern

1. Use transcript search for lines, names, theme words, and quote candidates.
2. Use face/person detection for character continuity.
3. Use shot detection for clean cut points.
4. Use motion analysis for action peaks.
5. Use OCR to avoid baked captions/signage conflicts.
6. Use masks for cutouts, object flashes, and text occlusion only when quality is sufficient.

## QA Checklist

- Scripts can be rerun from the artifact folder.
- Inputs and outputs use absolute or clearly rooted paths.
- Render manifest names all A/B/C outputs.
- Known missing providers are documented exactly.
- Generated artifacts do not overwrite source media.
