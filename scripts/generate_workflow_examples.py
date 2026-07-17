#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = {"generator": "vibeedit-example", "generatorVersion": "0.1.0", "createdAt": "2026-07-13T00:00:00Z", "schemaSource": "schema/composition.schema.json", "catalogVersion": "0.1.0"}
ARTIFACT_PROVENANCE = {"generator": "vibeedit.examples", "implementationVersion": "0.1.0", "parameters": {}, "sourceIdentities": ["vibeedit-generated-example"], "cacheKey": "vibeedit-generated-example-v1"}


def main() -> int:
    examples = {
        "fan-edit": fan_edit(),
        "beat-synchronized": beat_synchronized(),
        "sound-design-layering": sound_design_layering(),
        "face-follow-text": face_follow_text(),
        "mask-subject-effect": mask_subject_effect(),
        "multiple-transitions": multiple_transitions(),
        "transparent-motion-overlay": transparent_motion_overlay(),
        "sam-segmentation": sam_segmentation(),
    }
    runner = "from pathlib import Path\n\nfrom vibeedit import render_example\n\n\nresult = render_example(Path(__file__).parent)\nprint(result or Path(__file__).parent / 'segmentation-unavailable.json')\n"
    for slug, (composition, manifest) in examples.items():
        directory = ROOT / "examples" / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "composition.json").write_text(json.dumps(composition, indent=2) + "\n", encoding="utf-8")
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (directory / "render.py").write_text(runner, encoding="utf-8")
    print(json.dumps({"ok": True, "examples": len(examples)}))
    return 0


def base(identifier: str, *, duration: int, width: int = 320, height: int = 180, backend: str = "ffmpeg", output: str | None = None, audio: bool = True):
    return {
        "schemaVersion": "1.0.0",
        "kind": "vibeedit.composition",
        "id": identifier,
        "canvas": {"width": width, "height": height, "frameRate": {"numerator": 30, "denominator": 1}, "backgroundColor": "#101217", "audioSampleRate": 48000},
        "durationFrames": duration,
        "sources": [],
        "timeline": {"tracks": []},
        "artifacts": {"masks": [], "tracking": [], "analysis": []},
        "render": {"backend": backend, "output": {"uri": output or f"{identifier}.mp4", "container": "mp4", "videoCodec": "h264", "audioCodec": "aac", "pixelFormat": "yuv420p"}, "deterministic": True},
        "verification": {"durationFrames": duration, "width": width, "height": height, "frameRate": {"numerator": 30, "denominator": 1}, "hasVideo": True, "hasAudio": audio, "maxDurationDriftFrames": 1},
        "provenance": PROVENANCE,
    }


def source(identifier: str, kind: str, uri: str, duration: int):
    return {"id": identifier, "kind": kind, "uri": uri, "identity": {"algorithm": "generated", "value": f"vibeedit-{identifier}-v1"}, "durationFrames": duration, "license": {"status": "generated", "commercialOutputAllowed": True, "redistributionAllowed": True}}


def video(identifier: str, source_id: str, start: int, duration: int, *, in_frame: int = 0, effects=None, metadata=None):
    return {"id": identifier, "kind": "video", "placement": {"startFrame": start, "durationFrames": duration}, "source": {"sourceId": source_id, "inFrame": in_frame, "durationFrames": duration}, "effects": effects or [], **({"metadata": metadata} if metadata else {})}


def sfx(identifier: str, frame: int, *, frequency: int = 72, gain: int = -10, duration: int = 12, seed: int = 7):
    return {"id": identifier, "kind": "sound_effect", "placement": {"startFrame": frame, "durationFrames": duration}, "soundEffectId": "vibeedit://sfx/impact-procedural", "params": {"frequency": frequency}, "gainDb": gain, "variationSeed": seed, "avoidImmediateRepeat": True}


def manifest(identifier: str, name: str, description: str, families: list[str], *, extras=None, models=None, conditional=False):
    return {
        "id": f"vibeedit://template/{identifier}",
        "name": name,
        "description": description,
        "families": families,
        "requirements": {"extras": extras or [], "models": models or []},
        "conditional": conditional,
    }


