# Effects Recipes

Use these as deterministic starting points. Adjust only through semantic controls and available editing primitives.

## Shared Controls

- `intensity`: scales transform distance, blur, exposure, chromatic offset, shake, opacity, and audio cue strength together.
- `duration`: frame or second length of the event.
- `direction`: left/right/up/down/in/out/radial/custom vector.
- `optical_center`: subject, impact point, gaze target, frame center, object bbox center, or explicit coordinates.
- `subject_protection`: none/low/medium/high; reduces deformation over faces, text, captions, logos, hands, and important silhouettes.
- `audio_strength`: none/low/medium/high for whoosh, hit, riser, tail, or silence cue.

## Snap Zoom Impact

Job: emphasize impact, reveal, lyric, expression, or beat without losing subject readability.

Construction:

1. Duplicate or transform the target visual item over 6-14 frames.
2. Anchor scale to `optical_center`; overscan enough to avoid exposed edges.
3. Add anticipation: 1-3 frames of slight counter-scale or hold.
4. Peak scale on the impact frame, then settle with a small overshoot/correction.
5. Couple motion blur, exposure pulse, and optional chromatic offset to velocity.
6. Protect faces/text with reduced distortion or shorter peak.
7. Add optional low hit/whoosh through `sound-design`.

## Whip-Pan Bridge

Job: connect two clips through shared direction and velocity, not a canned transition.

Construction:

1. Ensure A and B have usable handles.
2. Move A out and B in along the same `direction` over 8-18 frames.
3. Place the cut/blend at maximum blur or frame-edge ambiguity.
4. Add directional blur and slight exposure streak peaking at the cut.
5. Align optical center with subject/action path when possible.
6. Settle B within 4-8 frames. Remove residual blur/color offset after settle.
7. Pair with a pre-cut whoosh and arrival hit when `audio_strength` is not none.

## Impact Flash

Job: punctuate a contact, beat, title reveal, or drop while preserving flash safety.

Construction:

1. Add a 1-4 frame exposure/color overlay centered on the target event.
2. Shape as quick attack, faster decay, never a repeating strobe.
3. Localize to impact region or mask protected subjects when needed.
4. Combine with subtle scale/shake only if it clarifies force.
5. Verify captions/text remain readable and the flash does not create unsafe patterns.

## Text Behind Subject

Job: make text feel embedded in the shot while preserving subject legibility.

Construction:

1. Route subject/background separation before constructing text. Prefer existing cutouts or masks; otherwise choose the best available segmentation/matting route for the footage and quality bar.
2. Place text between background and foreground subject layers.
3. Match perspective, scale, grain, color, and motion to the shot.
4. Animate text from a source anchor: gaze, motion path, beat, or reveal.
5. Add edge treatment only where masks need integration. Do not hide weak masking with excessive glow/blur.

## Object-Follow Reveal

Job: reveal text, clip B, color, or graphic treatment from a tracked object/person.

Construction:

1. Reuse object/person detections or cutouts. Use the highest-quality available segmentation when mask quality matters; use faster segmentation for previews or short interactive ranges.
2. Use object bbox/path as the reveal boundary or optical center.
3. Add look-ahead smoothing so the reveal anticipates motion without lag.
4. Keep the revealed element clipped to a clean region and settle after the object passes.
5. Verify the object remains readable and the reveal does not drift.

## Constructed Wipes and Slides

Job: transition by moving/timing/stacking timeline objects.

Construction:

1. Select a source-derived boundary: player motion, door edge, horizon, body silhouette, screen UI line, caption block, or object path.
2. Put A, B, matte/shape/text layers on separate timeline items.
3. Animate the matte or item transforms over the boundary; do not assume a stock transition.
4. Fill exposed edges through overscan, mirrored extension, background layer, or intentional graphic frame.
5. Coordinate B's entry motion and settle with A's exit.
6. If the project already has adjacent clips and no separate overlay/matte track, make the first pass non-destructive: propose transform/keyframe/matte additions against the existing timeline items, validate with the safest available dry-run or preview route, then apply only when the change can be confirmed.
7. In dry runs, identify adjacent clips by the project's native timing units and keep stable item labels or references in the plan so a later application step can target the same boundary.

