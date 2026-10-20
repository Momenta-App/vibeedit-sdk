import json
import shutil
from pathlib import Path

import pytest

from vibeedit import render, verify_output
from vibeedit.data import data_path
from vibeedit.ffmpeg import FFmpegRenderError, _thread_arguments


def test_ffmpeg_thread_arguments_honor_render_contract():
    assert _thread_arguments({"render": {}}) == ["-threads", "1"]
    assert _thread_arguments({"render": {"threads": 0}}, complex_filter=True) == ["-filter_complex_threads", "0", "-threads", "0"]
    assert _thread_arguments({"render": {"threads": 6}}, complex_filter=True) == ["-filter_complex_threads", "6", "-threads", "6"]


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_minimal_fixture_renders_real_media(tmp_path: Path):
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
    output = render(spec, tmp_path / "minimal.mp4")
    report = verify_output(output, spec["verification"])
    assert output.stat().st_size > 0
    assert report.passed, report.errors


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_procedural_sfx_renders_audio(tmp_path: Path):
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
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
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
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


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_multi_clip_fan_edit_supports_clean_cuts_and_transitions(tmp_path: Path):
    import subprocess

    sources = []
    for index, color in enumerate(("navy", "maroon", "darkgreen", "purple")):
        path = tmp_path / f"source-{index}.mp4"
        subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=160x90:r=30:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
        sources.append({"id": f"source-{index}", "kind": "video", "uri": str(path), "identity": {"algorithm": "generated", "value": color}, "durationFrames": 30})
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
    spec["id"] = "multi-clip-fan-edit"
    spec["canvas"].update({"width": 160, "height": 90})
    spec["durationFrames"] = 102
    spec["sources"] = sources
    spec["timeline"]["tracks"] = [
        {
            "id": "V1",
            "kind": "video",
            "order": 0,
            "items": [
                {"id": "hook", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 30}, "source": {"sourceId": "source-0", "inFrame": 0, "durationFrames": 30}, "effects": []},
                {"id": "setup", "kind": "video", "placement": {"startFrame": 24, "durationFrames": 30}, "source": {"sourceId": "source-1", "inFrame": 0, "durationFrames": 30}, "effects": []},
                {"id": "build", "kind": "video", "placement": {"startFrame": 54, "durationFrames": 24}, "source": {"sourceId": "source-2", "inFrame": 0, "durationFrames": 24}, "effects": []},
                {"id": "payoff", "kind": "video", "placement": {"startFrame": 72, "durationFrames": 30}, "source": {"sourceId": "source-3", "inFrame": 0, "durationFrames": 30}, "effects": [{"id": "stutter", "effectId": "vibeedit://effect/random-frame-stutter", "enabled": True, "params": {"seed": 7, "windowFrames": 4, "intensity": 0.7}, "implementationVersion": "0.1.0"}]},
                {"id": "hook-setup", "kind": "transition", "placement": {"startFrame": 24, "durationFrames": 6}, "transitionId": "vibeedit://transition/crossfade", "fromItemId": "hook", "toItemId": "setup", "params": {"curve": "linear"}, "implementationVersion": "0.1.0"},
                {"id": "build-payoff", "kind": "transition", "placement": {"startFrame": 72, "durationFrames": 6}, "transitionId": "vibeedit://transition/crossfade", "fromItemId": "build", "toItemId": "payoff", "params": {"curve": "linear"}, "implementationVersion": "0.1.0"},
            ],
        }
    ]
    spec["verification"] = {"durationFrames": 102, "width": 160, "height": 90, "frameRate": {"numerator": 30, "denominator": 1}, "hasVideo": True, "hasAudio": False, "maxDurationDriftFrames": 1}

    output = render(spec, tmp_path / "multi-clip.mp4")

    assert verify_output(output, spec["verification"]).passed
    assert json.loads(subprocess.run([shutil.which("ffprobe"), "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "json", str(output)], capture_output=True, text=True, check=True).stdout)["streams"][0]["nb_read_frames"] == "102"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_multi_clip_fan_edit_rejects_unmaterialized_timeline_gap(tmp_path: Path):
    import subprocess

    source = tmp_path / "source.mp4"
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=navy:s=160x90:r=30:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
    spec["canvas"].update({"width": 160, "height": 90})
    spec["durationFrames"] = 61
    spec["sources"] = [{"id": "source", "kind": "video", "uri": str(source), "identity": {"algorithm": "generated", "value": "source"}, "durationFrames": 60}]
    spec["timeline"]["tracks"] = [{"id": "V1", "kind": "video", "order": 0, "items": [{"id": "a", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 30}, "source": {"sourceId": "source", "inFrame": 0, "durationFrames": 30}, "effects": []}, {"id": "b", "kind": "video", "placement": {"startFrame": 31, "durationFrames": 30}, "source": {"sourceId": "source", "inFrame": 30, "durationFrames": 30}, "effects": []}]}]
    spec["verification"]["durationFrames"] = 61
    spec["verification"].update({"width": 160, "height": 90})

    with pytest.raises(FFmpegRenderError, match="clean boundary or an explicit adjacent transition"):
        render(spec, tmp_path / "invalid-gap.mp4")


def test_mixed_python_html_fixture_renders(tmp_path: Path):
    pytest.importorskip("playwright")
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text(encoding="utf-8"))
    output = render(spec, tmp_path / "mixed.mp4")
    report = verify_output(output, spec["verification"])
    assert report.passed, report.errors


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_agent_authored_html_css_javascript_renders(tmp_path: Path):
    pytest.importorskip("playwright")
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text(encoding="utf-8"))
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
def test_raw_html_css_atoms_render_end_to_end_without_javascript(tmp_path: Path):
    pytest.importorskip("playwright")
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text(encoding="utf-8"))
    spec["id"] = "raw-html-css-motion"
    spec["durationFrames"] = 24
    spec["cache"]["enabled"] = False
    spec["timeline"]["tracks"] = [
        {
            "id": "M1",
            "kind": "motion",
            "order": 10,
            "items": [
                {
                    "id": "raw-title",
                    "kind": "motion",
                    "placement": {"startFrame": 0, "durationFrames": 24},
                    "componentId": "vibeedit://motion/html-css",
                    "props": {
                        "html": '<!doctype html><html><head><title>Atoms</title></head><body class="ve-stage ve-center"><h1 class="ve-text ve-enter ve-shimmer ve-shadow" data-ve-from="bottom">RAW CSS</h1></body></html>',
                        "css": ":root{--ve-duration:.8s;--ve-accent:#9ef;--ve-shadow:rgba(0,0,0,.6)}body{background:#101217}",
                    },
                    "renderer": "auto",
                    "transparent": False,
                }
            ],
        }
    ]
    spec["verification"] = {"durationFrames": 24, "width": 640, "height": 360, "frameRate": {"numerator": 30, "denominator": 1}, "hasVideo": True, "hasAudio": False, "maxDurationDriftFrames": 1}
    output = render(spec, tmp_path / "raw-html-css.mp4")
    report = verify_output(output, spec["verification"])
    assert report.passed, report.errors


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_mixed_source_video_and_html_overlay_renders(tmp_path: Path):
    pytest.importorskip("playwright")
    import subprocess

    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text(encoding="utf-8"))
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
    import hashlib

    spec["sources"] = [{"id": "source", "kind": "video", "uri": str(source), "identity": {"algorithm": "sha256", "value": hashlib.sha256(source.read_bytes()).hexdigest()}, "durationFrames": 90, "license": {"status": "generated", "commercialOutputAllowed": True, "redistributionAllowed": True}}]
    next(track for track in spec["timeline"]["tracks"] if track["kind"] == "video")["items"] = [{"id": "clip", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 90}, "source": {"sourceId": "source", "inFrame": 0, "durationFrames": 90}, "effects": []}]
    next(track for track in spec["timeline"]["tracks"] if track["kind"] == "motion")["items"][0]["props"]["background"] = "transparent"
    output = render(spec, tmp_path / "mixed-source.mp4")
    report = verify_output(output, spec["verification"])
    assert report.passed, report.errors


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
def test_mixed_python_effect_transition_and_html_overlay_render_together(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("playwright")
    import subprocess

    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "cache"))
    spec = json.loads((data_path("examples", "effect-transition", "composition.json")).read_text(encoding="utf-8"))
    sources = []
    for index, color in enumerate(("0x172554", "0x4c0519")):
        source = tmp_path / f"source-{index}.mp4"
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
                f"color=c={color}:s=640x360:r=30:d=2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source),
            ],
            check=True,
        )
        sources.append({"id": f"source-{'a' if index == 0 else 'b'}", "kind": "video", "uri": str(source), "identity": {"algorithm": "generated", "value": f"source-{index}"}, "durationFrames": 60})
    spec["sources"] = sources
    spec["render"]["backend"] = "mixed"
    spec["timeline"]["tracks"].append(
        {
            "id": "M1",
            "kind": "motion",
            "order": 10,
            "items": [
                {
                    "id": "agent-title",
                    "kind": "motion",
                    "placement": {"startFrame": 0, "durationFrames": spec["durationFrames"]},
                    "componentId": "vibeedit://motion/html",
                    "props": {
                        "html": '<h1>PYTHON + WEB</h1>',
                        "css": "body{display:grid;place-items:center;background:transparent;color:white}h1{font:900 64px Arial;animation:enter .8s ease-out both}@keyframes enter{from{opacity:0;transform:translateY(60px);filter:blur(10px)}to{opacity:1;transform:none;filter:blur(0)}}",
                    },
                    "renderer": "html",
                    "transparent": True,
                }
            ],
        }
    )
    spec["verification"]["hasAudio"] = True
    spec["cache"] = {"enabled": True, "namespace": "mixed-media-base-test"}
    output = render(spec, tmp_path / "mixed-effect-transition.mp4")
    report = verify_output(output, spec["verification"])
    assert report.passed, report.errors
    first_record = json.loads(output.with_suffix(".mp4.vibeedit.json").read_text(encoding="utf-8"))

    spec["timeline"]["tracks"][-1]["items"][0]["props"]["html"] = "<h1>REVISED WEB LAYER</h1>"
    revised = render(spec, tmp_path / "mixed-effect-transition-revised.mp4")
    revised_record = json.loads(revised.with_suffix(".mp4.vibeedit.json").read_text(encoding="utf-8"))

    assert first_record["work"]["mediaBaseCacheHit"] is False
    assert first_record["work"]["mediaBaseFramesRendered"] == spec["durationFrames"]
    assert revised_record["work"]["mediaBaseCacheHit"] is True
    assert revised_record["work"]["mediaBaseFramesRendered"] == 0
    assert revised_record["work"]["videoFramesEncoded"] == spec["durationFrames"]


