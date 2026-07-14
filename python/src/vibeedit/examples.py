from __future__ import annotations

import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

from vibeedit.analysis import analyze_beats
from vibeedit.analysis import regular_beat_frames
from vibeedit.data import data_path
from vibeedit.ffmpeg import render_frame_sequence
from vibeedit.masks import composite_with_mask
from vibeedit.motion import tracking_point_at
from vibeedit.presets import apply_media_preset
from vibeedit.presets import render_transition_preset
from vibeedit.render import render
from vibeedit.validation import validate_composition
from vibeedit.verify import verify_output


def create_example(identifier: str, destination: str | Path = ".") -> Path:
    source = data_path("examples", identifier)
    if not source.is_dir():
        raise ValueError(f"unknown example: {identifier}")
    target = Path(destination) / identifier
    if target.exists():
        raise FileExistsError(f"destination already exists: {target}")
    shutil.copytree(source, target)
    return target


def render_example(directory: str | Path, output: str | Path | None = None) -> Path | None:
    root = Path(directory)
    spec = json.loads((root / "composition.json").read_text(encoding="utf-8"))
    validate_composition(spec)
    destination = Path(output) if output else root / spec["render"]["output"]["uri"]
    handlers = {
        "fan-edit": _render_media_recipe,
        "beat-synchronized": _render_beat_recipe,
        "sound-design-layering": _render_media_recipe,
        "face-follow-text": _render_face_follow,
        "mask-subject-effect": _render_mask_recipe,
        "multiple-transitions": _render_transition_recipe,
        "transparent-motion-overlay": _render_motion_recipe,
        "sam-segmentation": _render_sam_recipe,
    }
    if spec["id"] not in handlers:
        raise ValueError(f"unsupported packaged example: {spec['id']}")
    result = handlers[spec["id"]](root, spec, destination)
    if result is not None:
        report = verify_output(result, spec["verification"])
        if not report.passed:
            raise RuntimeError("\n".join(report.errors))
    return result


def _render_media_recipe(root: Path, spec, destination: Path) -> Path:
    _generate_declared_sources(root, spec)
    return render(root / "composition.json", destination)


def _render_beat_recipe(root: Path, spec, destination: Path) -> Path:
    _generate_declared_sources(root, spec)
    artifact = analyze_beats(root / "sources" / "music.wav", root / "artifacts" / "beats.json", frame_rate_numerator=spec["canvas"]["frameRate"]["numerator"], frame_rate_denominator=spec["canvas"]["frameRate"]["denominator"], sensitivity=1.1, minimum_gap_frames=5)
    detected = json.loads(Path(artifact.artifact_uri).read_text(encoding="utf-8"))["beats"]
    expected = list(regular_beat_frames(bpm=120, duration_frames=spec["durationFrames"], frame_rate_numerator=30))
    if detected != expected:
        raise RuntimeError(f"beat analysis did not recover the generated beat grid: {detected} != {expected}")
    return render(root / "composition.json", destination)


def _render_face_follow(root: Path, spec, destination: Path) -> Path:
    from PIL import Image
    from PIL import ImageDraw

    points = next(item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "motion")["props"]["trackingFrames"]
    frames = root / "sources" / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    width = spec["canvas"]["width"]
    height = spec["canvas"]["height"]
    records = []
    for frame in range(spec["durationFrames"]):
        x, y = tracking_point_at(points, frame)
        image = Image.new("RGB", (width, height), "#18202b")
        drawing = ImageDraw.Draw(image)
        drawing.ellipse((x * width - 34, y * height - 34, x * width + 34, y * height + 34), fill="#ecff4d", outline="#ffffff", width=4)
        drawing.ellipse((x * width - 14, y * height - 10, x * width - 7, y * height - 3), fill="#101217")
        drawing.ellipse((x * width + 7, y * height - 10, x * width + 14, y * height - 3), fill="#101217")
        image.save(frames / f"frame-{frame:06d}.png")
        records.append({"frame": frame, "detections": [{"trackId": 1, "label": "face", "confidence": 1, "x": round(x - 34 / width, 6), "y": round(y - 34 / height, 6), "width": round(68 / width, 6), "height": round(68 / height, 6)}]})
    (root / "artifacts").mkdir(exist_ok=True)
    (root / "artifacts" / "face-tracks.json").write_text(json.dumps({"schemaVersion": "1.0.0", "kind": "face_tracking", "coordinateSpace": "normalized", "frames": records}, indent=2) + "\n", encoding="utf-8")
    _encode_frames(frames / "frame-%06d.png", root / "sources" / "subject.mp4", spec)
    return render(root / "composition.json", destination)