## Editor Mapping

When an editor automation layer is available, map recipes to supported action families instead of raw data-file patches:

- Media/timing: select media, add clips, trim, split, move, and run sequence safety checks.
- Visual treatment: apply color/filter/processors, blend modes, keyframes, masks, and catalog transitions only when a catalog transition is explicitly requested.
- Text layers: add/style titles with exact text, style, transform, blend, and keyframe parameters.
- Audio coupling: place and mix whoosh, hit, riser, tail, ducking, or silence cues.

For constructed transitions, prefer clip movement, keyframes, masks, and color/blur treatment. Do not replace a constructed recipe with a stock transition unless the user asked for a catalog transition or the recipe deliberately uses one as a small component.

## Color, Blur, Chromatic, and Glitch Looks

Job: express viewpoint, energy, memory, digital disruption, speed, or emotional temperature.

Construction:

1. Define the look's job and duration before applying it.
2. Apply color/blur/chromatic/glitch as localized or time-bounded timeline treatment.
3. Couple intensity to beats, source motion, dialogue stress, or reveal timing.
4. Protect faces, captions, logos, and important objects.
5. Return to neutral unless the story intentionally stays altered.
6. Avoid random independent jitter. Keep parameters inside a designed envelope.

## Tutorial-Derived Effect Building Blocks

These examples come from short AE/Premiere-style tutorials but are rewritten as editor-neutral building blocks. Use them as named options and complexity references, not as mandatory presets. Each one still needs real source evidence, target timeline references, native timing units, keyframes, validation, and honest unproven claims.

### Analog Film Damage

Job: make a clip feel like unstable scanned film, decayed broadcast, or damaged memory without hiding the subject.

Construction:

1. Add a time-bounded adjustment/treatment item over the target range, or apply the treatment to selected clip items.
2. Slightly overscale the image, about `101-103%`, so shake and blur do not expose edges.
3. Add low-amplitude position jitter in a designed envelope; keep faces/text under `subject_protection` steadier than the background.
4. Layer monochrome or low-saturation noise around `8-20%`.
5. Add a small Gaussian blur, then a sharpening/unsharp pass so the image feels processed rather than merely soft.
6. Add exposure flicker with irregular but bounded keyframes; avoid repeating strobe patterns.
7. Add grain as the last visible pass. Keep intensity low enough that source action is still readable.
8. Validate that captions, faces, logos, and fast motion remain legible.

### Analog Glitch

Job: create analog signal breakup or tape-tracking disruption for digital stress, memory collapse, or a rough section bridge.

Construction:

1. Add contrast lift to simplify the image before distortion.
2. Add one or two stripe/venetian-blind-style masks or line mattes in different directions.
3. Add horizontal or vertical noise-wave displacement, keeping amplitude under control near protected subjects.
4. Add mild chromatic separation or color-channel offset, usually strongest for one to three frames around the peak.
5. Add glow or color tint only to the disrupted lines/bright regions.
6. Optionally posterize time for a short window such as `6-12fps` equivalent, then return to normal cadence.
7. Time the breakup as a phrase accent, interruption, or transition support. Do not leave random independent jitter running across unrelated footage.

### Apple-Style Text Slide

Job: introduce clean editorial text with product-style restraint, high readability, and smooth motion.

Construction:

1. Add a text item on a dedicated text track with exact timeline range and target message.
2. Animate position over about `15-20` frames from an offscreen or offset start to final placement.
3. Animate opacity from `0` to `100%` over about `12-15` frames.
4. Use eased curves with fast acceleration and a soft settle; avoid bounce unless the edit style calls for it.
5. Keep letter spacing, scale, and line breaks stable through the animation.
6. If placed over video, add a subtle background dim, blur, or subject-aware placement instead of a decorative card.

### Camera Shutter

Job: make a cut or photo sequence feel like camera bursts, paparazzi flashes, or rapid captured frames.

