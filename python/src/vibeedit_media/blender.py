"""Subprocess-backed Blender helpers.

The module never imports Blender. Callers can inspect command construction,
check executable availability, or run Blender only when explicitly requested.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vibeedit_media.backend import MissingBackendError


@dataclass(frozen=True)
class BlenderCapabilities:
    blender_path: str | None
    available: bool
    error: str | None = None


def check_capabilities(blender: str = "blender") -> BlenderCapabilities:
    """Return Blender executable availability without launching it."""

    blender_path = shutil.which(blender) if _bare_command(blender) else blender
    if blender_path:
        return BlenderCapabilities(blender_path=blender_path, available=True)
    return BlenderCapabilities(
        blender_path=None,
        available=False,
        error="Blender must be installed or supplied explicitly.",
    )


def build_render_command(
    *,
    script_file: str | os.PathLike[str] | None = None,
    blend_file: str | os.PathLike[str] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    frame: int | None = None,
    frame_start: int | None = None,
    frame_end: int | None = None,
    animation: bool = False,
    background: bool = True,
    blender: str = "blender",
    extra_args: list[str] | tuple[str, ...] = (),
    script_args: list[str] | tuple[str, ...] = (),
) -> list[str]:
    """Build a Blender CLI command.

    Example:
        blender --background project.blend -o renders/frame_#### -f 1 --python render.py
    """

    if frame is not None and animation:
        raise ValueError("frame and animation cannot both be set.")
    if frame is not None and (frame_start is not None or frame_end is not None):
        raise ValueError("frame cannot be combined with frame_start or frame_end.")
    if frame_start is not None and frame_end is None:
        raise ValueError("frame_end is required when frame_start is set.")
    if frame_end is not None and frame_start is None:
        raise ValueError("frame_start is required when frame_end is set.")

    command = [blender]
    if background:
        command.append("--background")
    if blend_file is not None:
        command.append(str(blend_file))
    if output_path is not None:
        command.extend(["-o", str(output_path)])
    if frame_start is not None and frame_end is not None:
        command.extend(["-s", str(frame_start), "-e", str(frame_end)])
    if animation:
        command.append("-a")
    if frame is not None:
        command.extend(["-f", str(frame)])
    if script_file is not None:
        command.extend(["--python", str(script_file)])
    command.extend(extra_args)
    if script_args:
        command.append("--")
        command.extend(script_args)
    return command


def render(
    *,
    script_file: str | os.PathLike[str] | None = None,
    blend_file: str | os.PathLike[str] | None = None,
    output_path: str | os.PathLike[str] | None = None,
    frame: int | None = None,
    frame_start: int | None = None,
    frame_end: int | None = None,
    animation: bool = False,
    background: bool = True,
    blender: str = "blender",
    extra_args: list[str] | tuple[str, ...] = (),
    script_args: list[str] | tuple[str, ...] = (),
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run Blender after verifying the optional executable backend exists."""

    _require_blender(blender)
    return subprocess.run(
        build_render_command(
            script_file=script_file,
            blend_file=blend_file,
            output_path=output_path,
            frame=frame,
            frame_start=frame_start,
            frame_end=frame_end,
            animation=animation,
            background=background,
            blender=blender,
            extra_args=extra_args,
            script_args=script_args,
        ),
        check=check,
        text=True,
        capture_output=True,
    )


def script_source(body: str, *, imports: list[str] | tuple[str, ...] = ()) -> str:
    """Return a Blender Python script template for caller-owned file writing."""

    import_block = "\n".join(imports) if imports else "import bpy"
    return f"""{import_block}


def main():
{_indent(body, 4)}


if __name__ == "__main__":
    main()
"""


def _require_blender(blender: str) -> str:
    capabilities = check_capabilities(blender)
    if capabilities.blender_path:
        return capabilities.blender_path
    raise MissingBackendError(
        backend="blender",
        message=capabilities.error or "Blender is unavailable.",
        install_hint="Install Blender and ensure the blender executable is on PATH, or pass blender explicitly.",
    )


def _bare_command(command: str) -> bool:
    return Path(command).name == command


def _indent(source: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in source.splitlines()) or f"{prefix}pass"
