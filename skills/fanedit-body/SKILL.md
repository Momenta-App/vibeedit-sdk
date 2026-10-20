---
name: fanedit-body
description: Build the high-entertainment visual body of a VibeEdit fan edit using fight, training, iconic motion, faces, and beat-driven visuals while avoiding visible talking during song-only sections.
---

# Fanedit Body

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


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

## Reviewed song body sync

Use the user's selected permitted song, content-SHA-bound beat map, human review events and optional intro-loop notes from the active project. No song or reviewed beat map is bundled. For a historical CreedEditSong recipe, the body entry was 21.961s after a protected 16.8577–21.8964s lead-in; those numbers are examples only and must never be applied to a different song identity. Derive the actual body entry from this project's reviewed beats and frame/sample mapping.

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
