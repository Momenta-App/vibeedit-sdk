from __future__ import annotations

import json
import math
import tempfile
from fractions import Fraction
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
    from vibeedit.project import Project
    composition_path = root / Project(root).read()["composition"] if (root / "project.vibeedit.json").is_file() else root / "composition.json"
    spec = json.loads(composition_path.read_text(encoding="utf-8"))
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
        "dialogue-quote": _render_caption_recipe,
        "talking-head-captions": _render_caption_recipe,
    }
    if spec["id"] not in handlers:
        raise ValueError(f"unsupported packaged example: {spec['id']}")
    result = render(composition_path, destination) if (root/"project.vibeedit.json").is_file() and spec["id"] not in {"dialogue-quote", "talking-head-captions", "beat-synchronized"} else handlers[spec["id"]](root, spec, destination)
    if result is not None:
        if (root / "project.vibeedit.json").is_file():
            spec = json.loads((root / Project(root).read()["composition"]).read_text())
        report = verify_output(result, spec["verification"])
        if not report.passed:
            raise RuntimeError("\n".join(report.errors))
    return result


def _render_media_recipe(root: Path, spec, destination: Path) -> Path:
    _generate_declared_sources(root, spec)
    return render(root / "composition.json", destination)


def _render_beat_recipe(root: Path, spec, destination: Path) -> Path:
    from vibeedit.project import Project, create_project, atomic_json, file_digest
    if (root / "project.vibeedit.json").is_file():
        return render(root / Project(root).read()["composition"], destination)
    _generate_declared_sources(root, spec)
    artifact = analyze_beats(root / "sources" / "music.wav", root / "artifacts" / "beats.json", frame_rate_numerator=spec["canvas"]["frameRate"]["numerator"], frame_rate_denominator=spec["canvas"]["frameRate"]["denominator"], sensitivity=1.1, minimum_gap_frames=5)
    detected = json.loads(Path(artifact.artifact_uri).read_text(encoding="utf-8"))["beats"]
    expected = list(regular_beat_frames(bpm=120, duration_frames=spec["durationFrames"], frame_rate_numerator=30))
    if detected != expected:
        raise RuntimeError(f"beat analysis did not recover the generated beat grid: {detected} != {expected}")
    # Materialize the existing composition with exact project source identities,
    # preserving the local beat candidate artifact and review binding.
    with tempfile.TemporaryDirectory(prefix="vibeedit-beat-seed-") as temporary:
        seed = Path(temporary)/"composition.json"
        blank = json.loads(json.dumps(spec))
        blank["sources"] = []
        blank["timeline"]["tracks"] = []
        blank["artifacts"] = {"masks": [], "tracking": [], "analysis": []}
        atomic_json(seed, blank)
        create_project(root, seed)
    project = Project(root)
    mapping = {}
    for original in spec["sources"]:
        project.register_source(root/original["uri"], expected_revision=project.read()["revision"], receipt={"kind":"generated-fixture", "generator":"vibeedit.examples"})
        source = next(source for source in project.read()["sources"] if source["sha256"] == file_digest(root/original["uri"]))
        mapping[original["id"]] = source["id"]
        original.update(id=source["id"], uri=source["path"], identity={"algorithm":"sha256", "value":source["sha256"]})
    for track in spec["timeline"]["tracks"]:
        for item in track["items"]:
            if item.get("source"):
                item["source"]["sourceId"] = mapping[item["source"]["sourceId"]]
            if item["id"] == "drop-accent":
                item.setdefault("metadata", {})["reviewBeat"] = {"sourceId":mapping["music"], "index":4, "offsetFrames":0}
    for analysis in spec["artifacts"]["analysis"]:
        analysis["sourceIds"] = [mapping[identity] for identity in analysis["sourceIds"]]
    beat_review = {"schemaVersion":"vibeedit.beatCandidates.v1","sourceId":mapping["music"],"sourceSha256":project.source(mapping["music"])["sha256"],"origin":"local full-mix beat candidates; not human reviewed","beats":[{"timeSec":frame/30,"strength":1} for frame in detected]}
    atomic_json(root/"artifacts"/"beats-review.json", beat_review)
    project.update(project.read()["revision"], lambda value:value["beats"].append({"sourceId":mapping["music"],"path":"artifacts/beats-review.json","origin":"machine-candidates"}))
    atomic_json(root/"composition.json", spec)
    return render(root / "composition.json", destination)


