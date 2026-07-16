# Text effect conformance

Date: 2026-07-16

Canonical VibeEdit source revision: `2403e3f94cfabf7236d5401bd4beeadefde1d725`

## Outcome

Every text effect currently registered in VibeEdit is saved in the public SDK
catalog with a verified preview:

- 76 registered text effects tested.
- 53 source-preserved VibeEdit HTML/CSS/JS effects with their original local
  renderers, configuration, fonts, and design assets.
- 21 portable-runtime caption/text effects.
- 2 baseline components: `caption-rail` and `negative`.
- 76 passed and 0 failed.
- 76 individual H.264 MP4 previews added to the hash-bound asset ledger.
- 89 total distributed preview/audio assets after this run.

This work preserves the existing VibeEdit library. It does not introduce a
replacement text library or a new skill. The 53 motion-title entries run the
packaged original VibeEdit HTML/CSS/JS implementation rather than an inferred
generic family. Original MOGRT binaries and external media are not bundled.

## Source fidelity

Every canonical entry was rendered from both the tracked VibeEdit source and
the packaged SDK clone at frames 2, 24, and 43 over the same matte:

- 53 of 53 passed the source-fidelity threshold.
- 50 are pixel-identical at all three samples.
- `Clean Style`, `Apple Word`, and `Apple Smooth` are perceptually equivalent;
  their minimum SSIM values are 0.958599, 0.990891, and 0.986067. The visible
  difference is confined to browser glyph antialiasing at the second localhost
  origin, not geometry, wording, font selection, layout, or motion.
- The accepted perceptual floor is SSIM 0.95; the measured minimum is 0.958599.

The 23 portable-runtime effects pass render conformance but do not claim pixel
identity with a separate source page.

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

The earlier 76/76 report used an insufficient acceptance bar: it proved that
each effect rendered, moved, decoded, and remained in frame, but it did not
prove visual fidelity. The MOGRT importer had collapsed 53 distinct designs
into eight generic motion families. That caused Bubble, Bottom/Above In, the
Apple group, Aesthetic Purple/Strinking, Clean, Elegant, Old Money, Reboot, VHS,
and Warp to lose their defining typography, layers, gradients, masks, and
motion. Those generic family renderers are now fallback-only; browser/video
rendering loads the saved source implementation from the packaged read-only
asset server.

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
- Canonical seeking initially read a legacy top-level frame-rate field. Both
  runtimes and the harness now read `canvas.frameRate`, preventing 24/60 fps
  compositions from being sought as 30 fps.

## Evidence

- Full result ledger: [text-effect-conformance.json](evidence/text-effects/text-effect-conformance.json)
- Source-fidelity ledger: [source-fidelity.json](evidence/text-effects/source-fidelity.json)
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

Compare all canonical clones with a tracked VibeEdit source server:

```bash
npm run text:fidelity -- --source-base-url http://127.0.0.1:8765/text-effect-catalog/components/html-motion-mogrt/
```

Regenerate only the review sheets from saved previews with:

```bash
npm run text:previews -- --contact-only
```
