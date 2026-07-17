import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vibeedit import plan_revision, render, render_revision
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
    assert plan["executionStatus"] == "verified-frame-cache"


def test_text_color_revision_reuses_sources_tracking_audio_and_unrelated_layers():
    previous = json.loads(data_path("examples", "face-follow-text", "composition.json").read_text())
    revised = json.loads(json.dumps(previous))
    revised["timeline"]["tracks"][1]["items"][0]["props"]["foreground"] = "#FFCC00"

    plan = plan_revision(previous, revised)
    reusable = {(item["kind"], item["id"]) for item in plan["reusableArtifacts"]}

    assert plan["revisionKind"] == "motion"
    assert plan["dirtyFrameRanges"] == [{"startFrame": 0, "endFrame": 60}]
    assert {("source-decoding", "subject"), ("tracking", "face-track"), ("audio-mix", "final"), ("layer", "subject"), ("layer", "lock")} <= reusable


def test_transition_revision_invalidates_only_overlap_and_handles():
    previous = json.loads(data_path("examples", "effect-transition", "composition.json").read_text())
    revised = json.loads(json.dumps(previous))
    revised["timeline"]["tracks"][0]["items"][2]["transitionId"] = "vibeedit://transition/transitions-core-film-burn"

    plan = plan_revision(previous, revised)

    assert plan["revisionKind"] == "transition"
    assert plan["dirtyFrameRanges"] == [{"startFrame": 48, "endFrame": 60}]
    assert plan["requiredRerenderJobs"] == [{"kind": "transition", "layerIds": ["crossfade"], "frameRange": {"startFrame": 48, "endFrame": 60}, "sourceHandles": ["clip-a", "clip-b"], "reason": "transition implementation or parameters changed only within its overlap"}]
    assert plan["executionStatus"] == "planned-not-yet-executed"


def test_scene_removal_reuses_prefix_and_source_artifacts():
    previous = json.loads(data_path("examples", "effect-transition", "composition.json").read_text())
    revised = json.loads(json.dumps(previous))
    revised["durationFrames"] = 60
    revised["timeline"]["tracks"][0]["items"] = [revised["timeline"]["tracks"][0]["items"][0]]
    revised["timeline"]["tracks"][1]["items"] = []
    revised["verification"]["durationFrames"] = 60
    revised["verification"]["hasAudio"] = False

    plan = plan_revision(previous, revised)

    assert plan["revisionKind"] == "scene-removal"
    assert plan["dirtyFrameRanges"] == [{"startFrame": 48, "endFrame": 60}]
    assert plan["stitchPlan"]["strategy"] == "reuse-prefix-and-rebuild-timeline-tail"
    assert set(plan["decodeWorkAvoided"]) == {"source-a", "source-b"}


def test_audio_gain_revision_reuses_every_video_frame():
    previous = json.loads(data_path("examples", "effect-transition", "composition.json").read_text())
    revised = json.loads(json.dumps(previous))
    revised["timeline"]["tracks"][1]["items"][0]["gainDb"] = -6

    plan = plan_revision(previous, revised)

    assert plan["revisionKind"] == "audio"
    assert plan["dirtyFrameRanges"] == []
    assert plan["dirtyAudioRanges"] == [{"startFrame": 48, "endFrame": 60}]
    assert plan["expectedReuse"]["reusedFrames"] == 108
    assert [job["kind"] for job in plan["requiredRerenderJobs"]] == ["audio-mix", "remux"]
    assert plan["executionStatus"] == "verified-audio-remix"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_audio_gain_revision_stream_copies_video_and_matches_clean_audio(tmp_path: Path):
    previous = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    previous["cache"] = {"enabled": False}
    previous["timeline"]["tracks"] = [{"id": "A1", "kind": "audio", "order": 0, "items": [{"id": "impact", "kind": "sound_effect", "placement": {"startFrame": 5, "durationFrames": 10}, "soundEffectId": "vibeedit://sfx/impact-procedural", "params": {"frequency": 72}, "gainDb": -12, "variationSeed": 1, "avoidImmediateRepeat": True}]}]
    previous["verification"]["hasAudio"] = True
    previous_output = render(previous, tmp_path / "previous-audio.mp4")
    revised = json.loads(json.dumps(previous))
    revised["timeline"]["tracks"][0]["items"][0]["gainDb"] = -6

    incremental = render_revision(previous, revised, previous_output, tmp_path / "incremental-audio.mp4")
    reference = render(revised, tmp_path / "reference-audio.mp4")
    record = json.loads(incremental.with_suffix(".mp4.vibeedit.json").read_text())

    def stream_md5(path: Path, stream: str) -> str:
        result = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", stream, "-f", "framemd5", "-"], capture_output=True, text=True, check=True)
        return "\n".join(line for line in result.stdout.splitlines() if not line.startswith("#"))

    assert stream_md5(incremental, "0:v:0") == stream_md5(reference, "0:v:0")
    assert stream_md5(incremental, "0:a:0") == stream_md5(reference, "0:a:0")
    assert record["work"]["framesRendered"] == 0
    assert record["work"]["framesReused"] == previous["durationFrames"]
    assert record["work"]["audioRangesRemixed"] == [{"startFrame": 5, "endFrame": 15}]


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_external_audio_gain_revision_matches_clean_render(tmp_path: Path):
    video = tmp_path / "video.mp4"
    audio = tmp_path / "music.wav"
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=2", str(audio)], check=True)
    previous = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    previous["cache"] = {"enabled": False}
    previous["canvas"].update({"width": 160, "height": 90})
    previous["durationFrames"] = 60
    previous["sources"] = [{"id": "video", "kind": "video", "uri": str(video), "identity": {"algorithm": "generated", "value": "video"}, "durationFrames": 60}, {"id": "music", "kind": "audio", "uri": str(audio), "identity": {"algorithm": "generated", "value": "music"}, "durationFrames": 60}]
    previous["timeline"]["tracks"] = [{"id": "V1", "kind": "video", "order": 0, "items": [{"id": "video", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 60}, "source": {"sourceId": "video", "inFrame": 0, "durationFrames": 60}, "effects": []}]}, {"id": "A1", "kind": "audio", "order": 0, "items": [{"id": "music", "kind": "audio", "placement": {"startFrame": 6, "durationFrames": 48}, "source": {"sourceId": "music", "inFrame": 3, "durationFrames": 48}, "role": "music", "gainDb": -12, "pan": 0.25, "fadeInFrames": 4, "fadeOutFrames": 4, "effects": []}]}]
    previous["verification"] = {"durationFrames": 60, "width": 160, "height": 90, "frameRate": {"numerator": 30, "denominator": 1}, "hasVideo": True, "hasAudio": True, "maxDurationDriftFrames": 1}
    previous_output = render(previous, tmp_path / "previous-external.mp4")
    revised = json.loads(json.dumps(previous))
    revised["timeline"]["tracks"][1]["items"][0]["gainDb"] = -6

    incremental = render_revision(previous, revised, previous_output, tmp_path / "incremental-external.mp4")
    reference = render(revised, tmp_path / "reference-external.mp4")

    def stream_md5(path: Path, stream: str) -> str:
        result = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", stream, "-f", "framemd5", "-"], capture_output=True, text=True, check=True)
        return "\n".join(line for line in result.stdout.splitlines() if not line.startswith("#"))

    assert stream_md5(incremental, "0:v:0") == stream_md5(reference, "0:v:0")
    assert stream_md5(incremental, "0:a:0") == stream_md5(reference, "0:a:0")


