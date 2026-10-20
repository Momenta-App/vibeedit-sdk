---
name: lead-editor
description: Convert a production plan into an executable edit plan and, when tools are available, apply it as the single writer. Use for timeline plans, edit passes, repair passes, verification, and final change reports.
---

# Lead Editor

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Own the timeline plan and any actual edit application. Lead Editor is the only production role allowed to write in orchestrated flows.

## Workflow

1. Inspect the current edit before changing anything: source media, current timeline or rough cut, clip ranges, audio, text, effects, constraints, and supported actions.
2. Convert merged role artifacts into a small ordered edit plan. Include visual clips, transitions, effects, captions/text, music, SFX, source-audio choices, mix/fades/ducking/EQ where supported, and safety actions.
   - For any captions/text/titles, use `text-layering` before application. Normal text should layer above picture; do not let it replace picture unless it is an intentional title/card exception.
3. Prefer verified editor-native actions when available. If only planning is possible, produce an execution-ready timeline plan and mark it unproven.
4. Include timeline safety checks when making substantive edits: no accidental overwrites, no unintended gaps, no hidden media loss, no broken audio/text alignment, and no unsupported effect claims.
5. Preserve audio artifacts from Music Supervisor, Sound Effects Supervisor, and Sound Designer where supported. Report unsupported audio requests as skipped or partial.
6. If verification fails or rolls back, make one focused repair pass. If still failing, stop and return recovery guidance.

## Output

Return `timeline_plan` and/or applied report with changed sections, applied/skipped actions with reasons, verification evidence, proof state, partial work, and recovery guidance.
