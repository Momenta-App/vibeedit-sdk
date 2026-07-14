"""Lazy optional dependency helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from vibeedit_media.backend import MissingBackendError


class MissingOptionalDependencyError(MissingBackendError):
    """Raised when a helper needs an optional Python dependency."""

    def __init__(self, module: str, extra: str):
        self.module = module
        self.extra = extra
        super().__init__(
            backend=extra,
            message=f"Missing optional dependency '{module}'.",
            install_hint=f"Install it with 'pip install vibeedit-media[{extra}]'.",
        )


def require_module(module: str, extra: str) -> Any:
    try:
        return import_module(module)
    except ImportError as error:
        raise MissingOptionalDependencyError(module, extra) from error


def require_numpy() -> Any:
    return require_module("numpy", "numpy")


def require_pillow() -> Any:
    return require_module("PIL.Image", "pillow")


def require_pillow_draw() -> tuple[Any, Any, Any]:
    return (
        require_module("PIL.Image", "pillow"),
        require_module("PIL.ImageDraw", "pillow"),
        require_module("PIL.ImageFont", "pillow"),
    )


def require_cv2() -> Any:
    return require_module("cv2", "opencv")


def require_moviepy_clip() -> Any:
    try:
        return import_module("moviepy.editor").ImageSequenceClip
    except ImportError:
        try:
            return import_module("moviepy").ImageSequenceClip
        except ImportError as error:
            raise MissingOptionalDependencyError("moviepy", "moviepy") from error
