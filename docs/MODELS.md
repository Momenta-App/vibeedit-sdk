# Optional local model packs

Core editing needs no model weights. Model setup and inference are optional, explicit operations. This is the `0.2.0-beta.1` qualification guide; full TransNet/SAM2.1/SAM3.1/Apple Silicon acceptance remains open in the [launch ledger](launch/PUBLIC-LEDGER.json).

```sh
vibeedit models list --json
vibeedit models probe sam31-mlx --json
```

The catalog reports immutable source/weight pins, terms, download sizes, resource estimates and unsupported states. Setup uses `uv` and an isolated Python 3.12 environment. Weights are not shipped inside the base archives. Dependency/runtime overhead is additional to the listed downloads.

| Pack | Pinned runtime and model | Download estimate | Limits |
|---|---|---|---|
| `transnet` | Official TransNetV2; TensorFlow 2.21.0 | 36.5 MB plus runtime | Shot candidates, not semantic scene understanding. |
| `sam21` | Meta SAM2.1 hiera tiny; Torch 2.12.0 | 211.7 MB plus runtime | Explicit target box; actual CUDA/MPS/CPU selection is reported. |
| `sam31-mlx` | Public MLX-community SAM3.1 bf16; mlx-vlm 0.7.6 | 3.495 GB plus runtime | Apple Silicon MLX/Metal; 16 GB memory estimate. Independent per-frame candidates. |

The actual Linux CPU TransNet qualification on a 144-frame native-clock fixture returned the three manually observed incoming cut boundaries 8,37,123. Its raw prediction peaks 7,36,122 refer to outgoing frames. This bounded case does not establish general cut accuracy. [The supplemental workflow](https://github.com/Momenta-App/vibeedit-sdk/actions/runs/39510473292) retains exact final-wheel, native-frame and runtime identities. The same workflow ran SAM2.1 on CPU and returned 18 native-resolution candidates for six selected frames. Candidate review found foreground/background leakage, partial bodies and contact-edge defects; higher scores did not reliably identify the best subject mask. Full SAM2.1 editorial review and SAM3.1 Apple Silicon inference remain required. Template shapes are not SAM evidence.

Pinned TensorFlow 2.21 and Torch 2.12 macOS wheels support ARM64 rather than Intel. Their model packs report unsupported on Intel macOS while portable core editing remains separate. MLX reports unsupported on Intel macOS, Linux and Windows; it never substitutes SAM2.1. Current runtime-wheel floors include macOS 12 for TensorFlow and macOS 14 for Torch/MLX. These are installation constraints, not qualification of every OS release or GPU. The standard hosted Apple runner's 7 GB memory is below SAM3.1's estimate despite its available Metal device.

## Setup and inference

```sh
vibeedit models setup transnet --cache ./model-cache --json
vibeedit models run transnet source.mp4 --cache ./model-cache --max-frames 1200 --output source.shots.json --json
vibeedit models setup sam21 --cache ./model-cache --json
vibeedit models run sam21 source.mp4 --cache ./model-cache --frames 0,10,20 --prompt '{"boxNormalized":[0.1,0.05,0.8,0.95]}' --output subject.json --json
vibeedit models setup sam31-mlx --cache ./model-cache --json
vibeedit models run sam31-mlx source.mp4 --cache ./model-cache --frames 0,10,20 --prompt '{"text":"a person"}' --output subject-sam31.json --json
```

Select an adequately sized cache volume, but system swap headroom is still required. Before heavy inference, the shared resource gate checks system-volume free space of at least 25 GiB, at least 15% free memory, and available one/five-minute load no greater than 10. Unknown memory probes fail closed. Setup estimates and model-specific memory needs are separate requirements. The package does not delete user files or kill unrelated processes to satisfy a gate.

One per-user cross-process lease coordinates heavy work across model-cache choices. After a crash, inspect its recorded owner and actual original process before removing only a proven-stale lease. Partial outputs are retained for inspection rather than overwritten. Existing output reuse requires the same source/model/runtime/prompt/frame identities and unchanged mask bytes.

Models retain exact source SHA256/length, native frame ordinals, PTS, time base/origin and prompt/runtime/model provenance. Nonmonotonic clocks require an explicit mapping. TransNet preserves raw predictions and half-open native shot ranges. SAM emits a `vibeedit.masks.v1` index plus native-resolution PNG alternatives. Every candidate and score is retained; top score is not confirmed identity. Unselected frames have no mask.

SAM2.1 requires exactly one explicit native-pixel `box` or `[0,1]` `boxNormalized`. SAM3.1 requires target `text`, with optional native-pixel `box` and finite `[0,1]` `scoreThreshold`. Unknown fields, invalid coordinates and nonfinite values fail closed. Inference uses verified local artifacts without implicit model downloads.

## Review and editable effects

Inspect target identity, full-resolution edges, hard cuts, occlusion entry/exit, subject/prop contact and neighboring-frame stability. A runtime probe or nonempty mask is insufficient. Independent per-frame inference can support sparse flashes; it is not automatic long-video tracking.

After inspecting the PNG alternatives, save a source/index-bound review:

```json
{
  "schemaVersion": "vibeedit.mask-review.v1",
  "indexSha256": "<actual immutable index SHA256>",
  "sourceSha256": "<actual source SHA256>",
  "author": "<actual reviewer>",
  "reviewed": true,
  "mode": "sparse",
  "selections": [{"frameOrdinal": 10, "candidate": 0}]
}
```

`sparse` leaves other frames inactive. `dense` requires a selection or explicit empty decision for every native frame. Never carry a later frame's mask backward to fill a gap.

```sh
vibeedit models export subject-sam31.json --review mask-review.json --output reviewed-mask.json --id subject --json
vibeedit models effect subject-sam31.json --review mask-review.json --source source.mp4 --output derived/subject-flash --color '#ffffff' --json
```

Export adapts reviewed candidates into the existing SAM RLE/CompositionSpec contract. Effect renders an actual same-frame composite and a derived editable video layer, retaining selected masks, original index/review audit copies and exact source-frame mappings. Its visual MP4 is silent; retain original audio timing separately in the parent edit. Encoding is lossy, so inspect the actual result, including pixels outside masks, before acceptance.

The default effect mapping requires CFR with rational-clock quantization tolerance. VFR/irregular input needs explicit `--frame-map` data declaring source ordinals; the loss report identifies repeated/dropped frames. Source media remains intact.

Place the index and its complete `.masks` sibling directory under the project, alongside review/export files. Register the entire model-result tree under `project register-artifact --category masks` and the entire effect tree under `--category renders`, with the current revision and registered source ID. [Project guidance](PROJECTS.md) shows the exact registration/export commands. Registering only the index omits its PNG alternatives.

## Terms and provenance

Machine-readable definitions are in `python/src/vibeedit/model_packs.py`; detailed SAM3.1/tokenizer pins are packaged in `model_runners/pins.json`. TransNet and SAM2.1 preserve their upstream terms. SAM3.1 uses the custom [SAM License](https://github.com/facebookresearch/sam3/blob/7f473cfd983d5eb43040ff608f66bff0d7bdcb53/LICENSE); MLX-vlm and CLIP retain their separate MIT terms. Optional downloads preserve the pinned notices. VibeEdit's MIT license does not relicense upstream weights. No private model cache, source movie or research library is a runtime dependency.
