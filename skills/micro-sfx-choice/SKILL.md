---
name: micro-sfx-choice
description: Use when choosing micro motion-design SFX types for UI, text, graphic, or object events. Provides deterministic maps from event intent to clicks, taps, ticks, pops, hits, whooshes, and layered combinations.
---

# Micro SFX Choice

Use this skill before composing a short UI/text/motion SFX bed. It chooses the sound family and layer recipe for each visual event.

Load `references/sfx_choice_map.json` when you need exact mappings. Validate or print the map with:

```bash
python3 <SKILL_DIR>/scripts/quick_validate.py --print
```

Load `references/user-calibrated-families.md` when choosing from the bundled `micro_01`-`micro_50` WAVs by human-reviewed source-video behavior. These family labels are more specific than broad catalog tags like `click`, `tap`, or `text-pop`.

## Choice Rules

- `click`: discrete selection, cursor down/up, tab switch, checkbox, tiny latch.
- `tap`: button press, card touch, key press, icon nudge, small UI confirmation.
- `tick`: counter step, grid cell pulse, meter/bar increment, timeline marker, scan step.
- `pop`: text character, chip, badge, tooltip, small module appearing.
- `hit`: large card snap, panel lock, logo/object landing, strong beat-confirm.
- `whoosh`: slide, sweep, panel enter/exit, cursor travel, connector draw, object reveal.
- `layered`: plan a transient with body/tail only when the visual has both contact and travel, or when a hero reveal needs more weight. Composer input may use legacy `layer`, but it is normalized to `layered`.

## Evidence

The existing `micro-sfx-composer` catalog contains 50 assets tagged around UI/button/text material: 46 `tap`/`ui`, 43 `text-pop`, 34 `click`, 22 `tick`, 9 `motion`, 5 `pop`, 4 `whoosh`, with mostly light clips. The motion demo uses 72 bursty events over 6 seconds for button taps, text pops, motion ticks, module switches, and box motion.

## Output Contract

Return a per-event choice list:

```json
{
  "event": "panel_enter",
  "sfx_type": "whoosh",
  "layers": ["soft_whoosh", "landing_tap"],
  "timing_ms": [-70, 0],
  "gain_db": [-12, -8]
}
```

Prefer one sound per visible event. Add layers only when the event has separate anticipation, contact, and settle phases.

Layer recipes are planning guidance. The current `micro-sfx-composer` renders one selected catalog clip per event; for a layered recipe, pass one event per intended layer or choose the dominant layer/event and keep the rest in the timing plan.
