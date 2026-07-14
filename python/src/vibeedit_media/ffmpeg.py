"""Subprocess-backed FFmpeg helpers.

The module deliberately avoids importing ffmpeg-python. Callers can pass custom
binary paths for bundled or sandboxed FFmpeg builds.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class FFmpegError(RuntimeError):
    """Raised when an FFmpeg command fails."""

    def __init__(self, message: str, command: list[str] | None = None, stderr: str | None = None):
        super().__init__(message)
        self.command = command
        self.stderr = stderr


class MissingFFmpegError(FFmpegError):
    """Raised when ffmpeg or ffprobe is unavailable."""


@dataclass(frozen=True)
class FFmpegCapabilities:
    ffmpeg_path: str | None
    ffprobe_path: str | None
    ffmpeg_version: str | None
    ffprobe_version: str | None
    available: bool
    error: str | None = None


def check_capabilities(ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> FFmpegCapabilities:
    """Return FFmpeg availability without raising for missing tools."""

    ffmpeg_path = _resolve_tool(ffmpeg, "ffmpeg")
    ffprobe_path = _resolve_tool(ffprobe, "ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        return FFmpegCapabilities(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            ffmpeg_version=None,
            ffprobe_version=None,
            available=False,
            error="ffmpeg and ffprobe must both be installed or supplied explicitly.",
        )

    try:
        return FFmpegCapabilities(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            ffmpeg_version=_version(ffmpeg_path),
            ffprobe_version=_version(ffprobe_path),
            available=True,
        )
    except (FFmpegError, OSError) as error:
        return FFmpegCapabilities(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            ffmpeg_version=None,
            ffprobe_version=None,
            available=False,
            error=str(error),
        )


def probe(input_path: str | os.PathLike[str], ffprobe: str = "ffprobe") -> dict[str, Any]:
    """Run ffprobe and return the parsed JSON stream/format metadata."""

    ffprobe_path = _require_tool(ffprobe, "ffprobe")
    result = _run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        ]
    )
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise FFmpegError("ffprobe returned invalid JSON.", result.args, result.stderr) from error
    if isinstance(data, dict):
        return data
    raise FFmpegError("ffprobe returned an unexpected JSON payload.", result.args, result.stderr)


def normalize(
    input_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    *,
    ffmpeg: str = "ffmpeg",
    width: int | None = None,
    height: int | None = None,
    fps: int | None = 30,
    audio_rate: int = 48_000,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    crf: int = 18,
    preset: str = "veryfast",
    pix_fmt: str = "yuv420p",
    overwrite: bool = True,
    extra_args: list[str] | tuple[str, ...] = (),
) -> Path:
    """Normalize media into an editor-friendly MP4-style output."""

    filters = []
    if width or height:
        filters.append(f"scale={width or -2}:{height or -2}")
    if fps:
        filters.append(f"fps={fps}")

    return render(
        input_path,
        output_path,
        ffmpeg=ffmpeg,
        video_filters=filters,
        video_codec=video_codec,
        audio_codec=audio_codec,
        audio_rate=audio_rate,
        crf=crf,
        preset=preset,
        pix_fmt=pix_fmt,
        overwrite=overwrite,
        extra_output_args=["-movflags", "+faststart", *extra_args],
    )


def render(
    input_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    *,
    ffmpeg: str = "ffmpeg",
    start: float | None = None,
    duration: float | None = None,
    video_filters: list[str] | tuple[str, ...] = (),
    audio_filters: list[str] | tuple[str, ...] = (),
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    audio_rate: int | None = None,
    crf: int | None = 18,
    preset: str | None = "veryfast",
    pix_fmt: str | None = "yuv420p",
    overwrite: bool = True,
    extra_input_args: list[str] | tuple[str, ...] = (),
    extra_output_args: list[str] | tuple[str, ...] = (),
) -> Path:
    """Render one input with optional trims and filters."""

    ffmpeg_path = _require_tool(ffmpeg, "ffmpeg")
    output = Path(output_path)
    command = [ffmpeg_path, "-hide_banner", "-y" if overwrite else "-n"]
    if start is not None:
        command.extend(["-ss", _seconds(start)])
    command.extend([*extra_input_args, "-i", str(input_path)])
    if duration is not None:
        command.extend(["-t", _seconds(duration)])
    if video_filters:
        command.extend(["-vf", ",".join(video_filters)])
    if audio_filters:
        command.extend(["-af", ",".join(audio_filters)])
    command.extend(["-c:v", video_codec, "-c:a", audio_codec])
    if audio_rate is not None:
        command.extend(["-ar", str(audio_rate)])
    if crf is not None:
        command.extend(["-crf", str(crf)])
    if preset is not None:
        command.extend(["-preset", preset])
    if pix_fmt is not None:
        command.extend(["-pix_fmt", pix_fmt])
    command.extend([*extra_output_args, str(output)])
    _run(command)
    return output


def concat(
    input_paths: list[str | os.PathLike[str]] | tuple[str | os.PathLike[str], ...],
    output_path: str | os.PathLike[str],
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    transition: str | None = None,
    transition_duration: float = 0.5,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    overwrite: bool = True,
    extra_args: list[str] | tuple[str, ...] = (),
) -> Path:
    """Concatenate clips, optionally using a simple xfade/acrossfade transition.

    Transition mode is practical for two clips. More complex timelines should
    build an explicit filter graph in a higher-level planner and call `render`.
    """

    if len(input_paths) < 2:
        raise ValueError("concat requires at least two input paths.")
    if transition:
        if len(input_paths) != 2:
            raise ValueError("transition concat currently supports exactly two input paths.")
        return _concat_with_transition(
            input_paths,
            output_path,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            transition=transition,
            transition_duration=transition_duration,
            video_codec=video_codec,
            audio_codec=audio_codec,
            overwrite=overwrite,
            extra_args=extra_args,
        )
    return _concat_demuxer(input_paths, output_path, ffmpeg=ffmpeg, overwrite=overwrite, extra_args=extra_args)


def _concat_demuxer(
    input_paths: list[str | os.PathLike[str]] | tuple[str | os.PathLike[str], ...],
    output_path: str | os.PathLike[str],
    *,
    ffmpeg: str,
    overwrite: bool,
    extra_args: list[str] | tuple[str, ...],
) -> Path:
    ffmpeg_path = _require_tool(ffmpeg, "ffmpeg")
    output = Path(output_path)
    with tempfile.NamedTemporaryFile("w", suffix=".ffconcat", encoding="utf-8", delete=False) as list_file:
        list_path = Path(list_file.name)
        for input_path in input_paths:
            list_file.write(f"file {_quote_concat_path(input_path)}\n")
    try:
        _run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-y" if overwrite else "-n",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                *extra_args,
                str(output),
            ]
        )
    finally:
        list_path.unlink(missing_ok=True)
    return output


def _concat_with_transition(
    input_paths: list[str | os.PathLike[str]] | tuple[str | os.PathLike[str], ...],
    output_path: str | os.PathLike[str],
    *,
    ffmpeg: str,
    ffprobe: str,
    transition: str,
    transition_duration: float,
    video_codec: str,
    audio_codec: str,
    overwrite: bool,
    extra_args: list[str] | tuple[str, ...],
) -> Path:
    ffmpeg_path = _require_tool(ffmpeg, "ffmpeg")
    output = Path(output_path)
    first_duration = _duration(input_paths[0], ffprobe=ffprobe)
    offset = max(0, first_duration - transition_duration)
    filter_complex = (
        f"[0:v][1:v]xfade=transition={transition}:duration={transition_duration}:offset={offset}[v];"
        f"[0:a][1:a]acrossfade=d={transition_duration}[a]"
    )
    _run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-y" if overwrite else "-n",
            "-i",
            str(input_paths[0]),
            "-i",
            str(input_paths[1]),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            video_codec,
            "-c:a",
            audio_codec,
            *extra_args,
            str(output),
        ]
    )
    return output


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise FFmpegError(f"Could not run command: {_format_command(command)}", command, str(error)) from error
    if result.returncode == 0:
        return result
    raise FFmpegError(
        f"Command failed with exit code {result.returncode}: {_format_command(command)}",
        command,
        result.stderr,
    )


def _require_tool(command: str, label: str) -> str:
    path = _resolve_tool(command, label)
    if path:
        return path
    raise MissingFFmpegError(f"{label} was not found. Install FFmpeg or pass a {label} binary path.")


def _resolve_tool(command: str, label: str) -> str | None:
    actual = os.environ.get("VIBEEDIT_MEDIA_FFMPEG" if label == "ffmpeg" and command == "ffmpeg" else "VIBEEDIT_MEDIA_FFPROBE" if label == "ffprobe" and command == "ffprobe" else "") or command
    if _bare_command(actual):
        return shutil.which(actual)
    return actual if Path(actual).exists() else None


def _version(command: str) -> str:
    return (_run([command, "-version"]).stdout.splitlines() or [""])[0]


def _duration(input_path: str | os.PathLike[str], *, ffprobe: str) -> float:
    data = probe(input_path, ffprobe=ffprobe)
    try:
        return float(data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        return 0


def _bare_command(command: str) -> bool:
    return not any(separator and separator in command for separator in (os.sep, os.altsep))


def _quote_concat_path(input_path: str | os.PathLike[str]) -> str:
    return "'" + str(input_path).replace("'", "'\\''") + "'"


def _seconds(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)