def _render_mask_recipe(root: Path, spec, destination: Path) -> Path:
    import numpy
    from PIL import Image

    frames = root / "frames"
    masks = root / "artifacts" / "masks"
    frames.mkdir(parents=True, exist_ok=True)
    masks.mkdir(parents=True, exist_ok=True)
    width = spec["canvas"]["width"]
    height = spec["canvas"]["height"]
    yy, xx = numpy.mgrid[:height, :width]
    for frame in range(spec["durationFrames"]):
        center_x = width * (0.25 + 0.5 * frame / max(1, spec["durationFrames"] - 1))
        matte = (((xx - center_x) / 44) ** 2 + ((yy - height * 0.53) / 70) ** 2 <= 1).astype(numpy.uint8) * 255
        base = numpy.zeros((height, width, 4), dtype=numpy.uint8)
        base[:, :, :3] = (18, 26, 40)
        base[:, :, 3] = 255
        base[matte > 0, :3] = (236, 255, 77)
        treated = apply_media_preset(base, "vibeedit://effect/filters-cinematic-teal-orange", progress=frame / max(1, spec["durationFrames"] - 1))
        Image.fromarray(composite_with_mask(base, treated, matte)).save(frames / f"frame-{frame:06d}.png")
        Image.fromarray(matte).save(masks / f"mask-{frame:06d}.png")
    return render_frame_sequence(spec, frames / "frame-%06d.png", destination)


def _render_transition_recipe(root: Path, spec, destination: Path) -> Path:
    import numpy
    from PIL import Image

    frames = root / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    colors = [(235, 49, 85, 255), (46, 230, 166, 255), (75, 123, 255, 255)]
    cards = [numpy.full((spec["canvas"]["height"], spec["canvas"]["width"], 4), color, dtype=numpy.uint8) for color in colors]
    for frame in range(spec["durationFrames"]):
        if frame < 30:
            image = cards[0]
        elif frame < 45:
            image = render_transition_preset(cards[0], cards[1], "vibeedit://transition/transitions-core-push-left", progress=(frame - 30) / 14)
        elif frame < 75:
            image = cards[1]
        elif frame < 90:
            image = render_transition_preset(cards[1], cards[2], "vibeedit://transition/transitions-core-film-burn", progress=(frame - 75) / 14)
        else:
            image = cards[2]
        Image.fromarray(numpy.asarray(image, dtype=numpy.uint8)).save(frames / f"frame-{frame:06d}.png")
    return render_frame_sequence(spec, frames / "frame-%06d.png", destination)


def _render_motion_recipe(root: Path, spec, destination: Path) -> Path:
    return render(root / "composition.json", destination)


def _render_sam_recipe(root: Path, spec, destination: Path) -> Path | None:
    from vibeedit.vision import CapabilityRouter

    status = next(item for item in CapabilityRouter().status() if item["id"] == "vision.segmentation")
    if not status["available"]:
        (root / "segmentation-unavailable.json").write_text(json.dumps({"ok": False, "capability": status, "action": "Install `vibeedit[sam]` and run `vibeedit setup --sam`, or configure a verified VIBEEDIT_SAM_RUNNER."}, indent=2) + "\n", encoding="utf-8")
        return None
    _generate_declared_sources(root, spec)
    CapabilityRouter().segment(root / "sources" / "subject.mp4", root / "artifacts" / "sam-mask.json", duration_frames=spec["durationFrames"])
    return render(root / "composition.json", destination)


def _generate_declared_sources(root: Path, spec) -> None:
    sources = root / "sources"
    sources.mkdir(exist_ok=True)
    duration = spec["durationFrames"] / (spec["canvas"]["frameRate"]["numerator"] / spec["canvas"]["frameRate"]["denominator"])
    for source in spec["sources"]:
        path = root / source["uri"]
        if source["kind"] == "video":
            pattern = "testsrc2" if source["id"].endswith("a") or source["id"] in {"source", "subject"} else "smptebars"
            _run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"{pattern}=size={spec['canvas']['width']}x{spec['canvas']['height']}:rate=30:duration={duration:.6f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)])
        if source["kind"] == "audio":
            _write_pulse_audio(path, spec["durationFrames"], tuple(regular_beat_frames(bpm=120, duration_frames=spec["durationFrames"], frame_rate_numerator=30)))


def _write_pulse_audio(path: Path, duration_frames: int, beats: tuple[int, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 48_000
    samples_per_frame = sample_rate // 30
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        values = bytearray()
        for frame in range(duration_frames):
            for index in range(samples_per_frame):
                value = round(math.sin(2 * math.pi * 96 * index / sample_rate) * 22_000 * math.exp(-8 * index / samples_per_frame)) if frame in beats else 0
                values.extend(value.to_bytes(2, "little", signed=True))
        audio.writeframes(values)


def _encode_frames(sequence: Path, output: Path, spec) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rate = spec["canvas"]["frameRate"]
    _run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-framerate", f"{rate['numerator']}/{rate['denominator']}", "-i", str(sequence), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-frames:v", str(spec["durationFrames"]), str(output)])


def _ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("examples require FFmpeg; run `vibeedit doctor`")
    return executable


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"command failed with exit code {result.returncode}")
