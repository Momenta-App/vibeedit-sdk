---
name: micro-sfx-object-adaptation
description: Use when adapting micro SFX to slow or fast and small or large UI, text, physical, or graphic objects. Provides exact adaptation maps for scale, speed, layering, timing, and gain.
---

# Micro SFX Object Adaptation

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill when a chosen SFX type needs to fit object size and motion speed.

Load `references/object_adaptation_map.json` for exact recipes. Validate or print:

```bash
python3 <SKILL_DIR>/scripts/quick_validate.py --print
```

## Adaptation Rules

- Small fast events stay dry, short, and low gain: click/tick/pop.
- Small slow events need fewer hits with softer tails: pop/tap with wider spacing.
- Large fast events need a transient plus body: hit/tap, sometimes whoosh into hit.
- Large slow events need motion lead-in: whoosh plus soft landing, fewer total hits.
- Text favors pops and ticks; UI favors clicks/taps/ticks; physical objects favor hits/whooshes; graphic shapes can use any family but must follow visible motion phase.

Do not make a large object loud only by raising gain. Add body/tail layers and leave headroom.

Use canonical role names `pop`, `hit`, and `layered` in downstream JSON. Layered object recipes are plans unless rendered as separate per-layer events or reduced to one chosen composer clip for the dominant layer.
