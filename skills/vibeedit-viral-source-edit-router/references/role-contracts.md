# Role Contracts

Use these contracts when orchestrating viral source-native edits. Prefer parallel subagents for independent discovery and critique, then integrate their outputs in the main agent. If subagents are unavailable, simulate the same roles in separate passes and label unverified assumptions.

## Shared Rules

Every role returns:

- `role`
- `proof_state`
- `inputs_inspected`
- `decisions`
- `evidence_paths`
- `source_ranges` when known
- `rejected_options`
- `blockers`
- `next_actions`

Do not route through Creed-specific or generic fan-edit stacks as core dependencies. Prior workflows may be referenced only as compare-against examples for proof discipline, no-text defaults, renderability boundaries, or source-board shape.

Post-structure roles run in a strict order:

1. `viral_transition_reviewer`
2. `viral_effects_reviewer`
3. `qa_review`
4. `memory_wiki_editor`

The transition reviewer may request timeline or clip changes when a transition needs them. The effects reviewer must not change the main structure.

## Producer

Own the edit brief and orchestration.

Inputs:

- user request
- workspace/project context
- available media, transcripts, analysis, prior renders, platform target

Outputs:

- one-sentence edit thesis
- role assignment list
- duration and aspect-ratio decision
- default text decision, usually no overlays
- current proof state and handoff path

Prompt shape:

```text
Act as producer for a source-native viral edit. Confirm the brief, assign role work, keep proof states honest, and return only decisions grounded in inspected artifacts.
```

## Source Researcher

Find the real material.

Inputs:

- source media paths
- transcripts/captions
- analysis outputs
- thumbnails/contact sheets
- metadata and prior workspace artifacts

Outputs:

- source inventory
- ranked evidence map
- candidate moments with exact ranges or nearest known anchors
- missing analysis list
- provenance notes

Reject:

- remembered timestamps not confirmed by files
- famous scenes that are not present in the current source set
- "probably there" moments without evidence

## Style Analyst

Define the viral grammar for this specific edit.

Inputs:

- provided references
- comparable edits the user names
- platform/runtime constraints
- source material texture

Outputs:

- style lanes
- pacing profile
- transition/effect restraint
- color/texture posture
- sonic density target
- compare-against notes from inspected references

Defaults:

- source-native framing
- no text overlays
- visible source performance over decorative treatment

## Story Editor

Turn moments into an emotional argument.

Inputs:

- source research board
- user theme
- style lanes
- quote/moment candidates

Outputs:

- `the edit where ...` sentence
- hook/build/turn/peak/aftershock structure
- selected and rejected source moments
- continuity risks
- non-chronological ordering rationale when used

Rules:

- Do not summarize plot unless the user asks for recap.
- Prefer moments that argue the thesis visually or sonically.
- Keep internal labels as metadata, not renderable text.

## Song Analyst

Treat music or source audio as editable structure.

Inputs:

- song/audio files
- beat maps, stems, waveforms, onsets, lyrics when available
- source dialogue/source-sound needs

Outputs:

- crop candidates
- intro/build/drop/loop or hard-ending map
- beat/transient anchors
- dialogue duck/pause plan when needed
- silence and source-sound opportunities

Proof note:

- Beat maps and waveform inspection support planning. Frame/sample sync is not proven until a rendered or timeline artifact is inspected.

## Action/Sync Planner

Map source motion to audio and cuts.

Inputs:

- selected moments
- beat/transient map
- source motion/action notes
- planned SFX anchors

Outputs:

- timeline timing grid
- impact, gaze, reveal, motion, and camera-punch anchors
- cut density plan
- speed-ramp/stutter candidates
- sync risk list

Rules:

- Do not cut on every beat by default.
- Reserve the strongest source action for the strongest musical or story moment.
- Mark +/- frame precision as unproven until inspected.

## Quote/Moment Curator

Choose dialogue, faces, gestures, images, and source-sound moments.

Inputs:

- transcripts/captions
- source researcher candidates
- story thesis
- song structure

Outputs:

- quote candidates with exact source ranges
- visual moment board
- source-sound moments
- context warnings
- mouth-speaking risk list for music-body sections

Rules:

- Quotes require real source audio ranges and context checks.
- Do not create quote cards or subtitles by default.
- A quote-led section needs audio plan support before assembly.

## SFX Planner

Plan concrete punctuation without delegating the router to an external sound stack.

Inputs:

- action/sync plan
- song/audio map
- available SFX library or generation capability
- source-sound opportunities

Outputs:

- SFX spots with timeline time, asset or generation need, gain intent, and sync reason
- riser/hit/whoosh/impact restraint notes
- mix hierarchy
- missing asset list

Rules:

- No fake SFX placeholders in a final package.
- Dense SFX must serve specific actions, transitions, or musical turns.
- Silence can be a designed sound choice.

## Assembly Planner

Convert planning into an executable edit packet.

Inputs:

- story structure
- selected source ranges
- song/audio plan
- SFX plan
- effects/transition decisions
- target renderer/editor capabilities

Outputs:

- timeline map
- media layer list
- audio layer list
- effect/transition operation list
- source-native dimensions/fps/codec plan
- dry-run or apply command when available

Rules:

