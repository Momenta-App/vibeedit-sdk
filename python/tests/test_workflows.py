import json
import shutil
import wave
from pathlib import Path

import pytest

from vibeedit import analyze_beats
from vibeedit import composite_with_mask
from vibeedit import regular_beat_frames
from vibeedit import sound_design_plan
from vibeedit import synthesize_impact
from vibeedit import tracking_point_at


def test_regular_beat_grid_uses_rational_frame_timing():
    assert regular_beat_frames(bpm=120, duration_frames=61, frame_rate_numerator=30) == (0, 15, 30, 45, 60)
    assert regular_beat_frames(bpm=120, duration_frames=60, frame_rate_numerator=30_000, frame_rate_denominator=1_001) == (0, 15, 30, 45)


def test_tracking_interpolation_clamps_and_is_deterministic():
    points = [{"frame": 0, "x": 0.2, "y": 0.3}, {"frame": 10, "x": 0.8, "y": 0.7}]
    assert tracking_point_at(points, 5) == pytest.approx((0.5, 0.5))
    assert tracking_point_at(points, -2) == (0.2, 0.3)
    assert tracking_point_at([{"frame": 0, "x": -1, "y": 2}], 0) == (0, 1)


def test_mask_composite_applies_only_the_matte():
    numpy = pytest.importorskip("numpy")
    base = numpy.zeros((2, 2, 3), dtype=numpy.uint8)
    treated = numpy.full((2, 2, 3), 200, dtype=numpy.uint8)
    mask = numpy.array([[0, 255], [128, 0]], dtype=numpy.uint8)
    result = composite_with_mask(base, treated, mask)
    assert result[0, 0].tolist() == [0, 0, 0]
    assert result[0, 1].tolist() == [200, 200, 200]
    assert result[1, 0].tolist() == [100, 100, 100]


def test_procedural_sound_and_layer_plan_are_reproducible(tmp_path: Path):
    first = synthesize_impact(tmp_path / "a.wav", seed=9)
    second = synthesize_impact(tmp_path / "b.wav", seed=9)
    assert first.read_bytes() == second.read_bytes()
    assert first.with_suffix(".wav.vibeedit.json").is_file()
    plan = sound_design_plan([{"frame": 10}, {"frame": 20, "frequency": 96}], variation_seed=7)
    assert [item["variationSeed"] for item in plan] == [7, 8]
    assert all(item["avoidImmediateRepeat"] for item in plan)


def test_real_audio_beat_analysis_writes_provenance_and_reuses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg is unavailable")
    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "cache"))
    source = tmp_path / "pulses.wav"
    samples = []
    for frame in range(30):
        value = 24_000 if frame in {5, 15, 25} else 0
        samples.extend([value] * 1_600)
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48_000)
        audio.writeframes(b"".join(value.to_bytes(2, "little", signed=True) for value in samples))
    artifact = analyze_beats(source, tmp_path / "beats.json", frame_rate_numerator=30, sensitivity=1.1, minimum_gap_frames=3)
    payload = json.loads(Path(artifact.artifact_uri).read_text())
    assert payload["beats"] == [5, 15, 25]
    assert artifact.provenance["cacheKey"]
    assert artifact.provenance["cacheHit"] is False
    cached = analyze_beats(source, tmp_path / "beats-cached.json", frame_rate_numerator=30, sensitivity=1.1, minimum_gap_frames=3)
    assert cached.provenance["cacheHit"] is True
    assert cached.provenance["cacheKey"] == artifact.provenance["cacheKey"]
    assert Path(cached.artifact_uri).read_bytes() == Path(artifact.artifact_uri).read_bytes()
