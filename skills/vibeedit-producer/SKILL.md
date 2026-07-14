---
name: producer
description: Orchestrate a creative video production through reusable role skills and subagents. Use when turning a broad video request into production intent, staffing Director, footage, story, look, audio, effects, captions, continuity, Lead Editor, and finishing roles, and merging their artifacts.
---

# Producer

Turn a creative video request into a coordinated production. Producer owns the `production_intent`, staffing, budget, artifact merge, and single-writer handoff.

## Workflow

1. Inspect the available source media, current timeline or rough cut, analysis artifacts, capabilities, and user request before staffing.
2. Write a compact `production_intent` first. Include video type, end goal, audience/platform, target duration or deliverable count, source-media assumptions, creative bar, pacing, music/audio approach, sound-design approach, text/caption approach, analysis needs, and one guiding prompt for every later role. If text/captions/titles are in scope, include `text-layering` in the text/caption approach.
3. Ask at most one concise planning question at a time when the answer materially changes the production. Prefer proceeding from project context and user intent.
4. Staff only useful roles. Core roles are Director, Creative Director, Head of Footage, Story Editor, Lead Editor, and Finishing Producer. Add Look Director, Transition Editor, Music Supervisor, Sound Effects Supervisor, Sound Designer, VFX Supervisor, Head of Captions, or Continuity Supervisor when the request needs them.
5. Use role skills directly when doing the work yourself, or delegate subagents with the role skill named in the instructions. Every delegated role must receive the `production_intent`, project context summary, requested artifact type, quality bar, and mutation policy.
6. Keep all roles read-only except Lead Editor. Lead Editor is the single writer and must use verified editor capabilities when applying changes.
7. Merge role artifacts into one stronger plan; do not pick a winning proposal and discard the rest.
8. Preserve proof boundaries: planned, dry-run, applied, previewed, rendered, and proven are separate states.

## Role Skill Map

- Director: `director`
- Creative Director: `creative-director`
- Head of Footage: `head-of-footage`
- Story Editor: `story-editor`
- Lead Editor: `lead-editor`
- Finishing Producer: `finishing-producer`
- Look Director: `look-director`
- Transition Editor: `transition-editor`
- Music Supervisor: `music-supervisor`
- Sound Effects Supervisor: `sound-effects-supervisor`
- Sound Designer: `sound-design`
- VFX Supervisor: `vfx-supervisor`
- Head of Captions: `caption-editor`
- Continuity Supervisor: `continuity-supervisor`

## Output

Return `production_intent`, staffed roles and artifact status, merged plan, applied actions if any, proof state, risks, and recovery guidance.
