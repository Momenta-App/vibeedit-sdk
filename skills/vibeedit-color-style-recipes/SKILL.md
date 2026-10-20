---
name: vibeedit-color-style-recipes
description: Apply repeatable fan-edit color and style recipes, including black-and-white-to-color intensity switches, red emphasis, contrast grades, grain, vignette, and source unification.
---

# VibeEdit Color Style Recipes

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill when defining or applying the visual identity of a fan edit.

## Core Rule

Color is part of the story. Pick a look that supports the emotion and keep it consistent enough that mixed source clips feel like one edit.

## Common Recipes

- Villain/cold: low exposure, high contrast, cool shadows, restrained saturation, red accent, hard vignette.
- Hero/triumph: bright highlights, warm skin, controlled contrast, glow on reveal or victory.
- Tragedy: low saturation, faded blacks, slow contrast rise, soft vignette, minimal flashes.
- Sports/action: high contrast, sharpness, saturation pop, impact flashes, brief shake.
- Nostalgia: warm grade, light grain, lower contrast, soft bloom, slower dissolves.
- Dark-to-intense: black-and-white or low saturation intro, then color returns on drop or decision.

## Red Usage

Use red deliberately:

- Key lyric or quote word.
- Blood, danger, villain, anger, warning, rivalry, or power.
- Text extrusion, underline, shadow, edge glow, or brief flicker.
- Avoid making every word red; red loses force when constant.

## Implementation

- Use adjustment layers for global grade.
- Use clip-level correction to match exposure and skin/subject visibility.
- Use vignettes to focus faces, not to hide poor framing.
- Use grain/noise lightly to unify sources.
- Use color pulses only on beats or transitions.

## QA Checklist

- Grade supports the edit thesis.
- Subject remains visible after contrast/vignette.
- Color switch has a story or audio trigger.
- Red accents mark important moments only.
- Mixed sources feel intentionally unified.
