---
name: vibeedit-creed-corpus-cross-reference
description: Analyze the separate Creed reference corpus of viral edits and cross-reference learned edit grammar against Creed 1, Creed 2, and Creed 3 source moments without producing the current CreedEditSong hook/body render package.
---

# VibeEdit Creed Corpus Cross Reference

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill only when the task is to learn from the Creed viral-edit corpus, compare a set of reference edits against Creed 1/2/3 source material, or build reusable cross-reference data.

This is not the `CreedEditSong` hook/body route. It does not own song intro trimming, body-entry alignment, or render package validation for the current single-song edit mode.

## Scope

- Inventory the current reference corpus before assuming there are exactly 77 usable edits.
- For each usable edit, record source file, metadata, duration, audio/song evidence, visual sections, hook/body/drop structure, SFX grammar, and proof boundary.
- Cross-reference observed visual moments against `Creed 1.mp4`, `Creed 2.mp4`, and `Creed 3.mp4` only when current source-analysis artifacts, source matches, frame evidence, or manual review support the match.
- Separate confirmed source matches from candidate-only similarities.
- Return reusable lessons, candidate shot boards, and rejection notes that another route may consume.

## Output Contract

Return a corpus artifact with:

- `route`: `vibeedit-creed-corpus-cross-reference`
- `corpus_root`
- `inventory`: discovered edits, rejected files, and why
- `reference_grammar`: hook, body, drop, SFX, transition, pacing, and color lessons
- `trilogy_cross_reference`: confirmed and candidate matches per Creed movie
- `source_match_boundary`: confirmed count, candidate count, and evidence paths
- `handoff_to_creed_edit_song`: optional lessons or candidate boards, never a render-ready package
- `proof_boundary`: what is measured, inferred, candidate-only, or unverified

Do not claim that a `CreedEditSong` package used 77-edit/trilogy evidence unless this route produced a current artifact and that package cites it.
