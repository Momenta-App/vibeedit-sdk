import hashlib
import json
import shutil
from pathlib import Path

import pytest

from vibeedit import plan_revision, render
from vibeedit.data import data_path


def _bounded_text_spec() -> dict:
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text())
    spec["id"] = "bounded-text-revision"
    spec["canvas"].update({"width": 320, "height": 180})
    spec["durationFrames"] = 30
    spec["timeline"]["tracks"] = [
        {
            "id": "M1",
            "kind": "motion",
            "order": 10,
            "items": [
                {
                    "id": "bounded-title",
                    "kind": "motion",
                    "placement": {"startFrame": 10, "durationFrames": 10},
                    "componentId": "vibeedit://text/negative",
                    "props": {"text": "FIRST CUT", "foreground": "#FFFFFF", "background": "#101217"},
                    "transparent": False,
                    "renderer": "html",
                }
            ],
        }
    ]
    spec["verification"].update({"durationFrames": 30, "width": 320, "height": 180, "hasAudio": False})
    return spec


def test_revision_plan_invalidates_only_bounded_text_range():
    previous = _bounded_text_spec()
    revised = json.loads(json.dumps(previous))
    revised["timeline"]["tracks"][0]["items"][0]["props"]["text"] = "REVISED CUT"

    plan = plan_revision(previous, revised)

    assert plan["incrementalEligible"] is True
    assert plan["changedFields"] == ["/timeline/tracks/0/items/0/props/text"]
    assert plan["dirtyFrameRanges"] == [{"startFrame": 10, "endFrame": 20}]
    assert plan["expectedReuse"] == {"totalFrames": 30, "dirtyFrames": 10, "reusedFrames": 20, "ratio": 0.666667}
    assert plan["requiredRerenderJobs"][0]["kind"] == "motion-layer"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_bounded_text_revision_reuses_clean_frames_and_matches_full_render(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("playwright")
    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "cache"))
    previous = _bounded_text_spec()
    previous["cache"] = {"enabled": True, "namespace": "revision-test"}
    revised = json.loads(json.dumps(previous))
    revised["timeline"]["tracks"][0]["items"][0]["props"]["text"] = "REVISED CUT"

    render(previous, tmp_path / "previous.mp4")
    incremental = render(revised, tmp_path / "incremental.mp4")
    incremental_record = json.loads(incremental.with_suffix(".mp4.vibeedit.json").read_text())
    revised["cache"]["enabled"] = False
    reference = render(revised, tmp_path / "reference.mp4")

    assert incremental_record["work"] == {"framesRendered": 10, "framesReused": 20, "reuseKind": "content-addressed-composite-frames"}
    assert hashlib.sha256(incremental.read_bytes()).hexdigest() == hashlib.sha256(reference.read_bytes()).hexdigest()
