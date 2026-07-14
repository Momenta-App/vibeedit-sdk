---
name: structured-timeline-editor
description: Convert creative edit intent into a precise, structured timeline change plan. Use when an edit requires careful track/layer reasoning, media reference validation, timing math, keyframes, color/effect stacks, repair diagnostics, and proof-state honesty across any editing system.
---

# Structured Timeline Editor

Use this skill when the edit needs structural precision rather than only taste guidance. It is not tied to a specific JSON schema, app, or tool call. Its job is to turn a creative plan into a clear, verifiable timeline model that another editor, tool, or automation layer can apply safely.

## Fast Loop

1. Inspect the current edit model: timeline sections, tracks/layers, clips/items, source ranges, transitions, effects, keyframes, audio, text, media references, and any constraints supplied by the editing environment.
2. Capture the starting state in human terms before proposing changes: what exists, where it lives in time, what media it references, and which parts are risky to alter.
3. Author a candidate change plan before applying anything. The plan should include exact ranges, layer/track targets, source references, effect parameters, and fallback behavior.
4. Validate the candidate against the editing environment:
   - source media exists and is referenced consistently
   - track/layer targets exist or are explicitly created
   - visual items do not accidentally overlap destructively on the same layer
   - audio and visual layers remain logically separated unless the system intentionally combines them
   - transitions have compatible adjacent material and enough handles
   - keyframes are ordered, in range, and meaningful
   - color/effect parameters are within supported ranges
   - text overlays remain above picture unless the beat is an intentional title card
5. Apply only through the safest available mechanism. If application is unavailable, return an execution-ready plan and label it `planned`, not `applied`.
6. Treat apply success as incomplete until the result is re-read, previewed, rendered, or otherwise verified.
7. Repair from concrete diagnostics. Do not guess a second candidate without explaining what failed and why the repair addresses it.
8. Keep this substrate neutral: it enforces structure, media/track validity, timing, effects/keyframes/color validity, guarded application, repair diagnostics, and proof honesty. Creative intent, taste, pacing, genre, and edit style belong in other skills.

## Must Remember

- Preserve the native timeline model. Do not invent schema fields, ids, tracks, or capabilities that the target editor does not support.
- Preserve source media/provenance and make changes reversible where possible.
- Normal text belongs above picture; do not let captions, labels, lyrics, or lower thirds replace the base video unless the plan declares a title/card exception.
- Validate every media reference, layer/track reference, transition target, effect id/name, and keyframe target against available state.
- Color-grade and LUT-style changes need explicit before/after intent, parameter ranges, and readability checks. Do not add a heavy grade just because a control exists.
- Keyframes should have a job: anticipation, acceleration, peak, reveal, settle, follow-through, or readability. Avoid decorative keyframes that create jitter.
- Keep proof states distinct: `planned`, `dry-run`, `applied`, `confirmed`, `previewed`, `rendered`, and `proven`.

## Output Shape

Return:

- starting-state summary
- candidate timeline change plan
- validation checklist and failed assumptions
- repair plan when validation fails
- applied/skipped changes when execution is available
- proof state and verification evidence
- recovery guidance
