---
name: effects
description: Design visual effects, transitions, background-removal routes, text treatments, and reusable preset recipes built from timeline primitives. Use for snap zoom impacts, whip-pan bridges, impact flashes, text-behind-subject, object-follow reveals, constructed wipes/slides, color/blur/chromatic/glitch looks, subject protection, and semantic controls such as intensity, duration, direction, optical center, subject protection, and audio strength. Do not use for app integration work.
---

# Effects

Build effects as deterministic recipes, not generic preset names. A recipe is a timeline construction from clips/items, transforms, keyframes, masks/cutouts, blend/opacity/color/blur/chromatic/glitch primitives, text layers, timing, and optional audio cues.

## Editing Contract

- Treat inspected source media, timeline state, analysis artifacts, and derived assets as truth. Do not invent effects, masks, renders, or tool support.
- Prefer existing transcripts, captions, beat maps, scenes, object/person detections, cutouts, derived assets, and timeline state before requesting new analysis.
- Make reversible, timeline-native changes where possible and preserve source media/provenance.
- In orchestrated production flows, Lead Editor is the only production writer; this skill supplies effect recipes, route choices, target specs, and review notes.
- Verify timeline and render readiness after meaningful changes when possible. Never claim a render, preview, mutation, detection, cutout, or background-removal result exists unless evidence proves it.
- Keep proof states distinct: `planned`, `dry-run`, `applied`, `confirmed`, `previewed`, `rendered`, and `proven`. If execution is unavailable, return an execution-ready timeline plan with exact assumptions and mark unproven work as unproven.

## Recipe Method

1. Inspect source clip(s), timeline context, handles, frame rate, aspect ratio, audio anchors, protected subjects, captions/text, and available editing primitives.
2. State the effect job: continuity, emphasis, concealment, reveal, energy change, viewpoint, rhythm, or readability.
   - Scale by selected edit effort when present: Low uses one simple supported treatment or none when a clean cut is stronger; Medium adds a modest support layer and one clear transition/accent idea; High considers varied section-level treatments, subject/readability choices, and effect-pack discovery when useful; Ultra may combine constructed transitions, subject/background routes, chained effect packs, and polish passes only when verified capabilities support them.
3. Choose a source anchor: motion path, impact, gaze, geometry, color boundary, object, lyric, transient, silence, or foreground/background relationship.
4. Pick the effect family from the job and anchor, not from a favorite preset. When multiple families fit, name the tradeoff and choose one; vary from recent same-source choices if the evidence supports more than one valid treatment.
5. Build one dominant structural action, then add only support layers that improve the job.
6. Define semantic controls: `intensity`, `duration`, `direction`, `optical_center`, `subject_protection`, and `audio_strength`. Add recipe-specific controls only when useful.
7. Choreograph phases: anticipation, acceleration, peak/cut/reveal, release, settle. Use non-linear curves unless linearity is the point.
8. Apply as small reversible timeline changes when execution is available. Verify no black borders, unintended text/face warping, alpha holes, unsafe flashes, unreadable captions, or bad settles.

## Background-Removal Routing

Reuse existing cutouts, detections, masks, and derived assets first.

- Fast local video segmentation: use for person/subject cutouts or background separation when semantic localization is simple and speed matters.
- Interactive segmentation: use for object/background masks, preview-quality cutouts, or short video ranges where speed matters. Good prompt style: give a concrete target and selection cue, such as `mask the person in the red jacket`, `separate the foreground car`, or `remove the sky background`; include a point, box, frame, or reference when the tool supports it.
- High-quality segmentation: use when edge quality matters: hair, hands, faces, props, overlapping people, product edges, or hero cutouts. Good prompt style: specify the exact subject boundary and what to exclude, such as `keep the full dancer including hair and hands; exclude the wall and shadow`.
- Strongest available still-image matting or segmentation: use for difficult still images, high-quality mattes, or final cutouts. Confirm video support before promising temporal masks.
- If the route is unavailable, do not fake a cutout. Use a non-segmentation design or report the missing capability.

## Core Recipes

Read `references/recipes.md` for exact constructions and controls. Include at least these options when relevant:

- Snap zoom impact
- Whip-pan bridge
- Impact flash
- Text-behind-subject
- Object-follow reveal
- Constructed wipes and slides
- Color, blur, chromatic, and glitch looks

## Preset Rules

Presets are allowed only as deterministic recipes. A good preset exposes semantic controls and maps them to timeline changes. Avoid opaque names like "cool glitch"; prefer `glitch-look(intensity=0.35, duration=12f, subject_protection=high, audio_strength=low)`.

## Anti-Bias Selection

- Calibration examples and core recipes are a detail standard, not a menu of preferred answers. Do not default to flashes, zooms, glitches, or subject cutouts unless the inspected moment calls for them.
- For a full edit, use different effect jobs across sections: for example one continuity bridge, one impact accent, one subject/readability treatment, one texture/viewpoint passage, and one plain cut section when appropriate.
- If two valid effects fit the same source moment, choose the one that best clarifies story, motion, or rhythm; record the rejected option briefly when the choice is close.
- Higher effort does not authorize unsupported claims. Keep unavailable custom shaders, masks, previews, renders, generated assets, or effect-pack outputs explicitly skipped, fallback-only, or unproven. Low and Medium should not be escalated into full effect-stack plans unless the user asks.

## Output Shape

Report the selected effort level, recipe, source anchors, exact timeline targets, controls, mutation proof state, subject/background route, confirmation/verification evidence, and unresolved risks. Never say an effect rendered or previewed unless the preview/render was actually produced and inspected.
