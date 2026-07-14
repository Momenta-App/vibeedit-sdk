"""Small project and render contracts for standalone media work."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Canvas:
    width: int
    height: int
    fps: int
    audio_sample_rate: int = 48_000


class Project:
    def __init__(self, root: Path, canvas: Canvas):
        self.root = root
        self.canvas = canvas
        self.timeline = Timeline(canvas)

    @classmethod
    def create(cls, root: str | Path, *, canvas: Canvas):
        project = cls(Path(root), canvas)
        project.root.mkdir(parents=True, exist_ok=True)
        return project

    def write_timeline(self, output: str | Path) -> Path:
        path = self.root / output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.timeline.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path


class Timeline:
    def __init__(self, canvas: Canvas):
        self.canvas = canvas
        self.items: list[dict[str, Any]] = []

    def add_section_video(self, *, id: str, section_id: str, src: str, start: float, duration: float):
        self.items.append(
            {"id": id, "type": "section_video", "track": "V1", "sectionId": section_id, "src": src, "start": start, "duration": duration}
        )

    def add_section_audio(self, *, id: str, section_id: str, src: str, start: float, duration: float, volume_db: float = 0):
        self.items.append(
            {
                "id": id,
                "type": "section_audio",
                "track": "A1",
                "sectionId": section_id,
                "src": src,
                "start": start,
                "duration": duration,
                "volumeDb": volume_db,
            }
        )

    def add_music(self, *, id: str, src: str, start: float, duration: float, volume_db: float = -12):
        self.items.append({"id": id, "type": "music", "track": "A1", "src": src, "start": start, "duration": duration, "volumeDb": volume_db})

    def add_transition_overlay(self, *, id: str, transition_id: str, src: str, start: float, duration: float):
        self.items.append(
            {
                "id": id,
                "type": "transition_overlay",
                "track": "V1",
                "transitionId": transition_id,
                "src": src,
                "start": start,
                "duration": duration,
            }
        )

    def add_transition_sfx(self, *, id: str, transition_id: str, src: str, start: float, duration: float, volume_db: float = -6):
        self.items.append(
            {
                "id": id,
                "type": "transition_sfx",
                "track": "A1",
                "transitionId": transition_id,
                "src": src,
                "start": start,
                "duration": duration,
                "volumeDb": volume_db,
            }
        )

    def to_dict(self):
        return {"version": 1, "canvas": _canvas(self.canvas), "tracks": _tracks(), "items": self.items}


@dataclass(frozen=True)
class SectionRender:
    id: str
    folder: Path
    duration: float
    brief: str = ""

    def write_generated_clip(self, *, backend, output: str, background: str = "#101217", title: str | None = None, subtitle: str | None = None, canvas: Canvas | None = None):
        actual_canvas = canvas or Canvas(width=1920, height=1080, fps=30)
        self.folder.mkdir(parents=True, exist_ok=True)
        return backend.write_color_clip(
            self.folder / output,
            duration=self.duration,
            width=actual_canvas.width,
            height=actual_canvas.height,
            fps=actual_canvas.fps,
            audio_sample_rate=actual_canvas.audio_sample_rate,
            background=background,
            title=title,
            subtitle=subtitle,
        )

    def write_metadata(
        self,
        *,
        output: str = "metadata.json",
        canvas: Canvas | None = None,
        video: str = "output.mp4",
        audio: str | None = "output.mp4",
        normalized: dict[str, Any] | None = None,
        notes: list[str] | None = None,
        warnings: list[str] | None = None,
    ):
        actual_canvas = canvas or Canvas(width=1920, height=1080, fps=30)
        return _write_json(
            self.folder / output,
            {
                "id": self.id,
                "kind": "section",
                "duration": self.duration,
                "brief": self.brief,
                "canvas": _canvas(actual_canvas),
                "video": _manifest_path(self.folder / video),
                "audio": _manifest_path(self.folder / audio) if audio else None,
                "normalized": normalized or _normalized_defaults(actual_canvas),
                "notes": notes or [],
                "warnings": warnings or [],
            },
        )

    def write_image_clip(self, *, backend, image: str | Path, output: str, canvas: Canvas | None = None):
        actual_canvas = canvas or Canvas(width=1920, height=1080, fps=30)
        self.folder.mkdir(parents=True, exist_ok=True)
        return backend.write_image_clip(
            image,
            self.folder / output,
            duration=self.duration,
            fps=actual_canvas.fps,
            audio_sample_rate=actual_canvas.audio_sample_rate,
        )


@dataclass(frozen=True)
class TransitionRender:
    id: str
    folder: Path
    mode: str
    from_section: str
    to_section: str
    start: float
    duration: float
    handles: dict[str, float]

    def write_overlay(self, *, backend, output: str, style: str = "flash-wipe", color: str = "#f4d35e", canvas: Canvas | None = None):
        actual_canvas = canvas or Canvas(width=1920, height=1080, fps=30)
        self.folder.mkdir(parents=True, exist_ok=True)
        return backend.write_overlay_clip(
            self.folder / output,
            duration=self.duration,
            width=actual_canvas.width,
            height=actual_canvas.height,
            fps=actual_canvas.fps,
            color=color,
        )

    def write_sfx(self, *, backend, output: str, style: str = "soft-whoosh", audio_sample_rate: int = 48_000):
        self.folder.mkdir(parents=True, exist_ok=True)
        return backend.write_silence(self.folder / output, duration=self.duration, audio_sample_rate=audio_sample_rate)

    def write_metadata(
        self,
        *,
        output: str = "metadata.json",
        video: str = "output.webm",
        audio: str | None = "sfx.wav",
        alpha: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ):
        return _write_json(
            self.folder / output,
            {
                "id": self.id,
                "kind": "transition",
                "mode": self.mode,
                "fromSection": self.from_section,
                "toSection": self.to_section,
                "start": self.start,
                "duration": self.duration,
                "handles": self.handles,
                "video": _manifest_path(self.folder / video),
                "audio": _manifest_path(self.folder / audio) if audio else None,
                "alpha": alpha or {"format": "webm", "codec": "vp9"},
                "warnings": warnings or [],
            },
        )


def _tracks():
    return [
        {"id": "V1", "kind": "video", "role": "video", "renderOrder": 1},
        {"id": "A1", "kind": "audio", "role": "audio"},
    ]


def _canvas(canvas: Canvas) -> dict[str, int]:
    return {"width": canvas.width, "height": canvas.height, "fps": canvas.fps, "audioSampleRate": canvas.audio_sample_rate}


def _normalized_defaults(canvas: Canvas) -> dict[str, Any]:
    return {"videoCodec": "h264", "audioCodec": "aac", "pixelFormat": "yuv420p", "audioSampleRate": canvas.audio_sample_rate}


def _manifest_path(path: str | Path) -> str:
    actual = Path(path)
    for anchor in ("sections", "transitions"):
        if anchor in actual.parts:
            return str(Path(*actual.parts[actual.parts.index(anchor) :]))
    return actual.name


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path
