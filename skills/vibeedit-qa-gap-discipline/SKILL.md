---
name: vibeedit-qa-gap-discipline
description: Verify fan-edit skills and renders with frame checks, OCR, audio timing, style review, accepted-gap rules, and exact limitation reporting.
---

# VibeEdit QA Gap Discipline

Use this skill when reviewing fan-edit formulas, render outputs, reconstruction reports, or reusable skills.

## Core Standard

Do not claim perfection from weak evidence. A render passes only when the relevant visual, audio, text, timing, style, and artifact requirements are proven or exact gaps are documented.

## Required Checks

- File exists and opens.
- Duration, fps, resolution, audio codec, sample rate, and channel count are valid.
- A/B/C outputs exist when the formula requires them.
- Beat and text events align to audio.
- OCR finds readable text without accidental overlap.
- Faces and key subjects are not covered by text or effects.
- Contact sheet shows the intended story progression.
- Video review or frame sampling checks hook, build, drop, aftershock, and loop.
- Known provider gaps are explicit.

## Accepted Gap Rules

Accepted gaps must be exact:

- Source-baked captions, signage, watermarks, or OCR detections preserved for reference fidelity.
- Missing provider key, named directly.
- Deterministic substitute footage when semantic matching could not be proven.
- Synthetic beat/song when no source audio is used.
- Unsupported model intentionally skipped by project instruction.

Never write vague excuses like "model limitations" without naming the model, missing input, failed check, and effect on output.

## Repair Loop

1. Identify the failing requirement.
2. Decide whether it is generated-output failure or source-baked/reference exception.
3. Repair generated text, timing, effects, masks, crops, audio, or render code.
4. Rerun the relevant review.
5. Update QA notes with pass/fail and exact residual limitations.

## QA Checklist

- Every deliverable path resolves.
- Every failure has a repair or accepted-gap reason.
- Accepted gaps do not hide fixable generated-output issues.
- Final index/status agrees with the actual files.