Construction:

1. Split or duplicate target moments into short `4-5` frame visual items.
2. Stagger items on upper tracks if the look uses multiple photo slices.
3. Animate each item from just outside the frame into position, or out of the frame into the next beat.
4. Add directional blur peaking near the movement frame and falling to zero by the settle frame.
5. Add a short glow/exposure pulse on the first visible frame of each shutter beat.
6. Use a consistent direction unless the story calls for chaotic capture.
7. Validate no black gaps appear between staggered slices.

### Chromatic Silhouette

Job: isolate a subject as a noisy chromatic outline, ghost, threat, aura, or music-reactive silhouette.

Construction:

1. Duplicate the source item above the original.
2. Route a temporal subject mask or cutout for the duplicate; a single face/object box is not enough.
3. Convert the duplicate to a high-contrast white or tinted silhouette.
4. Add light blur around `3-8px` and high monochrome noise when the silhouette should feel unstable.
5. Add chromatic offsets by channel around the silhouette edge, not across the entire frame unless distortion is intentional.
6. Cut or keyframe the silhouette in short bursts for flicker, or keep it continuous for a supernatural aura.
7. If segmentation is unavailable, fall back to a rough shape/matte and clearly mark edge quality as unproven.

### Crop Flash

Job: introduce the incoming clip as a cropped, overexposed graphic fragment before revealing normal contrast.

Construction:

1. Use incoming clip handles to create a separate `3-5` frame segment before or at the cut.
2. Crop and scale that segment to the chosen reveal area: face, hand, weapon, logo, horizon, motion edge, or abstract frame slice.
3. Set exposure/levels so the first frame is nearly blown out.
4. Animate white input/exposure back to normal by the final frame of the segment.
5. Snap or ease the crop/scale into the full incoming clip depending on whether the job is impact or smooth reveal.
6. Validate that the crop has a source-derived reason and is not just a random zoomed rectangle.

### Crystal Flash

Job: create a sharp refracted flash transition that feels like mirrored glass, fractured light, or an optical glitch.

Construction:

1. Add a `4` frame adjustment/treatment item centered on the cut or impact.
2. Add invert or negative treatment and animate original blend/mix from normal to full inversion and back.
3. Add non-uniform transform, such as scale-width expansion from about `100` to `140-155`, then back or into settle.
4. Add mirror/reflection-center motion across the frame over the same `4` frames.
5. Keep the strongest distortion on the cut frame or one frame before it.
6. Use sharp curves; the effect should feel like a snap, not a slow dissolve.
7. Validate against unsafe flashing and caption/face unreadability.

### Defocus Flash In

Job: bring a clip in through lens defocus, chromatic split, and brightness lift.

Construction:

1. Add a `4-6` frame adjustment/treatment item at the incoming clip start or cut.
2. Keyframe directional or lens blur from `0` to peak and back to `0`.
3. Add chromatic separation peaking at the same center frame.
4. Add lens distortion or scale warp with a negative/positive peak that relaxes into the incoming clip.
5. Add brightness/contrast lift only around the peak.
6. End with all distortion reset by the settle frame so the incoming clip reads cleanly.

### Dynamic Flicker

Job: make a cut, beat, or reveal pulse with rapid brightness/contrast alternation and short blur.

Construction:

1. Add a `5-7` frame treatment over the target frame.
2. Slightly scale up, about `103-106%`, to cover blur edges.
3. Keyframe directional blur `0 -> peak -> 0`.
4. Keyframe brightness and contrast on every frame in an alternating pattern, such as `0, high, 0, higher, 0, high, 0`.
5. Keep the pattern short. A long repeating flicker risks becoming unsafe and tiring.
6. Optional: add a secondary minimax/scatter/block layer below for grit if it improves the moment.

### Extract Flash Transition

Job: reduce the image to high-contrast luminance shapes during a transition, then return to normal.

Construction:

