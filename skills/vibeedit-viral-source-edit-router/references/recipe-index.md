# Viral Source Edit Router Recipes

This folder documents the read-only Python recipes in
`scripts/viral_source_edit_recipes.py`.

Default dataset root:

`fan_Edit_Data/workspace/reference-corpora/creed-analysis-dataset`

Supported commands:

- `edit-moments`: query edit-local shots mapped to approximate source moments.
- `recurring-moments`: query repeated/iconic source quotes, moments, and story patterns.
- `proof-tiers`: summarize candidate, confirmed, and derived preferred planning rows.
- `story-sequences`: collapse edit-to-source moments into reusable story sequence patterns.
- `timing-candidates`: inspect mixed-audio beat/song rows and human-reviewed punch/action timing rows.
- `emit-learned-memory`: write shared learned-style JSON under `derived/viral-source-edit-learning/` unless `--output` is supplied.

Proof tier rules:

- `candidate` is provisional source or vibe evidence. It is useful for search and planning, not exact source claims.
- `confirmed` preserves rows already confirmed by the upstream dataset.
- `preferred` is not a source proof tier. It is a derived planning label for confirmed, high-confidence, recurring rows.

The script does not mutate raw media, transcripts, production-analysis runs, caches, original human labels, or existing skill folders.