def fan_edit():
    spec = base("fan-edit", duration=180)
    spec["sources"] = [
        source("source-a", "video", "sources/source-a.mp4", 36),
        source("source-b", "video", "sources/source-b.mp4", 42),
        source("source-c", "video", "sources/source-c.mp4", 42),
        source("source-d", "video", "sources/source-d.mp4", 42),
        source("source-e", "video", "sources/source-e.mp4", 30),
        source("music", "audio", "sources/music.wav", 180),
    ]
    spec["timeline"]["tracks"] = [
        {
            "id": "V1",
            "kind": "video",
            "order": 0,
            "items": [
                video("hook", "source-a", 0, 36, metadata={"fanEditRole": "hook", "selectionReason": "immediate subject recognition and motion", "syncAnchor": "opening transient"}),
                video("setup", "source-b", 36, 42, metadata={"fanEditRole": "setup", "selectionReason": "establish contrast before acceleration", "syncAnchor": "phrase boundary"}),
                video("build", "source-c", 72, 42, effects=[{"id": "build-stutter", "effectId": "vibeedit://effect/random-frame-stutter", "enabled": True, "params": {"seed": 11, "windowFrames": 3, "intensity": 0.35}, "implementationVersion": "0.1.0"}], metadata={"fanEditRole": "build", "selectionReason": "increase visual instability before the drop", "syncAnchor": "riser peak"}),
                video("drop", "source-d", 108, 42, effects=[{"id": "drop-stutter", "effectId": "vibeedit://effect/random-frame-stutter", "enabled": True, "params": {"seed": 12, "windowFrames": 4, "intensity": 0.7}, "implementationVersion": "0.1.0"}], metadata={"fanEditRole": "drop", "selectionReason": "strongest action and contrast payoff", "syncAnchor": "downbeat"}),
                video("aftershock", "source-e", 150, 30, metadata={"fanEditRole": "aftershock", "selectionReason": "short resolving image that can hard-loop", "syncAnchor": "final phrase"}),
                {"id": "build-bridge", "kind": "transition", "placement": {"startFrame": 72, "durationFrames": 6}, "transitionId": "vibeedit://transition/crossfade", "fromItemId": "setup", "toItemId": "build", "params": {"curve": "linear"}, "implementationVersion": "0.1.0"},
                {"id": "drop-bridge", "kind": "transition", "placement": {"startFrame": 108, "durationFrames": 6}, "transitionId": "vibeedit://transition/crossfade", "fromItemId": "build", "toItemId": "drop", "params": {"curve": "linear"}, "implementationVersion": "0.1.0"},
            ],
        },
        {
            "id": "A1",
            "kind": "audio",
            "order": 0,
            "role": "music-and-accents",
            "items": [
                {"id": "music-bed", "kind": "audio", "placement": {"startFrame": 0, "durationFrames": 180}, "source": {"sourceId": "music", "inFrame": 0, "durationFrames": 180}, "role": "music", "gainDb": -12, "pan": 0, "fadeInFrames": 3, "fadeOutFrames": 8, "effects": []},
                sfx("hook-hit", 0, frequency=92, gain=-16, duration=10, seed=10),
                sfx("build-hit", 72, frequency=76, gain=-14, seed=11),
                sfx("drop-hit", 108, frequency=55, gain=-8, duration=18, seed=12),
                sfx("aftershock-hit", 150, frequency=66, gain=-15, seed=13),
            ],
        },
    ]
    spec["timeline"]["markers"] = [
        {"id": "hook", "frame": 0, "label": "Hook", "kind": "fan-edit-structure"},
        {"id": "setup", "frame": 36, "label": "Setup", "kind": "fan-edit-structure"},
        {"id": "build", "frame": 72, "label": "Build", "kind": "fan-edit-structure"},
        {"id": "drop", "frame": 108, "label": "Drop", "kind": "fan-edit-structure"},
        {"id": "aftershock", "frame": 150, "label": "Aftershock", "kind": "fan-edit-structure"},
    ]
    spec["audio"] = {"targetLufs": -16, "truePeakDb": -1, "preventImmediateSfxRepeat": True, "ducking": {"musicUnderSfxDb": -3}}
    spec["metadata"] = {"fanEdit": {"concept": "pressure turns into controlled impact", "structure": ["hook", "setup", "build", "drop", "aftershock"], "audioArchitecture": "music-led with selective impact accents", "textDecision": "none", "ordering": "non-chronological moment roles"}}
    return spec, manifest("fan-edit", "Fan Edit", "Executable five-moment hook/setup/build/drop/aftershock fan edit with clean cuts, motivated crossfades, selective stutter, music, and beat punctuation.", ["fan-edit", "multi-clip", "effects", "transitions", "sound-design"])


