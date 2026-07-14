---
name: vibeedit-compact-3d-typography
description: Create refined fan-edit typography with compact one-word lyric reveals, red emphasis, perspective-tilted 3D flat text, face-aware placement, and no accidental overlap.
---

# VibeEdit Compact 3D Typography

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
