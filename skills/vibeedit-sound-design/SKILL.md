---
name: sound-design
description: Plan, apply, audit, or revise sound design for an active edit or source sequence. Use for spotting visual/editorial/emotional sound needs, SFX and music decisions, sync, layers, mix hierarchy, silence, audio automation, review, and mapping plans to audio timeline items/assets. Do not use for generic DAW-only advice, visual effects, or app integration work.
---

# Sound Design

Run an audio post pass on the active edit. Sound design owns spotting, SFX/music decisions, sync, layers, mix, silence, review, and mapping plans to audio timeline items, assets, and automation.

## Editing Contract

- Treat inspected media, current edit, analysis artifacts, derived assets, audio items, waveform/beat data, transcripts, and available capabilities as truth.
- Prefer existing transcripts, captions, beat maps, scene data, detections, source audio, derived audio assets, and timeline state before requesting expensive analysis or generation.
- Make reversible, timeline-native changes where possible and preserve source media/provenance.
- In orchestrated production flows, Lead Editor is the only production writer; this skill supplies spotting, audio decisions, asset provenance, mix direction, and review notes.
- Verify timeline and render readiness after meaningful changes when possible. Never claim a render, preview, mutation, generated asset, or mix pass exists unless evidence proves it.
- Keep proof states distinct: `planned`, `dry-run`, `applied`, `confirmed`, `previewed`, `rendered`, and `proven`. If execution is unavailable, return an execution-ready audio timeline plan with exact assumptions and mark unproven work as unproven.

## Workflow

1. Inspect timeline picture, existing audio, clip boundaries, transitions, speed changes, dialogue/source sound, music, SFX, waveform/beat data, captions/transcripts, and existing audio automation.
2. Review current project/library audio inventory before generation. Reuse close matches first. Generation is allowed only when source audio, existing music, existing SFX, or an editable/repurposable library sound cannot credibly serve the spot.
3. Write one concise `sound_intent` for each coherent sequence.
4. Spot visual, editorial, environmental, and emotional events. Mark exact onsets and windows: contact, cut, reveal, movement start, movement peak, arrival, phrase boundary, drop, breath, or silence.
5. For every important spot choose exactly one decision: `use_source_audio`, `use_existing_music`, `use_existing_sfx`, `edit_or_repurpose`, `generate_sfx`, `generate_music`, `ambience_or_texture`, or `intentional_silence`.
6. Resolve all critical/high spots. Use generation or retrieval only when an existing asset cannot credibly serve the intent.
7. Build complex hero moments as layers, not overloaded single sounds. Common stacks include riser -> pre-drop silence -> whoosh -> impact hit -> sub boom -> tail; whoosh + hit at cuts; music bed ducked under dialogue; crowd/room texture under sports/action; final sting + tail for buttoned endings.
8. When generating or retrieving sound, write prompts by function, material, perspective, space, and sync target. Vary wording and layer choices to match the source moment; do not reuse one generic whoosh, hit, riser, or impact prompt across unrelated spots.
9. Persist generated SFX/music for reuse before placement when the workflow exposes a reusable library. Keep label, tags, category, timing metadata, and generation provenance. Never count a placeholder or fixture fallback as generated audio.
10. Treat generation as source acquisition only. Once usable media/library references or blocked reasons exist, proceed to placement, trimming, gain, fades, EQ, automation, and safety checks. Do not stay in a generation loop.
11. Place timeline-native audio items/assets and automation from the chosen media/library ids. Keep sync within one frame for hard impacts unless a documented lead/trail serves perception.
12. Mix in story priority: dialogue/voice, primary story sound, important Foley/hard effects, music, ambience/room tone, decorative effects. Automate around dialogue and avoid clutter.
13. Use silence deliberately. Record the reason and exact window.
14. Review with picture, audio-only, and around dense edits. Revise missing, late, repetitive, spatially wrong, muddy, or dialogue-masking moments.

## Selectivity And Variety

- A strong pass has changing density. Some moments use only source audio or music, some use layered design, and some use intentional silence.
- Avoid defaulting to whoosh-plus-hit for every cut. Choose texture and transient shape from the visible material: engine, glass, cloth, metal, crowd, breath, room, weapon, tire, footstep, UI, or abstract music accent.
- Repeated motifs must evolve by pitch, duration, space, sync offset, layer count, or mix priority. Repetition should support recognition, not fill space.
- For music-aware social/trailer edits, consult `references/tonal-sfx-lessons.md` for tonal SFX, riser, hit, drone, EQ, reverb, and layering patterns. Treat it as one source-biased palette, not a default style.

## Source Choices

- Use source audio for dialogue, vocal reactions, performance sounds, real impacts, crowd/location sound, or recognizable sync. Trim, duck, split, lower, or mute source audio when it conflicts or contains dead air/noise.
- Use existing project music when supplied, when beat/lyrics already drive the cut, or when generation would not improve the edit. Duck it under dialogue/source story sound and restore it at drops/payoffs.
- Use existing SFX/library audio when the label, tags, waveform, duration, or metadata closely matches the spot. Edit pitch, gain, fade, EQ, trim, or tail before generating a near-duplicate.
- Generate SFX for short isolated whooshes, hits, risers, impacts, glitch accents, UI/text clicks, stingers, bass drops, transition sounds, and stylized motion accents when no existing sound fits.
- Generate music only when the tool is callable, the edit needs a new instrumental bed, and existing project/library music is missing or unsuitable.
- Add ambience/texture when a sequence feels empty, cuts expose silence, sports/action needs crowd/room continuity, or a world needs glue under edits.
- Use silence/negative space for breath, anticipation, pre-drop tension, dialogue clarity, impact contrast, or endings. Silence is an authored layer and must have an exact frame/window.

## Timeline Mapping

- Represent new sounds as audio assets plus timeline audio items with source provenance where available.
- Use trim, offset, gain, fade, pan, filter, pitch/stretch, reverb/space matching, and automation only when supported by the active editing environment.
- Keep generated or retrieved assets named by function and target, such as `sfx_whip_arrival_drop_012`.
- Preserve existing useful source audio. Do not flatten or destructively replace original media.
- A spot list must include frames/windows, layer roles, sync anchors, source choice, media/library references when known, reuse/generate/fallback decision, track/layer target when known, start/duration, gain, fade, EQ, ducking/automation, and blocked/skipped reasons.

## Output Shape

Include:

- `sound_intent` by sequence
- Spot list with priority, target frame/time, decision, and rationale
- Asset actions: existing, generated/retrieved, edited/repurposed, or silence
- Timeline item/automation plan or applied mutations
- Mix hierarchy and dialogue/music protection
- Review evidence, render/preview honesty, unresolved gaps, and undo/recovery notes when available
