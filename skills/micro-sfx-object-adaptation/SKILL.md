---
name: micro-sfx-object-adaptation
description: Use when adapting micro SFX to slow or fast and small or large UI, text, physical, or graphic objects. Provides exact adaptation maps for scale, speed, layering, timing, and gain.
---

# Micro SFX Object Adaptation

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
