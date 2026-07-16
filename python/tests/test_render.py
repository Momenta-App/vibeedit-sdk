import json
import shutil
from pathlib import Path

import pytest

from vibeedit import render, verify_output
from vibeedit.data import data_path


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_minimal_fixture_renders_real_media(tmp_path: Path):
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    output = render(spec, tmp_path / "minimal.mp4")
    report = verify_output(output, spec["verification"])
    assert output.stat().st_size > 0
    assert report.passed, report.errors


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_procedural_sfx_renders_audio(tmp_path: Path):
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    spec["timeline"]["tracks"] = [
        {
            "id": "A1",
            "kind": "audio",
            "order": 0,
            "items": [
                {
                    "id": "impact",
                    "kind": "sound_effect",
                    "placement": {"startFrame": 5, "durationFrames": 10},
                    "soundEffectId": "vibeedit://sfx/impact-procedural",
                    "params": {"frequency": 72},
                    "gainDb": -12,
                    "variationSeed": 1,
                    "avoidImmediateRepeat": True,
                }
            ],
        }
    ]
    spec["verification"]["hasAudio"] = True
    output = render(spec, tmp_path / "with-audio.mp4")
    assert verify_output(output, spec["verification"]).passed


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_external_audio_clip_is_trimmed_placed_and_mixed(tmp_path: Path):
    import subprocess

    video = tmp_path / "video.mp4"
    audio = tmp_path / "music.wav"
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=navy:s=160x90:r=30:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=2", str(audio)], check=True)
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    spec["canvas"]["width"] = 160
    spec["canvas"]["height"] = 90
    spec["durationFrames"] = 60
    spec["sources"] = [
        {"id": "video", "kind": "video", "uri": str(video), "identity": {"algorithm": "generated", "value": "video"}, "durationFrames": 60},
        {"id": "music", "kind": "audio", "uri": str(audio), "identity": {"algorithm": "generated", "value": "music"}, "durationFrames": 60},
    ]
    spec["timeline"]["tracks"] = [
        {"id": "V1", "kind": "video", "order": 0, "items": [{"id": "video", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 60}, "source": {"sourceId": "video", "inFrame": 0, "durationFrames": 60}, "effects": []}]},
        {"id": "A1", "kind": "audio", "order": 0, "items": [{"id": "music", "kind": "audio", "placement": {"startFrame": 6, "durationFrames": 48}, "source": {"sourceId": "music", "inFrame": 3, "durationFrames": 48}, "role": "music", "gainDb": -6, "pan": 0.25, "fadeInFrames": 4, "fadeOutFrames": 4, "effects": []}]},
    ]
    spec["verification"] = {"durationFrames": 60, "width": 160, "height": 90, "frameRate": {"numerator": 30, "denominator": 1}, "hasVideo": True, "hasAudio": True, "maxDurationDriftFrames": 1}
    output = render(spec, tmp_path / "external-audio.mp4")
    assert verify_output(output, spec["verification"]).passed


def test_mixed_python_html_fixture_renders(tmp_path: Path):
    pytest.importorskip("playwright")
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text())
    output = render(spec, tmp_path / "mixed.mp4")
    report = verify_output(output, spec["verification"])
    assert report.passed, report.errors


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_agent_authored_html_css_javascript_renders(tmp_path: Path):
    pytest.importorskip("playwright")
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text())
    spec["id"] = "agent-authored-web-motion"
    spec["durationFrames"] = 24
    spec["cache"]["enabled"] = False
    spec["timeline"]["tracks"] = [
        {
            "id": "M1",
            "kind": "motion",
            "order": 10,
            "items": [
                {
                    "id": "web-title",
                    "kind": "motion",
                    "placement": {"startFrame": 0, "durationFrames": 24},
                    "componentId": "vibeedit://motion/html",
                    "props": {
                        "html": '<h1 id="title">WRITE FOR THE WEB</h1>',
                        "css": "body{display:grid;place-items:center;background:#101217;color:white}h1{font:900 54px Arial;animation:enter .8s ease-out both}@keyframes enter{from{opacity:0;transform:translateY(80px);filter:blur(12px)}to{opacity:1;transform:none;filter:blur(0)}}",
                        "javascript": "addEventListener('vibeedit:frame', ({detail}) => document.body.dataset.frame = detail.frame)",
                    },
                    "renderer": "auto",
                    "transparent": False,
                }
            ],
        }
    ]
    spec["verification"] = {"durationFrames": 24, "width": 640, "height": 360, "frameRate": {"numerator": 30, "denominator": 1}, "hasVideo": True, "hasAudio": False, "maxDurationDriftFrames": 1}
    output = render(spec, tmp_path / "agent-html.mp4")
    report = verify_output(output, spec["verification"])
    assert report.passed, report.errors


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_mixed_source_video_and_html_overlay_renders(tmp_path: Path):
    pytest.importorskip("playwright")
    import subprocess

    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text())
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=30:duration=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:sample_rate=48000:duration=3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
    )
    spec["sources"] = [{"id": "source", "kind": "video", "uri": str(source), "identity": {"algorithm": "sha256", "value": "generated-test-source"}, "durationFrames": 90, "license": {"status": "generated", "commercialOutputAllowed": True, "redistributionAllowed": True}}]
    next(track for track in spec["timeline"]["tracks"] if track["kind"] == "video")["items"] = [{"id": "clip", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 90}, "source": {"sourceId": "source", "inFrame": 0, "durationFrames": 90}, "effects": []}]
    next(track for track in spec["timeline"]["tracks"] if track["kind"] == "motion")["items"][0]["props"]["background"] = "transparent"
    output = render(spec, tmp_path / "mixed-source.mp4")
    report = verify_output(output, spec["verification"])
    assert report.passed, report.errors


def test_render_cache_records_reproducible_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "cache"))
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    spec["cache"] = {"enabled": True, "namespace": "test", "implementationVersion": "0.1.0", "runtimeVersions": {}}
    first = render(spec, tmp_path / "first.mp4")
    first_record = json.loads(first.with_suffix(".mp4.vibeedit.json").read_text())
    second = render(spec, tmp_path / "second.mp4")
    second_record = json.loads(second.with_suffix(".mp4.vibeedit.json").read_text())
    assert first_record["cacheHit"] is False
    assert second_record["cacheHit"] is True
    assert first_record["cacheKey"] == second_record["cacheKey"]
    assert first_record["output"]["sha256"] == second_record["output"]["sha256"]
