---
name: vibeedit-pacing-contrast
description: Control short-form fan-edit pacing, visual contrast, clip duration, speed ramps, holds, and intensity changes so edits feel sharp without becoming unreadable.
---

# VibeEdit Pacing Contrast

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill when shaping the rhythm and intensity curve of a fan edit.

## Core Rule

Fast is not automatically better. The edit needs contrast: quiet to loud, black-and-white to color, slow hold to rapid cuts, face to action, quote to drop.

## Pacing Shape

- Hook: 0.5 to 2.0 seconds, immediately legible.
- Setup: slightly longer shots so the viewer understands the subject.
- Build: progressively shorter shots or stronger effects.
- Drop: fastest or most forceful section, but still readable.
- Aftershock: one held reaction, consequence, or final punch.
- Loop: end with timing that can return to the start.

## Clip Duration Heuristics

- Quote/face/stare: longer holds.
- Action impacts: short holds around the impact frame.
- Build clips: shorten over time.
- Repeated percussion: do not always cut; use object flashes, zoom pulses, or text word changes.
- High-motion footage: needs more frames than still faces.

## Contrast Moves

- Black-and-white intro into color at intensity.
- Silent or ducked quote into song start.
- Wide shot into close-up.
- Calm face into action burst.
- Clean text into red-emphasis impact.
- Full-frame clip into cutout/segmented layer.

## Speed Rules

- Speed ramp into a beat, not randomly through the shot.
- Slow motion should reveal emotion or impact.
- Fast motion should bridge to a cut or energy rise.
- Do not speed up dialogue unless stylized audio is intentionally discarded.

## QA Checklist

- Viewer can identify the subject in every section.
- The timeline has at least one clear intensity contrast.
- Fast cuts do not erase the emotional argument.
- Holds occur for a reason, not because there was no footage.
