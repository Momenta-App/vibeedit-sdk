# Viral Source Edit Package Contract

This contract defines dry-run edit plan packages for future source/movie and song inputs. Packages are planning artifacts only: they do not render, mutate source media, edit project files, or claim source truth beyond their evidence state.

## Required Package Shape

Each package is a directory containing:

- `index.json`: machine-readable package index and file map.
- `memory.json`: compact local wiki memory for follow-up planning passes.
- `edit-plan.json`: structured edit plan with section timing, source candidates, audio intent, text policy, and renderability notes.
- `proof-ledger.json`: every claim separated by proof state.
- `source.md`: source/movie profile, aspect-ratio policy, candidate source moments, and unresolved checks.
- `story.md`: thesis, lane, structure, non-chronological rationale, and story evidence.
- `song.md`: song section map, beat/energy assumptions, and sync targets.
- `quote.md`: quote or source-dialogue intent, including unresolved proof boundaries.
- `transitions.md`: post-structure cut review, transition posture, per-cut decisions, downstream transition skills, and unresolved mask/timeline changes.
- `effects.md`: additive post-transition effect pass, unused song anchors, planned visual punctuation, downstream effect skills, and no-structure-change notes.
- `sfx.md`: SFX/sound-design recipe notes and silence/ducking intent.
- `qa.md`: preflight QA checklist and blocked render claims.

## Defaults

- Aspect ratio defaults to `source`. The package may record a detected or requested ratio, but must not force a social crop unless requested.
- On-screen text overlays default to `false`. Story labels, beat roles, quote roles, and internal section names are metadata only unless a later text pass explicitly materializes final text layers.
- Transition review runs after the main structure and before effects. It may request clip or timeline changes for transition quality, especially subject-flash transitions that need a strong clip-B subject and no-jump landing.
- Effects review runs after transition decisions. It is additive only and must not change clip choices, cut order, cut timing, or transition decisions.
- Packages are dry-run by default. The default state is `planned`, not `tested`, `reviewed`, or `accepted`.
- Creed corpus evidence is optional learned evidence. It can suggest source-selection grammar, pacing, song section behavior, and proof discipline, but it does not confirm future source/movie moments.

## Proof States

Use these states exactly in the proof ledger:

- `learned`: pattern observed from a reference corpus or prior package.
- `inferred`: planner conclusion from provided metadata or reusable grammar.
- `candidate`: possible source, quote, SFX, or sync target that still needs confirmation.
- `preferred`: ranked choice among candidates before confirmation.
- `confirmed`: backed by direct source/media inspection or a user-provided authoritative input.
- `planned`: included in the dry-run edit package.
- `tested`: executed through a test or preview workflow.
- `reviewed`: inspected by a human or review model with recorded evidence.
- `accepted`: explicitly approved as final.

No package may promote a claim to `tested`, `reviewed`, or `accepted` unless the corresponding operation actually happened and the evidence path is recorded.

## Arbitrary Input Contract

Future source/movie and song inputs can be supplied as JSON files:

```json
{
  "title": "Movie title",
  "source_id": "movie-or-source-id",
  "aspect_ratio": "source",
  "moments": [
    {
      "id": "moment-001",
      "start_sec": 10.0,
      "end_sec": 14.2,
      "story_function": "hook",
      "vibe": "recognizable entrance",
      "proof_state": "candidate"
    }
  ]
}
```

```json
{
  "title": "Song title",
  "artist": "Artist",
  "duration_sec": 24.0,
  "bpm": 128.0,
  "sections": [
    { "name": "hook", "start_sec": 0.0, "end_sec": 3.0, "energy": "medium" },
    { "name": "drop", "start_sec": 8.0, "end_sec": 14.0, "energy": "high" }
  ]
}
```

Missing fields should be represented as unresolved candidates, not fabricated confirmations.
