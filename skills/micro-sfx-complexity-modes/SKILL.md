---
name: micro-sfx-complexity-modes
description: Use when setting micro SFX complexity from low through ultra. Defines exact changes to hit count, layering depth, event density, timing jitter, volume envelopes, motion coupling, and verification strictness.
---

# Micro SFX Complexity Modes

Use this skill to scale a micro SFX plan without changing the creative target.

Load `references/complexity_modes.json` for exact numbers. Validate or print:

```bash
python3 <SKILL_DIR>/scripts/quick_validate.py --print
```

## Modes

- `low`: clear, sparse accents for major visible events only.
- `medium`: one hit for each readable interaction or text group.
- `medium-high`: denser UI rhythm with selective secondary ticks and pops.
- `high`: layered motion bed with grouped hits, tails, and stricter frame checks.
- `ultra`: maximum micro-detail; every sound must be justified by a visible event and audited closely.

Use the lowest mode that sells the motion. For `high` and `ultra`, dense overlap is allowed only when the visual itself is dense.
