# Event Schema

The planner accepts one JSON object.

```json
{
  "duration": 1.8,
  "fps": 30,
  "complexity": "medium",
  "events": [
    {
      "id": "title-01",
      "time": 0.42,
      "role": "pop",
      "weight": 0.8,
      "layers": 2,
      "group": "title"
    }
  ]
}
```

## Root Fields

- `duration` required: timeline duration in seconds.
- `fps` optional: defaults to `30`; used for frame-distance warnings.
- `complexity` optional: `low`, `medium`, `medium-high`, `high`, or `ultra`; defaults to `medium`. Legacy `max` is accepted as an alias for `ultra`.
- `events` required: array of event objects.

## Event Fields

- `id` required: stable string used for deterministic variation.
- `time` required: visual anchor time in seconds.
- `role` optional: `click`, `tap`, `tick`, `pop`, `hit`, `whoosh`, `layered`, `riser`, `glitch`, or `tail`; defaults to `tap`. Legacy `text-pop`, `impact`, and `layer` are accepted as aliases for `pop`, `hit`, and `layered`.
- `weight` optional: `0.0-1.0`, where heavier events get stronger gain, more tail, and more ducking.
- `layers` optional: requested layer count. The planner caps this by complexity and role.
- `group` optional: repeated events in the same group receive small gain/pitch variation.
- `duration` optional: visual event duration in seconds. Useful for swipes, risers, and long transitions.

Unknown fields are preserved under `source` in the output event so downstream agents can retain context without the planner needing to understand it.
