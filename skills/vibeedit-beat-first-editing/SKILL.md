---
name: vibeedit-beat-first-editing
description: Build fan edits from beat maps, waveform energy, lyric timing, and impact timing so cuts, text, effects, speed ramps, and emotional turns land on the music.
---

# VibeEdit Beat-First Editing

Use this skill when making or reviewing a fan edit where the song, beat, lyric cadence, or audio energy should drive the timeline.

## Required Inputs

- Source video or shot library.
- Song, reference audio, or synthetic beat target.
- Beat map from `librosa`, `madmom`, `aubio`, `essentia`, or local waveform/onset analysis.
- Transcript or lyric timing from AssemblyAI when dialogue or lyrics are present.
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
