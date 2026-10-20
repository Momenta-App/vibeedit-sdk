---
name: micro-sfx-timing-craft
description: Use when planning or reviewing precise micro-SFX timing for motion edits, UI accents, text pops, impacts, transitions, and layered short sound design. Covers micro offsets, transient placement, pre/post-roll, overlap, layering, ducking, per-hit gain, intra-sound volume automation, pitch/tonal variation, density, rhythm, and complexity-aware numeric timing ranges. Includes a deterministic event-timeline planner/validator for JSON timing specs.
---

# Micro SFX Timing Craft

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill to turn visual event timings into a readable micro-SFX timing plan. This skill plans craft decisions only; it does not render audio, edit videos, or call the micro-SFX composer.

## Workflow

1. Identify visual anchors: impact frames, text reveals, button taps, motion starts, landings, and transitions.
2. Read [references/timing-ranges.md](references/timing-ranges.md) for numeric offset, overlap, gain, ducking, and density ranges.
3. Read [references/character-type-on-speed-ladder.md](references/character-type-on-speed-ladder.md) when planning character-level text reveals or comparing type-on speeds.
4. Read [references/event-schema.md](references/event-schema.md) when preparing JSON for the planner.
5. Run `scripts/plan_micro_sfx_timing.py` when event timings need deterministic validation or a reusable timeline manifest.
6. Inspect warnings before using the plan. Fix out-of-bounds events, overloaded density, or unclear role choices before rendering elsewhere.

## Planner

```bash
python3 <SKILL_DIR>/scripts/plan_micro_sfx_timing.py \
  --events /tmp/events.json \
  --out /tmp/micro_sfx_timing_plan.json
```

The input JSON contains a `duration`, optional `fps` and `complexity`, and an `events` array. The output JSON contains normalized event roles, planned transient/start/end timings, per-layer gain and pitch suggestions, ducking windows, automation points, and warnings.

Use `--complexity low|medium|medium-high|high|ultra` to override the file-level complexity. Legacy `max` input is accepted as an alias for `ultra`. Use `--strict` to exit non-zero when warnings are emitted.

## Craft Rules

- Place crisp hit transients slightly before the visual landing when the sound has attack latency; keep hard clicks on-frame or within one frame.
- Give whooshes, risers, and swipes enough pre-roll to imply motion before the visual lands.
- Use tails and post-roll to sell weight, but keep micro UI/tap sounds short enough that the next event remains legible.
- Layer only when each layer has a role: transient, body, air, tail, or tonal accent. Do not stack multiple layers doing the same job.
- Duck beds or previous tails around primary hits instead of pushing every hit louder.
- Vary gain and pitch in small deterministic steps for repeated hits; avoid random-sounding jumps unless the edit is intentionally chaotic.
- Lower density or simplify layers when events are closer than the target minimum gap for the chosen complexity.
- For character type-on, sound only visible non-space characters and reveal the exact character index at that event time. A whole-word or whole-line reveal with repeated clicks is not character-level typing.

## Output Boundaries

The planner output is a timing/mix manifest, not proof that audio exists or that a final render sounds good. Treat it as source for later composer, DAW, or edit-agent work, then verify by listening or inspecting the rendered waveform.
