from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from vibeedit.ffmpeg import probe
from vibeedit.spec import JSONObject, VerificationReport


def verify_output(path: str | Path, expectations: JSONObject | None = None) -> VerificationReport:
    output = Path(path)
    if not output.is_file() or output.stat().st_size == 0:
        return VerificationReport(False, str(output), (), ("output does not exist or is empty",))
    metadata = probe(output)
    streams = metadata.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    expected = expectations or {}
    checks: list[JSONObject] = [{"id": "decodable", "passed": True}]
    errors: list[str] = []

    for key, actual in (("width", video.get("width") if video else None), ("height", video.get("height") if video else None)):
        if key not in expected:
            continue
        passed = actual == expected[key]
        checks.append({"id": key, "passed": passed, "expected": expected[key], "actual": actual})
        if not passed:
            errors.append(f"{key}: expected {expected[key]}, got {actual}")

    for key, actual in (("hasVideo", video is not None), ("hasAudio", audio is not None)):
        if key not in expected:
            continue
        passed = actual == expected[key]
        checks.append({"id": key, "passed": passed, "expected": expected[key], "actual": actual})
        if not passed:
            errors.append(f"{key}: expected {expected[key]}, got {actual}")

    if video and "frameRate" in expected:
        actual_rate = Fraction(video.get("avg_frame_rate", "0/1"))
        expected_rate = Fraction(expected["frameRate"]["numerator"], expected["frameRate"]["denominator"])
        passed = actual_rate == expected_rate
        checks.append({"id": "frameRate", "passed": passed, "expected": str(expected_rate), "actual": str(actual_rate)})
        if not passed:
            errors.append(f"frameRate: expected {expected_rate}, got {actual_rate}")

    if video and "durationFrames" in expected:
        frames = int(video.get("nb_frames") or 0)
        if not frames:
            rate = Fraction(video.get("avg_frame_rate", "0/1"))
            duration = Fraction(str(metadata.get("format", {}).get("duration", "0")))
            frames = round(duration * rate)
        drift = abs(frames - expected["durationFrames"])
        maximum = expected.get("maxDurationDriftFrames", 0)
        passed = drift <= maximum
        checks.append({"id": "durationFrames", "passed": passed, "expected": expected["durationFrames"], "actual": frames, "drift": drift})
        if not passed:
            errors.append(f"durationFrames: expected {expected['durationFrames']}±{maximum}, got {frames}")

    return VerificationReport(not errors, str(output), tuple(checks), tuple(errors))

