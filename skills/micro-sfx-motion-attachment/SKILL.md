---
name: micro-sfx-motion-attachment
description: Use when attaching micro SFX to exact visual motion targets such as text characters, modules, boxes, buttons, cursors, grids, panels, connectors, and object reveals.
---

# Micro SFX Motion Attachment

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill after choosing SFX types. It binds each sound to a visible motion phase so audio does not become a generic rhythm bed.

Load `references/motion_attachment_map.json` for exact target maps. Validate or print:

```bash
python3 <SKILL_DIR>/scripts/quick_validate.py --print
```

For character-level type-on work, read `references/character-type-on-speed-ladder.md`. It captures the proven five-speed pattern where every visible non-space character gets its own visual event and `iphone-typing-character` SFX hit.

## Attachment Rules

- Characters: pop on first readable frame, optional tick on secondary bounce. For true type-on, never animate the whole word per event; target the exact character index.
- Modules: tap/hit on route switch or snap; do not fire during idle drift.
- Boxes: tick for pulse, hit for large snap, pop for spawn.
- Buttons: click at down/select, tap at confirmation or elastic return.
- Cursors: click at contact, soft whoosh during fast travel.
- Grids: ticks on individual cells; grouped taps every 4-8 cells if density is high.
- Panels: whoosh before entrance, hit/tap on lock.
- Connectors: whoosh/tick while drawing, click at endpoint latch.
- Object reveals: anticipation whoosh before reveal, pop/hit at first full silhouette.

Use canonical role names `pop`, `hit`, and `layered` in downstream JSON. Legacy `text-pop`, `impact`, and `layer` may be accepted by scripts as aliases, but references should emit canonical names.

The demo evidence uses one timeline event to drive character pop, grid cell pulse, meter bar pulse, module shove, connector wire pulse, cursor movement, and counter update. Keep that one-event-to-many-visuals pattern only when the visuals truly share the same frame.
