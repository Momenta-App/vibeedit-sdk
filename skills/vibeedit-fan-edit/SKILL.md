---
name: fan-edit
description: Create, plan, audit, or revise short fan edits from available source media or an existing timeline. Use for sports/action edits, character edits, dialogue-to-drop edits, hook/setup/build/drop/aftershock/loop structures, clip choice, beat pacing, evidence-based review, and orchestration of effects and sound-design skills. Do not use for generic plot summaries, app integration work, or broad code changes.
---

# Fan Edit

Make a short audiovisual argument from the source media or timeline. Fan edit owns the concept, structure, clip evidence, pacing, and review. Use `effects` for visual recipes and subject/background treatment. Use `sound-design` for spotting, SFX/music decisions, sync, layers, mix, and silence.

## Editing Contract

- Treat inspected source media, transcripts, captions, beat maps, current cuts, and existing timeline notes as the truth. Do not invent moments, assets, renders, or capabilities.
- Fan edit is the orchestrator. It may route to specialist skills, but it must convert their output into concrete timeline edits, assets, or explicit unproven notes before render. A specialist skill name in metadata is not execution.
- Read selected edit effort when present. Effort controls ambition and review depth, not runtime speed:
  - Low: make the smallest useful edit with cleanup, trims, simple ordering, light titles/effects, and minimal sound work. Do not force dense fan-edit structure or layered effects.
  - Medium: make a deliberate short edit with hook/setup/build/payoff or aftershock, ranked moments, modest supported effects, and focused audio decisions. Keep complexity bounded.
  - High: make a full fan edit with non-chronological moment selection, multi-pass pacing, motivated visual variation, sound/effects/VFX consideration, effect-pack discovery when useful, and stronger confirmation.
  - Ultra: use layered tracks, constructed transitions, subject/background separation when available, chained effect ideas, SFX/polish passes, and the strongest practical verification.
- Preserve source media and provenance. Prefer reversible edit decisions and clearly separate the creative plan from any executed timeline changes.
- Prefer existing transcripts, captions, beat maps, scene notes, object/person detections, cutouts, derived assets, and timeline state before requesting new analysis.
- In orchestrated production flows, Lead Editor is the only production writer; this skill supplies concept, structure, evidence, timing, review notes, and specialist direction.
- Verify timeline and render readiness after meaningful changes when the editing environment allows it. Never claim a preview, render, mutation, detection, or cutout exists unless it was actually produced or inspected.
- Higher effort raises ambition only inside verified capabilities. Keep unsupported masks, generated assets, custom effects, previews, renders, and effect-pack work explicitly skipped, fallback-only, or unproven. Lower effort is allowed to be restrained even for fan-edit requests.
- Keep proof states distinct: `planned`, `dry-run`, `applied`, `confirmed`, `previewed`, `rendered`, and `proven`. If execution is unavailable, return an execution-ready timeline plan with exact assumptions and mark unproven work as unproven.

## Renderability Boundary

Separate planning data from renderable layers.

- Planning markers, role labels, quote-slot labels, clip theses, skill-path names, effect names, and review notes are non-renderable unless a later pass turns them into concrete media, audio, text, effect, or transition layers.
- Do not create `kind: "text"` or equivalent renderable text layers for motivational labels, quote placeholders, or internal story beats. On-screen text is allowed only when the user asks for text or a text skill produces a final text treatment with exact copy, timing, placement, and purpose.
- Do not render from a board that only contains placeholder effect or transition markers. A renderable effect/transition must identify the concrete implementation, generated asset or shader/effect primitive, timing, source handles, and fallback if unsupported.
- Quote moments must be real audio edits, not just labels. A quote section needs selected source dialogue ranges, isolated/enhanced dialogue when available, music duck/pause automation, mix levels, and timeline audio clips before render.
- If only a rough planning board exists, call it a plan or animatic. Do not call it a finished fan edit or review render unless the render intentionally exposes placeholders for debugging.

## Required Routing Gates

Before applying or rendering a full fan edit, run these gates in order:

1. **Audio architecture gate:** Decide whether the edit is music-only, quote-led, source-sound-led, or hybrid. For quote-led or hybrid edits, route to `vibeedit-quote-audio-structure`, `sound-design`, and voice-isolation guidance when available. The output must include actual audio clip ranges, pause/duck points, and mix intent.
2. **Text intent gate:** Decide whether on-screen text is needed. If yes, route to the relevant text skill and require final text layers. If no, keep all story labels in metadata only.
3. **Effects/transition gate:** Route each desired flash, stutter, subject reveal, segment transition, mask, or stylized cut through the relevant effects/transition/segmentation skill. Keep unsupported effects as unrendered notes, not fake approximations, unless the user explicitly asks for rough placeholders.
4. **Timeline materialization gate:** Convert selected clips, real audio edits, final text layers, and concrete effects into the editor-native timeline. Preserve non-renderable planning metadata separately.
5. **Pre-render audit gate:** Check for placeholder markers, unresolved quote slots, fake text labels, unmaterialized skill names, missing media, and unsupported effects. Block finished renders until these are resolved or explicitly marked as rough/debug.

