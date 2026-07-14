---
name: vibeedit-creed-edit
description: Route natural Creed fan-edit requests like "make me a Creed edit" into a production-visible no-text action/music edit workflow with live dataset discovery, source selection, song crop, punch sync, SFX, render, review, and memory/proof handoff.
---

# VibeEdit Creed Edit

Use this skill for natural Creed edit requests, especially broad asks such as "make me a Creed edit", "Creed action edit", "Creed music edit", "viral Creed edit", or "use the Creed movies with a song".

This is a thin production-visible router. It does not replace the fan-edit, Creed analysis, sound, effects, render, or review skills. It selects the workflow, sets defaults, and keeps proof boundaries honest.

## Route Boundaries

Keep the current `CreedEditSong` hook/body workflow separate from reference-corpus research.

- Use this skill for the single-song Creed edit mode: quote hook over the `CreedEditSong` intro, then punch/body visuals locked to the body beats.
- Do not fold the 77-edit/trilogy cross-reference corpus into this route. That is a different skill and route: `vibeedit-creed-corpus-cross-reference`.
- The corpus route may learn reusable grammar from viral edits and cross-reference Creed 1/2/3 source moments, but it must return lessons or candidate boards into this route only after it records its own evidence boundaries.
- A `CreedEditSong` render package should not claim "77-edit" or "trilogy cross-reference" evidence unless that separate route produced a current artifact and the package cites it explicitly.

## Default Intent

Unless the user asks otherwise, build a hook + body Creed edit using `CreedEditSong`:

- Strong quote/story hook first, then a music-driven fight/training body.
- No on-screen text overlays unless explicitly requested.
- No explanatory labels, quote cards, subtitles, captions, or motivational words.
- Music drives the edit.
- Source dialogue is used only for the hook and must pass the full-context quote gates from `fanedit-hook` and `fanedit-polish-router`.
- For short-video polish, supporting quote interruptions may be added sometimes after the hook and inside the body. Use the curated Creed supporting quote manifest through `vibeedit-quote-audio-structure`; pause or heavily duck the music, play the quote with slowed source video emphasis, then ramp back into the body on a beat or impact.
- Do not use the overexposed Creed 1 "Baby Creed" / "Don't call me that" / "VIP pass next to your pop" exchange, or the isolated "Don't call me that" line, as the hook. It is banned for freshness in the current CreedEditSong route.
- Prioritize boxing, training, entrances, stare-downs, impacts, knockdowns, exhausted recovery, comeback pressure, and quiet aftershock.
- Target sub-60-second social delivery unless the project or user specifies another runtime or aspect ratio.

If the user explicitly asks for Creed kinetic text, captions, lyrics, or quote typography, route to `vibeedit-creed-kinetic-text` after source and audio timing are selected. Do not load or use the text skill for the default no-text edit.

## Discovery First

Discover current paths before planning. Do not rely on memory or hard-coded ids unless current files confirm them.

Check likely roots:

```bash
find fan_Edit_Data/workspace -maxdepth 5 \( -iname '*Creed*.mp4' -o -iname '*creed*.mp4' \) -print
find fan_Edit_Data/workspace -maxdepth 5 \( -iname '*beatmap*.json' -o -iname '*layer1*.json' -o -iname '*transcript*.json' -o -iname '*story_moments*.json' \) -print
find fan_Edit_Data/workspace/reference-corpora/creed-viral -maxdepth 3 -type f | sed -n '1,120p'
find fan_Edit_Data/workspace -maxdepth 5 \( -iname 'status.json' -o -iname 'run_summary.json' -o -iname 'source_meta.json' -o -iname 'provider_media.json' \) -print
```

Use confirmed paths for:

- Source movies: `Creed 1.mp4`, `Creed 2.mp4`, `Creed 3.mp4`, or whichever Creed files are actually present.
- Production-analysis artifacts: transcripts, shot boundaries, scene/semantic summaries, VEV1/person/face data, motion or audio markers, thumbnails/contact sheets.
- Reference corpus: `fan_Edit_Data/workspace/reference-corpora/creed-viral` when present.
- Song inputs and analysis: selected music file, beatmap, Layer 1, waveform/onset data, and crop candidates.
- Curated supporting quotes: `fan_Edit_Data/workspace/projects/f7216bfb-3bfd-4182-bc23-0607fcac97ae/renders/creed-supporting-quotes/quote-audio-manifest.json` when present. Use active `quotes[]` only; ignore `removed_quotes[]`.
- Existing workspace/project outputs, render history, and accepted prior manifests.

If a required source, song, transcript, beatmap, or renderer is missing, report the missing item and keep the state `planned` or `blocked`. Do not invent timestamps, clips, audio assets, or renders.

## Router Order

