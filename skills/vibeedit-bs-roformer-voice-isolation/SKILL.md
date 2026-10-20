---
name: vibeedit-bs-roformer-voice-isolation
description: Optional local BS-Roformer 1297 vocal and instrumental stem workflow with a pinned public audio-separator runtime, explicit customer-supplied permitted weights/config and listening review. Runtime/model inference qualification remains open.
---

# VibeEdit BS-Roformer Voice And Instrumental Isolation

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use for optional local vocal/instrumental stems when the task calls for clean dialogue, karaoke, lyric analysis or music removal. Preserve source audio and compare separation artifacts by listening before adoption. Model choice is explicit; do not silently replace BS-Roformer 1297 with another architecture.

## Availability and provenance

The owned runner is `scripts/isolate_voice_bs_roformer.py`. It uses public **audio-separator==0.47.0** (MIT) through its local Python API. Runtime wheel identity and upstream model/config release links are pinned in `references/provenance.json`. Install the optional runtime into a separate customer environment after checking disk/device requirements; it is not installed by the base SDK. `python scripts/isolate_voice_bs_roformer.py --probe` reports availability without downloading models or importing Torch.

BS-Roformer 1297 filename: `model_bs_roformer_ep_317_sdr_12.9755.ckpt`. The upstream release exposes no API SHA digest and the weight license has not been verified. The package bundles no weights and performs no automatic model download. Runtime MIT does not grant weight rights. Public model/runtime qualification remains open. A customer who already holds permitted local weights/config must supply a project-relative receipt with `model`, `modelSha256`, `config`, `configSha256`, `license`, `licenseUrl`, and `verifiedBy`. Do not invent that receipt or represent availability as commercial permission.

## Run from this installed skill directory

```bash
python scripts/isolate_voice_bs_roformer.py \
  --project "$PROJECT" --input media/source.mp4 \
  --model-receipt models/bs-roformer-permission.json \
  --start 42.25 --duration 8.5
```

`--start` / `--duration` are original-source seconds. Omit duration for the remaining source; frame requests must first be converted using the original probed rational frame rate. The runner extracts local PCM, pads sections shorter than two seconds for model safety, separates both stems and trims them back to the requested duration. It overrides the upstream download resolver to use only the exact local model/config. It never uses a private desktop script, local gauntlet cache or paid remote API.

Outputs live under project `artifacts/voice-isolation/<identity>/`: source/model/config/runtime/window-bound manifest, `vocals.wav` and `instrumental.wav`, with SHA256. Interrupted runs stay `running` and are not silently overwritten/retried. Preserve the original operation directory for inspection before explicitly choosing a new attempt. Successful separation remains `needs-listening-review`, with `inferenceQualified=false` until the pinned runtime/model pair is actually qualified.

Listen to speech clarity, music leakage, transients and artifacts at the exact trimmed boundaries. Register the selected stem in the project, retain its source-clock/manifest lineage, and mix through the SDK. If this optional route is unavailable, continue other editing work and report the precise missing runtime/model/rights or qualification step; do not claim isolated voice.
