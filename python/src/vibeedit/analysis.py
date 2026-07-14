from __future__ import annotations

import array
import hashlib
import json
import math
import shutil
import statistics
import subprocess
from fractions import Fraction
from pathlib import Path

from vibeedit.cache import cache_key
from vibeedit.cache import restore_cached_artifact
from vibeedit.cache import store_cached_artifact
from vibeedit.spec import AnalysisArtifact
from vibeedit.spec import JSONObject


def regular_beat_frames(
    *,
    bpm: int | float,
    duration_frames: int,
    frame_rate_numerator: int,
    frame_rate_denominator: int = 1,
    offset_frame: int = 0,
) -> tuple[int, ...]:
    if bpm <= 0:
        raise ValueError("bpm must be greater than zero")
    if duration_frames < 0 or offset_frame < 0:
        raise ValueError("frame counts must be non-negative")
    if frame_rate_numerator <= 0 or frame_rate_denominator <= 0:
        raise ValueError("frame rate terms must be greater than zero")
    spacing = Fraction(60 * frame_rate_numerator, frame_rate_denominator) / Fraction(str(bpm))
    return tuple(
        frame
        for index in range(math.ceil(max(0, duration_frames - offset_frame) / spacing) + 1)
        if (frame := offset_frame + round(Fraction(index) * spacing)) < duration_frames
    )


def analyze_beats(
    source: str | Path,
    output: str | Path,
    *,
    frame_rate_numerator: int,
    frame_rate_denominator: int = 1,
    sensitivity: float = 1.35,
    minimum_gap_frames: int = 6,
) -> AnalysisArtifact:
    if sensitivity <= 0:
        raise ValueError("sensitivity must be greater than zero")
    if minimum_gap_frames < 1:
        raise ValueError("minimum_gap_frames must be at least one")
    if frame_rate_numerator <= 0 or frame_rate_denominator <= 0:
        raise ValueError("frame rate terms must be greater than zero")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("beat analysis requires FFmpeg on PATH")
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(path)
    sample_rate = 48_000
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    parameters: JSONObject = {
        "frameRate": {"numerator": frame_rate_numerator, "denominator": frame_rate_denominator},
        "sensitivity": sensitivity,
        "minimumGapFrames": minimum_gap_frames,
        "sampleRate": sample_rate,
    }
    version_result = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, check=False)
    runtime_versions = {"ffmpeg": (version_result.stdout or version_result.stderr).splitlines()[0] if version_result.returncode == 0 else "unavailable"}
    key = cache_key("analysis.beats", {"sourceSha256": source_hash, **parameters}, implementation_version="0.1.0", runtime_versions=runtime_versions)
    destination = Path(output)
    cache_hit = restore_cached_artifact("analysis.beats", key, destination)
    if not cache_hit:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace").strip() or "FFmpeg audio decode failed")
        samples = array.array("h")
        samples.frombytes(result.stdout)
        hop = max(1, round(sample_rate * frame_rate_denominator / frame_rate_numerator))
        energies = [_rms(samples[start : start + hop]) for start in range(0, len(samples), hop)]
        baseline = statistics.median(energies) if energies else 0.0
        threshold = max(1.0, baseline * sensitivity, max(energies, default=0.0) * 0.05)
        candidates = [index for index, energy in enumerate(energies) if energy >= threshold and (index == 0 or energy >= energies[index - 1]) and (index == len(energies) - 1 or energy > energies[index + 1])]
        beats = []
        for frame in candidates:
            if beats and frame - beats[-1] < minimum_gap_frames:
                if energies[frame] > energies[beats[-1]]:
                    beats[-1] = frame
                continue
            beats.append(frame)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({"schemaVersion": "1.0.0", "kind": "beats", "frameRate": parameters["frameRate"], "beats": beats, "energy": [round(value, 6) for value in energies]}, indent=2) + "\n", encoding="utf-8")
        store_cached_artifact("analysis.beats", key, destination)
    return AnalysisArtifact(
        id=destination.stem,
        kind="beats",
        artifact_uri=str(destination),
        format="vibeedit.beats+json",
        provenance={"generator": "vibeedit.analysis.analyze_beats", "implementationVersion": "0.1.0", "parameters": parameters, "sourceIdentities": [source_hash], "runtimeVersions": runtime_versions, "cacheKey": key, "cacheHit": cache_hit},
    )


def _rms(samples) -> float:
    return math.sqrt(sum(sample * sample for sample in samples) / max(1, len(samples)))
