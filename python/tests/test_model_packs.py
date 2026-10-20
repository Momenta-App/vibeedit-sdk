import argparse
import json
from fractions import Fraction
from pathlib import Path

import pytest

from vibeedit.model_packs import PACKS, PINS, _definition_digest, _lease, _supported, probe_model_pack, register_commands
from vibeedit.model_runners.transnet import build_index, plan


def test_catalog_has_all_requested_models_and_immutable_provenance():
    assert set(PACKS) == {"transnet", "sam21", "sam31-mlx"}
    for name, pack in PACKS.items():
        assert len(pack["revision"]) == 40
        assert pack["downloadBytes"] > 1_000_000
        assert pack["diskEstimateBytes"] > pack["downloadBytes"]
        assert pack["termsUrl"].startswith("https://")
        assert len(_definition_digest(name)) == 64
    for repo in ["mlx-community/sam3.1-bf16", "openai/clip-vit-base-patch32"]:
        for file in PINS[repo]["files"]:
            assert PINS[repo]["revision"] in file["url"]
            assert len(file["sha256"]) == 64
            assert file["bytes"] > 0


def test_commands_do_not_download_on_list_or_probe(tmp_path, capsys):
    parser = argparse.ArgumentParser()
    register_commands(parser.add_subparsers())
    args = parser.parse_args(["models", "list", "--cache", str(tmp_path), "--json"])
    assert args.handler(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schemaVersion"] == "vibeedit.models.v1"
    assert all(not pack["available"] for pack in result["packs"])
    assert list(tmp_path.iterdir()) == []


def test_model_lease_prevents_duplicate_heavy_work_and_retains_unknown_owner(tmp_path):
    with _lease(tmp_path, resource_root=tmp_path):
        assert json.loads((tmp_path / ".model.lock/owner.json").read_text(encoding="utf-8"))["pid"] > 0
        with pytest.raises(RuntimeError, match="Inspect owner.json"):
            with _lease(tmp_path, resource_root=tmp_path):
                pytest.fail("duplicate lease admitted")
    assert not (tmp_path / ".model.lock").exists()
    (tmp_path / ".model.lock").mkdir()
    with pytest.raises(RuntimeError, match="interrupted"):
        with _lease(tmp_path, resource_root=tmp_path):
            pytest.fail("unknown owner admitted")
    assert (tmp_path / ".model.lock").exists()


def test_transnet_preserves_nonzero_origin_vfr_and_half_open_ranges():
    index = build_index({"sha256": "a" * 64, "byteLength": 7}, [100, 140, 201, 244], Fraction(1, 1000), 300, [[0, 0], [2, 3]], .5, False, 80)
    assert index["clock"]["presentationPts"] == [100, 140, 201, 244]
    assert index["clock"]["originPts"] == 80
    assert index["shots"][0]["startMicros"] == index["shots"][0]["startUs"] == 20_000
    assert index["shots"][0]["endFrameExclusive"] == 2
    assert index["shots"][1]["startMicros"] == 121_000
    assert index["shots"][-1]["endMicros"] == index["shots"][-1]["endUs"] == 220_000
    follow = plan(index, ["shot_000002"], 0, "all", 6, 512)
    assert follow["submitted"] is False
    assert follow["requests"][0]["selectedNativeFrames"] == 2
    with pytest.raises(ValueError, match="strictly increasing"):
        build_index({}, [100, 100], "1/1000", 200, [[0, 1]], .5)


def test_missing_pack_reports_actionable_retry(tmp_path):
    result = probe_model_pack("transnet", tmp_path)
    assert result["available"] is False
    unsupported = _supported("transnet")  # Real host; do not fake a supported runtime.
    if unsupported:
        assert result["status"] == "unsupported-platform"
        assert result["reason"] == unsupported
        assert "retry" not in result  # No unusable setup instruction on Intel macOS.
        assert list(tmp_path.iterdir()) == []
        return
    assert result["status"] == "not-installed"
    assert result["retry"].startswith("vibeedit models setup transnet")


def test_segment_clock_uses_actual_vfr_native_pts(tmp_path):
    import shutil
    import subprocess
    from vibeedit.model_runners.segment import clock
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg required for real source-clock boundary test")
    source = tmp_path / "space ü source.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=32x24:r=24000/1001:d=0.25", "-vf", "setpts=PTS+2/TB", "-c:v", "ffv1", str(source)], check=True)
    stream, frames, pts = clock(source, 12)
    assert int(stream["start_pts"]) > 0
    assert len(pts) == len(frames) == 6
    assert all(b > a for a, b in zip(pts, pts[1:]))
    with pytest.raises(ValueError, match="exceeds"):
        clock(source, 2)


