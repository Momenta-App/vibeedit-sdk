"""MoviePy helpers kept behind lazy optional imports."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from vibeedit_media.images import ImageInput
from vibeedit_media.images import to_numpy_image
from vibeedit_media.optional import require_moviepy_clip


def clip_from_frames(frames: Iterable[ImageInput], fps: int = 24):
    ImageSequenceClip = require_moviepy_clip()
    return ImageSequenceClip([to_numpy_image(frame, "RGB") for frame in frames], fps=fps)


def write_video(
    frames: Iterable[ImageInput],
    path: str | Path,
    fps: int = 24,
    codec: str = "libx264",
    audio: bool = False,
    **kwargs,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    clip = clip_from_frames(frames, fps)
    try:
        clip.write_videofile(str(destination), fps=fps, codec=codec, audio=audio, **kwargs)
    finally:
        close = getattr(clip, "close", None)
        if close:
            close()
    return destination
