---
name: vibeedit-segmentation-cutouts
description: Use SAM-style masks, character cutouts, object layers, foreground/background separation, and frame-accurate cutout transitions in VibeEdit fan edits.
---

# VibeEdit Segmentation Cutouts

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill when a fan edit needs cutouts, background removal, text behind subjects, object-only effects, or mask-based transitions.

## When To Segment

- Character intro with the subject isolated over black or a moving background.
- Text behind subject or beside subject with clean occlusion.
- Object-only flash on minor beats.
- Foreground subject transition into the next clip.
- Background replacement, curtain reveal, poster-style title frame, or layered motion.

## Frame-Accurate Transition Recipe

This transition uses the start of clip B as a masked layer over the end of clip A.

1. Choose clip B with a strong segmentable person/object in its first 0.3 to 1.0 seconds.
2. Generate a mask for that exact duration from the start of clip B.
3. Remove that same duration from the visible start of clip B.
4. Place the masked subject from clip B over the end of clip A.
5. Time the masked layer so its final transition frame matches the first visible frame of clip B.
6. At the cut, the mask should be in the exact same position, scale, pose, and timestamp as clip B.
7. Optionally animate the masked layer entering from side, top, bottom, scale, blur, or opacity, but it must land perfectly at the cut.

## Tools

- Prefer local segmentation: SAM 2.1/SAM 3.1, Apple Vision, rembg/U2Net, OpenCV masks, or project-provided mask artifacts.
- Use masks as alpha videos or image sequences.
- Store masks with source timestamp, frame count, fps, and crop/scale metadata.
- Do not use low-quality masks for text-behind-subject if edges flicker.

## Layering Rules

- Base video on lower track.
- Cutout/masked subject above base.
- Text above or below cutout depending on occlusion design.
- Adjustment effects can target full frame or mask layer only.
- Keep matte edges clean with feathering, choke/expand, and motion blur when needed.

## QA Checklist

- Mask duration and clip-B removed duration match exactly.
- Cutout lands frame-accurately on the clip-B start.
- No visible jump in scale, position, or pose at transition.
- Mask edge flicker is not more distracting than the transition benefit.
- Text behind subject stays readable and does not fight the mask.
