from __future__ import annotations

from fractions import Fraction
from collections.abc import Callable


TransitionFilterBuilder = Callable[..., str]
_TRANSITION_FILTERS: dict[str, TransitionFilterBuilder] = {}


def register_transition_filter(identifier: str, builder: TransitionFilterBuilder, *, replace: bool = False) -> None:
    if not identifier.startswith("vibeedit://transition/"):
        raise ValueError("transition identifier must start with vibeedit://transition/")
    if identifier in _TRANSITION_FILTERS and not replace:
        raise ValueError(f"transition filter is already registered: {identifier}")
    _TRANSITION_FILTERS[identifier] = builder


def transition_filter(identifier: str, params: dict, *, duration_frames: int, offset_frames: int, numerator: int, denominator: int) -> str:
    if identifier == "vibeedit://transition/crossfade":
        return crossfade_filter(duration_frames=duration_frames, offset_frames=offset_frames, numerator=numerator, denominator=denominator)
    builder = _TRANSITION_FILTERS.get(identifier)
    if builder is None:
        raise ValueError(f"no Python/FFmpeg filter is registered for transition: {identifier}")
    result = builder(params=params, duration_frames=duration_frames, offset_frames=offset_frames, numerator=numerator, denominator=denominator)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"transition filter builder returned an empty filter: {identifier}")
    return result


def frames_to_seconds(frames: int, numerator: int, denominator: int) -> Fraction:
    return Fraction(frames * denominator, numerator)


def crossfade_filter(*, duration_frames: int, offset_frames: int, numerator: int, denominator: int) -> str:
    duration = frames_to_seconds(duration_frames, numerator, denominator)
    offset = frames_to_seconds(offset_frames, numerator, denominator)
    return f"xfade=transition=fade:duration={float(duration):.9f}:offset={float(offset):.9f}"