- Planning markers are not renderable layers.
- Every effect must name a real implementation or stay omitted.
- Text layers remain absent unless intentionally materialized.

## Viral Transition Reviewer

Review all cuts after the main structure exists and before the effects pass.

Skill link:

- `vibeedit-viral-transition-reviewer`

Inputs:

- locked or draft main structure
- cut list or timeline map
- selected source ranges and clip handles
- song sections, beat/transient anchors, and style direction
- source subject clarity at each clip-B entry

Outputs:

- edit-level transition posture: `none`, `light`, `medium`, or `heavy`
- per-cut decision: clean cut or transition
- transition family and downstream skill links
- subject-flash candidates and rejected candidates
- requested clip or timeline adjustments when needed for a strong subject or no-jump landing
- SAM execution command, SAM artifact path, and proof state for mask-dependent transitions

Downstream skill links:

- `vibeedit-transition-editor`
- `vibeedit-flash-subject-transition`
- `vibeedit-sam31-mlx-flash-subject-transition`
- `vibeedit-masking-router`
- `vibeedit-segmentation-cutouts`
- `vibeedit-sam21-video-segmentation`
- `vibeedit-reverse-curtain-reveal`
- `vibeedit-reverse-curtain-subject-reveal`
- `vibeedit-tile-object-reveal`
- `vibeedit-random-frame-stutter`
- `vibeedit-effects`

Rules:

- Review every clip-to-clip cut, including cuts kept clean.
- Run before the effects reviewer.
- Heavier, faster songs may justify higher transition complexity and frequency; lower-energy or performance-led edits may need mostly clean cuts.
- Subject flash is preferred when it is earned: clip B needs a strong segmentable first-frame subject and the transition should focus the story.
- This role may change clip selection or timeline alignment only to improve transition quality, subject focus, or no-jump landing.
- Do not claim a transition was previewed, rendered, reviewed, or accepted without evidence.

Prompt shape:

```text
Act as the viral transition reviewer. After the main edit structure is complete, inspect every cut, decide clean cut vs transition, set transition weight and frequency from the song/style, prefer subject flash only when clip B has a strong maskable subject, and return downstream transition skill contracts with proof states.
```

## Viral Effects Reviewer

Add tasteful visual punctuation after transition decisions are fixed.

Skill link:

- `vibeedit-viral-effects-reviewer`

Inputs:

- main structure
- transition reviewer output
- song sections, beats, transients, lyric/audio details
- source motion and subject clarity
- available masks or masking route state

Outputs:

- effect density: `none`, `light`, `medium`, or `heavy`
- unused audio anchor map
- additive effects plan
- downstream skill links
- SAM execution command, SAM artifact path, and proof state for mask-dependent effects
- rejected effect ideas with taste rationale
- no-structure-change confirmation

Downstream skill links:

- `vibeedit-effects`
- `vibeedit-effects-punctuation`
- `vibeedit-subject-effects`
- `vibeedit-sam31-mlx-subject-effects`
- `vibeedit-masking-router`
- `vibeedit-segmentation-cutouts`
- `vibeedit-sam21-video-segmentation`
- `vibeedit-color-style-recipes`
- `vibeedit-random-frame-stutter`
- `vibeedit-reverse-curtain-reveal`
- `vibeedit-tile-object-reveal`

Rules:

- Run after the transition reviewer.
- Do not change clip choice, cut order, cut timing, or transition decisions.
- Select effects for song anchors not already expressed by a cut, transition, source impact, quote, or speed change.
- For close beat clusters, prefer one short flash per selected beat and chain flashes to the music.
- Use shimmers, pulses, style switches, or glows for longer sustained moments.
- Mask-dependent effects require a real SAM execution path, preferably `vibeedit-sam31-mlx-subject-effects` locally. Router-only planning, proxy masks, boxes, and geometric masks are not valid test outputs.
- Do not claim an effect was previewed, rendered, reviewed, or accepted without evidence.

Prompt shape:

```text
Act as the viral effects reviewer. After transition decisions are fixed, find unused song anchors and add tasteful additive effects without changing structure. Time flashes exactly to beats or source contacts, execute mask-dependent effects through the right SAM downstream skill, and return effect contracts with SAM artifact paths and proof states.
```

## QA/Review

Inspect the real artifact or block the claim.

Inputs:

- preview/render/timeline artifact
- edit package
- source and audio maps
- transition reviewer output
- effects reviewer output

Outputs:

- full-speed review
- muted review
- audio-only review
- frame/sample spot checks at dense sync points
- duplicate/freeze/black-frame checks
- mouth-speaking and context checks
- mobile/social-scale check when relevant
- accepted gaps or revision list

Rules:

- A plan is not a preview.
- A render file is not a reviewed edit.
- Acceptance requires recorded checks or explicitly accepted gaps.

## Memory/Wiki Editor

Preserve only facts worth reusing.

Inputs:

- accepted edit package
- review results
- final artifact paths
- durable discoveries about source, style, timing, or workflow

Outputs:

- memory/wiki candidate notes
- provenance references
- facts not to store

Rules:

- Store proven source ranges, accepted style lessons, reusable commands, and final artifact paths.
- Do not store guesses, rejected experiments unless instructive, or unreviewed claims as fact.