def beat_synchronized():
    spec = base("beat-synchronized", duration=108)
    spec["sources"] = [source("source-a", "video", "sources/source-a.mp4", 66), source("source-b", "video", "sources/source-b.mp4", 54), source("music", "audio", "sources/music.wav", 108)]
    spec["timeline"]["tracks"] = [
        {"id": "V1", "kind": "video", "order": 0, "items": [video("clip-a", "source-a", 0, 66), video("clip-b", "source-b", 54, 54), {"id": "beat-crossfade", "kind": "transition", "placement": {"startFrame": 54, "durationFrames": 12}, "transitionId": "vibeedit://transition/crossfade", "fromItemId": "clip-a", "toItemId": "clip-b", "params": {"curve": "linear"}, "implementationVersion": "0.1.0"}]},
        {"id": "A1", "kind": "audio", "order": 0, "items": [{"id": "music", "kind": "audio", "placement": {"startFrame": 0, "durationFrames": 108}, "source": {"sourceId": "music", "inFrame": 0, "durationFrames": 108}, "role": "music", "gainDb": -12, "pan": 0, "fadeInFrames": 2, "fadeOutFrames": 4, "effects": []}, sfx("drop-accent", 60, frequency=54, gain=-11, seed=21)]},
    ]
    spec["artifacts"]["analysis"] = [{"id": "beats", "kind": "beats", "artifactUri": "artifacts/beats.json", "format": "vibeedit.beats+json", "sourceIds": ["music"], "provenance": {**ARTIFACT_PROVENANCE, "generator": "vibeedit.analysis.analyze_beats"}}]
    return spec, manifest("beat-synchronized", "Beat-Synchronized Edit", "Executable 120 BPM edit that analyzes generated audio and verifies cuts against the recovered integer-frame beat grid.", ["beat-analysis", "audio", "transitions"], extras=["vision"])


def sound_design_layering():
    spec = base("sound-design-layering", duration=90)
    spec["sources"] = [source("source", "video", "sources/source.mp4", 90), source("ambience", "audio", "sources/ambience.wav", 90)]
    spec["timeline"]["tracks"] = [
        {"id": "V1", "kind": "video", "order": 0, "items": [video("source", "source", 0, 90)]},
        {"id": "A1", "kind": "audio", "order": 0, "role": "ambience", "items": [{"id": "ambience", "kind": "audio", "placement": {"startFrame": 0, "durationFrames": 90}, "source": {"sourceId": "ambience", "inFrame": 0, "durationFrames": 90}, "role": "ambience", "gainDb": -22, "pan": 0, "fadeInFrames": 6, "fadeOutFrames": 8, "effects": []}]},
        {"id": "A2", "kind": "audio", "order": 1, "role": "sfx", "items": [sfx("low-hit", 15, frequency=55, gain=-14, seed=31), sfx("mid-hit", 45, frequency=88, gain=-12, seed=32), sfx("high-hit", 75, frequency=144, gain=-16, seed=33)]},
    ]
    spec["audio"] = {"targetLufs": -16, "truePeakDb": -1, "preventImmediateSfxRepeat": True, "ducking": {"musicUnderSfxDb": -3}}
    return spec, manifest("sound-design-layering", "Sound-Design Layering", "Executable ambience bed plus three seeded procedural transient layers with gain, fades, and anti-repetition metadata.", ["audio", "sound-design", "sfx"])


def face_follow_text():
    spec = base("face-follow-text", duration=60, backend="mixed")
    points = [{"frame": 0, "x": 0.25, "y": 0.48}, {"frame": 15, "x": 0.42, "y": 0.42}, {"frame": 30, "x": 0.62, "y": 0.54}, {"frame": 45, "x": 0.75, "y": 0.44}, {"frame": 59, "x": 0.55, "y": 0.5}]
    spec["sources"] = [source("subject", "video", "sources/subject.mp4", 60)]
    spec["timeline"]["tracks"] = [
        {"id": "V1", "kind": "video", "order": 0, "items": [video("subject", "subject", 0, 60)]},
        {"id": "M1", "kind": "motion", "order": 10, "items": [{"id": "tracked-title", "kind": "motion", "placement": {"startFrame": 0, "durationFrames": 60}, "componentId": "vibeedit://text/negative-face-follow", "props": {"text": "LOCKED ON", "trackingFrames": points, "background": "transparent"}, "renderer": "html", "transparent": True}]},
        {"id": "A1", "kind": "audio", "order": 0, "items": [sfx("lock", 30, frequency=96, gain=-13, seed=41)]},
    ]
    spec["artifacts"]["tracking"] = [{"id": "face-track", "kind": "face", "artifactUri": "artifacts/face-tracks.json", "startFrame": 0, "durationFrames": 60, "coordinateSpace": "normalized", "format": "vibeedit.face-tracks+json", "provenance": {**ARTIFACT_PROVENANCE, "generator": "vibeedit.examples.controlled_face_track"}}]
    return spec, manifest("face-follow-text", "Face-Following Text", "Executable tracked-text overlay using deterministic interpolation from a frame-addressed face TrackingArtifact.", ["tracking", "face", "text", "html"], extras=["browser"])


