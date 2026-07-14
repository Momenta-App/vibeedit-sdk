---
name: vibeedit-story-shot-selection
description: Select fan-edit shots by emotional function, character arc, source quote, subject clarity, motion, and story progression instead of using random attractive clips.
---

# VibeEdit Story Shot Selection

Use this skill when choosing source moments for a fan edit, especially character edits, villain edits, sports edits, anime/game edits, or movie edits.

## Core Rule

A fan edit is a short emotional argument. Every shot must have a job: hook, identity, threat, weakness, escalation, proof, reversal, drop, aftershock, or loop.

## Selection Workflow

1. Define the edit thesis in one sentence.
2. Build a source inventory from shot detection, transcript, face/person/object detection, motion scores, and thumbnails.
3. Tag candidate shots by story function.
4. Prefer shots with clear faces, readable body position, strong silhouettes, and low wasted space.
5. Match shots to the song structure instead of chronological order unless the story needs chronology.
6. Keep repeated shots only when repetition creates obsession, memory, rivalry, or escalation.

## Story Functions

- Hook: iconic quote, face, silhouette, object, action, or contradiction in the first 1 to 2 seconds.
- Setup: show who the edit is about and what pressure they are under.
- Build: increase stakes through stronger reactions, faster motion, tighter faces, or clearer conflict.
- Drop: use the most iconic action, transformation, reveal, victory, betrayal, or loss.
- Aftershock: hold a face, body, smoke, aftermath, crowd, or quiet consequence.
- Loop: end on a pose, line, look, or motion that can rhythmically return to the opening.

## Content Finding

Use local analysis before manual guessing:

- Use transcript search for iconic lines, repeated phrases, character names, threats, vows, and emotional words.
- Face clustering or face tracks to find the same character across scenes.
- Object/person detection to find weapons, cars, crowds, rivals, masks, doors, vehicles, and props.
- Shot boundary detection to locate clean transition handles.
- Motion and optical-flow scores to find action peaks.
- OCR to detect source captions, signage, scoreboards, UI, or baked watermarks that may affect text placement.

## Negative Rules

- Do not add descriptive text that explains what is happening in the scene.
- Do not choose a shot only because it is noisy or effect-friendly.
- Do not leave empty frame space unless it is being used for typography or tension.
- Do not cover the emotional face with text unless the design intentionally makes text the subject.

## QA Checklist

- The shot order can be explained as a story, not just a montage.
- The subject is readable in every important frame.
- The drop shot is the strongest story proof.
- Dialogue or quote selections support the same story thread.
