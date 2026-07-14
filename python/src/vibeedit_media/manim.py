"""Subprocess-backed Manim helpers.

The module checks for Manim without importing it. The optional Manim dependency
is only needed by callers that execute generated scene modules or render.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vibeedit_media.backend import MissingBackendError


Quality = Literal[
    "low_quality",
    "medium_quality",
    "high_quality",
    "production_quality",
    "fourk_quality",
    "l",
    "m",
    "h",
    "p",
    "k",
]

_QUALITY_FLAGS = {
    "low_quality": "l",
    "medium_quality": "m",
    "high_quality": "h",
    "production_quality": "p",
    "fourk_quality": "k",
    "l": "l",
    "m": "m",
    "h": "h",
    "p": "p",
    "k": "k",
}


@dataclass(frozen=True)
class ManimCapabilities:
    manim_path: str | None
    python_module: bool
    available: bool
    error: str | None = None


def check_capabilities(manim: str = "manim") -> ManimCapabilities:
    """Return Manim CLI/module availability without importing Manim."""

    manim_path = shutil.which(manim) if _bare_command(manim) else manim
    python_module = importlib.util.find_spec("manim") is not None
    if manim_path:
        return ManimCapabilities(manim_path=manim_path, python_module=python_module, available=True)
    return ManimCapabilities(
        manim_path=None,
        python_module=python_module,
        available=False,
        error="Manim must be installed or supplied explicitly.",
    )


def build_render_command(
    scene_file: str | os.PathLike[str],
    scene_name: str,
    *,
    quality: Quality = "medium_quality",
    media_dir: str | os.PathLike[str] | None = None,
    output_file: str | os.PathLike[str] | None = None,
    transparent: bool = False,
    format: str | None = None,
    manim: str = "manim",
    extra_args: list[str] | tuple[str, ...] = (),
) -> list[str]:
    """Build a Manim CLI command.

    Example:
        manim -q m --media_dir renders/manim scene.py IntroScene
    """

    if quality not in _QUALITY_FLAGS:
        raise ValueError(f"Unsupported Manim quality: {quality}")

    command = [manim, "-q", _QUALITY_FLAGS[quality]]
    if media_dir is not None:
        command.extend(["--media_dir", str(media_dir)])
    if output_file is not None:
        command.extend(["--output_file", str(output_file)])
    if transparent:
        command.append("--transparent")
    if format is not None:
        command.extend(["--format", format])
    command.extend(extra_args)
    command.extend([str(scene_file), scene_name])
    return command


def render(
    scene_file: str | os.PathLike[str],
    scene_name: str,
    *,
    quality: Quality = "medium_quality",
    media_dir: str | os.PathLike[str] | None = None,
    output_file: str | os.PathLike[str] | None = None,
    transparent: bool = False,
    format: str | None = None,
    manim: str = "manim",
    extra_args: list[str] | tuple[str, ...] = (),
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run Manim after verifying the optional executable backend exists."""

    _require_manim(manim)
    return subprocess.run(
        build_render_command(
            scene_file,
            scene_name,
            quality=quality,
            media_dir=media_dir,
            output_file=output_file,
            transparent=transparent,
            format=format,
            manim=manim,
            extra_args=extra_args,
        ),
        check=check,
        text=True,
        capture_output=True,
    )


def scene_module_source(scene_name: str, construct_body: str, *, imports: list[str] | tuple[str, ...] = ()) -> str:
    """Return a Manim scene module template for caller-owned file writing."""

    import_block = "\n".join(imports) if imports else "from manim import Scene, Text, Write"
    return f"""{import_block}


class {scene_name}(Scene):
    def construct(self):
{_indent(construct_body, 8)}
"""


def _require_manim(manim: str) -> str:
    capabilities = check_capabilities(manim)
    if capabilities.manim_path:
        return capabilities.manim_path
    raise MissingBackendError(
        backend="manim",
        message=capabilities.error or "Manim is unavailable.",
        install_hint="Install with 'pip install vibeedit-media[manim]' and ensure the manim executable is on PATH, or pass manim explicitly.",
    )


def _bare_command(command: str) -> bool:
    return Path(command).name == command


def _indent(source: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in source.splitlines()) or f"{prefix}pass"