def _render_caption_recipe(root: Path, spec, destination: Path) -> Path:
    return render(prepare_caption_example(root), destination)


def prepare_caption_example(directory, *, media=None, words=None):
    """Bind a caption/quote starting point to supplied source-time words or a labeled fixture."""
    from vibeedit.project import Project, atomic_json, create_project, file_digest
    from vibeedit.ffmpeg import probe
    root = Path(directory)
    if (root/"project.vibeedit.json").is_file():
        if not (root/".vibeedit"/"caption-template-ready.json").is_file():
            raise ValueError("caption template initialization is incomplete; reconcile its existing source/baseline before continuing, preserving the same project")
        if media is not None or words is not None:
            raise ValueError("template already initialized; preserve corrections and use a new project for another source")
        return root/Project(root).read()["composition"]
    if (media is None) != (words is None):
        raise ValueError("supply both user video and source-time word JSON; do not invent dialogue")
    spec = json.loads((root/"composition.json").read_text())
    if spec["id"] not in {"dialogue-quote", "talking-head-captions"}:
        raise ValueError("not a caption/quote template")
    fixture = media is None
    if fixture:
        (root/"sources").mkdir(exist_ok=True)
        media = root/"sources"/"generated-standin.mp4"
        _run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "gradients=size=640x360:rate=30:duration=3:c0=0x111827:c1=0x314044:x0=0:y0=0:x1=640:y1=360:seed=1", "-f", "lavfi", "-i", "sine=frequency=196:sample_rate=48000:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(media)])
        word_data = json.loads((root/"words.json").read_text())
    else:
        media = Path(media)
        word_data = json.loads(Path(words).read_text())
    metadata = probe(media)
    if not any(stream.get("codec_type") == "video" for stream in metadata["streams"]):
        raise ValueError("caption template requires a supplied video source")
    has_audio = any(stream.get("codec_type") == "audio" for stream in metadata["streams"])
    if not isinstance(word_data, dict) or not isinstance(word_data.get("words"), list) or not word_data["words"]:
        raise ValueError("words JSON requires nonempty words with stable id/text/startUs/endUs in normalized video time")
    for word in word_data["words"]:
        if not isinstance(word, dict) or not isinstance(word.get("id"), str) or not word["id"] or not isinstance(word.get("text"), str) or not word["text"].strip() or len(word["text"]) > 4096 or len(word["id"]) > 256 or any(type(word.get(k)) is not int for k in ("startUs", "endUs")) or not 0 <= word["startUs"] < word["endUs"]:
            raise ValueError("invalid stable word identity, text or integer source clock")
    if len({word["id"] for word in word_data["words"]}) != len(word_data["words"]):
        raise ValueError("word IDs must be unique")
    duration_us = round(Fraction(metadata.get("format", {}).get("duration", "0"))*1_000_000)
    if any(word["endUs"] > duration_us for word in word_data["words"]):
        raise ValueError("word anchor falls outside supplied source")
    create_project(root, root/"composition.json")
    project = Project(root)
    project.register_source(media, expected_revision=0, receipt={"kind":"generated-fixture" if fixture else "user-supplied", "wordTiming":"user normalized video-time anchors; not independently certified"})
    source = project.read()["sources"][0]
    if any(word["endUs"] > source["durationUs"] for word in word_data["words"]):
        raise ValueError("word anchor falls outside supplied source")
    baseline = {"schemaVersion":"vibeedit.localWords.v1", "sourceSha256":source["sha256"], "clock":"video-relative", "words":word_data["words"], "provenance":{"kind":"synthetic-layout-fixture" if fixture else "user-supplied", "speakerIdentity":"unresolved", "timingIndependentlyCertified":False}}
    baseline_path = root/"words-baseline.json"
    atomic_json(baseline_path, baseline)
    project.import_analysis(source["id"], baseline_path, service="local-caption-input", job_id="local-"+file_digest(baseline_path)[:24], schema_version=baseline["schemaVersion"], expected_revision=project.read()["revision"])
    baseline_id = project.read()["analysis"][0]["id"]
    rate = Fraction(spec["canvas"]["frameRate"]["numerator"], spec["canvas"]["frameRate"]["denominator"])
    frames = max(1, round(Fraction(source["durationUs"],1_000_000)*rate))
    def frame(value):
        return round(Fraction(value,1_000_000)*rate)
    spec["durationFrames"] = frames
    spec["sources"] = [{"id":source["id"], "kind":"video", "uri":source["path"], "identity":{"algorithm":"sha256", "value":source["sha256"]}, "durationFrames":frames, "metadata":{"nativeClock":source["clock"]}}]
    component = "vibeedit://text/caption-rail"
    spec["timeline"]["tracks"] = [
      {"id":"V1","kind":"video","order":0,"items":[{"id":"source-clip","kind":"video","placement":{"startFrame":0,"durationFrames":frames},"source":{"sourceId":source["id"],"inFrame":0,"durationFrames":frames},"effects":[]}]},
      {"id":"M1","kind":"motion","order":10,"items":[{"id":"caption-"+str(index),"kind":"motion","placement":{"startFrame":frame(word["startUs"]),"durationFrames":max(1,frame(word["endUs"])-frame(word["startUs"]))},"componentId":component,"props":{"text":word["text"],"accent":"#ffffff" if spec["id"] == "dialogue-quote" else "#ecff4d","background":"rgba(8,10,14,.88)"},"renderer":"html","transparent":True,"metadata":{"reviewWord":{"sourceId":source["id"],"baselineId":baseline_id,"targetId":word["id"]},"sourceStartUs":word["startUs"],"sourceEndUs":word["endUs"]}} for index,word in enumerate(word_data["words"])]}
    ]
    if has_audio:
        spec["timeline"]["tracks"].append({"id": "A1", "kind": "audio", "order": 0, "items": [{"id": "source-dialogue", "kind": "audio", "placement": {"startFrame": 0, "durationFrames": frames}, "source": {"sourceId": source["id"], "inFrame": 0, "durationFrames": frames}, "gainDb": 0}]})
    spec["verification"].update(durationFrames=frames, hasAudio=has_audio)
    spec.setdefault("metadata", {}).update(templateSource={"sourceId":source["id"],"sourceSha256":source["sha256"],"baselineId":baseline_id,"fixture":fixture,"speakerIdentity":"unresolved","sourceClock":"normalized video microseconds; original native census retained"})
    validate_composition(spec)
    atomic_json(root/"composition.json", spec)
    project.snapshot()
    atomic_json(root/".vibeedit"/"caption-template-ready.json", {"sourceId":source["id"],"sourceSha256":source["sha256"],"baselineId":baseline_id,"initialCompositionSha256":file_digest(root/"composition.json")})
    return root/"composition.json"


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
    (root/"segmentation-needs-review.json").write_text(json.dumps({"ok":False,"state":"needs-review","candidate":"artifacts/sam-mask.json","meaning":"Packaged SAM 2.1 candidate generation only; no visible mask effect or SAM 3.1 proof","action":"Inspect source identity/candidates. For an actual subject effect use models run sam21 or explicit sam31-mlx, review source/index-bound candidates, then models effect. See EDITING.md."},indent=2)+"\n")
    return None


def _generate_declared_sources(root: Path, spec) -> None:
    sources = root / "sources"
    sources.mkdir(exist_ok=True)
    duration = spec["durationFrames"] / (spec["canvas"]["frameRate"]["numerator"] / spec["canvas"]["frameRate"]["denominator"])
    video_index = 0
    for source in spec["sources"]:
        path = root / source["uri"]
        if source["kind"] == "video":
            if spec["id"] == "fan-edit":
                source_filter = f"testsrc2=size={spec['canvas']['width']}x{spec['canvas']['height']}:rate=30:duration={duration:.6f},hue=h={video_index * 47}:s=1.35,eq=contrast=1.1:brightness=-0.04"
            else:
                pattern = "testsrc2" if source["id"].endswith("a") or source["id"] in {"source", "subject"} else "smptebars"
                source_filter = f"{pattern}=size={spec['canvas']['width']}x{spec['canvas']['height']}:rate=30:duration={duration:.6f}"
            _run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source_filter, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)])
            video_index += 1
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
