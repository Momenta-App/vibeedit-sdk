# Timing Ranges

Use seconds unless noted. Treat ranges as craft defaults, not hard laws; the planner chooses deterministic values inside these ranges based on event role and complexity.

## Complexity Profiles

| Complexity | Event spacing target | Max layers | Overlap posture | Typical use |
| --- | ---: | ---: | --- | --- |
| `low` | 0.140-0.240 | 1-2 | mostly separated | hero UI moves, sparse title reveals |
| `medium` | 0.085-0.160 | 2-3 | controlled tails | readable text pops, buttons, menus |
| `medium-high` | 0.060-0.120 | 2-3 | selective secondary ticks | dense but readable UI rhythm |
| `high` | 0.045-0.100 | 2-4 | intentional clusters | rapid UI grids, kinetic type, beat accents |
| `ultra` | 0.028-0.070 | 3-5 | dense burst design | glitch bursts, fast montage punctuation |

## Role Timing

| Role | Transient offset from visual | Pre-roll | Post-roll | Notes |
| --- | ---: | ---: | ---: | --- |
| `click` | -0.004 to +0.004 | 0.000-0.010 | 0.020-0.060 | Keep tight; avoid long tails. |
| `tap` | -0.008 to +0.006 | 0.000-0.014 | 0.030-0.080 | Good for buttons and small cards. |
| `tick` | -0.003 to +0.006 | 0.000-0.008 | 0.020-0.055 | Good for counters, grid cells, and scan steps. |
| `pop` | -0.014 to -0.002 | 0.006-0.022 | 0.045-0.110 | Let the transient lead the visual slightly. |
| `hit` | -0.018 to -0.004 | 0.010-0.035 | 0.080-0.220 | Add body/tail only for important hits. |
| `whoosh` | -0.030 to -0.008 | 0.090-0.260 | 0.030-0.120 | Pre-roll carries motion into the landing. |
| `layered` | -0.024 to -0.004 | 0.080-0.220 | 0.100-0.300 | Plan distinct anticipation/contact/body/tail purposes. |
| `riser` | -0.020 to +0.000 | 0.180-0.480 | 0.020-0.080 | End at or just before the visual hit. |
| `glitch` | -0.010 to +0.010 | 0.010-0.050 | 0.030-0.130 | Use short clusters and pitch variance. |
| `tail` | +0.000 to +0.020 | 0.000-0.015 | 0.120-0.350 | Tail supports a prior hit; keep gain lower. |

## Mix Ranges

- Primary transient gain: `-10` to `-5` dB.
- Secondary layer gain: `-18` to `-10` dB.
- Tail/body layer gain: `-22` to `-12` dB.
- Repeated-hit gain variation: `0.5` to `2.5` dB across nearby hits.
- Pitch variation for repeated taps/clicks: `-1.5` to `+1.5` semitones.
- Tonal accent variation: `-3` to `+3` semitones when it will not fight music key.
- Ducking around primary hits: reduce bed/tails by `2` to `6` dB for `0.045` to `0.180` seconds.
- Automation attack/release inside a micro sound: attack `0.003-0.020`, hold `0.010-0.060`, release `0.030-0.180`.

## Density Checks

- Warn when planned transients are closer than one frame unless the complexity is `ultra`.
- Warn when more than three primary-role events land inside 180 ms.
- Warn when total active layers exceed the profile max for the same time window.
- Prefer fewer, better-placed hits over filling every visual change.

## Character Type-On Speed Ladder

Use `iphone-typing-character` (`micro_23`-`micro_25`) for readable character reveals. Each visible non-space character gets one event and one exact visual target.

| Label | Gap per visible character | Use |
| --- | ---: | --- |
| slow | 120 ms | deliberate tutorial/readability pass |
| medium | 85 ms | default readable UI/type-on rhythm |
| quick | 60 ms | energetic but still separable characters |
| fast | 40 ms | dense kinetic text; individual hits still perceived |
| burst | 25 ms | flourish/burst; use sparingly and verify by frame proof |
