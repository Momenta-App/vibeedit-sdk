---
name: vibeedit-reverse-curtain-reveal
description: "Create VibeEdit reverse crush / curtain reveal effects where the screen starts black and a video is revealed from the center by two opening bars. Use for horizontal or vertical curtain reveals, optional masked subject cutouts, optional random-frame-stutter backgrounds, SAM2.1 hard-edge alpha routing, configurable speed/easing/timing/bar color, and production-library artifacts."
---

# VibeEdit Reverse Curtain Reveal

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


A screen starts black and two bars open outward from the center. Keep the base reveal simple; select a masked subject or randomized background only when it improves the source moment.

## Portable render

Run from this installed skill directory, using the Python environment containing the SDK, OpenCV and NumPy. `PROJECT` is the user's project directory. Source paths are relative to it; the source must cover the complete requested duration.

```bash
python scripts/render_reverse_curtain_reveal_effect.py \
  --project "$PROJECT" --input media/source.mp4 --source-start 0 \
  --duration 3.2 --orientation horizontal --output-name reveal-v1.mp4
```

The script never discovers a movie library. Each new output name creates `artifacts/curtain/<name>/` with the silent MP4, contact sheet and SHA-bound source/clock/trace/validation receipt. Existing runs are preserved; use a new name for revisions. Mix approved audio separately using the SDK CompositionSpec.

## Controls and creative contract

- `--orientation horizontal`: a center vertical strip widens left/right.
- `--orientation vertical`: a center horizontal strip widens up/down.
- `--speed` divides `--open-duration`; 1.5–3 can suit fast fan-edit punctuation.
- `--open-start` delays opening. `--duration` sets total output length; allow a readable revealed hold.
- `--easing smoothstep|linear|ease-out-cubic` controls acceleration.
- `--feather-pixels` softens bar edges only when intended; default crisp.
- `--bar-color R,G,B` defaults to black.

For a masked subject, read the sibling `vibeedit-reverse-curtain-subject-reveal` skill. Obtain actual masks using the explicitly selected SDK `models run sam21` or `models run sam31-mlx`, review source/frame/candidate identities, then materialize a source-aligned alpha. Never substitute a geometric mask as segmentation evidence. The SDK model-index export is not itself an alpha-video transport; producing a full aligned reviewed alpha is a separate explicit step.

The subject companion implements randomized-frame background selection internally: sample without replacement only from the explicit background window, one unique source frame per output frame. A short candidate pool fails instead of extending into unrelated source footage. Do not pause/freeze unless the creative brief explicitly asks for a repeat motif.

Hard-edge alpha is the default: do not blur, dilate, feather, glow or shadow the subject unless the brief asks for stylized edges. Prefer the plain source background for cinematic reveals and randomized background plus hard-edge alpha for intentionally busy iconic hits.

This OpenCV recipe is limited to CFR sources and ordinal frame mapping. VFR needs an explicit normalized proxy retaining original-clock mapping; a matching average rate alone is not a guarantee of every native timestamp.

## Verification

```bash
python scripts/quick_validate.py --project "$PROJECT" \
  --receipt artifacts/curtain/reveal-v1/receipt.json
```

The validator rechecks exact source/output hashes, dimensions/frame count and start-black/end-revealed/monotonic progress tests. Review the actual video/contact sheet for the source moment, framing, edge quality, timing and audio mix before acceptance. Passing mechanical checks leaves `needs-editorial-review` visible.
