---
name: vibeedit-reverse-curtain-subject-reveal
description: "Advanced companion for vibeedit-reverse-curtain-reveal. Use after the main reverse-curtain skill selects a masked subject cutout: subject-over/under-curtain layer modes, external hard-edge SAM2.1 alpha, slowed bottom-anchored moving subjects, optional random-frame-stutter backgrounds, and production-library review artifacts."
---

# VibeEdit Reverse Curtain Subject Reveal

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use after the sibling `vibeedit-reverse-curtain-reveal` skill selects a moving cutout. Preserve a strong source moment, readable motion and a clean landing; source exhaustion must never hide as a final-frame freeze.

## Explicit inputs

Run from this installed skill directory in the SDK Python environment. Supply a user-owned project, relative source and reviewed alpha-video paths, and explicit original-source subject/background windows. The alpha starts at the selected subject-window start, matches the original source FPS and covers every selected frame. Its full-frame coordinate geometry must match the original source before the identical center crop. A detached model index or candidate PNG is not a ready alpha video.

```bash
python scripts/render_reverse_curtain_subject_reveal_effect.py \
  --project "$PROJECT" --input media/source.mp4 \
  --source-start 0 --source-end 2 --background-start 2 --background-end 6 \
  --external-alpha masks/reviewed-alpha.mp4 --mask-source external_alpha \
  --duration 3.2 --layer-mode subject_over_curtain \
  --orientation vertical --background-mode random_frame_stutter \
  --output-name subject-reveal-v1.mp4
```

Actual SAM2.1 or SAM3.1 mask creation is explicit: inspect `vibeedit models describe sam21` / `sam31-mlx`, run the selected model, review its native source/frame/candidate output and persist accepted selections. Use `models effect` for SDK-supported subject fills. For this companion's full subject cutout, materialize a reviewed source-aligned alpha video separately. There is no implicit Apple Vision or other model fallback. A geometric alpha is useful only as a labeled compositing fixture, never proof of SAM quality.

## Layer and timing rules

- `subject_over_curtain`: cutout remains visible above the black bars.
- `subject_under_curtain`: cutout appears only through the opening.
- `--background-mode source`: normal moving source background.
- `random_frame_stutter` (`stutter` alias): one random source still per output frame sampled without replacement inside the explicit window; insufficient diversity fails. Keep the pool broad enough to avoid accidental repeated frames.
- `--orientation horizontal|vertical`: left/right or up/down opening as in the parent skill.
- `--speed`, `--open-start`, `--open-duration`: reveal timing; higher speed shortens effective opening duration.
- `--subject-min-playback-speed` defaults to 0.5. Provide at least half the render's real duration in continuous source/mask frames. Too short fails; never accept final-frame hold.
- `--subject-scale`, `--subject-y-offset`: bottom-anchored subject placement; inspect faces/hands/feet for crop damage.
- Mask defaults are hard (`maskBlur=0`, `maskDilate=0`, `maskOpen=0`). Do not soften or stylize edges unless requested.
- `--mask-allow-components`: preserve disconnected subject parts; default largest-component cleanup can discard objects, limbs or secondary people and needs review.
- Shadow/rim strength defaults to zero. Add only for an explicit style reason, never to hide a poor matte.

This OpenCV recipe is limited to CFR sources and ordinal frame mapping. A VFR source needs an explicit normalized proxy with retained original-clock mapping; a matching average rate alone is not a guarantee of every native timestamp. Use the SDK native-clock workflow for that preparation.

## Output and review

Every new output name creates project-relative `artifacts/curtain/<name>/` with a silent video, contact/matte sheets and source/alpha/output SHA-bound receipt. Source clock, windows, geometry, frame trace and mechanical limits remain inspectable. No output is automatically promoted into a production library.

```bash
python scripts/quick_validate.py --project "$PROJECT" \
  --receipt artifacts/curtain/subject-reveal-v1/receipt.json
```

Inspect full speed and sampled edges, both layer modes, full reveal landing, unique source-frame counts, no end hold, nonempty masks, subject framing and downstream audio sync. A successful fixture validates compositing only. Real model quality and editorial acceptance require actual footage and a recorded review.
