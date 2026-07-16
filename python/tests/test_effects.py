import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vibeedit import random_frame_stutter_mapping, register_transition_filter, register_video_effect_filter, render, verify_output
from vibeedit.data import data_path


def test_random_frame_stutter_schedule_is_seeded_and_duration_preserving():
    first = random_frame_stutter_mapping(seed=7, window_frames=8, intensity=0.75)
    assert first == random_frame_stutter_mapping(seed=7, window_frames=8, intensity=0.75)
    assert first != random_frame_stutter_mapping(seed=8, window_frames=8, intensity=0.75)
    assert len(first) == 8
    assert all(0 <= source < 8 for source in first)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_effect_transition_example_renders(tmp_path: Path):
    ffmpeg = shutil.which("ffmpeg")
    sources = tmp_path / "sources"
    sources.mkdir()
    for output, source in (("a.mp4", "testsrc2=size=320x180:rate=30:duration=2"), ("b.mp4", "smptebars=size=320x180:rate=30:duration=2")):
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(sources / output)], check=True)
    spec = json.loads(data_path("examples", "effect-transition", "composition.json").read_text())
    spec["sources"][0]["uri"] = str(sources / "a.mp4")
    spec["sources"][1]["uri"] = str(sources / "b.mp4")
    register_video_effect_filter("vibeedit://effect/agent-contrast", lambda params: f"eq=contrast={float(params.get('contrast', 1.08)):.3f}")
    register_transition_filter(
        "vibeedit://transition/agent-wipe-left",
        lambda *, params, duration_frames, offset_frames, numerator, denominator: f"xfade=transition=wipeleft:duration={duration_frames * denominator / numerator:.9f}:offset={offset_frames * denominator / numerator:.9f}",
    )
    spec["timeline"]["tracks"][0]["items"][0]["effects"][0].update({"effectId": "vibeedit://effect/agent-contrast", "params": {"contrast": 1.12}})
    spec["timeline"]["tracks"][0]["items"][2]["transitionId"] = "vibeedit://transition/agent-wipe-left"
    output = render(spec, tmp_path / "effect-transition.mp4")
    report = verify_output(output, spec["verification"])
    assert report.passed, report.errors
