from __future__ import annotations

import hashlib
import math
import wave
from pathlib import Path

from vibeedit.cache import write_artifact_provenance
from vibeedit.spec import JSONObject


def synthesize_impact(
    output: str | Path,
    *,
    duration_seconds: float = 0.4,
    frequency: float = 72,
    gain_db: float = -10,
    sample_rate: int = 48_000,
    seed: int = 0,
) -> Path:
    if duration_seconds <= 0 or frequency <= 0 or sample_rate <= 0:
        raise ValueError("duration, frequency, and sample rate must be greater than zero")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    amplitude = min(1.0, 10 ** (gain_db / 20))
    samples = bytearray()
    state = seed & 0xFFFFFFFF
    for index in range(round(duration_seconds * sample_rate)):
        time = index / sample_rate
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        noise = (state / 0xFFFFFFFF * 2 - 1) * 0.08
        envelope = math.exp(-8 * time / duration_seconds)
        value = (math.sin(2 * math.pi * frequency * time) + noise) * envelope * amplitude
        samples.extend(round(max(-1, min(1, value)) * 32767).to_bytes(2, "little", signed=True))
    with wave.open(str(destination), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(samples)
    parameters: JSONObject = {"durationSeconds": duration_seconds, "frequency": frequency, "gainDb": gain_db, "sampleRate": sample_rate, "seed": seed}
    write_artifact_provenance(destination.with_suffix(destination.suffix + ".vibeedit.json"), {"schemaVersion": "1.0.0", "generator": "vibeedit.sound.synthesize_impact", "implementationVersion": "0.1.0", "parameters": parameters, "output": {"path": destination.name, "bytes": destination.stat().st_size, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}, "license": "VibeEdit procedural generation; SEE LICENSE IN LICENSE.md"})
    return destination


def sound_design_plan(events: list[JSONObject], *, variation_seed: int = 0) -> list[JSONObject]:
    return [
        {
            "id": str(event.get("id", f"sfx-{index + 1}")),
            "kind": "sound_effect",
            "placement": {"startFrame": int(event["frame"]), "durationFrames": int(event.get("durationFrames", 12))},
            "soundEffectId": str(event.get("soundEffectId", "vibeedit://sfx/impact-procedural")),
            "params": {"frequency": float(event.get("frequency", 72))},
            "gainDb": float(event.get("gainDb", -10)),
            "variationSeed": variation_seed + index,
            "avoidImmediateRepeat": True,
        }
        for index, event in enumerate(events)
    ]
