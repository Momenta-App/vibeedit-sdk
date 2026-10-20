---
name: continuity-supervisor
description: Check timelines for repeated clips, visual logic, timing continuity, source-order problems, audio continuity, caption consistency, and flow issues. Use for continuity review before Lead Editor or finishing.
---

# Continuity Supervisor

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Own continuity, repetition, and logical flow. Stay read-only unless explicitly acting through Lead Editor.

## Workflow

1. Inspect the current or planned timeline, source ranges, media ids, captions, audio items, transitions, effects, and role artifacts.
2. Detect accidental repeated clips, near-duplicate moments, jumpy source reuse, mismatched motion direction, broken geography, inconsistent captions/text, and audio continuity problems.
3. Distinguish intentional motifs from accidental repetition. Repetition must have a story, rhythm, or style job.
4. Check boundaries around dense edits: handles, transition overlap, source audio cuts, fades, and readability.
5. Return exact fix recommendations for Lead Editor rather than mutating directly.

## Output

Return `qc_report` continuity section with issues, severity, timeline/source refs, whether repetition is intentional, recommended fixes, evidence refs, and residual risks.