1. Load `fan-edit` as the parent edit contract.
2. Load `fanedit-polish-router` for renderability gates and proof vocabulary.
3. Load `vibeedit-creed-viral-edit-analysis` to choose movie-local source moments from current media and analysis artifacts.
4. Load `fanedit-body` for the no-text music/action body.
5. Load `vibeedit-quote-audio-structure` when adding optional supporting quote interruptions from the curated Creed quote manifest.
6. Load `vibeedit-punch-sfx-library` for every boxing punch, bag hit, block, and heavy-face impact SFX selection.
7. Load `sound-design` for song crop, silence, non-punch SFX, whooshes, hits, ducking, ramp-backs, and mix hierarchy.
8. Load `vibeedit-effects-punctuation`, transition, masking, or subject-effect skills only for effects that will be materially implemented.
9. Load `vibeedit-python-analysis-rendering` or the current render implementation only after concrete clips, audio ranges, and effects exist.
10. Load review/QA discipline before calling a render accepted or proven.

Only claim a child skill was used when its instructions were loaded and the result is represented by concrete assets, layer specs, manifests, or explicit blockers.

## Source Selection

Build a compact source board before cutting:

- Map each candidate to `movie`, `source_range`, `story_function`, `visual_reason`, `motion_or_audio_anchor`, and `evidence_path`.
- Use `vibeedit-creed-viral-edit-analysis` for story functions and transcript/shot evidence.
- Use `fanedit-body` for music-only action shot quality and mouth-speaking avoidance.
- Prefer non-chronological order when it makes a stronger edit.
- Keep a no-repeat ledger for every selected source range.
- Reserve the strongest hit, reversal, face, knockdown, or comeback image for the drop or final escalation.

Default theme lane: `prove_yourself` or `legacy_pressure`, selected from the strongest available source evidence. Do not mix father/family/love scenes into a training/fight edit unless they directly support the chosen lane.

## Song Crop And Sync

Treat the song as an editable source, not a full-track obligation.

- For the current Creed hook/body workflow, discover and use `CreedEditSong` at `fan_Edit_Data/workspace/media/8cc86491-f6ca-46f3-b1cc-924ba0fd07f8/CreedEditSong.MP3`.
- Use `fan_Edit_Data/workspace/outputs/untitled-05-beat-labeling/main_beat_map.json` and `labels.json` as the human-reviewed `CreedEditSong` heavy/light body map, despite the historical folder name.
- Use `fan_Edit_Data/workspace/media/8cc86491-f6ca-46f3-b1cc-924ba0fd07f8/analysis/audio/intro_loop_editing_notes.json` to preserve the final intro lead-in `16.8577-21.8964s` inside the portion that plays under the hook.
- Aim the body entry at the first labeled heavy beat around `21.961s` in the song source, mapped to the hook-end timeline.
- During the hook quote, play the intro-loop portion of `CreedEditSong` under the dialogue at half volume or lower; lower it when ASR or listening review says the quote is competing with the song.
- Fit hook length by trimming only from the beginning of the song audio. If the hook is `H` seconds long and the target body beat is `21.961s`, the intro song source range should end at `21.961s` and start near `21.961 - H`. Do not wait on the timeline with a music-only bridge just to reach `21.961s`.
- The hook/body timeline handoff is the hook end. The song body starts there with source time `21.961s`, and the package must record the hook duration, source trim start, song body-entry time, and frame/sample delta.
- Start the first body punch clip with a short visual pre-roll, usually `0.45-0.55s`, so the contact frame/SFX lands exactly on the mapped first beat. Example: if the beat maps to timeline `10.0s`, start the punch shot around `9.5s` and choose the source start so the labeled contact frame reaches `10.0s`.
- Treat the beat phrase as repeating sections: two heavy beats, a light-beat run, two heavy beats, a light-beat run. Each section should prefer one movie-local source segment or nearby clips from the same movie/timestamp neighborhood.
- Discover existing beatmap and Layer 1 artifacts first.
- If missing and local analysis is allowed, route through the repo's current audio beat/layer analyzers and register artifacts when the workspace workflow supports it.
- Choose a song crop with a clear hook, build, drop, and loop or hard ending.
- Align cuts to downbeats, transients, phrase changes, source motion peaks, glove impacts, head turns, camera punches, crowd hits, and breath pauses.
- Leave silence or source-only audio only when it strengthens an impact, stare, recovery, or pre-drop tension.

Do not call schedule math proof. A punch-sync or beat-sync claim is only proven after the rendered or exported audio/video is inspected against frames/samples.

## Supporting Quote Interruptions

Supporting quotes are optional flavor for short videos, not required structure. Use them sometimes when they deepen the current theme lane and the edit can return to the body cleanly.

