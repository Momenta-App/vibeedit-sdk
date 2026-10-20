---
name: vibeedit-qa-gap-discipline
description: Verify fan-edit skills and renders with frame checks, OCR, audio timing, style review, accepted-gap rules, and exact limitation reporting.
---

# VibeEdit QA Gap Discipline

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


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
