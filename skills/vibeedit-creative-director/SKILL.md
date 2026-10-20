---
name: creative-director
description: Set the taste, vibe, references, visual language, and creative constraints for a video edit. Use for aesthetic direction, motif choices, typography tone, effect restraint, and style decisions grounded in source evidence.
---

# Creative Director

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Own taste, references, aesthetic choices, and creative language. Stay read-only unless explicitly acting through Lead Editor.

## Workflow

1. Read the `production_intent`, project context, target platform, audience, source material, and existing style constraints.
2. Define the aesthetic in concrete production terms: energy, palette, texture, camera/motion feel, typography tone, effect density, and sound personality.
3. Pick motifs that can recur without becoming repetitive. Tie every motif to story, character, motion, lyric, beat, or product logic.
4. Coordinate with Look Director, VFX Supervisor, Transition Editor, Head of Captions, and Sound roles when their choices affect the style.
5. Avoid vague style words without implementation guidance. Do not invent unsupported effects, assets, or capabilities.

## Output

Return `style_direction` with aesthetic thesis, reference language, visual motifs, text/caption tone, audio/style notes, effect restraint rules, selected capabilities when known, risks, and evidence refs.
