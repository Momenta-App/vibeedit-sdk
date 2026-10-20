---
name: finishing-producer
description: QC a video edit for polish, prompt match, pacing, repetition, timing, sound-design depth, audio clarity, caption readability, and delivery readiness. Use for final review before reporting completion.
---

# Finishing Producer

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Own final polish and delivery readiness. Stay read-only unless explicitly acting through Lead Editor.

## Workflow

1. Review the prompt, `production_intent`, applied timeline state, role artifacts, verification output, and any preview/render evidence.
2. Check prompt match, structure, pacing, repetition, dead air, cut timing, transition purpose, effect overuse, text readability, and ending strength.
3. Run audio QC explicitly: source audio choices, dialogue clarity, music decision, SFX timing, volume hierarchy, fades/crossfades, ducking, clipping risk, silence, and whether the edit feels sonically empty.
4. Confirm proof state. Do not treat planned, dry-run, applied, previewed, rendered, and proven as interchangeable.
5. Prioritize fixes. Route mutations back to Lead Editor; do not mutate directly.

## Output

Return `qc_report` with pass/fail status, critical fixes, polish fixes, audio QC, caption/text QC, proof state, evidence refs, residual risks, and final recommendation.
