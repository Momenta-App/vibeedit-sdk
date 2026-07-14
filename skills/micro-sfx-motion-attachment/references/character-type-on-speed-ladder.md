# Character Type-On Speed Ladder

Use this when a text reveal must visibly appear one character at a time.

## Rule

Each visible non-space character gets one event, one `iphone-typing-character` sound, and one exact visual target. Do not trigger repeated sounds while animating the entire word or line; that reads as a block pop with clicks.

Use `micro_23`, `micro_24`, and `micro_25` in rotation for subtle iPhone-like typing clicks. Skip spaces.

## Five Speed Options

| Option | Gap per visible character | Feel |
| --- | ---: | --- |
| slow | 120 ms | deliberate, tutorial-friendly |
| medium | 85 ms | readable default |
| quick | 60 ms | energetic but separable |
| fast | 40 ms | dense kinetic type |
| burst | 25 ms | very fast flourish; verify visually |

## Visual Coupling

- Initial character state: opacity `0`, y offset `20-32px`, scale `0.84-0.92`.
- On character event: opacity to `1`, y to `0`, scale to `1`, duration `90-130ms`.
- Optional accent: brief color flash on the revealed character only.
- Row/word feedback may pulse, but it is secondary; the character reveal must be visible by itself.

## Event Shape

```json
{
  "time": 9.24,
  "family": "iphone-typing-character",
  "micro_id": 24,
  "target": "character reveal",
  "speed_key": "medium",
  "speed_label": "medium 85ms",
  "char_index": 3,
  "char": "E"
}
```

## Proof Standard

Create a contact sheet across the typing window. It must show partial words in progress, not only empty and complete states. A useful proof samples at least 3 fps over the reveal window.
