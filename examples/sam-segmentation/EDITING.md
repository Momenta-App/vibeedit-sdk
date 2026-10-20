# SAM candidates and reviewed subject effects

The legacy candidate example uses the SDK's packaged SAM 2.1 provider. Without it, `render.py` writes actionable unavailable evidence. With it, the example writes candidates and stops at `segmentation-needs-review.json`; it does not render an unmasked video and claim an effect. A configured custom provider must retain its actual model provenance. No SAM version is silently substituted.

For a production effect use the explicit model-pack workflow on your source:

```sh
vibeedit models setup sam21 --cache "MODEL_CACHE" --json
vibeedit models run sam21 "source.mp4" --frames 0,10,20 --prompt '{"boxNormalized":[0.1,0.05,0.8,0.95]}' --output mask-index.json --cache "MODEL_CACHE" --json
```

Choose frame ordinals and prompts for the actual subject. Review each candidate at its original source frame, especially hard cuts, occlusion/contact and boundaries. Save `mask-review.json` with schema `vibeedit.mask-review.v1`, exact index/source SHA-256, actual reviewer, `reviewed: true`, explicit sparse/dense mode and `{frameOrdinal,candidate}` selections. Missing sparse frames remain inactive.

```sh
vibeedit models effect mask-index.json --review mask-review.json --source "source.mp4" --output derived/subject-flash --color '#ffffff' --json
```

This produces the visible derivative plus editable CompositionSpec/provenance using the same original frame/PTS mapping. The general renderer does not implement a mask merely because `maskIds` is present. For Apple Silicon SAM 3.1 use the distinct `sam31-mlx` setup/run pack, then the same source/index-bound review/effect steps. Its actual SAM3.1/MLX terms, resource probes and inference qualification are separate from SAM2.1; inspect `vibeedit models list --json` and the source archive's model guide.

The generated ellipse in `mask-subject-effect` is a compositing fixture. It supplies no SAM inference or real-subject quality proof. Real model inference and cut/occlusion/contact review remain required for launch acceptance.
