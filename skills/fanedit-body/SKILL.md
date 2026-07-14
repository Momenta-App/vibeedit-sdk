---
name: fanedit-body
description: Build the high-entertainment visual body of a VibeEdit fan edit using fight, training, iconic motion, faces, and beat-driven visuals while avoiding visible talking during song-only sections.
---

# Fanedit Body

Use this skill for the body section of a fan edit: the main visual run while the song plays.

## Core Rule

The body is visual entertainment first and story support second. It should feel like the song is driving a sequence of iconic, high-impact images.

Never repeat a frame in normal body construction. Repeated source frames, recycled micro-ranges, and near-overlapping source windows are a hard failure unless the user explicitly asks for a deliberate repeat motif.

## Shot Selection

- Prefer fighting, training, entrances, knockdowns, stare-downs, ring pressure, physical exhaustion, victory, loss, and aftermath.
- Use shots tied to the same story axis as the hook.
- Avoid shots where the visible subject is clearly speaking during song-only sections.
- Good song-only shots include fighting, training, walking, reacting silently, being watched while someone else speaks off screen, crowd/ring pressure, and narrator-like voiceover sections where the mouth is not visible.
- Do not choose body shots only because they are local to the quote. Search broader movie sections for stronger visual appeal.
- Stay inside the selected theme lane. For `training_perseverance` or `prove_yourself`, prioritize training, ring pressure, setbacks, and work. Do not add love/family footage unless it is the declared emotional lane.
- Treat late-fight spoiler/payoff visuals as final climax or aftershock only. Do not burn them in the opening body unless the user asks for spoiler-heavy edits.
- Keep a source-range ledger and reject any clip whose frames overlap prior hook, body, filler, or bridge clips.

## Pacing

- Start readable, then accelerate.
- Use longer holds for faces, stares, and recovery.
- Use shorter cuts for impacts, punches, training hits, and movement peaks.
- Align cuts, speed ramps, and color changes to beat-map onsets when available.
- Reserve the strongest visual impact for the drop or final escalation.

## CreedEditSong Body Sync

For Creed edits using `CreedEditSong`, use the human-reviewed beat labels, not the historical folder name, as song truth:

- Song file: `fan_Edit_Data/workspace/media/8cc86491-f6ca-46f3-b1cc-924ba0fd07f8/CreedEditSong.MP3`.
- Beat labels: `fan_Edit_Data/workspace/outputs/untitled-05-beat-labeling/labels.json`.
- Main beat map: `fan_Edit_Data/workspace/outputs/untitled-05-beat-labeling/main_beat_map.json`.
- Intro loop notes: `fan_Edit_Data/workspace/media/8cc86491-f6ca-46f3-b1cc-924ba0fd07f8/analysis/audio/intro_loop_editing_notes.json`.

The first body hit should target the first human-labeled heavy beat around `21.961s`, after the protected final intro lead-in `16.8577-21.8964s`. The beat-label output folder still says `untitled-05`; treat that as stale path history while preserving the current `CreedEditSong` identity inside the artifacts.

Use the beat labels as selection pressure:

- `heavy_beat`: pair with misses, heavy face punches, knockdowns, or major hits.
- `light_beat`: pair with normal punches, blocks, bag hits, lighter contact, or motion texture.
- Record beat-to-impact timing in frames, targeting +/- 1 frame for hard impacts and misses. +/- 2 frames is reviewable but not perfect.
- Preserve the visible body start at the song body entry. Trim the song only from its beginning so the hook quote length determines how much intro is heard before the body starts.
- Keep the hook quote over the intro-loop bed at half volume by default, then bring the song up at the body entry.
- Treat the beat phrase as sections: two heavy beats, a light-beat run, two heavy beats, a light-beat run. Prefer the same source clip, nearby source clips, or at least the same movie inside each section.
- When several beats are close together, one strong source shot with multiple impact labels is preferred over excessive cutting.
- Use human punch/contact labels when present, and explicitly mark weaker micro-timeline inference when no human impact label overlaps the shot.
- Add SFX spots for each beat-matched impact: heavy beats use heavy face-punch, miss/whiff, knockdown, or major-hit assets; light beats use normal punch, block, bag-hit, or light-contact assets. Each spot needs an asset path or generation-needed status, timeline time, gain, and sync delta.

## Output Contract

Return `body_section`:

- `section_type`: `body`
- `story_axis`
- `visual_thesis`
- `shot_beats`: source ranges, story function, motion/impact reason, mouth-speaking risk
- `source_uniqueness`: no-repeat ledger entry and overlap check result for every shot
- `beat_sync`: song time, beat/onset reference, cut reason
- `impact_mapping`: heavy/light beat type, expected impact category, actual or inferred source impact category, timing delta in frames, and proof boundary
- `sfx_sync`: asset path or generation-needed status, target beat, target visual impact, timeline time, sync delta in frames, gain, and proof boundary
- `effects_plan`: concrete visual punctuation
- `avoidance_notes`: talking-mouth avoidance and any accepted gaps
- `proof`: rendered, sampled, reviewed, and gaps

## QA

- The body is visually exciting without needing source dialogue.
- Mouth-moving shots are avoided or justified.
- The strongest visual moment lands on a strong beat.
- The body still supports the story introduced by the hook.
- No source frames or source ranges repeat.
- Every shot is in the chosen theme lane or has a written exception.
