---
name: negative
description: Create flat bold all-caps NEGATIVE text overlays where timestamped words replace each other exactly. Supports Ultra, Max, Medium, Small, and Extra Small size modes, centered placement, difference blending over footage, stale-word clearing, and no 3D, shadows, face tracking, or decorative effects.
---

# Negative Text

Use this skill for stark all-caps word hits: one word or short caption at a time, flat fill, no 3D, no shadows, no glow, no face tracking, no perspective, and no decorative effects.

Default to `medium` for normal use. Almost never use `ultra` or `max`; reserve those modes for rare full-screen impact moments or when the user explicitly asks for giant text.

## Style Contract

- Render bold uppercase text only.
- Each timestamped word or caption replaces the previous one. Do not accumulate words on screen.
- Prefer word-by-word rendering for any caption, lyric, transcript, or dialogue source. If the input contains phrase or sentence captions, split them into single-word events using supplied word timings when present, or distribute words across the caption interval when only segment timing exists.
- Use exact input timestamps. A word appears on the first output frame at or after its timestamp.
- If there is no next word after the clear timeout, remove the text so stale words do not stay on screen.
- Default blend mode is `difference`, using the text as a mask to invert the footage below it. On black review plates this appears white, but over video it must visibly invert the underlying pixels rather than paste plain white text.
- Do not add shadows, blur, outlines, 3D tilt, perspective, tracking, face detection, or subject avoidance.
- Never shrink any non-Ultra text below the Extra Small minimum. If text would become too small, split it into word hits instead of rendering an unreadably tiny centered caption.

## Size Modes

- `ultra`: the word fills the frame as aggressively as possible. It may stretch horizontally and vertically. Only use this for square or landscape outputs where `width >= height`; never use it for vertical renders. This is rare and should be explicitly requested.
- `max`: fill as much of the frame as possible without distorting the text. Use sparingly for major impact words only.
- `medium`: centered, clearly smaller than Max. This is the default size mode.
- `small`: centered, small but still bold and readable.
- `extra-small`: centered subtle caption/text size, and the minimum readable size for this skill.

## Placement

All modes are centered. Do not place Negative text at the bottom, sides, corners, upper third, or lower third.

## Canonical Renderer

Use the bundled Python script:

```bash
python3 .agents/skills/negative/scripts/negative_text.py \
  --captions-json /tmp/negative-captions.json \
  --mode medium \
  --width 1280 \
  --height 720 \
  --duration 8 \
  --out-dir /tmp/negative-review
```

`--captions-json` and `--captions-file` are preferred because they can ingest transcript, lyric, and caption sources and convert them to word hits. Accepted caption inputs:

- JSON list of word objects: `{ "start": 0.420, "end": 0.700, "text": "AGAIN" }`
- JSON object with `words`, `captions`, `lyrics`, or `segments`
- Segment JSON with `{ "start": 1.0, "end": 2.5, "text": "stand up now" }`
- Transcript JSON where segments contain `words`
- `.srt`, `.vtt`, and `.lrc` files

When a segment has only phrase-level timing, distribute its words evenly from `start` to `end`. When no `end` exists, use `--word-gap` spacing. Millisecond timestamps are accepted and normalized to seconds.

`--words-json` is still supported:

```json
[
  { "time": 0.000, "text": "RISE" },
  { "time": 0.420, "text": "AGAIN" },
  { "time": 1.100, "text": "NOW" }
]
```

Useful options:

```bash
--mode ultra|max|medium|small|extra-small
--blend-mode difference|normal
--background-video /path/to/source.mp4
--captions-json /path/to/captions.json
--captions-file /path/to/captions.srt
--clip-start 12.5
--no-background-audio
--clear-after 0.75
--word-gap 0.24
--fps 24
--plate-color "#000000"
--text-color "#ffffff"
--no-video
```

The renderer writes:

- `layout.json`: resolved mode, placement, word timings, clear times, text boxes, and validation data.
- `contact-sheet.jpg`: representative frames.
- `validation-report.json`: timing, bounds, mode, stale-text, and flat-style checks.
- `review.mp4`: review render unless `--no-video` is used.

When `--background-video` is supplied, the script extracts that source window, renders the flat text over the footage, and muxes the matching source audio by default. Use `--no-background-audio` for silent review renders. Without `--background-video`, it uses a solid review plate.

## QA Standard

Before claiming the skill works:

1. Run the gauntlet after script changes.
2. Confirm all words are uppercase in layout output.
3. Confirm only one word/caption is visible at a time.
4. Confirm each visible interval starts at the exact supplied timestamp.
5. Confirm stale text clears after `--clear-after` when no new word arrives.
6. Confirm phrase captions split into word events and stay at or above the Extra Small minimum.
7. Confirm Ultra rejects vertical output.
8. Confirm `max` does not distort text.
9. Confirm medium, small, and extra-small are visibly much smaller than max.
10. Confirm difference blending is used over footage unless explicitly disabled.
11. Confirm there are no shadows, outlines, 3D transforms, face tracking, or decorative effects.

Run:

```bash
python3 .agents/skills/negative/scripts/run_negative_gauntlet.py \
  --out-dir fan_Edit_Data/agent-artifacts/negative-skill-gauntlet
```
