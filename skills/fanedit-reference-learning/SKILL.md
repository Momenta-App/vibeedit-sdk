---
name: fanedit-reference-learning
description: Learn reusable fan-edit grammar from reference video corpora and source media, including story beats, quote and music structure, clip-selection patterns, pacing curves, confidence-labeled source matches, and reusable recommendations without mutating timelines directly.
---

# Fanedit Reference Learning

Use this skill when studying reference fan edits, edit corpora, or paired reference/source media to extract reusable editing grammar. The goal is to produce evidence-backed lessons and source-match recommendations that another editor, skill, or timeline mutator can apply.

This skill is analysis-only. It should not directly mutate timelines, project JSON, media manifests, or rendered outputs.

## Inputs To Prefer

- Reference videos, cutdowns, captions, audio tracks, thumbnails, or contact sheets.
- Source media, workspace media records, production-analysis runs, transcripts, shot lists, scene summaries, face/person tracks, object detections, motion scores, OCR, and beat maps.
- Existing rendered edits and their manifests when available.
- User intent: target character, emotion, runtime, platform, song, and whether chronology matters.

## Learning Workflow

1. Inventory the reference corpus and source media. Record which files are reference edits and which files are source truth.
2. Segment each reference into hook, setup, build, drop, aftershock, loop, quote breaks, and text/effect emphasis points.
3. Analyze pacing from measured cuts, hold lengths, beat/onset alignment, speed changes, quote interruptions, and visual intensity changes.
4. Match reference moments back to source media when possible using transcript text, audio phrases, visual thumbnails, scene summaries, OCR, and face/person continuity.
5. Label source matches with confidence. Separate exact transcript/thumbnail matches from inferred story equivalents.
6. Extract reusable grammar: shot function order, quote placement, music ducking, repeated motifs, transition density, text density, effect punctuation, theme discipline, hook selection quality, body-shot taste, and when the edit lets a moment breathe.
7. Produce recommendations as planning material, not as applied timeline changes.

## Output Contract

For a reference-learning pass, include:

- `reference_structure`: section map with timestamps, pacing notes, and audio/quote behavior.
- `story_grammar`: reusable beat pattern in plain language.
- `clip_selection_patterns`: what kinds of source shots the reference favors and avoids.
- `pacing_curve`: slow/medium/fast sections, cut density, and drop timing.
- `quote_music_structure`: quote hooks, pauses, ducks, lyric hits, and re-entry points.
- `source_matches`: source filename, movie/source timestamp, reference timestamp, match basis, and confidence.
- `reuse_recommendations`: how to adapt the grammar to the current target without copying unsupported details or requiring the output to look exactly like the reference.

For each source match, include the evidence type: transcript, thumbnail/frame, scene summary, OCR, face/person track, audio match, or manual visual inference.

## Boundaries

- Do not mutate timelines directly. Hand off a recommendation packet to the relevant edit, sound, text, effects, or workspace skill when application is requested.
- Do not overfit to one reference. Preserve the difference between a reusable grammar rule and a one-off stylistic accident.
- Do not treat the reference as an exact visual template. The target is to understand its vibe, story mechanics, content-selection standard, and pacing discipline well enough to make a fresh edit with similar quality.
- Do not claim an exact source match from visual resemblance alone. Use medium or low confidence unless transcript, frame, scene, or audio evidence confirms it.
- Do not paste large raw corpora into the live answer. Summarize lessons and cite local artifact paths or dataset names.
- Do not override domain-specific skills. Use Creed-specific, text, sound, transition, or segmentation skills when the task moves into those domains.

## Validation

Before delivering lessons or recommendations:

- Confirm reference timestamps are reference-local and source timestamps are source-local.
- Check that every high-confidence source match has at least one concrete evidence artifact.
- Report unmatched reference moments instead of forcing weak matches.
- Verify pacing claims with measured section durations, cut counts, beat/onset notes, or visible reference timestamps.
- Separate observations from recommendations so later timeline work can choose what to apply.
- Include residual risk when source media, transcript, beat map, or visual artifacts are missing.
