---
name: fanedit-hook
description: Build the opening quote or story entry for a VibeEdit fan edit, including isolated source voice over a chosen song bed, clear story tension, and a launch point into the body.
---

# Fanedit Hook

Use this skill for section 1 of a fan edit: the entry quote and beginning of the story.

## Core Rule

The hook must make the viewer understand the edit's emotional question before the body starts. It is allowed to be quiet, but it cannot be vague.

A hook should be clip-hunted like a viral standalone moment. If the first 5-20 seconds would not be worth watching by itself, it is not strong enough to open the edit.

## Inputs

- Edit thesis or story axis.
- Candidate source quote ranges with transcript text and full-source timestamps.
- Song, beat map, and likely lyric-free or lower-vocal moments.
- Voice-isolation manifests when custom music overlaps dialogue.
- Candidate reaction or consequence shots from the same story thread.
- Surrounding source utterances before and after each candidate quote.
- Source shot timings that overlap the quote, setup, reaction, and consequence.

## Selection Rules

- Choose one quote or compact section that starts the story.
- Do not use overexposed hooks that the user has banned for freshness. For the current Creed workflow, reject the Creed 1 `4571.24-4593.16` exchange built around "Baby Creed", "Don't call me that", "Who you talking to?", and "VIP pass next to your pop"; do not use the full exchange, a compressed version, or the isolated "Don't call me that" line as the opening hook.
- Prefer a compact scene beat with setup, response, and escalation over a lone line.
- Score the candidate as a standalone clip: identity wound, disrespect, challenge, confession, threat, decision, or emotional reversal.
- Reject countdowns, referee counts, outcome reveals, final-fight payoffs, and other spoiler moments unless the visual payoff is present and the edit has earned it.
- Prefer isolated source voice over a lowered custom song bed when the user song is already part of the edit.
- Use full source audio only when the song intentionally stops and the original scene audio is clean, dramatic, and free of competing music.
- Keep the picture quote-synced unless a deliberate reaction cutaway is marked.
- If a quote must be split, insert a short music-only bridge that clarifies the story rather than generic hype.
- Do not cut off a phrase early. Use surrounding utterances to find the natural start and end of the thought.

## Reference Grammar: Creed Identity Hook

When using the Creed reference `7540284053279362334`, adapt the grammar rather than copying its visuals or trying to make the output look identical:

- Setup: an identity label lands as disrespect or pressure.
- Response: the main character rejects the label.
- Escalation: another character pushes the wound into legacy, name, fear, or challenge.
- Handoff: body visuals prove the character is not just the label.

The older Creed 1 identity hook around `1:16:12-1:16:34` (`4571.24-4593.16` source seconds) is now a banned freshness example, not a selectable reference. Mine different scenes or movies for the same kind of self-contained conflict, theme clarity, and escalation without reusing that "Baby Creed" / "Don't call me that" / "VIP pass" exchange.

## Output Contract

Return `hook_section`:

- `section_type`: `hook`
- `story_axis`
- `viewer_question`
- `quote_beats`: exact source ranges, transcript, audio mode, stem path or source-audio reason
- `quote_context`: preceding utterances, following utterances, speaker IDs, source shot ranges, and why the quote boundary is complete
- `standalone_clip_score`: why the hook works as its own clip
- `theme_lane`: the selected lane, such as `legacy_identity`, `prove_yourself`, `training_perseverance`, `rivalry_pressure`, or `love_family`
- `picture_beats`: quote-synced shots and any reaction/cutaway shots
- `music_plan`: song start, ducking, pause, or resume points
- `bridge_beats`: optional music-only bridges used to hide phrase cuts
- `handoff`: what body section should visually answer next
- `proof`: planned, materialized, rendered, ASR checked, and gaps

## QA

- The first heard quote is intelligible.
- The song does not compete with the quote.
- Rendered quote hooks pass ASR phrase QA for the expected story cues. If source audio is used, the custom song must not appear in the ASR transcript as competing lyric bleed.
- The viewer can state the story question after the hook.
- The body handoff is specific, not just "start montage."
- No repeated source frames are used inside the hook.
- The quote is not a clipped fragment; surrounding source context confirms the boundary.
- The quote is not a payoff/spoiler/countdown used without its visual story.
