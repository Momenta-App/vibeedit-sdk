# Character Type-On Speed Ladder

Use this when planning exact event times for visible character-by-character text reveals.

## Timing Rule

Create one event per visible non-space character. Event time equals the frame where that character starts becoming readable. Skip spaces and do not reuse one event to reveal the whole word.

Use the `iphone-typing-character` family (`micro_23`-`micro_25`) and rotate the exact file IDs to avoid identical repeated clicks.

## Five Speed Options

| Option | Gap per visible character | Suggested complexity | Notes |
| --- | ---: | --- | --- |
| slow | 120 ms | low/medium | clearest teaching pace |
| medium | 85 ms | medium | default readable type-on |
| quick | 60 ms | medium-high | lively but still character-readable |
| fast | 40 ms | high | dense kinetic text |
| burst | 25 ms | ultra | flourish; verify with contact sheet |

## Gain and Variation

- Gain: start around `-12` to `-9` dBFS equivalent for typing clicks, lower when layered under other SFX.
- Variation: deterministic `micro_23`, `micro_24`, `micro_25` rotation plus `0.5-1.5 dB` gain movement is enough.
- Do not add whooshes or thuds to each character. Reserve heavier sounds for word completion or line landing.

## Verification

For a rendered demo, make a typing-window contact sheet sampled at about `3 fps`. Passing proof shows each speed row at partial-progress states, with different rows completing at visibly different times.
