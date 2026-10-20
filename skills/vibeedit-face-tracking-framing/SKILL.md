---
name: vibeedit-face-tracking-framing
description: Use face/person/body detection to center subjects, align match cuts, track faces through motion, avoid white space, and place text away from faces.
---

# VibeEdit Face Tracking Framing

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill when a fan edit needs face-centered cuts, body alignment, subject tracking, or face-aware text placement.

## Core Standard

The viewer should always know where to look. Faces, bodies, and key objects should be framed intentionally, and text should not cover the main face unless the design explicitly calls for it.

## Analysis Inputs

- Apple Vision face/person boxes.
- Local face detector or tracker.
- Body/keypoint detector if available.
- Shot boundaries and frame samples.
- OCR/text boxes to avoid collisions.

## Framing Rules

- For face montage cuts, align eyes or face center across shots.
- For body montage cuts, align torso/pose center across shots.
- Crop to remove wasted white space unless emptiness is part of tension.
- Track the subject through movement with soft or hard stabilization:
  - Soft track: subject drifts naturally but remains readable.
  - Hard lock: face/body stays nearly fixed for intense match-cut effects.
- Keep action readable; do not over-center if the movement direction needs room.

## Text Placement

- If the face is centered, place text to side, lower-left, lower-right, or around the body shape.
- If the face is close-up, avoid eyes and mouth.
- If text must cross a subject, put it behind the subject with a reliable mask.
- Use face and OCR boxes as collision constraints during render.

## Match-Cut Face Sequence

1. Select shots of the same character or related characters.
2. Extract face boxes near target beats.
3. Compute crop/scale so face centers line up.
4. Cut every few frames or every beat depending on song energy.
5. Use slight zoom or color pulse to hide minor alignment differences.
6. Verify no frame has cropped-off eyes or unusable blur.

## QA Checklist

- Main face/body is readable in every important frame.
- Crop removes dead space without cutting off critical action.
- Face-centered match cuts align consistently.
- Text does not cover the face by accident.
- Tracking strength matches emotion: softer for drama, harder for impact.
