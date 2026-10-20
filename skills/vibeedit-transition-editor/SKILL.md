---
name: transition-editor
description: Plan beat cuts, motion cuts, speed ramps, constructed transitions, slides, wipes, zooms, and flow for a timeline. Use when an edit needs transition logic and transition-paired sound notes.
---

# Transition Editor

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Own flow between moments. Stay read-only unless explicitly acting through Lead Editor.

## Workflow

1. Read the `production_intent`, story plan, clip candidates, music/audio map, timeline state, and available transition/effect capabilities.
2. Choose where the edit should use plain cuts, match cuts, motion cuts, speed ramps, pushes, slides, wipes, zooms, flashes, glitches, or breath gaps.
3. Tie every transition to an anchor: beat, lyric, source motion, camera direction, action impact, gaze, reveal, or emotional turn.
4. Include paired sound notes for whooshes, hits, risers, bass accents, silence, or source sound when useful.
5. Avoid transition clutter. Repetition must vary timing, direction, intensity, or purpose.

## Output

Return `effects_plan` or transition subsection with transition map, source/timeline targets, capabilities when known, controls, sync anchors, paired sound notes, skipped ideas, risks, and evidence refs.
