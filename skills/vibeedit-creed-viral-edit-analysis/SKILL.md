---
name: vibeedit-creed-viral-edit-analysis
description: Analyze Creed movie source media and production-analysis artifacts to learn viral fan-edit structure, match quotes to source moments, identify recurring Creed story moments, and recommend timestamped source clips with story functions for narrative-first Creed edits.
---

# VibeEdit Creed Viral Edit Analysis

Use this skill when planning, auditing, or learning from Creed-focused viral fan edits. It owns source-moment analysis, quote/source matching, narrative structure, recurring Creed motifs, and recommendations for which movie timestamps should be used for a story-driven edit.

This is not a typography or render skill. Use `vibeedit-creed-kinetic-text` only after source moments and quotes are selected and the task is specifically about Creed-style kinetic text rendering.

## Scope

- Identify source movies and media IDs, especially `Creed 1.mp4`, `Creed 2.mp4`, and `Creed 3.mp4` when present in the workspace.
- Read production-analysis artifacts before guessing: transcript indexes, shot lists, scene summaries, face/person tracks, motion scores, OCR, thumbnails, and source metadata.
- Match reference-edit quotes or captions back to exact transcript words, source timestamps, speaker context, and confidence.
- Learn recurring Creed viral-edit moments: legacy pressure, name identity, father/son inheritance, training proof, public humiliation, rivalry, injury, comeback, corner speech, final bell, quiet aftermath.
- Recommend source moments with movie timestamp, duration, story function, quote/audio use, visual reason, and confidence.
- Explain why the selected order forms a short emotional argument, not just a montage.

## Workflow

1. Confirm the available Creed sources and their movie identity from workspace metadata, filenames, manifests, or ffprobe-backed media records.
2. Locate the relevant production-analysis run directories for those sources. Prefer current analysis artifacts over manual memory.
3. Build a transcript index around names, insults, vows, family references, legacy language, fight terms, and repeated emotional phrases.
4. Build a visual moment index from shot boundaries, thumbnails/contact sheets, face/person tracks, motion peaks, and scene summaries.
5. Match requested quotes, reference captions, or story beats to source moments using transcript text first, then scene summary and visual context.
6. Tag each candidate with one primary story function: hook, identity, pressure, wound, training, rivalry, proof, reversal, drop, aftershock, or loop.
7. Recommend a compact source plan for the target edit length. Reserve the strongest source proof for the drop or emotional turn.

## Output Contract

Return recommendations as a compact table or JSON-like list with:

- `movie`: source title or filename.
- `source_timestamp`: movie-local start time, plus end time or duration.
- `story_function`: one of the declared functions.
- `moment`: short description of what happens on screen.
- `quote`: exact quote text when used, or `none`.
- `quote_timestamp`: transcript word or segment timestamp when different from visual start.
- `audio_role`: open quote, under-music quote, music-only, ducked return quote, or final loop.
- `why`: the story reason this moment belongs in the edit.
- `confidence`: high, medium, or low, with the evidence type.

When recommending a sequence, include a one-sentence edit thesis and a section map such as intro, setup, build, drop, aftershock, and loop.

## Boundaries

- Do not mutate a timeline, project JSON, manifest, or workspace media record from this skill alone.
- Do not render Creed kinetic typography, choose font geometry, or validate text layout here.
- Do not invent exact timestamps. If transcript or shot evidence is missing, label the match as low confidence and state what needs inspection.
- Do not select moments only because they are visually intense. Every recommended source moment must have a story function.
- Do not treat a reference edit as ground truth if its quote, timing, or source context conflicts with the actual movie analysis.

## Validation

Before handing off recommendations:

- Verify every high-confidence quote against transcript words or transcript segment text.
- Verify every high-confidence visual moment against a thumbnail, frame sample, scene summary, or shot-boundary artifact.
- Check movie-local timestamps against the source file duration and confirm they are not render-local or clip-local unless explicitly labeled.
- Include evidence paths or artifact names used for the analysis.
- Mark uncertain speaker IDs, partial quote matches, and visually inferred moments as medium or low confidence.
- Confirm the final plan has a readable story arc and does not duplicate the same story function without a deliberate reason.
