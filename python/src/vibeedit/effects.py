from __future__ import annotations

import random
from collections.abc import Callable


VideoEffectFilterBuilder = Callable[[dict], str]
_VIDEO_EFFECT_FILTERS: dict[str, VideoEffectFilterBuilder] = {}


def register_video_effect_filter(identifier: str, builder: VideoEffectFilterBuilder, *, replace: bool = False) -> None:
    if not identifier.startswith("vibeedit://effect/"):
        raise ValueError("effect identifier must start with vibeedit://effect/")
    if identifier in _VIDEO_EFFECT_FILTERS and not replace:
        raise ValueError(f"effect filter is already registered: {identifier}")
    _VIDEO_EFFECT_FILTERS[identifier] = builder


def video_effect_filter(identifier: str, params: dict) -> str:
    if identifier == "vibeedit://effect/random-frame-stutter":
        return random_frame_stutter_filter(params)
    builder = _VIDEO_EFFECT_FILTERS.get(identifier)
    if builder is None:
        raise ValueError(f"no Python/FFmpeg filter is registered for effect: {identifier}")
    result = builder(params)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"effect filter builder returned an empty filter: {identifier}")
    return result


def random_frame_stutter_mapping(*, seed: int, window_frames: int = 4, intensity: float = 0.75) -> tuple[int, ...]:
    if window_frames < 1:
        raise ValueError("window_frames must be positive")
    if not 0 <= intensity <= 1:
        raise ValueError("intensity must be between 0 and 1")
    generator = random.Random(seed)
    return tuple(
        max(0, index - generator.randint(1, min(index, window_frames - 1))) if index and generator.random() < intensity else index
        for index in range(window_frames)
    )


def random_frame_stutter_filter(params: dict) -> str:
    mapping = random_frame_stutter_mapping(
        seed=int(params.get("seed", 1)),
        window_frames=int(params.get("windowFrames", 4)),
        intensity=float(params.get("intensity", 0.75)),
    )
    return "shuffleframes=" + " ".join(str(index) for index in mapping)
