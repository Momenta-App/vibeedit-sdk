---
name: clean-text-animation
description: "Create CapCut-style clean word-by-word text animations from arbitrary phrases, based on the Follow for more reference: words rise in from below with subtle blur trails, clean hold, and optional glyph-clipped shimmer on a chosen word. Use when making or recreating clean kinetic text tutorials, social edit text reveals, or reusable text animation presets."
---

# Clean Text Animation

Use this skill to render or specify a clean text reveal where each word enters from below, settles into one centered line, and optionally applies a high-quality shimmer inside the chosen word's glyphs only.

## Quick Render

Use `scripts/render_clean_text.py` when a concrete preview clip is useful:

```bash
python3 .agents/skills/clean-text-animation/scripts/render_clean_text.py \
  --text "Follow for more" \
  --output tmp/clean-text/clean_text.mp4 \
  --contact-sheet tmp/clean-text/clean_text_sheet.jpg \
  --shimmer last
```

Common options:

- `--text`: Any phrase. The script splits on whitespace and animates each word.
- `--shimmer none`: No shimmer. This is the default.
- `--shimmer last`: Shimmer the final word.
- `--shimmer word:TEXT`: Shimmer the first word matching `TEXT`, case-insensitive.
- `--shimmer index:N`: Shimmer the zero-based word index.
- `--size 720x1280`: Output frame size.
- `--duration 1.0`: Main reveal duration in seconds.
- `--hold 0.4`: Extra hold after the reveal.
- `--font-size 47`: Starting font size. The script reduces it if needed to fit.

## Style Rules

- Keep one visible text layer per word. Do not add a faint full-sentence duplicate unless the user asks for the instructional CapCut construction view.
- Animate from below into the baseline. The first visible word should appear after the blank opening frame.
- Stagger words by about 2 frames at 30 fps.
- Use a subtle blur/trail during entry, not a strong reflection.
- Fit the full phrase inside the frame with side margins before rendering.
- If shimmer is enabled, clip it to the word glyph mask. Do not create an outside glow, halo, rectangle, underline, or general highlight.
- Let the shimmer be a narrow internal spectral sweep that passes once and returns the word to the base color.

## Parameter Guidance

For short phrases like `Follow for more`, use:

- `duration`: `1.0`
- `hold`: `0.4`
- `stagger-frames`: `2`
- `rise`: `54` for the last word and `38` for earlier words
- `shimmer`: `last` only when the user wants the accent

For longer phrases:

- Auto-fit the line rather than allowing edge clipping.
- Keep the same 2-frame stagger until the phrase becomes too dense; then shorten per-word duration before reducing the stagger.
- Prefer no shimmer unless the user asks for polish on a specific word.

## Verification

After rendering, inspect the contact sheet or at least a mid-shimmer preview frame. Confirm:

- The first frame is blank or near-blank.
- Words enter from below.
- The phrase fits horizontally.
- There is no duplicate full-sentence ghost layer.
- Optional shimmer stays fully inside the target word.
