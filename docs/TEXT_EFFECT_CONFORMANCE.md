# Text effect conformance

Date: 2026-07-16

Canonical VibeEdit source revision: `2403e3f94cfabf7236d5401bd4beeadefde1d725`

## Outcome

Every text effect currently registered in VibeEdit is saved in the public SDK
catalog with a verified preview:

- 76 registered text effects tested.
- 74 portable components imported from the tracked VibeEdit text catalog.
- 2 baseline components: `caption-rail` and `negative`.
- 76 passed and 0 failed.
- 76 individual H.264 MP4 previews added to the hash-bound asset ledger.
- 89 total distributed preview/audio assets after this run.

This work preserves the existing VibeEdit library. It does not introduce a
replacement text library or a new skill. The imported entries are deterministic
portable adaptations of the existing tracked components. MOGRT adaptations do
not redistribute source binaries, fonts, or external media.

## Acceptance contract

Each effect is rendered in Chromium at 640 x 360, 24 fps, for 48 frames over a
split dark/light conformance field. The suite verifies:

- repeated-frame determinism;
- visible pixels distinct from the background;
- expected text in the rendered DOM;
- a measurable primary text box fully inside the frame;
- temporal change for every effect that claims motion;
- zero network requests;
- zero console or page errors;
- complete 48-frame H.264 decode;
- byte count and SHA-256 agreement with `catalog/assets.json`.

OCR is recorded as advisory evidence only. Stylized, glowing, distorted, and
mask-filled text can be visually correct while being difficult for Tesseract to
recognize. DOM presence, geometry, pixels, deterministic rendering, and decoded
video are the hard acceptance checks.

## Defects found and repaired

The first broad run exposed both harness gaps and real component gaps:

- Glitch effects were sampled at two identical modulo phases. The temporal
  sample was moved by one frame so real phase changes are measured.
- Matrix decode was inspected before its final reveal. DOM and geometry checks
  now use the final rendered frame.
- `negative` and `caption-rail` required text but had no catalog preview value.
  Stable conformance copy is now provided by the preview harness.
- Texture and texture-mask described moving texture but rendered a static fill.
  Matching deterministic background-position motion was added to both the
  JavaScript and Python runtimes.
- Contact-sheet generation could capture before every preview image decoded.
  Evidence generation now waits for every image to be complete.

## Evidence

- Full result ledger: [text-effect-conformance.json](evidence/text-effects/text-effect-conformance.json)
- Continuous review reel: [review-reel.mp4](evidence/text-effects/review-reel.mp4)
- Representative contact sheet: [contact-sheet.jpg](evidence/text-effects/contact-sheet.jpg)
- Early-state contact sheet: [contact-sheet-early.jpg](evidence/text-effects/contact-sheet-early.jpg)
- Mid-state contact sheet: [contact-sheet-mid.jpg](evidence/text-effects/contact-sheet-mid.jpg)
- Late-state contact sheet: [contact-sheet-late.jpg](evidence/text-effects/contact-sheet-late.jpg)
- Individual previews: `catalog/previews/text-effects/`

Regenerate the complete suite with:

```bash
npm run text:previews
```

Regenerate only the review sheets from saved previews with:

```bash
npm run text:previews -- --contact-only
```
