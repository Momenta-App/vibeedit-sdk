# Python-authored effects and transitions

Agents can define new trusted effects and transitions in Python while keeping
pixel processing inside FFmpeg. Registration is process-local and explicit;
CompositionSpec JSON never auto-imports or executes Python code.

```python
from vibeedit import register_transition_filter, register_video_effect_filter

register_video_effect_filter(
    "vibeedit://effect/my-contrast",
    lambda params: f"eq=contrast={float(params.get('contrast', 1.1)):.3f}",
)

register_transition_filter(
    "vibeedit://transition/my-wipe",
    lambda *, params, duration_frames, offset_frames, numerator, denominator:
        "xfade=transition=wipeleft:"
        f"duration={duration_frames * denominator / numerator:.9f}:"
        f"offset={offset_frames * denominator / numerator:.9f}",
)
```

After registration, use those stable identifiers in ordinary `Effect` and
`Transition` entries. The mixed dispatcher can combine the registered filters
with two source-video clips, audio, and Chromium HTML/CSS/JavaScript/WebGPU
motion layers.

This path is intended for effects expressible as FFmpeg filters. Analysis,
segmentation, optical flow, generated masks, or other complex Python work should
produce a derived media or artifact layer first, then reference that artifact
from CompositionSpec. This keeps per-frame Python out of the hot render loop.