def mask_subject_effect():
    spec = base("mask-subject-effect", duration=60, backend="python")
    spec["timeline"]["tracks"] = [{"id": "A1", "kind": "audio", "order": 0, "items": [sfx("mask-hit", 30, frequency=64, gain=-12, seed=51)]}]
    spec["artifacts"]["masks"] = [{"id": "subject-mask", "kind": "image_sequence", "startFrame": 0, "durationFrames": 60, "artifactUri": "artifacts/masks/mask-%06d.png", "format": "image/png", "inverted": False, "provenance": {**ARTIFACT_PROVENANCE, "generator": "vibeedit.examples.controlled_subject_mask"}}]
    return spec, manifest("mask-subject-effect", "Mask-Driven Subject Effect", "Executable moving subject matte that confines a catalog color treatment to the subject on every frame.", ["masks", "subject-effects", "effects"], extras=["effects"])


def multiple_transitions():
    spec = base("multiple-transitions", duration=120, backend="python")
    spec["timeline"]["tracks"] = [{"id": "A1", "kind": "audio", "order": 0, "items": [sfx("push-hit", 37, frequency=82, gain=-13, seed=61), sfx("burn-hit", 82, frequency=58, gain=-11, seed=62)]}]
    return spec, manifest("multiple-transitions", "Multiple Transitions", "Executable three-card sequence with independently rendered push and film-burn catalog transitions.", ["transitions", "effects"], extras=["effects"])


def transparent_motion_overlay():
    spec = base("transparent-motion-overlay", duration=60, backend="html", output="transparent-motion-overlay.webm", audio=False)
    spec["timeline"]["tracks"] = [{"id": "M1", "kind": "motion", "order": 0, "items": [{"id": "overlay", "kind": "motion", "placement": {"startFrame": 0, "durationFrames": 60}, "componentId": "vibeedit://text/mogrt-fluorscent", "props": {"text": "ALPHA READY", "background": "transparent"}, "renderer": "html", "transparent": True}]}]
    spec["render"]["output"] = {"uri": "transparent-motion-overlay.webm", "container": "webm", "videoCodec": "vp9", "pixelFormat": "yuva420p", "transparent": True}
    return spec, manifest("transparent-motion-overlay", "Transparent Motion Overlay", "Executable deterministic HTML title rendered as a VP9 alpha overlay for downstream compositing.", ["html", "motion", "transparent-overlay"], extras=["browser"])


def sam_segmentation():
    spec = base("sam-segmentation", duration=60, audio=False)
    spec["sources"] = [source("subject", "video", "sources/subject.mp4", 60)]
    spec["timeline"]["tracks"] = [{"id": "V1", "kind": "video", "order": 0, "items": [video("subject", "subject", 0, 60)]}]
    spec["artifacts"]["masks"] = [{"id": "sam-mask", "kind": "rle", "startFrame": 0, "durationFrames": 60, "artifactUri": "artifacts/sam-mask.json", "format": "vibeedit.sam-mask+json", "inverted": False, "provenance": {**ARTIFACT_PROVENANCE, "generator": "vibeedit.vision.segment", "model": "configured-at-runtime", "modelVersion": "configured-at-runtime"}}]
    return spec, manifest("sam-segmentation", "Conditional SAM Segmentation", "Executable capability-gated SAM recipe that produces a mask with a checksum-declared external provider and writes actionable degradation evidence otherwise.", ["segmentation", "sam", "masks"], extras=["sam"], models=["checksum-declared SAM 2.1 or 3.1 provider"], conditional=True)


if __name__ == "__main__":
    raise SystemExit(main())
