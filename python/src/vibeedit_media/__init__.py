"""Standalone media helpers for VibeEdit."""

import importlib

from vibeedit_media.backend import MissingBackendError
from vibeedit_media.core import Canvas
from vibeedit_media.core import Project
from vibeedit_media.core import SectionRender
from vibeedit_media.core import TransitionRender
from vibeedit_media.effects import apply_effect
from vibeedit_media.preset_catalog import apply_preset_to_image
from vibeedit_media.preset_catalog import build_agent_plan
from vibeedit_media.preset_catalog import get_preset
from vibeedit_media.preset_catalog import list_presets
from vibeedit_media.preset_catalog import load_catalog
from vibeedit_media.preset_catalog import render_transition_frame
from vibeedit_media.effects import blur_image
from vibeedit_media.effects import canny_edges
from vibeedit_media.effects import grayscale_image
from vibeedit_media.effects import invert_image
from vibeedit_media.ffmpeg import FFmpegCapabilities
from vibeedit_media.ffmpeg import FFmpegError
from vibeedit_media.ffmpeg import MissingFFmpegError
from vibeedit_media.ffmpeg import check_capabilities
from vibeedit_media.ffmpeg import concat
from vibeedit_media.ffmpeg import normalize
from vibeedit_media.ffmpeg import probe
from vibeedit_media.ffmpeg import render
from vibeedit_media.freecut_effects import FREECUT_EFFECTS
from vibeedit_media.freecut_effects import FREECUT_PRESETS
from vibeedit_media.freecut_effects import apply_freecut_effect
from vibeedit_media.freecut_effects import apply_freecut_effect_to_frames
from vibeedit_media.freecut_effects import apply_freecut_preset
from vibeedit_media.freecut_effects import get_freecut_effect
from vibeedit_media.freecut_effects import list_freecut_effects
from vibeedit_media.freecut_effects import write_freecut_effect_video
from vibeedit_media.frames import FrameSpec
from vibeedit_media.frames import checkerboard_frame
from vibeedit_media.frames import frame_sequence
from vibeedit_media.frames import gradient_frame
from vibeedit_media.frames import solid_frame
from vibeedit_media.images import composite_images
from vibeedit_media.images import crop_image
from vibeedit_media.images import open_image
from vibeedit_media.images import render_text_image
from vibeedit_media.images import resize_image
from vibeedit_media.images import save_image
from vibeedit_media.images import to_numpy_image
from vibeedit_media.images import to_pil_image
from vibeedit_media.movie import clip_from_frames
from vibeedit_media.movie import write_video
from vibeedit_media.optional import MissingOptionalDependencyError
from vibeedit_media.project import HistoryRetention
from vibeedit_media.project import RESTORE_BEHAVIOR_ORDER
from vibeedit_media.project import RuntimeProbe
from vibeedit_media.project import VideoProject
from vibeedit_media.project import create_video_project
from vibeedit_media.project import open_video_project
from vibeedit_media.project import preflight_runtime
from vibeedit_media.project import probe_video_output

__all__ = [
    "Canvas",
    "FFmpegCapabilities",
    "FFmpegError",
    "FREECUT_EFFECTS",
    "FREECUT_PRESETS",
    "FrameSpec",
    "HistoryRetention",
    "MissingBackendError",
    "MissingFFmpegError",
    "MissingOptionalDependencyError",
    "Project",
    "RESTORE_BEHAVIOR_ORDER",
    "RuntimeProbe",
    "SectionRender",
    "TransitionRender",
    "VideoProject",
    "apply_effect",
    "apply_freecut_effect",
    "apply_freecut_effect_to_frames",
    "apply_freecut_preset",
    "apply_preset_to_image",
    "build_agent_plan",
    "get_preset",
    "get_freecut_effect",
    "list_presets",
    "list_freecut_effects",
    "load_catalog",
    "render_transition_frame",
    "blender",
    "blur_image",
    "canny_edges",
    "checkerboard_frame",
    "check_capabilities",
    "clip_from_frames",
    "composite_images",
    "concat",
    "create_video_project",
    "crop_image",
    "frame_sequence",
    "gradient_frame",
    "grayscale_image",
    "invert_image",
    "manim",
    "normalize",
    "open_video_project",
    "open_image",
    "preflight_runtime",
    "probe",
    "probe_video_output",
    "render_text_image",
    "resize_image",
    "render",
    "save_image",
    "solid_frame",
    "to_numpy_image",
    "to_pil_image",
    "write_video",
    "write_freecut_effect_video",
]


def __getattr__(name: str):
    if name in {"blender", "manim"}:
        return importlib.import_module(f"vibeedit_media.{name}")
    raise AttributeError(f"module 'vibeedit_media' has no attribute {name!r}")
