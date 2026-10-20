---
name: vibeedit-beat-first-editing
description: Build fan edits from beat maps, waveform energy, lyric timing, and impact timing so cuts, text, effects, speed ramps, and emotional turns land on the music.
---

# VibeEdit Beat-First Editing

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill when making or reviewing a fan edit where the song, beat, lyric cadence, or audio energy should drive the timeline.

## Required Inputs

- Source video or shot library.
- Song, reference audio, or synthetic beat target.
- Beat map from `librosa`, `madmom`, `aubio`, `essentia`, or local waveform/onset analysis.
- Transcript or lyric timing from the Myriograph public `analyze speakers` service (with an explicitly authorized retail ceiling) when dialogue or lyrics are present.
- Shot boundaries, motion scores, face/person tracks, and existing clip metadata when available.

Never guess beat precision if analysis is available. Build the edit from measured onsets, beat strength, section changes, and waveform peaks.

## Beat Skeleton

1. Mark the hook before or on the first recognizable beat.
2. Split the audio into intro, setup, build, drop, aftershock, and loop.
3. Reserve the strongest source moment for the strongest drop or lyric reveal.
4. Use longer holds for quote, stare, threat, or grief moments.
5. Compress clip durations during the build.
6. Put cuts, zoom punches, flashes, text pops, and segmentation hits on onsets.
7. Let one or two key moments breathe after a drop instead of cutting continuously.

## Timing Rules

- Major beat: cut, speed ramp peak, flash, transition, or text reveal.
- Minor beat: mask-only flash, micro zoom, one-word text change, color pulse, or shake impulse.
- Pre-drop: hold tension for 4 to 12 frames longer than expected.
- Drop: align subject impact, face reveal, weapon/action hit, or title word to the strongest onset.
- Lyric hit: reveal only the word being heard or the most important word in the line.
- Dialogue break: stop or duck the song intentionally; do not let quote audio fight the song.

## Python Analysis Pattern

Use Python for repeatable timing:

- `librosa.load` for mono analysis and `librosa.onset.onset_detect` for onset candidates.
- `librosa.beat.beat_track` for tempo and beat grid.
- RMS energy and spectral flux for intensity changes.
- `ffmpeg` or `moviepy` for frame-accurate extraction and render assembly.
- Store beat data as JSON with seconds, frame numbers, confidence, and beat type.

## QA Checklist

- Every major cut has a declared audio reason.
- Text appears within 1 to 2 frames of the lyric/dialogue/beat it supports.
- Effects do not drift late after the hit.
- The drop contains the best visual moment, not a random high-motion clip.
- If no exact beat map exists, the report says timing was approximated from waveform peaks.