def test_adding_face_follow_text_reuses_tracking_artifact():
    revised = json.loads(data_path("examples", "face-follow-text", "composition.json").read_text())
    previous = json.loads(json.dumps(revised))
    previous["timeline"]["tracks"][1]["items"] = []

    plan = plan_revision(previous, revised)

    assert plan["revisionKind"] == "motion"
    assert any(item["kind"] == "tracking" and item["id"] == "face-track" for item in plan["reusableArtifacts"])


def test_sam_prompt_invalidates_mask_and_downstream_composite_only():
    previous = json.loads(data_path("examples", "sam-segmentation", "composition.json").read_text())
    previous["timeline"]["tracks"][0]["items"][0]["maskIds"] = ["sam-mask"]
    previous["artifacts"]["masks"][0]["provenance"]["parameters"] = {"prompt": "person"}
    revised = json.loads(json.dumps(previous))
    revised["artifacts"]["masks"][0]["provenance"]["parameters"]["prompt"] = "red coat"
    revised["artifacts"]["masks"][0]["provenance"]["cacheKey"] = "red-coat-mask-v1"

    plan = plan_revision(previous, revised)

    assert plan["revisionKind"] == "artifact"
    assert plan["changedArtifacts"][0]["id"] == "sam-mask"
    assert plan["dirtyFrameRanges"] == [{"startFrame": 0, "endFrame": 60}]
    assert any(item["id"] == "subject" and "invalidated artifact" in item["reason"] for item in plan["dirtyLayers"])
    assert [job["kind"] for job in plan["requiredRerenderJobs"]] == ["artifact", "composite"]


def test_container_only_revision_plans_stream_copy_remux():
    previous = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    revised = json.loads(json.dumps(previous))
    revised["render"]["output"]["container"] = "mkv"
    revised["render"]["output"]["uri"] = "output.mkv"

    plan = plan_revision(previous, revised)

    assert plan["revisionKind"] == "container"
    assert plan["dirtyFrameRanges"] == []
    assert plan["stitchPlan"]["strategy"] == "stream-copy-remux"
    assert plan["requiredRerenderJobs"] == [{"kind": "remux", "reason": "container changed while encoded streams remain compatible"}]


def test_incompatible_container_codec_does_not_claim_remux_support():
    previous = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    revised = json.loads(json.dumps(previous))
    revised["render"]["output"].update({"container": "webm", "uri": "output.webm"})

    plan = plan_revision(previous, revised)

    assert plan["revisionKind"] == "full"
    assert plan["incrementalEligible"] is False
    assert plan["executionStatus"] == "full-render-required"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_container_only_revision_stream_copies_video_and_matches_full_render(tmp_path: Path):
    previous = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    previous["cache"] = {"enabled": False}
    previous_output = render(previous, tmp_path / "previous.mp4")
    revised = json.loads(json.dumps(previous))
    revised["render"]["output"].update({"container": "mkv", "uri": "revised.mkv"})

    incremental = render_revision(previous, revised, previous_output, tmp_path / "incremental.mkv")
    reference = render(revised, tmp_path / "reference.mkv")
    record = json.loads(incremental.with_suffix(".mkv.vibeedit.json").read_text())

    def frame_md5(path: Path) -> str:
        result = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", "0:v:0", "-f", "framemd5", "-"], capture_output=True, text=True, check=True)
        return "\n".join(line for line in result.stdout.splitlines() if not line.startswith("#"))

    assert frame_md5(incremental) == frame_md5(reference)
    assert record["work"]["framesRendered"] == 0
    assert record["work"]["framesReused"] == previous["durationFrames"]
    assert record["work"]["encodedVideoBytesReused"] > 0


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