def test_render_cache_records_reproducible_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "cache"))
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
    spec["cache"] = {"enabled": True, "namespace": "test", "implementationVersion": "0.1.0", "runtimeVersions": {}}
    first = render(spec, tmp_path / "first.mp4")
    first_record = json.loads(first.with_suffix(".mp4.vibeedit.json").read_text(encoding="utf-8"))
    second = render(spec, tmp_path / "second.mp4")
    second_record = json.loads(second.with_suffix(".mp4.vibeedit.json").read_text(encoding="utf-8"))
    assert first_record["cacheHit"] is False
    assert second_record["cacheHit"] is True
    assert first_record["cacheKey"] == second_record["cacheKey"]
    assert first_record["output"]["sha256"] == second_record["output"]["sha256"]


def test_project_render_cache_stays_inside_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from vibeedit.cache import cache_root

    monkeypatch.delenv("VIBEEDIT_CACHE_DIR", raising=False)
    project = tmp_path / "project"
    (project / "compositions").mkdir(parents=True)
    (project / "project.vibeedit.json").write_text("{}", encoding="utf-8")
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
    spec["canvas"].update({"width": 64, "height": 64})
    spec["durationFrames"] = 3
    spec["timeline"]["tracks"] = []
    spec["cache"] = {"enabled": True, "namespace": "workspace-cache"}
    path = project / "compositions" / "main.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    first = render(path, project / "first.mp4")
    second = render(path, project / "second.mp4")
    assert cache_root(path.parent) == project / ".vibeedit" / "cache"
    assert cache_root() != cache_root(path.parent)
    assert list((project / ".vibeedit" / "cache" / "renders").glob("*.mp4"))
    assert json.loads(second.with_suffix(".mp4.vibeedit.json").read_text(encoding="utf-8"))["cacheHit"] is True
    assert first.read_bytes() == second.read_bytes()


