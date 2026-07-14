"""Internal video project and revision helpers for VibeEdit agents."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from vibeedit_media.core import Canvas
from vibeedit_media.core import Project
from vibeedit_media.ffmpeg import check_capabilities
from vibeedit_media.ffmpeg import probe


RESTORE_BEHAVIOR_ORDER = [
    "use_existing_saved_media_if_available",
    "regenerate_from_saved_python_if_media_was_pruned",
    "show_recoverable_error_if_runtime_or_assets_are_missing",
]


@dataclass(frozen=True)
class HistoryRetention:
    timeline_history_limit: int = 50
    python_code_history_limit: int = 50
    rendered_media_history_limit: int = 5

    def to_dict(self):
        return {
            "timelineHistoryLimit": self.timeline_history_limit,
            "pythonCodeHistoryLimit": self.python_code_history_limit,
            "renderedMediaHistoryLimit": self.rendered_media_history_limit,
        }


@dataclass(frozen=True)
class RuntimeProbe:
    ready: bool
    status: str
    checks: dict[str, Any]
    errors: list[str]

    def to_dict(self):
        return {"ready": self.ready, "status": self.status, "checks": self.checks, "errors": self.errors}


class VideoProject:
    """Small persisted project model used by product-level video tools."""

    def __init__(self, root: Path, *, canvas: Canvas, title: str, brief: str = "", retention: HistoryRetention | None = None):
        self.root = root
        self.title = title
        self.brief = brief
        self.retention = retention or HistoryRetention()
        self.project = Project(root, canvas)

    @property
    def canvas(self):
        return self.project.canvas

    @property
    def timeline(self):
        return self.project.timeline

    @classmethod
    def create(cls, root: str | Path, *, canvas: Canvas, title: str, brief: str = "", retention: HistoryRetention | None = None):
        video_project = cls(Path(root), canvas=canvas, title=title, brief=brief, retention=retention)
        video_project.root.mkdir(parents=True, exist_ok=True)
        for folder in ("sections", "transitions", "audio", "history/timeline", "history/python", "history/rendered"):
            (video_project.root / folder).mkdir(parents=True, exist_ok=True)
        video_project.write_project_manifest()
        video_project.save_timeline(label="created", reason="project_created")
        return video_project

    @classmethod
    def open(cls, root: str | Path):
        manifest = _read_json(Path(root) / "project.json")
        video_project = cls(
            Path(root),
            canvas=_canvas_from_dict(manifest["canvas"]),
            title=manifest.get("title", ""),
            brief=manifest.get("brief", ""),
            retention=HistoryRetention(
                timeline_history_limit=manifest.get("retention", {}).get("timelineHistoryLimit", 50),
                python_code_history_limit=manifest.get("retention", {}).get("pythonCodeHistoryLimit", 50),
                rendered_media_history_limit=manifest.get("retention", {}).get("renderedMediaHistoryLimit", 5),
            ),
        )
        timeline_path = video_project.root / "timeline.json"
        if timeline_path.exists():
            for item in _read_json(timeline_path).get("items", []):
                video_project.timeline.items.append(item)
        return video_project

    def write_project_manifest(self):
        return _write_json(
            self.root / "project.json",
            {
                "version": 1,
                "kind": "video_project",
                "title": self.title,
                "brief": self.brief,
                "canvas": _canvas(self.canvas),
                "retention": self.retention.to_dict(),
                "restoreBehavior": {"preferredOrder": RESTORE_BEHAVIOR_ORDER},
                "paths": {
                    "timeline": "timeline.json",
                    "sections": "sections",
                    "transitions": "transitions",
                    "audio": "audio",
                    "history": "history",
                },
            },
        )

    def add_section(self, *, id: str, start: float, duration: float, src: str | None = None, folder: str | None = None, brief: str = ""):
        section_folder = self.root / "sections" / (folder or id)
        section_folder.mkdir(parents=True, exist_ok=True)
        self.timeline.add_section_video(id=f"{id}-video", section_id=id, src=src or f"sections/{folder or id}/output.mp4", start=start, duration=duration)
        _write_json(section_folder / "metadata.json", {"id": id, "kind": "section", "duration": duration, "brief": brief, "status": "planned"})
        return self.save_timeline(label=f"add_section:{id}", reason="section_added")

    def add_transition(
        self,
        *,
        id: str,
        from_section: str,
        to_section: str,
        start: float,
        duration: float,
        src: str | None = None,
        folder: str | None = None,
        mode: str = "overlay",
    ):
        transition_folder = self.root / "transitions" / (folder or id)
        transition_folder.mkdir(parents=True, exist_ok=True)
        self.timeline.add_transition_overlay(
            id=f"{id}-overlay",
            transition_id=id,
            src=src or f"transitions/{folder or id}/output.webm",
            start=start,
            duration=duration,
        )
        _write_json(
            transition_folder / "metadata.json",
            {"id": id, "kind": "transition", "mode": mode, "fromSection": from_section, "toSection": to_section, "start": start, "duration": duration, "status": "planned"},
        )
        return self.save_timeline(label=f"add_transition:{id}", reason="transition_added")

    def add_audio_track(self, *, id: str, src: str, start: float, duration: float, role: str = "music", section_id: str | None = None, transition_id: str | None = None, volume_db: float | None = None):
        if role == "section_audio":
            self.timeline.add_section_audio(id=id, section_id=section_id or id, src=src, start=start, duration=duration, volume_db=0 if volume_db is None else volume_db)
            return self.save_timeline(label=f"add_audio:{id}", reason="audio_added")
        if role == "transition_sfx":
            self.timeline.add_transition_sfx(id=id, transition_id=transition_id or id, src=src, start=start, duration=duration, volume_db=-6 if volume_db is None else volume_db)
            return self.save_timeline(label=f"add_audio:{id}", reason="audio_added")
        self.timeline.add_music(id=id, src=src, start=start, duration=duration, volume_db=-12 if volume_db is None else volume_db)
        return self.save_timeline(label=f"add_audio:{id}", reason="audio_added")

    def save_timeline(self, *, label: str = "autosave", reason: str = "timeline_saved"):
        index_path = self.root / "history" / "timeline" / "index.json"
        index = _read_index(index_path)
        revision_id = _next_revision_id("timeline", index)
        manifest = {
            **self.timeline.to_dict(),
            "restoreBehavior": {"preferredOrder": RESTORE_BEHAVIOR_ORDER},
            "revision": {"id": revision_id, "label": label, "reason": reason, "createdAt": _now()},
        }
        _write_json(self.root / "timeline.json", manifest)
        _write_json(self.root / "history" / "timeline" / f"{revision_id}.json", manifest)
        _write_bounded_index(
            self.root,
            index_path,
            [*index, {"id": revision_id, "label": label, "reason": reason, "path": f"history/timeline/{revision_id}.json", "createdAt": manifest["revision"]["createdAt"]}],
            self.retention.timeline_history_limit,
        )
        return self.root / "history" / "timeline" / f"{revision_id}.json"

    def store_python_render_script(self, *, target_id: str, source: str, kind: str, label: str = "render"):
        folder = self.root / "history" / "python" / target_id
        index_path = folder / "index.json"
        index = _read_index(index_path)
        revision_id = _next_revision_id("script", index)
        path = folder / f"{revision_id}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        _write_bounded_index(
            self.root,
            index_path,
            [*index, {"id": revision_id, "targetId": target_id, "kind": kind, "label": label, "path": f"history/python/{target_id}/{revision_id}.py", "createdAt": _now()}],
            self.retention.python_code_history_limit,
        )
        return path

    def store_rendered_media(self, *, target_id: str, path: str | Path, kind: str, label: str = "render", metadata: dict[str, Any] | None = None):
        index_path = self.root / "history" / "rendered" / target_id / "index.json"
        index = _read_index(index_path)
        revision_id = _next_revision_id("media", index)
        media_path = Path(path)
        stored_path = self.root / "history" / "rendered" / target_id / f"{revision_id}{media_path.suffix or '.mp4'}"
        if media_path.exists():
            stored_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(media_path, stored_path)
        entry = {
            "id": revision_id,
            "targetId": target_id,
            "kind": kind,
            "label": label,
            "path": _project_path(self.root, stored_path if stored_path.exists() else media_path),
            "sourcePath": _project_path(self.root, media_path),
            "exists": stored_path.exists(),
            "metadata": metadata or {},
            "createdAt": _now(),
        }
        _write_bounded_index(self.root, index_path, [*index, entry], self.retention.rendered_media_history_limit)
        return entry

    def restore_plan(self, *, target_id: str):
        media_entries = list(reversed(_read_index(self.root / "history" / "rendered" / target_id / "index.json")))
        media = next((entry for entry in media_entries if (self.root / entry["path"]).exists()), None)
        if media:
            return {"action": "use_existing_media", "targetId": target_id, "media": media, "restoreBehavior": {"preferredOrder": RESTORE_BEHAVIOR_ORDER}}
        script_entries = list(reversed(_read_index(self.root / "history" / "python" / target_id / "index.json")))
        script = next((entry for entry in script_entries if (self.root / entry["path"]).exists()), None)
        if script:
            return {"action": "regenerate_from_python", "targetId": target_id, "script": script, "restoreBehavior": {"preferredOrder": RESTORE_BEHAVIOR_ORDER}}
        return {
            "action": "recoverable_error",
            "targetId": target_id,
            "error": "No saved media or Python render script is available for this target.",
            "restoreBehavior": {"preferredOrder": RESTORE_BEHAVIOR_ORDER},
        }


def create_video_project(root: str | Path, *, canvas: Canvas, title: str, brief: str = "", retention: HistoryRetention | None = None):
    return VideoProject.create(root, canvas=canvas, title=title, brief=brief, retention=retention)


def open_video_project(root: str | Path):
    return VideoProject.open(root)


def preflight_runtime(*, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe", require_numpy: bool = False, require_pillow: bool = False, require_cv2: bool = False):
    capabilities = check_capabilities(ffmpeg=ffmpeg, ffprobe=ffprobe)
    checks = {"ffmpeg": capabilities.__dict__}
    errors = [] if capabilities.available else [capabilities.error or "ffmpeg probe failed."]
    for name, required in {"numpy": require_numpy, "PIL": require_pillow, "cv2": require_cv2}.items():
        if required:
            checks[name] = _module_available(name)
            if not checks[name]["available"]:
                errors.append(checks[name]["error"])
    return RuntimeProbe(ready=not errors, status="ready" if not errors else "repairable", checks=checks, errors=errors)


def probe_video_output(path: str | Path, *, ffprobe: str = "ffprobe"):
    output = Path(path)
    if not output.exists():
        return {"ready": False, "path": str(output), "error": "Video output does not exist."}
    return {"ready": True, "path": str(output), "probe": probe(output, ffprobe=ffprobe)}


def _read_index(path: Path):
    if not path.exists():
        return []
    data = _read_json(path)
    return data.get("entries", [])


def _write_bounded_index(root: Path, path: Path, entries: list[dict[str, Any]], limit: int):
    bounded = entries[-max(1, limit) :]
    for entry in entries[: -max(1, limit)]:
        stale_path = entry.get("path")
        if stale_path and stale_path.startswith("history/"):
            (root / stale_path).unlink(missing_ok=True)
    return _write_json(path, {"version": 1, "entries": bounded})


def _next_revision_id(prefix: str, entries: list[dict[str, Any]]):
    return f"{prefix}-{max([_revision_number(prefix, entry.get('id', '')) for entry in entries], default=0) + 1:06d}"


def _revision_number(prefix: str, id: str):
    if not id.startswith(f"{prefix}-"):
        return 0
    if not id.removeprefix(f"{prefix}-").isdigit():
        return 0
    return int(id.removeprefix(f"{prefix}-"))


def _module_available(name: str):
    try:
        __import__(name)
        return {"available": True}
    except ImportError as error:
        return {"available": False, "error": f"Missing Python module: {name}: {error}"}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _canvas(canvas: Canvas):
    return {"width": canvas.width, "height": canvas.height, "fps": canvas.fps, "audioSampleRate": canvas.audio_sample_rate}


def _canvas_from_dict(data: dict[str, Any]):
    return Canvas(width=data["width"], height=data["height"], fps=data["fps"], audio_sample_rate=data.get("audioSampleRate", 48_000))


def _project_path(root: Path, path: Path):
    if path.is_absolute():
        return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    return str(path)


def _now():
    return datetime.now(timezone.utc).isoformat()
