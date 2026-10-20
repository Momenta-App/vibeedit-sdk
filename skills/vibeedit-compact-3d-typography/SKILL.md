---
name: vibeedit-compact-3d-typography
description: Create refined fan-edit typography with compact one-word lyric reveals, red emphasis, perspective-tilted 3D flat text, face-aware placement, and no accidental overlap.
---

# VibeEdit Compact 3D Typography

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill whenever a fan edit uses lyric text, quote text, title cards, ranking labels, or kinetic caption hits.

## Core Standard

Text should feel designed, compact, and timed. It should usually reveal one word or one tight phrase at a time. Never use text to narrate what the viewer can already see.

## Text Source Rules

- Use lyrics, dialogue, iconic quotes, title/ranking phrases, or a short theme phrase.
- Do not write explanatory scene descriptions.
- For story edits, use one quote or one recurring theme and reveal pieces of it across the edit.
- If the song stops for dialogue, caption only the quote words that need emphasis.

## Layout Rules

- Keep text compact: tight line count, controlled tracking, strong stroke/shadow, and little dead space.
- Avoid overlaps by design; text can sit close, but lines and words must never collide accidentally.
- Protect faces. If a face is centered, place text on the side or lower corner.
- For close-up faces, use bottom-left, bottom-right, or side-stacked text that avoids eyes and mouth.
- Centered text is allowed only when it is the designed focal point.
- Use safe margins for social formats; do not pin text to the edge unless it is an intentional edge-title effect.

## Fan-Edit 3D Text Recipe

The reference style often uses flat text made dimensional:

1. Render bold condensed uppercase text with white or near-white fill.
2. Add black stroke and a dark red or black extrusion layer.
3. Create perspective: top edge pushed slightly back, bottom edge forward.
4. Tilt based on placement:
   - Left-side text: left side is slightly closer to camera.
   - Right-side text: right side is slightly closer to camera.
5. Add a small shadow/contact layer so it sits in the frame.
6. Use red fill, red stroke, or red extrusion to emphasize one important word.

Python implementation can use PIL/Pillow text masks, OpenCV perspective transforms, layered offsets for extrusion, and `ffmpeg`/MoviePy compositing.

## Word Reveal Timing

- Reveal one important word per beat, syllable, or lyric stress.
- Keep previous words only if building a compact phrase; otherwise replace.
- Use red on the key word: threat, name, negative, victory, pain, or punchline.
- Avoid large gaps between words; the phrase should feel tight without touching.
- On impact words, use a 1 to 3 frame scale pop, extrusion pulse, or red flicker.

## QA Checklist

- Text does not overlap faces unless intentionally masked behind/around them.
- Text never describes the scene.
- Long lines are split into compact beats.
- Red emphasis has a reason.
- Perspective direction matches screen position.
- OCR review finds readable words and no accidental collisions.
