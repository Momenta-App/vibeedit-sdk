---
name: text-layering
description: Use when placing or reviewing text items so captions, titles, lower thirds, labels, lyrics, and callouts layer above base video instead of replacing it.
---

# Text Layering

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this as a small placement guardrail before text mutations and during QC.

## Core Rule

Text is an overlay by default. Normal text belongs on a visual layer above the picture, not as a sequential replacement on the base video track.

- The base picture track should remain picture-first. Do not place normal text, captions, lower thirds, labels, lyrics, or callouts as a replacement for picture.
- Use an existing text/title/overlay visual layer above the base video, or create one when the editing environment allows it.
- If a mask, plate, blur, or shape supports the text, stack it below the text and above the video: text on top, mask/plate under it, video below both.
- A standalone title card can occupy its own timed section only when the user asks for a title card, chapter card, intro card, end card, or an intentional all-text beat. Record that exception in the plan.
- Never solve an overlap problem by moving text into the base picture layer. Create or choose a higher visual layer instead.

## Fast Check

Before applying or claiming success, verify:

- text items do not replace the base picture
- normal overlay text overlaps the relevant video frames
- text is above support layers, and support layers are above video
- standalone text-only beats are explicitly marked as title/card exceptions

## Handoff Field

Include a compact note in text plans and applied reports: `textLayering: overlay above picture; verified true/false`. If verification is false, do not claim the text placement is complete.