- Source them from `fan_Edit_Data/workspace/projects/f7216bfb-3bfd-4182-bc23-0607fcac97ae/renders/creed-supporting-quotes/quote-audio-manifest.json`.
- Use active manifest `quotes[]` only. Do not use removed entries.
- Short/high-energy quotes can punctuate the body: pause or heavily duck the song, slow the matching source video for the quote, then ramp the music back up into a beat, punch, or action shot.
- Medium quotes should be audio-first: begin the quote over a slowed bridge, reaction, or darkened action shot with the song muted/ducked; reveal the matching quote video only for the final few words.
- Prefer 0-2 medium quote interruptions in a sub-60-second edit. Too many makes the edit stop feeling like a music/action body.
- Prefer isolated voice over source audio when the song overlaps the quote. If isolation is not produced and QA'd, record it as `isolation_needed` or `source_audio_candidate`.
- The render package must record `supporting_quote_interventions[]` with manifest id, audio file, source range, video reveal range, slow-motion factor, music duck/pause automation, ramp-back duration, re-entry beat/impact, and proof state.

## SFX And Effects

SFX are expected for this router unless the user asks for a clean music-only edit, but they must be concrete:

- Do not use flashing, white flash frames, flash transitions, or flash-subject-transition skills in the current CreedEditSong mode.
- Punch hits must use `vibeedit-punch-sfx-library` and the approved manifest at `fan_Edit_Data/workspace/outputs/punch-hit-impact-sfx-flat/approved/Punches-individual-flat/approved-punch-sfx-manifest.json`.
- Use `bag_block` assets for bag hits and blocks, `heavyface` assets for `heavy_face_punch`, and `normal` assets for normal/lighter punch contact.
- Use `whoosh_miss` assets only as supplementary air/miss support when an already selected clip needs that sound to make a rapid punch sequence work. Do not choose a clip because it is a miss/whoosh.
- Cycle category-locally so the same approved punch asset is not used twice in a row inside its category.
- Glove thuds, crowd swells, camera hits, whooshes, risers, drop impacts, and short stutters are good non-punch candidates.
- Every SFX event needs an asset path or generation result, timeline time, gain intent, and sync reason.
- Every heavy/light beat that is matched to a visual punch impact needs a corresponding SFX spot. Heavy punch beats should use `heavyface`; light/body/training punch beats should use `normal` or `bag_block`.
- Route misses, whiffs, or `whoosh_miss` labels through the approved punch SFX library only as supporting SFX layers with `selection_priority="supplementary"` and `supporting_only=true`.
- Hard punch impacts should target +/- 1 frame from the visual contact moment. If only +/- 2 frames can be proven, mark it as review instead of perfect.
- Every visual punctuation needs an implementation path: built-in effect, renderer operation, transition shader, mask-backed subject effect, or accepted omission.
- Do not add fake effect labels, fake placeholder clips, or unsupported masks to a final render package.

## Output Contract

Produce a `creed_edit_package` with:

- `edit_type`: `vibeedit-creed-edit`
- `intent`: `no_text_action_music` unless the user requested another mode
- `proof_state`: one of `planned`, `dry-run`, `applied`, `previewed`, `rendered`, `reviewed`, `accepted`, `blocked`
- `workspace_paths`: discovered source, corpus, analysis, song, and output roots
- `theme_lane`
- `source_board`: candidates and rejected examples with evidence paths
- `selected_timeline`: exact source ranges, timeline ranges, roles, sync anchors, and no-repeat ledger
- `song_crop`: source audio path, crop start/end, beatmap/layer evidence, entry/drop/loop points
- `sfx_plan`: concrete assets or blocked/generation-needed states
- `supporting_quote_interventions`: optional short/medium quote moments from the curated manifest, with music duck/pause and ramp-back details
- `effects_plan`: concrete operations or accepted omissions
- `text_plan`: empty by default, or explicit user-requested text-skill output
- `render_plan`: renderer path, dimensions, fps, codec, output target, and registration plan
- `review_plan`: full-speed, muted, audio-only, frame/sample sync, duplicate-frame, mouth-speaking, social-scale, and final-loop checks
- `memory_notes`: only facts proven by current files or generated artifacts that should be preserved later
- `gaps`: missing assets, unrun checks, unrendered effects, or unproven claims

## Proof Boundaries

- `planned`: source and timeline choices exist, but no editor mutation or render is proven.
- `dry-run`: a renderer or timeline operation validated inputs without changing the project.
- `applied`: project or timeline changed and the mutation path is known.
- `previewed`: an actual preview artifact or live surface was inspected.
- `rendered`: an MP4 or equivalent output exists.
- `reviewed`: QA inspected the output and recorded results.
- `accepted`: review passed or accepted gaps are explicit.
- `blocked`: a concrete missing dependency, source, permission, tool, or safety gate stopped progress.

Never collapse these states. Do not say ready, rendered, reviewed, accepted, or proven unless that exact state has evidence.

## Handoff

When execution is not possible in the current turn, hand off with:

- current discovered paths,
- current package path if one was written,
- exact next command or next inspection,
- proof state,
- blocked reason if any,
- and a no-overclaiming note for any unrendered or unreviewed work.
