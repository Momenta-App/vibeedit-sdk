---
name: vibeedit-face-tracking-framing
description: Use face/person/body detection to center subjects, align match cuts, track faces through motion, avoid white space, and place text away from faces.
---

# VibeEdit Face Tracking Framing

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
