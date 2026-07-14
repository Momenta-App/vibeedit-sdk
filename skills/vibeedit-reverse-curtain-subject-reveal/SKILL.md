---
name: vibeedit-reverse-curtain-subject-reveal
description: "Advanced companion for vibeedit-reverse-curtain-reveal. Use after the main reverse-curtain skill selects a masked subject cutout: subject-over/under-curtain layer modes, external hard-edge SAM2.1 alpha, slowed bottom-anchored moving subjects, optional random-frame-stutter backgrounds, and production-library review artifacts."
---

# VibeEdit Reverse Curtain Subject Reveal Companion

Use this as the advanced renderer for `vibeedit-reverse-curtain-reveal` when the effect needs a segmented character video cutout from a strong source moment.

Do not treat this as a separate top-level family. The main reverse-curtain skill chooses whether to use plain curtain, masked subject, random-frame background, SAM alpha, or a combination.

## Linked Skill Contracts

- Main route: `.agents/skills/vibeedit-reverse-curtain-reveal/SKILL.md`.
- Random-frame background: before using `--background-mode random_frame_stutter`, follow `.agents/skills/vibeedit-random-frame-stutter/SKILL.md` for no-pause, no-replacement, broad candidate-pool behavior.
- SAM2.1 alpha: when a reviewed alpha does not already exist, use `.agents/skills/vibeedit-sam21-video-segmentation/SKILL.md` first, then pass the accepted alpha with `--mask-source external_alpha --external-alpha /path/to/alpha.mp4`.
- Hard-edge rule: SAM alpha for this effect should be hard-edged by default. Do not feather, blur, dilate, soften, add glow, or hide edge quality unless the user explicitly asks for a stylized edge.

## Render

Default production example, subject above the curtain:

```bash
python3 .agents/skills/vibeedit-reverse-curtain-subject-reveal/scripts/render_reverse_curtain_subject_reveal_effect.py
```

Subject over a vertical-opening curtain with a random-frame-stutter background:

```bash
python3 .agents/skills/vibeedit-reverse-curtain-subject-reveal/scripts/render_reverse_curtain_subject_reveal_effect.py \
  --layer-mode subject_over_curtain \
  --background-mode random_frame_stutter \
  --orientation vertical \
  --output-name 021__sam21-creed-random-stutter-vertical-curtain-subject-over.mp4 \
  --no-library-update
```

## Controls

- `--layer-mode subject_over_curtain`: subject cutout is visible over black bars while the background opens.
- `--layer-mode subject_under_curtain`: subject cutout is under the bars and appears only inside the opening.
- `--background-mode source`: normal moving background.
- `--background-mode random_frame_stutter`: imports the `vibeedit-random-frame-stutter` behavior contract: one random source still per output frame, no repeated source frame when enough source frames exist. `stutter` is kept as a compatibility alias.
- `--orientation horizontal|vertical`: `vertical` uses horizontal bars that reveal the background by opening up/down from the center.
- `--speed`, `--open-start`, `--open-duration`: adjust reveal timing. The default curtain open duration is 3.0 seconds; higher speed shortens the effective open time for fast fan-edit hits.
- `--source-start`, `--source-end`: choose the character video moment used for the slowed subject cutout.
- `--background-start`, `--background-end`: choose the normal background window.
- `--subject-min-playback-speed`: minimum subject-layer playback speed. Default `0.5` means the subject is never slowed down past 0.5x; choose enough source and mask frames so the final source frame does not hold before the render ends.
- `--mask-source apple_vision`: default local person matte.
- `--mask-source external_alpha --external-alpha /path/to/alpha.mp4`: use a reviewed SAM2.1/SAM3 alpha video for the cutout.
- Mask edge defaults are hard: `maskBlur=0`, `maskDilate=0`, and `maskOpen=0`. Do not add smoothing, feathering, dilation, shadow, or rim lift unless the user explicitly asks for a stylized softened edge.
- `--mask-allow-components`: disable the default external-alpha connected-component cleanup. By default, SAM mattes keep the largest component to remove stray background blobs.
- `--subject-shadow-strength`, `--subject-rim-strength`: add subtle subject separation for subject-over-curtain variants.

## Mask Route

Default fallback mask route is Apple Vision `VNGeneratePersonSegmentationRequest` with accurate quality because this is a person cutout. For production fan-edit subject reveals, prefer a reviewed hard-edge SAM2.1 alpha when available or when the user asks for SAM quality. Use `vibeedit-sam21-video-segmentation` to create that alpha and `vibeedit-masking-router` before changing to any other model route.

The default selected moment is a longer Creed 2 Adonis window around `3900.0s`, chosen because it has enough continuous source frames for the 3.2s render at the default `0.5x` subject playback floor. Prefer source windows like this over short iconic shots that force a final-frame hold.

Hard source-length rule: do not accept or promote a render where the masked subject layer exhausts its source/mask frames and holds the final frame before the render ends. Pick a longer source window or rerun SAM with more frames. For the default `subject-min-playback-speed=0.5`, a 3.2s render needs enough mask frames to cover at least 1.6s of real source time; more is better. Treat validation `subjectHasNoEndHold=false` as a failed review render.

Combined stutter-curtain rule: for the production combined effect, the main reverse-curtain skill should select this companion renderer with `background-mode=random_frame_stutter`, `orientation=vertical`, and `layer-mode=subject_over_curtain`. This produces a different random background image every output frame, horizontal curtain bars opening up/down, and the hard-edge masked subject composited on top.

For SAM2.1 comparison, first run the prepared contract under:

`fan_Edit_Data/agent-artifacts/effect-building-pool/reverse-curtain-subject-reveal/sam21-small-test/prompt_contract.json`

After the SAM2.1 run writes a reviewed `alpha.mp4`, render with:

```bash
python3 .agents/skills/vibeedit-reverse-curtain-subject-reveal/scripts/render_reverse_curtain_subject_reveal_effect.py \
  --mask-source external_alpha \
  --external-alpha /path/to/sam21/alpha.mp4 \
  --output-name 008__effect-reverse-curtain-subject-reveal-sam21-small-over.mp4
```

## Production Output

Default render:

`fan_Edit_Data/agent-artifacts/effect-building-pool/production-set-flat/021__sam21-creed-random-stutter-vertical-curtain-subject-over.mp4`

Recipe:

`fan_Edit_Data/agent-artifacts/effect-building-pool/production-set-flat/effect-reverse-curtain-subject-reveal.recipe.json`

## QA

```bash
python3 .agents/skills/vibeedit-reverse-curtain-subject-reveal/scripts/quick_validate.py
```

Validation renders both layer modes, probes the MP4s, checks monotonic curtain progress, confirms non-empty masks, verifies the cutout uses many source frames, and writes contact sheets.
