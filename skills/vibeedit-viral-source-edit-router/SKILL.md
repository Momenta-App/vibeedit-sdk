---
name: vibeedit-viral-source-edit-router
description: Generalized VibeEdit router for viral source-native edits from movies, shows, sports, games, creator footage, trailers, interviews, or mixed source media. Use when a user asks to make, plan, audit, or hand off a viral edit that needs source research, style analysis, story/moment selection, song analysis, action sync, SFX, assembly planning, QA, and memory/wiki updates without depending on Creed-specific or generic fan-edit stacks.
---

# VibeEdit Viral Source Edit Router

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill as the standalone production router for source-driven viral edits. It can compare against prior Creed or fan-edit workflows, but its core route must not load or depend on `vibeedit-creed-edit`, `fan-edit`, `fanedit-polish-router`, `fanedit-body`, `sound-design`, or `lead-editor`.

## Defaults

- Use focused role passes, performed by the parent agent or useful authorized subagents; keep integration, proof boundaries and final handoff with one parent agent.
- Preserve source-native aspect ratio unless the user or platform target explicitly requires a crop. Record any crop as a creative or delivery decision.
- Use no on-screen text overlays by default. Add captions, quote cards, lyrics, labels, or typography only when the user asks or the source artifact requires it.
- Treat inspected source files, transcripts, beat maps, renders, reviews, and workspace artifacts as truth. Do not invent timestamps, quotes, assets, render states, or prior approvals.
- Keep planning labels out of renderable layers unless a later role materializes them as concrete clips, audio, effects, or text.
- After the main structure is complete, run the transition reviewer before the effects reviewer. Transition review may request clip or timeline changes for transition quality; effects review must stay additive and must not change structure.

## Load References

Read only what the task needs:

- `references/role-contracts.md` for all role responsibilities, inputs, outputs, and subagent prompts.
- `references/proof-vocabulary.md` before making any state, render, review, or acceptance claim.
- `references/output-package.md` when writing a plan, packet, handoff, manifest, or review report.

## Router Order

1. Confirm the request, target surface, available sources, workspace roots, song/audio inputs, duration target, aspect ratio constraints, and proof state.
2. Spawn or simulate role-specific subagents for producer, source researcher, style analyst, story editor, song analyst, action/sync planner, quote/moment curator, SFX planner, and assembly planner.
3. Require each role to return evidence paths, exact source ranges where available, rejected options, blockers, and proof state.
4. Once the main structure exists, run `vibeedit-viral-transition-reviewer` before effects. It reviews every cut, chooses clean cut vs transition, sets `none|light|medium|heavy` transition weight, and may request clip or timeline changes when a transition, especially a subject-flash transition, needs a stronger clip-B subject or no-jump landing.
5. After transition decisions are fixed, run `vibeedit-viral-effects-reviewer`. It adds tasteful beat/song-synced additive effects, especially flashes or shimmers on musical anchors not already served by cuts or transitions, and must not change structure.
6. Integrate the role outputs into one source-native edit package with a ranked moment board, timeline plan, transition plan, effects plan, audio/SFX plan, assembly plan, QA plan, memory notes, and explicit gaps.
7. Run QA/review and memory/wiki roles after the transition and effects passes.
8. Apply, preview, render, or review only through concrete current tools and artifacts. If execution is unavailable, stop at the highest proven state and hand off exact next actions.

## Specialist Role Links

Load these only when the post-structure pass is needed:

- `vibeedit-viral-transition-reviewer`: ordered first after assembly planning. It owns cut review, transition posture, transition frequency/complexity, subject-flash candidate selection, and allowed clip/timeline adjustments for transition quality.
- `vibeedit-viral-effects-reviewer`: ordered after transition review. It owns additive effects that make unused song anchors visible without changing structure.

The reviewer skills route to existing effect, mask, and transition skills. Do not modify individual transition or effect skills when using this router.

## Required Gates

- Source gate: every selected moment must cite current media or analysis evidence.
- Style gate: viral reference claims must cite inspected examples, not taste memory.
- Audio gate: music, dialogue, source sound, silence, and SFX must have timing and mix intent before assembly.
- Sync gate: action cuts and impacts must name the beat, transient, source motion, quote, or visual contact they target.
- Transition gate: every cut must be reviewed as either a clean cut or a planned transition before the effects pass. Subject-flash transitions require a strong clip-B subject or a requested clip/timeline adjustment.
- Effects gate: effects are additive after transition decisions. They must tie to a song anchor, source motion, or story attention reason and must not alter the main structure.
- Renderability gate: every layer must be real media, concrete effect operation, concrete audio, or intentionally absent.
- QA gate: do not call work reviewed, accepted, or proven without an artifact and recorded checks.
- Memory gate: write only durable facts proven by current artifacts, not guesses or creative hopes.

## Handoff

Return a compact package with:

- `proof_state`
- discovered source and output paths
- role outputs summarized by evidence, decision, and gap
- source-native aspect ratio decision
- text overlay decision, usually `none`
- selected timeline and sync anchors
- transition posture, per-cut decisions, downstream transition skills, and allowed timeline or clip adjustments
- additive effects plan, unused song anchors, downstream effect skills, and no-structure-change confirmation
- SFX/audio and assembly plans
- QA checklist and current review results
- memory/wiki notes
- exact next command or inspection when blocked
