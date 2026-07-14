"""Backend adapters for vibeedit_media."""

from __future__ import annotations

import os
from pathlib import Path

from vibeedit_media.ffmpeg import FFmpegCapabilities
from vibeedit_media.ffmpeg import check_capabilities
from vibeedit_media.ffmpeg import concat
from vibeedit_media.ffmpeg import normalize
from vibeedit_media.ffmpeg import probe
from vibeedit_media.ffmpeg import render
from vibeedit_media.ffmpeg import _require_tool
from vibeedit_media.ffmpeg import _run


class FFmpegBackend:
    """Small subprocess-backed FFmpeg backend.

    This class is intentionally thin: it centralizes binary selection and keeps
    higher-level render objects independent from subprocess command details.
    """

    def __init__(self, ffmpeg: str | None = None, ffprobe: str | None = None):
        self.ffmpeg = ffmpeg or os.environ.get("VIBEEDIT_MEDIA_FFMPEG", "ffmpeg")
        self.ffprobe = ffprobe or os.environ.get("VIBEEDIT_MEDIA_FFPROBE", "ffprobe")

    def capabilities(self) -> FFmpegCapabilities:
        return check_capabilities(ffmpeg=self.ffmpeg, ffprobe=self.ffprobe)

    def probe(self, input_path: str | os.PathLike[str]):
        return probe(input_path, ffprobe=self.ffprobe)

    def normalize(self, input_path: str | os.PathLike[str], output_path: str | os.PathLike[str], **kwargs):
        return normalize(input_path, output_path, ffmpeg=self.ffmpeg, **kwargs)

    def render(self, input_path: str | os.PathLike[str], output_path: str | os.PathLike[str], **kwargs):
        return render(input_path, output_path, ffmpeg=self.ffmpeg, **kwargs)

    def concat(self, input_paths, output_path: str | os.PathLike[str], **kwargs):
        return concat(input_paths, output_path, ffmpeg=self.ffmpeg, ffprobe=self.ffprobe, **kwargs)

    def write_color_clip(
        self,
        output_path: str | os.PathLike[str],
        *,
        duration: float,
        width: int,
        height: int,
        fps: int,
        audio_sample_rate: int,
        background: str = "#101217",
        title: str | None = None,
        subtitle: str | None = None,
    ) -> Path:
        ffmpeg_path = _require_tool(self.ffmpeg, "ffmpeg")
        output = Path(output_path)
        filters = [_drawtext(title, y="(h-text_h)/2-48", size=64), _drawtext(subtitle, y="(h-text_h)/2+42", size=32)]
        command = [
            ffmpeg_path,
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={background}:s={width}x{height}:r={fps}:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate={audio_sample_rate}",
            "-t",
            str(duration),
        ]
        if any(filters):
            command.extend(["-vf", ",".join(filter(None, filters))])
        command.extend(["-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)])
        _run(command)
        return output

    def write_image_clip(
        self,
        image_path: str | os.PathLike[str],
        output_path: str | os.PathLike[str],
        *,
        duration: float,
        fps: int,
        audio_sample_rate: int,
    ) -> Path:
        ffmpeg_path = _require_tool(self.ffmpeg, "ffmpeg")
        output = Path(output_path)
        _run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-y",
                "-loop",
                "1",
                "-framerate",
                str(fps),
                "-i",
                str(image_path),
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate={audio_sample_rate}",
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
        return output

    def write_overlay_clip(
        self,
        output_path: str | os.PathLike[str],
        *,
        duration: float,
        width: int,
        height: int,
        fps: int,
        color: str = "#f4d35e",
    ) -> Path:
        ffmpeg_path = _require_tool(self.ffmpeg, "ffmpeg")
        output = Path(output_path)
        fade_out_start = max(0, duration - 0.12)
        _run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s={width}x{height}:r={fps}:d={duration}",
                "-vf",
                f"format=yuva420p,fade=t=in:st=0:d=0.12:alpha=1,fade=t=out:st={fade_out_start}:d=0.12:alpha=1",
                "-c:v",
                "libvpx-vp9",
                "-an",
                str(output),
            ]
        )
        return output

    def write_silence(self, output_path: str | os.PathLike[str], *, duration: float, audio_sample_rate: int) -> Path:
        ffmpeg_path = _require_tool(self.ffmpeg, "ffmpeg")
        output = Path(output_path)
        _run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate={audio_sample_rate}",
                "-t",
                str(duration),
                "-c:a",
                "pcm_s16le" if output.suffix.lower() == ".wav" else "aac",
                str(output),
            ]
        )
        return output


def _drawtext(text: str | None, *, y: str, size: int) -> str | None:
    if not text:
        return None
    return (
        "drawtext="
        f"text='{_escape_drawtext(text)}':"
        "fontcolor=white:"
        f"fontsize={size}:"
        "x=(w-text_w)/2:"
        f"y={y}"
    )


def _escape_drawtext(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