## Workflow

1. Inspect state: aspect ratio, duration target, timeline or rough cut, source media, audio, captions/transcripts, scene/beat/object/person data, cutouts, derived assets, and available editing primitives.
2. Define five one-sentence emotional arguments. Each must name the subject, the contradiction/change/relationship, intended feeling, and at least three source-evidence candidates.
3. Choose three materially different directions. They must differ by thesis, point of view, audio architecture, recurring motif, or structural turn, not just grade/effects.
4. Select the strongest feasible direction and write: `the edit where ...`. If several directions are equally supported, prefer variety from any recent or same-fixture run by changing the thesis, motif, effect family, sound density, or ending shape. Do not force variety when the footage clearly supports one stronger editorial answer.
5. Build the structure: hook, setup, build, drop/turn, peak, aftershock, and loop or hard ending. Target subject recognition by about 0.7s and premise clarity by about 2.5s unless deliberate mystery has a payoff.
6. Build a ranked moment board from inspected evidence before choosing timeline order. Fan edits are not chronological summaries: do not walk the source video, split it into adjacent pieces, and shave time off each piece unless the user asks for a chronological recap. Hunt for standout chunks: epic lines, source-audio moments, silence-worthy dialogue, the focused character's best looks/actions/reactions/entrances/defeats/wins/transformations, high-octane action, impacts, reveals, motion peaks, celebrations, reversals, beautiful shots that can breathe, and story-defining moments that explain the edit's thesis.
7. Pick clips from the ranked moment board, not filenames, memory, or source order. For every selected clip record source range, timeline range, role, motion/audio anchor, evidence statement, and why it belongs at that timeline position.
8. Order moments for the song, character focus, contrast, payoff, visual beauty, and action energy. Source chronology is optional; use it only when it strengthens the edit.
9. Map pacing to phrase, bar, downbeat, lyric, transient, source motion, gaze, expression, impact, or reveal. Do not cut on every beat by default.
10. Run the required routing gates. Call `effects` when a visual treatment needs a timeline recipe, subject protection, background removal, constructed transition, text treatment, or reusable semantic controls.
11. Call `sound-design` when the edit needs SFX, music structure, dialogue/source-sound decisions, silence, sync, audio layering, automation, or mix review.
12. Apply in small passes: rough hook/payoff first, then bridge evidence, then audio, then effects, then intentional text. Keep each pass reversible.
13. Before rendering, remove or quarantine non-renderable planning markers from render layers. Render only concrete clips, audio, effects, transitions, and final text layers.
14. Review full-speed with sound, muted, audio-only, frame-by-frame at dense moments, phone scale when possible, and ending into restart. Revise concept, clip evidence, audio, timing, readability, then polish.

## Variety And Restraint

- Full fan edits should combine several motivated visual building blocks when the source supports them: transition glue, in-shot accents, subject or object reveals, text or graphic moments, color/texture sections, and plain cuts. Do not turn one impressive effect into the whole edit.
- Repeated effects must change role, timing, target, intensity, direction, or protected subject. A repeated motif should feel designed, not templated.
- Let quiet or plain editorial sections stay plain when source performance, geography, dialogue, or anticipation is stronger than another effect.
- Remove accidental dead air, but use intentional silence, source-only audio, muted-music breaks, or no added sound for epic lines, character focus, story turns, pre-drop tension, and beautiful moments. Sound design should be selective; do not add whooshes/hits everywhere.

## Background-Removal Routing

Use existing cutouts/detections/derived assets before new analysis. When a visual plan needs subject/background separation, route through `effects`:

- Fast local video segmentation: use for simple person/subject separation when speed matters.
- Interactive object segmentation: use for object/background masks, previews, and short video ranges where speed matters more than maximum edge quality.
- High-quality segmentation: use when edges, hair, hands, props, overlapping subjects, or hero cutouts matter.
- Still-image matting or strongest available segmentation: use for difficult stills or final cutouts. Confirm video support before promising temporal masks.

## Output Shape

For plans or execution reports, include:

- Concept: one sentence and `the edit where ...`
- Effort: selected level and the scope decisions it changed
- Structure: hook/setup/build/drop/aftershock/loop with timeline ranges
- Clip map: ranked moment candidates, chosen source ranges, roles, evidence, sync anchors, and non-chronological ordering rationale when source order is not used
- Effects plan: for each major effect section, include recipe name, job, source anchor, exact timeline target, controls, protected subjects, routing decision, and unproven states
- Sound plan: spots, assets/actions, sync points, automation, silence, and mix priorities
- Renderability audit: list placeholder markers removed or blocked, real audio clips created, intentional text layers, concrete effects/transitions, and any unrendered notes
- Applied changes: changed sections, undo/recovery notes when available, and verification evidence
- Gaps: missing tools/data and proof state for preview/render/mutation claims
