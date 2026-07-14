# Tonal SFX And Layering Lessons

Source: `.agent/skill-evals/video-editing/source-data/sound_design_lessons.json`

This reference distills 48 cleaned sound-design lessons from `@multiply.sound`. Treat it as one palette for music-aware social/trailer edits, not as the default answer for every sound pass. The source is biased toward tonal sound effects, risers, hits, whooshes, and music manipulation, so keep using the main skill's evidence-first and selective-sound rules.

## When This Helps

Use these patterns when the edit needs:

- A transition that feels musical instead of only noisy.
- A hook, drop, reveal, or ending that should resolve in key with the music.
- A short fan edit or trailer section where sound design must add emotion and momentum.
- A bridge between source audio and a music bed.
- A restrained way to intensify a moment without filling every cut with generic SFX.

Do not use this reference to justify adding sound to a visual-only task, masking dialogue, replacing useful source audio, or repeating whoosh/hit/riser stacks across every cut.

## Core Principles

- Match tonal SFX to the music key when the active project has a music bed or beat map. Tonal hits, drones, risers, loops, and transitions can clash if they are not key-compatible.
- Build complex moments as layers: movement cue, tonal lift, impact or arrival, tail, and room/space response. Keep each layer tied to a visual or musical function.
- Use tonal elements for emotional contour, not just loudness. A low drone can add dread; a tonal riser can lift into a drop; a musical hit can make an arrival feel intentional.
- Shape distance and memory with EQ and reverb. Low-pass filtering can push a sound away or underwater; reverb can glue layers, create space, or lengthen a tail.
- Let music and source audio carry sections when they already work. Silence, source-only moments, or plain music can be stronger than extra generated sounds.

## Useful Layer Recipes

### Musical Transition Lift

Job: move into a new clip, title, reveal, chorus, or action turn.

Layers:

- Pre-lap tonal riser or reversed tonal ping leading into the cut.
- Short whoosh only if there is visible movement or camera motion.
- Tonal hit on arrival, matched to the music key where known.
- Short reverb or room tail that clears before dialogue or the next dense beat.

Avoid using the same riser length and hit shape repeatedly. Vary duration, pitch, sync offset, space, and intensity by moment.

### Impact With Emotional Weight

Job: make a contact, crash, gunshot, shatter, slam, or hard reveal hit harder.

Layers:

- Material transient from the visual source: glass, metal, body, tire, fabric, gravel, weapon, door, water, or crowd.
- Low sub or tonal thump only when the moment needs weight.
- Optional tonal hit if a music bed is present and key-compatible.
- Debris, air, or reverb tail to show aftermath.

Keep hard impacts within one frame unless a deliberate lead or tail improves perception.

### Dread Or Build Bed

Job: make a setup section feel tense without overcutting.

Layers:

- Low drone or tonal pad under the section.
- Sparse riser or filtered texture near the end of the phrase.
- Small source details remain audible over the bed.
- Duck or thin the bed around dialogue.

Use automation to make the bed breathe. Do not leave a full-intensity drone under the entire edit by default.

### Rhythmic Loop Or Pulse

Job: support montage pacing without cutting on every beat.

Layers:

- Rhythmic loop, pulse, or tonal pattern aligned to the music phrase.
- Accent hits only on selected motion peaks, reveals, or transitions.
- Break or silence window before a peak to reset attention.

Loops should support structure. If the loop makes the edit feel mechanical, reduce density or return to source audio.

### Distant Or Underwater Treatment

Job: make vocals, music, or source sound feel distant, remembered, muffled, internal, or pre-drop.

Actions:

- Low-pass the source or music.
- Add reverb or a longer tail when space/memory is the goal.
- Reduce high-frequency clutter before a reveal.
- Restore full bandwidth on the visual or musical payoff.

Do not bury dialogue unless the story intent is to make it unintelligible.

## Generation Or Retrieval Prompt Patterns

Use prompts that specify function, material, musical relationship, space, and sync target.

Good prompt shapes:

- `short glass fracture transient for car-window shatter, bright shards, dry close perspective, sync at frame 405`
- `low tonal impact in B minor for action arrival, 180ms body thump with short room tail`
- `reverse tonal ping riser, key-matched to music bed, 18 frames, peaks one frame before cut`
- `soft distant market crowd wash, low-passed, supports chase tension without masking dialogue`
- `metal-and-air whoosh for motorcycle pass, left-to-right motion, no tonal hit`

Weak prompt shapes:

- `epic whoosh`
- `cool hit`
- `cinematic riser`
- `make it intense`
- `add trailer sound effects`

## Bias Checks

Before using tonal SFX, ask:

- Is there a music bed or known key? If not, would a non-tonal material sound fit better?
- Is the visual event actually musical, transitional, emotional, or rhythmic enough to need tonal support?
- Would source audio, silence, or room tone be stronger?
- Have recent spots already used riser -> hit or whoosh -> hit? If yes, vary the design or skip it.
- Will the added sound mask dialogue, source emotion, or the main story sound?

## Timeline Mapping Notes

Represent these ideas as audio assets/items and automation:

- Use the target editor's native timing units for timeline placement.
- Gain, fades, trim, offset, EQ/filter, pitch/stretch, reverb/space, pan, and ducking only when supported by the active editing environment.
- Asset names by function and target, such as `sfx_glass_transient_window_405` or `sfx_tonal_riser_rooftop_turn_224`.
- Preserve source media and useful source audio. Do not destructively flatten the mix.

Never claim generated assets, waveform analysis, mix preview, render, or applied automation unless files/tool output prove it.
