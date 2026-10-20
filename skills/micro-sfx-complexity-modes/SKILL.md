---
name: micro-sfx-complexity-modes
description: Use when setting micro SFX complexity from low through ultra. Defines exact changes to hit count, layering depth, event density, timing jitter, volume envelopes, motion coupling, and verification strictness.
---

# Micro SFX Complexity Modes

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


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
