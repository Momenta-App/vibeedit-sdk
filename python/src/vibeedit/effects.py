from __future__ import annotations

import random


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

