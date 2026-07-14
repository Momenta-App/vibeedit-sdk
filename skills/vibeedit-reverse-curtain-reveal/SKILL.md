---
name: vibeedit-reverse-curtain-reveal
description: "Create VibeEdit reverse crush / curtain reveal effects where the screen starts black and a video is revealed from the center by two opening bars. Use for horizontal or vertical curtain reveals, optional masked subject cutouts, optional random-frame-stutter backgrounds, SAM2.1 hard-edge alpha routing, configurable speed/easing/timing/bar color, and production-library artifacts."
---

# VibeEdit Reverse Curtain Reveal

Use this skill when a clip should start fully black and reveal the background video from the center as two black bars open outward.

This is the entry skill for the whole reverse-curtain family. Keep the base curtain simple unless the user asks for a subject cutout, a stuttered background, or a fan-edit impact variant.

## Render

Default horizontal reveal:

```bash
python3 .agents/skills/vibeedit-reverse-curtain-reveal/scripts/render_reverse_curtain_reveal_effect.py
```

Vertical reveal:

```bash
python3 .agents/skills/vibeedit-reverse-curtain-reveal/scripts/render_reverse_curtain_reveal_effect.py \
  --orientation vertical \
  --output-name 007__effect-reverse-curtain-reveal-vertical.mp4 \
  --no-manifest
```

Faster fan-edit reveal:

```bash
python3 .agents/skills/vibeedit-reverse-curtain-reveal/scripts/render_reverse_curtain_reveal_effect.py \
  --speed 2.0 \
  --open-duration 1.2 \
  --easing ease-out-cubic
```

Masked subject reveal with the preferred fan-edit options:

```bash
python3 .agents/skills/vibeedit-reverse-curtain-subject-reveal/scripts/render_reverse_curtain_subject_reveal_effect.py \
  --layer-mode subject_over_curtain \
  --background-mode random_frame_stutter \
  --orientation vertical \
  --mask-source external_alpha \
  --external-alpha /path/to/hard-edge-alpha.mp4 \
  --output-name 021__sam21-creed-random-stutter-vertical-curtain-subject-over.mp4
```

## Controls

- `--orientation horizontal`: reveals a center vertical strip that widens left/right.
- `--orientation vertical`: reveals a center horizontal strip that widens up/down.
- `--speed`: multiplies reveal speed by dividing `openDurationSeconds`.
- `--open-start`: delays the opening.
- `--open-duration`: base opening duration before speed is applied.
- `--duration`: total render duration.
- `--easing`: `smoothstep`, `linear`, or `ease-out-cubic`.
- `--feather-pixels`: softens bar edges when needed; default is crisp.
- `--bar-color`: RGB color for the bars; default is black.

## Composition Options

- Plain curtain: use this skill's renderer only.
- Masked subject curtain: route to `vibeedit-reverse-curtain-subject-reveal` for the advanced renderer and subject layer controls.
- Random-frame background: use `vibeedit-random-frame-stutter` as the behavior contract. Prefer one unique random source still per output frame for fast fan-edit versions. In the subject renderer this is exposed as `--background-mode random_frame_stutter`.
- SAM2.1 subject mask: use `vibeedit-sam21-video-segmentation` to create or review the alpha first, then pass it into the subject renderer with `--mask-source external_alpha --external-alpha /path/to/alpha.mp4`.
- Hard-edge mask rule: for this family, SAM alpha should be hard-edged by default. Do not add feathering, blur, dilation, softening, glow, rim, or shadow unless the user explicitly asks for a stylized edge.
- Preferred fan-edit route: slightly prefer `random_frame_stutter` plus hard-edge SAM2.1 alpha when the user wants the more complex/iconic subject reveal; use normal `source` background for cleaner cinematic reveals.

## Linked Skills

- `.agents/skills/vibeedit-reverse-curtain-subject-reveal/SKILL.md`: advanced masked-subject renderer, subject-over/under-curtain layer modes, external alpha wiring, source-length/no-hold validation.
- `.agents/skills/vibeedit-random-frame-stutter/SKILL.md`: random still/mini-burst selection rules, no-pause behavior, no-replacement diversity, optional rapid-frame SFX.
- `.agents/skills/vibeedit-sam21-video-segmentation/SKILL.md`: SAM2.1 prompt planning, local Torch/MPS segmentation, alpha review, hard-alpha QA.

When a task uses one of those options, read and follow the linked skill before rendering. The reverse curtain skill chooses the composition; the linked skills own their specialized behavior.

## Production Output

The default renderer writes:

`fan_Edit_Data/agent-artifacts/effect-building-pool/production-set-flat/007__effect-reverse-curtain-reveal-horizontal.mp4`

It also updates:

- `effect-reverse-curtain-reveal.recipe.json`
- `manifest.json`
- `README.md`
- `tmp/effect-building-pool-contact/*reverse-curtain*contact_sheet.jpg`

## QA

Run the validator after script edits or parameter changes:

```bash
python3 .agents/skills/vibeedit-reverse-curtain-reveal/scripts/quick_validate.py
```

The validator checks that both orientations render, probe as valid MP4 files, start black, end revealed, and keep monotonic reveal progress.
