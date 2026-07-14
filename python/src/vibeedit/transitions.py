from __future__ import annotations

from fractions import Fraction


def frames_to_seconds(frames: int, numerator: int, denominator: int) -> Fraction:
    return Fraction(frames * denominator, numerator)


def crossfade_filter(*, duration_frames: int, offset_frames: int, numerator: int, denominator: int) -> str:
    duration = frames_to_seconds(duration_frames, numerator, denominator)
    offset = frames_to_seconds(offset_frames, numerator, denominator)
    return f"xfade=transition=fade:duration={float(duration):.9f}:offset={float(offset):.9f}"