def test_difference_motion_inverts_real_video_only_under_alpha(tmp_path: Path):
    import subprocess

    pytest.importorskip("playwright.sync_api")
    source = tmp_path / "red.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=160x90:r=30:d=0.4", "-f", "lavfi", "-i", "sine=frequency=880:duration=0.4", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source)], check=True)
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text(encoding="utf-8"))
    spec["canvas"].update(width=160, height=90)
    spec["durationFrames"] = 12
    spec["cache"]["enabled"] = False
    spec["sources"] = [{"id": "source", "kind": "video", "uri": str(source), "identity": {"algorithm": "generated", "value": "red"}, "durationFrames": 12}]
    spec["render"]["motionBlendMode"] = "difference"
    spec["timeline"]["tracks"] = [
        {"id": "picture", "kind": "video", "order": 0, "items": [{"id": "picture", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 12}, "source": {"sourceId": "source", "inFrame": 0, "durationFrames": 12}, "effects": []}]},
        {"id": "invert", "kind": "motion", "order": 1, "items": [{"id": "mask", "kind": "motion", "placement": {"startFrame": 0, "durationFrames": 12}, "componentId": "vibeedit://motion/html-css", "renderer": "html", "transparent": True, "props": {"html": '<div class="solid"></div><div class="half"></div>', "css": '.solid,.half{position:absolute;top:0;width:40px;height:90px;background:white}.solid{left:40px}.half{left:80px;opacity:.5}'}}]},
    ]
    from vibeedit import plan_revision, render_revision

    previous = json.loads(json.dumps(spec))
    previous["render"]["motionBlendMode"] = "normal"
    plain = render(previous, tmp_path / "plain.mp4")
    plan = plan_revision(previous, spec)
    assert plan["revisionKind"] == "full"
    graph = {node["id"]: node["hash"] for node in plan["dependencyGraph"]["nodes"]}
    old_graph = {node["id"]: node["hash"] for node in plan_revision(previous, previous)["dependencyGraph"]["nodes"]}
    assert graph["composite:video"] != old_graph["composite:video"]
    output = render_revision(previous, spec, plain, tmp_path / "inverted.mp4")
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
    def pixel(x):
        offset = (45*160+x)*3
        return tuple(raw[offset:offset+3])
    assert pixel(20)[0] > 240 and max(pixel(20)[1:]) < 10
    assert pixel(60)[0] < 10 and min(pixel(60)[1:]) > 240
    assert all(115 < channel < 140 for channel in pixel(100))
    assert verify_output(output, {"hasVideo": True, "hasAudio": True, "width": 160, "height": 90}).passed


def test_changed_source_cannot_reuse_an_old_render_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import hashlib
    import subprocess

    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "cache"))
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=64x64:r=30:d=0.1", "-c:v", "libx264", str(source)], check=True)
    spec = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
    spec["canvas"].update(width=64, height=64)
    spec["durationFrames"] = 3
    spec["cache"] = {"enabled": True}
    spec["sources"] = [{"id": "source", "kind": "video", "uri": str(source), "identity": {"algorithm": "sha256", "value": hashlib.sha256(source.read_bytes()).hexdigest()}, "durationFrames": 3}]
    spec["timeline"]["tracks"] = [{"id": "picture", "kind": "video", "order": 0, "items": [{"id": "clip", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 3}, "source": {"sourceId": "source", "inFrame": 0, "durationFrames": 3}, "effects": []}]}]
    original = render(spec, tmp_path / "original.mp4")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    source.write_bytes(source.read_bytes() + b"changed source identity")
    with pytest.raises(ValueError, match="Source content changed"):
        render(spec, tmp_path / "stale-cache.mp4")
    assert not (tmp_path / "stale-cache.mp4").exists()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
