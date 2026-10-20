---
name: vibeedit-quote-audio-structure
description: Structure fan edits around source quotes, song starts and stops, lyric/dialogue timing, and recurring audio story threads.
---

# VibeEdit Quote Audio Structure

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill when a fan edit should include iconic source dialogue, song interruptions, quote hooks, or lyric-driven storytelling.

## Core Rule

Do not let the song run mindlessly. Strong edits often start with a quote, enter the song, stop or duck the song for a second quote, then return to the edit with more story weight.

## Quote Patterns

- Opening quote: source line before the beat starts; establishes character, conflict, joke, grief, threat, or theme.
- Split quote: one longer line broken into several parts across the edit.
- Return quote: stop the song later and return to the same scene, character, or theme from the opening.
- Answer quote: another character responds near the drop or aftershock.
- Final quote: short line or breath that loops back to the opening emotion.
- Supporting quote interruption: in a short video, briefly pause or heavily duck the song, play a curated source quote, slow the matching source video for emphasis, then ramp the music back into the body on a beat or impact.

## Creed Supporting Quote Library

For Creed or other short edits, the user must supply a permitted project-local supporting-quote manifest with exact source hashes, original-clock ranges and allowed use. The package does not contain a quote library.

Use only active `quotes[]` from that manifest. Do not use entries in `removed_quotes[]`.

- `short_high_energy` quotes may be sprinkled into the body as quick quote hits. Pause or duck the music, play the quote audio with the matching source video at a slower, readable pace, then ramp the music back up and re-enter action on a clean beat.
- `medium_supporting` quotes should usually start as audio-first interruptions: the voice begins over a darkened, slowed, or reaction/body bridge while the song is muted or heavily ducked; reveal the matching source video only for the last few words so the line lands with visual emphasis.
- Medium quotes are optional and should be used sparingly, usually 0-2 times in a sub-60-second edit. They must deepen the same story lane as the hook/body, not become a separate monologue track.
- Prefer isolated voice when the custom song overlaps the quote. If no isolation exists yet, mark `audio_mode=source_audio_candidate` or `isolation_needed` instead of claiming clean isolation.
- Each interruption needs a re-entry plan: target beat, impact, riser, silence snap, or body shot that brings the song back up.

## Audio Rules

- Use the Myriograph public `analyze speakers` service (with an explicitly authorized retail ceiling) transcript for quote words and timing.
- Use source audio only when it is iconic enough to justify interrupting the music.
- Duck or cut the song under quotes; do not make speech compete with vocals.
- For supporting quote interruptions, record whether the music is muted, paused, or ducked, and include the ramp-back duration.
- If using lyrics as text, reveal the lyric word being heard, not a paraphrase.
- If using source dialogue as text, caption only the important words.

## Story Rules

- Quotes must follow the same character, scene, rivalry, or theme.
- Do not insert unrelated cool lines just because they are recognizable.
- Use the quote to add meaning that the visuals alone cannot carry.
- After a quote interruption, re-enter the song on a clean beat or impact.

## QA Checklist

- Dialogue is intelligible.
- Music stop/duck feels intentional.
- Quote and text match actual audio.
- The quote changes how the viewer reads the next visual section.
- Supporting quote interruptions re-enter the song cleanly and do not stall the short-video pacing.
- Medium quotes reveal matching source video only near the final words unless there is a marked creative reason to show the full quote video.
- No generated text explains the story outside the audio/theme.