def test_corrupt_cached_weights_are_not_reported_available(tmp_path):
    import os
    from vibeedit.model_packs import _python
    runtime = tmp_path / "transnet"
    _python(runtime).parent.mkdir(parents=True)
    _python(runtime).write_text("not executed", encoding="utf-8")
    (runtime / "model.bin").write_bytes(b"corrupt")
    (runtime / "installed.json").write_text(json.dumps({"definitionSha256": _definition_digest("transnet"), "files": [{"path": "model.bin", "bytes": 7, "sha256": "a" * 64}]}), encoding="utf-8")
    result = probe_model_pack("transnet", tmp_path)
    assert result["available"] is False
    assert (runtime / "model.bin").read_bytes() == b"corrupt"
    assert _python(runtime).read_text(encoding="utf-8") == "not executed"
    unsupported = _supported("transnet")  # Platform rejection takes precedence.
    if unsupported:
        assert result["status"] == "unsupported-platform"
        assert result["reason"] == unsupported
        assert "files" not in result  # No claim that unsupported-host weights were checked.
        return
    assert result["status"] == "integrity-failed"
    assert result["files"] == ["model.bin"]


def test_mask_anchor_preserves_half_open_vfr_and_missing_last_duration():
    from vibeedit.model_runners.segment import frame_anchor
    pts = [100, 140, 201]
    native = [{"duration": 40}, {"duration": 61}, {}]
    first = frame_anchor(0, pts, native, Fraction(1, 1000), 80)
    assert (first["startUs"], first["endUs"], first["endPtsExclusive"]) == (20000, 60000, 140)
    final = frame_anchor(2, pts, native, Fraction(1, 1000), 80)
    assert final["startUs"] == 121000
    assert final["endUs"] is None
    assert final["endPtsExclusive"] is None
    assert final["timingQuality"] == "final-duration-unavailable"


def test_model_platform_limits_match_pinned_runtime_wheels():
    from vibeedit.model_packs import _supported
    assert "Intel" in _supported("sam21", system="Darwin", machine="x86_64", macos="26.4")
    assert "Intel" in _supported("transnet", system="Darwin", machine="x86_64", macos="26.4")
    assert "Apple Silicon" in _supported("sam31-mlx", system="Linux", machine="x86_64")
    assert "macOS 14" in _supported("sam21", system="Darwin", machine="arm64", macos="13.5")
    assert _supported("transnet", system="Darwin", machine="arm64", macos="12.0") is None
    assert "x86_64" in _supported("sam21", system="Windows", machine="arm64")

    assert "unqualified" in _supported("transnet", system="Linux", machine="ppc64le")


def test_shared_model_lease_blocks_jobs_in_distinct_caches(tmp_path):
    resource = tmp_path / "shared-hardware"
    with _lease(tmp_path / "cache-one", resource_root=resource):
        with pytest.raises(RuntimeError, match="busy"):
            with _lease(tmp_path / "cache-two", resource_root=resource):
                pytest.fail("different cache bypassed the shared model limit")


def test_heavy_model_admission_fails_closed_on_measured_resource_boundaries():
    from vibeedit.model_packs import _validate_resources
    safe = {"system": "Darwin", "volume": "/System/Volumes/Data", "diskFreeBytes": 25 * 1024 ** 3, "load": [10, 10], "memoryFreePercent": 15}
    assert _validate_resources(safe) == safe
    for change, message in [({"diskFreeBytes": safe["diskFreeBytes"] - 1}, "below 25 GiB"), ({"memoryFreePercent": None}, "unknown"), ({"memoryFreePercent": 14.99}, "below 15%"), ({"load": [10.01, 1]}, "above 10"), ({"load": [1, 10.01]}, "above 10")]:
        with pytest.raises(RuntimeError, match=message):
            _validate_resources({**safe, **change})


def test_segmentation_prompt_coordinates_and_unknown_fields_fail_closed():
    from vibeedit.model_runners.segment import validate_prompt
    validate_prompt("sam21", {"boxNormalized": [0, .1, 1, .9]}, 320, 180)
    validate_prompt("sam31-mlx", {"text": "person", "box": [0, 0, 320, 180], "scoreThreshold": .3}, 320, 180)
    for name, prompt, message in [
        ("sam31-mlx", {"text": "person", "boxNormalized": [0, 0, 1, 1]}, "Unsupported"),
        ("sam31-mlx", {"text": "person", "box": [0, 0, 320, 181]}, "native source pixels"),
        ("sam31-mlx", {"text": "person", "scoreThreshold": float("nan")}, "scoreThreshold"),
        ("sam21", {"box": [0, 0, 10, 10], "boxNormalized": [0, 0, 1, 1]}, "exactly one"),
        ("sam21", {"box": [True, 0, 10, 10]}, "finite xyxy"),
    ]:
        with pytest.raises(ValueError, match=message):
            validate_prompt(name, prompt, 320, 180)