1. Add a `12-18` frame treatment over the cut.
2. Add luminance invert with four keyframes: normal, inverted/held, normal/held, normal.
3. Add extract/threshold controls to clamp shadows and highlights into graphic shapes.
4. Use softness to prevent harsh unreadable edges unless the intent is Xerox/poster damage.
5. Pair with subtle blur or scale only when it helps hide the cut.
6. Validate that important faces and captions are not lost in the threshold pass.

### Flash Slow Shutter

Job: create smeared exposure trails, dream motion, sports impact drag, or memory delay.

Construction:

1. Apply a short echo/trail treatment to the target clip or moment.
2. Use a negative time offset or previous-frame trail so motion leaves behind the subject.
3. Limit echo count to a small stack, around `3-6`, with decaying opacity.
4. Posterize time or sample fewer frames only for the affected window.
5. Add a bright exposure attack that returns to normal within about `3` frames.
6. Validate that the subject remains recognizable and the trail does not obscure the next edit.

### Glowing Dirty Camcorder

Job: make footage feel like degraded camcorder playback with glowing highlights and intermittent blur.

Construction:

1. Posterize time for the selected window or clip, usually around `8-12fps` equivalent.
2. Add repeating one- or two-frame directional blur pulses, not constant blur.
3. Add monochrome noise around `15-25%`.
4. Lift highlights and deepen blacks to exaggerate consumer-camera contrast.
5. Add glow only to highlight regions so the image blooms rather than washing out.
6. Use sparingly or as a section look; if applied for a long range, reduce pulse intensity.

### Heat Map

Job: turn footage into thermal, emotional intensity, scanning, or subject-analysis color.

Construction:

1. Add a localized or full-frame treatment item over the target range.
2. Blur enough to simplify detail before color mapping.
3. Add noise for texture if the look should feel measured or unstable.
4. Map luminance to a designed heat palette with dark/cool shadows and hot highlights.
5. If subject recognition matters, protect faces and silhouettes with reduced blur or partial opacity.
6. Return to neutral unless the heat map is a deliberate section look.

### Liquid Chrome

Job: create a reflective metallic distortion, liquid surface, or high-energy transition skin.

Construction:

1. Add an adjustment/treatment layer over the target range.
2. Use the source clip or a derived luminance/noise layer as a bump/displacement map.
3. Set displacement/height high enough to create surface motion but low enough to keep the subject readable.
4. Add moving light direction or specular intensity so the surface feels alive.
5. Add metallic contrast and roundness/specular controls.
6. Pair with a wipe or snap only if the chrome treatment is bridging two sections.
7. Fallback: if true bump mapping is unavailable, approximate with displacement, contrast, highlights, and masked blur.

### Negative Zoom Transition

Job: punctuate a cut by zooming through a noisy photographic negative.

Construction:

1. Add a `5-7` frame treatment over the cut.
2. Add monochrome noise around `15-25%`.
3. Scale to about `110-120%` at the peak to hide edges and increase force.
4. Keyframe brightness/contrast up then back to normal.
5. Keyframe inversion/negative treatment for one to three frames around the peak.
6. Settle scale and color by the final frame.

### Neon Extract

Job: reduce footage or text to a glowing colored outline or posterized neon signal.

Construction:

1. Add a treatment layer over the target window or selected subject/text.
2. Add noise and extract/threshold to isolate bright shapes.
3. Tint the extracted result to a chosen motivated color.
4. Add strobe or flicker only in short windows.
5. For text, add mosaic/block treatment before glow when a digital-display feel is desired.
6. Keep the original footage underneath unless the section intentionally becomes fully graphic.

### Radial Shutter Impact

Job: hit an impact with radial focus, noise, blur, and center-weighted force.

Construction:

1. Use a `4-6` frame treatment centered on the impact.
2. Scale up to around `108-112%` on the impact frame and return to `100%`.
3. Add high shutter/motion blur with directional or radial bias.
4. Add monochrome noise around `40-55%` for the impact frame only.
5. Use an oval or radial mask centered on `optical_center` so force concentrates around the subject or contact.
6. Reset blur, noise, scale, and exposure by the settle frame.

### Snap Wipe

