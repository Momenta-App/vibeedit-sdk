"""Generated frame helpers backed by NumPy."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from vibeedit_media.optional import require_numpy

Color = tuple[int, int, int] | tuple[int, int, int, int]


@dataclass(frozen=True)
class FrameSpec:
    width: int
    height: int
    fps: int = 24
    duration: float = 1.0
    color: Color = (0, 0, 0)

    @property
    def frame_count(self) -> int:
        return max(1, round(self.fps * self.duration))


def solid_frame(width: int, height: int, color: Color = (0, 0, 0)):
    np = require_numpy()
    frame = np.zeros((height, width, len(color)), dtype=np.uint8)
    frame[:, :] = color
    return frame


def gradient_frame(
    width: int,
    height: int,
    start: Color = (0, 0, 0),
    end: Color = (255, 255, 255),
    axis: str = "x",
):
    np = require_numpy()
    if axis not in {"x", "y"}:
        raise ValueError("axis must be 'x' or 'y'")

    steps = width if axis == "x" else height
    ramp = np.linspace(start, end, steps, dtype=np.float32).astype(np.uint8)
    if axis == "x":
        return np.tile(ramp[None, :, :], (height, 1, 1))
    return np.tile(ramp[:, None, :], (1, width, 1))


def checkerboard_frame(
    width: int,
    height: int,
    cell_size: int = 16,
    colors: tuple[Color, Color] = ((32, 32, 32), (224, 224, 224)),
):
    np = require_numpy()
    if cell_size <= 0:
        raise ValueError("cell_size must be greater than zero")

    y = np.arange(height) // cell_size
    x = np.arange(width) // cell_size
    mask = (x[None, :] + y[:, None]) % 2
    return np.array(colors, dtype=np.uint8)[mask]


def frame_sequence(spec: FrameSpec, render: Callable[[int, float, FrameSpec], object] | None = None) -> Iterable[object]:
    def default_render(_index: int, _time: float, frame_spec: FrameSpec):
        return solid_frame(frame_spec.width, frame_spec.height, frame_spec.color)

    renderer = render or default_render
    return (renderer(index, index / spec.fps, spec) for index in range(spec.frame_count))
