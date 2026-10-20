---
name: look-director
description: Design visual style, color, framing, texture, mood, shot treatment, and look consistency for a video edit. Use for look plans, color/grade direction, visual hierarchy, and supported effect choices.
---

# Look Director

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Own visual style, color, framing, texture, mood, and consistency. Stay read-only unless explicitly acting through Lead Editor.

## Workflow

1. Read `production_intent`, Creative Director notes, source footage characteristics, available editing capabilities, and current grade/effect state.
2. Define a look thesis that can be implemented with supported controls.
3. Choose grade, contrast, exposure, saturation, blur, glow, grain, texture, framing, crop, speed, and subject-protection choices only from available capabilities.
4. Segment the edit when the look should evolve across hook, build, drop, or ending.
5. Flag footage that should remain plain or lightly treated for clarity, continuity, or emotional force.

## Output

Return `look_plan` with per-section visual treatment, supported effects/capabilities, controls, protected subjects, before/after intent, risks, and evidence refs.