Job: create a fast physical wipe or snap between clips through anchor movement, distortion, and stretch.

Construction:

1. Add a `3-5` frame treatment or matte around the cut.
2. Animate anchor/position rapidly across the frame, peaking at or just before the cut.
3. Add strong directional blur aligned with the wipe direction.
4. Add minimax/stretch or edge expansion to smear source detail into the wipe.
5. Add lens/optics compensation or slight rotation/scale for a more physical snap.
6. Settle the incoming clip within two to four frames.
7. Validate that no black edges are exposed during the snap.

### Swish Glow Transition

Job: bridge clips with a quick motion swish and soft glow.

Construction:

1. Add an `8-12` frame treatment centered on the cut.
2. Keyframe directional blur from `0` to a high peak at the cut and back to `0`.
3. Add glow that rises around the sides or center depending on the source luminance.
4. Use Bezier/eased curves so the swish accelerates into the cut and clears quickly.
5. Align direction with source motion or the intended next-frame entry.

### Textured Poster

Job: turn a subject and background into designed poster layers with texture separation.

Construction:

1. Duplicate the source and create a temporal mask/cutout for the subject.
2. Add background texture layers below the subject and subject texture layers clipped by the mask.
3. Use track-matte or mask routing so subject textures do not spill into the background.
4. Add noise or grain as an integration pass.
5. Choose two coherent color/texture families: one for subject, one for background.
6. Validate that subject edges are intentional and the poster treatment still reads at phone scale.

### Triple Extractor Directional

Job: create a hard directional flash with blur, luminance inversion, and threshold extraction.

Construction:

1. Add a very short treatment, around `3-5` frames, over the cut or impact.
2. Keyframe directional blur `0 -> high -> 0`.
3. Add a one-frame or two-frame luminance inversion peak.
4. Add extract/threshold to clamp the image into graphic blocks during the peak.
5. Use sharp curves. This should feel like an electrical snap, not a dissolve.
6. Reset all treatment values by the final frame.

### Twin Flash

Job: make a double-pulse transition or impact where the first pulse exposes detail and the second clears the frame.

Construction:

1. Add a `5-7` frame treatment over the target moment.
2. Keyframe levels/exposure with two distinct flashes rather than one smooth peak.
3. Add directional blur that peaks between or on the stronger pulse.
4. Keep the second pulse shorter or cleaner so the viewer can reorient.
5. Use for two-beat music accents, double impacts, or before/after reveals.

### Vortex Blur

Job: pull attention into a local swirl, tunnel, or pressure point without distorting the entire frame.

Construction:

1. Add radial/vortex blur as a masked local treatment around `optical_center`.
2. Feather the mask heavily so the effect blends into the original footage.
3. Keyframe blur amount up and down around the target action or cut.
4. Duplicate the treatment at multiple target points only when the footage motivates it.
5. Add minimax/edge smear at a cut if the vortex is being used as transition glue.
6. Fallback: if vortex blur is unavailable, approximate with radial blur, scale, and masked distortion.

### Wipe Flash Transition

Job: combine directional wipe energy with a flash so the cut feels fast but readable.

Construction:

1. Add a `5-7` frame treatment centered exactly on the cut.
2. Keyframe directional blur `0 -> high -> 0`.
3. Add exposure lift `0 -> high -> 0`, peaking on the cut frame.
4. Add alpha/edge handling or overscale so blur does not create black edges.
5. Align blur direction with source motion, object movement, or intended screen direction.
6. Duplicate only as a motif when the direction and intensity are varied by section.

### Xerox Photocopy

Job: turn a subject into a photocopied, noisy, high-contrast cutout for graphic emphasis or identity reveal.

Construction:

1. Create or reuse a temporal subject cutout.
2. Duplicate the original below so the photocopy can be blended over source context.
3. Add threshold/noise to the cutout layer, then shape midtones with curves.
4. Add tiny blur to avoid harsh digital stair-steps.
5. Add glow around high-contrast edges and a final noise pass.
6. Keep edge feather and contrast tuned to the subject; hair, hands, and props may require stronger mask quality.
