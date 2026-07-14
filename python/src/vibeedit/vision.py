from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from vibeedit.spec import JSONObject
from vibeedit.spec import Mask
from vibeedit.spec import TrackingArtifact
from vibeedit.cache import cache_key
from vibeedit.cache import cache_root
from vibeedit.cache import restore_cached_artifact
from vibeedit.cache import store_cached_artifact
from vibeedit.version import VERSION


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    x: float
    y: float
    width: float
    height: float

    def to_spec(self) -> JSONObject:
        return {"label": self.label, "confidence": self.confidence, "x": self.x, "y": self.y, "width": self.width, "height": self.height}


class CapabilityRouter:
    def status(self) -> list[JSONObject]:
        apple = _apple_provider()
        apple_capabilities = apple[1] if apple else set()
        opencv_ready = importlib.util.find_spec("cv2") is not None
        object_model = _object_provider()
        sam = _sam_provider()
        return [
            {"id": "vision.face", "available": "face" in apple_capabilities or opencv_ready, "provider": "apple-vision" if "face" in apple_capabilities else "opencv-haar" if opencv_ready else None, "detail": "Face detection", "setup": None if "face" in apple_capabilities or opencv_ready else 'Install with: pip install "vibeedit[vision]".'},
            {"id": "vision.face_tracking", "available": opencv_ready, "provider": "opencv-haar-centroid" if opencv_ready else None, "detail": "Deterministic temporal face tracking", "setup": None if opencv_ready else 'Install with: pip install "vibeedit[vision]".'},
            {"id": "vision.body", "available": "body" in apple_capabilities or opencv_ready, "provider": "apple-vision" if "body" in apple_capabilities else "opencv-hog-person" if opencv_ready else None, "detail": "Person/body bounding-box detection", "setup": None if "body" in apple_capabilities or opencv_ready else 'Install with: pip install "vibeedit[vision]".'},
            {"id": "vision.pose", "available": "pose" in apple_capabilities, "provider": "apple-vision" if "pose" in apple_capabilities else None, "detail": "Body pose detection", "setup": None if "pose" in apple_capabilities else "Run `vibeedit setup --vision` on supported macOS, or configure a capability-declaring VIBEEDIT_APPLE_VISION_RUNNER."},
            {"id": "vision.object", "available": "object" in apple_capabilities or object_model is not None, "provider": "apple-vision" if "object" in apple_capabilities else object_model[1]["id"] if object_model else None, "detail": "General object detection", "setup": None if "object" in apple_capabilities or object_model else "Run `vibeedit setup --vision` to install the checksum-pinned portable ONNX detector."},
            {"id": "vision.segmentation", "available": sam is not None, "provider": sam[1]["id"] if sam else None, "detail": "Subject segmentation through a checksum-declared external SAM provider" if sam else "Subject segmentation", "setup": None if sam else 'Install with: pip install "vibeedit[sam]"; then run vibeedit setup --sam, or configure a checksum-declared external provider.'},
        ]

    def detect_faces(self, path: str | Path) -> list[Detection]:
        apple = _apple_provider()
        if apple and "face" in apple[1]:
            return [Detection(**item) for item in _apple_request(apple[0], "face", path)["detections"]]
        if importlib.util.find_spec("cv2") is not None:
            return _opencv_faces(path)
        raise RuntimeError('face detection is unavailable; install with: pip install "vibeedit[vision]"')

    def detect_bodies(self, path: str | Path) -> list[Detection]:
        apple = _apple_provider()
        if apple and "body" in apple[1]:
            return [Detection(**item) for item in _apple_request(apple[0], "body", path)["detections"]]
        if importlib.util.find_spec("cv2") is not None:
            return _opencv_bodies(path)
        raise RuntimeError('body detection is unavailable; install with: pip install "vibeedit[vision]"')

    def detect_poses(self, path: str | Path) -> list[JSONObject]:
        apple = _apple_provider()
        if apple and "pose" in apple[1]:
            return _apple_request(apple[0], "pose", path)["poses"]
        raise RuntimeError("pose detection is unavailable; run `vibeedit doctor` for provider guidance")

    def detect_objects(self, path: str | Path) -> list[Detection]:
        apple = _apple_provider()
        if apple and "object" in apple[1]:
            return [Detection(**item) for item in _apple_request(apple[0], "object", path)["detections"]]
        object_model = _object_provider()
        if object_model:
            return _onnx_objects(path, object_model[0])
        raise RuntimeError("general object detection is unavailable; run `vibeedit doctor` for provider guidance")

    def track_faces(self, path: str | Path, output: str | Path, *, sample_every_frames: int = 1) -> TrackingArtifact:
        if sample_every_frames < 1:
            raise ValueError("sample_every_frames must be at least 1")
        if importlib.util.find_spec("cv2") is None:
            raise RuntimeError('face tracking is unavailable; install with: pip install "vibeedit[vision]"')
        import cv2

        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        runtime_versions = {"opencv": cv2.__version__}
        key = cache_key("vision.face_tracking", {"sourceSha256": source_hash, "sampleEveryFrames": sample_every_frames}, implementation_version=VERSION, runtime_versions=runtime_versions)
        destination = Path(output)
        cache_hit = restore_cached_artifact("vision.face_tracking", key, destination)
        if cache_hit:
            payload = json.loads(destination.read_text(encoding="utf-8"))
            return TrackingArtifact(
                id=destination.stem,
                kind="face",
                artifact_uri=str(destination),
                start_frame=0,
                duration_frames=int(payload["frameCount"]),
                coordinate_space="normalized",
                format="vibeedit.face-tracks+json",
                provenance={"generator": "vibeedit.vision.track_faces", "implementationVersion": VERSION, "runtime": "opencv", "runtimeVersion": cv2.__version__, "parameters": {"sampleEveryFrames": sample_every_frames}, "sourceIdentities": [source_hash], "cacheKey": key, "cacheHit": True},
            )
        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            raise ValueError(f"could not decode video: {source}")
        cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
        if cascade.empty():
            capture.release()
            raise RuntimeError("OpenCV face cascade is unavailable")
        frames = []
        previous = {}
        next_id = 1
        frame_index = 0
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if frame_index % sample_every_frames == 0:
                height, width = image.shape[:2]
                detections = [Detection("face", 1.0, float(x / width), float(y / height), float(w / width), float(h / height)) for x, y, w, h in cascade.detectMultiScale(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))]
                tracked, previous, next_id = _assign_track_ids(detections, previous, next_id)
                frames.append({"frame": frame_index, "detections": tracked})
            frame_index += 1
        capture.release()
        if frame_index == 0:
            raise ValueError(f"video contained no decodable frames: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({"schemaVersion": "1.0.0", "kind": "face_tracking", "coordinateSpace": "normalized", "sourceName": source.name, "sourceSha256": source_hash, "sampleEveryFrames": sample_every_frames, "frameCount": frame_index, "frames": frames}, indent=2) + "\n", encoding="utf-8")
        store_cached_artifact("vision.face_tracking", key, destination)
        return TrackingArtifact(
            id=destination.stem,
            kind="face",
            artifact_uri=str(destination),
            start_frame=0,
            duration_frames=frame_index,
            coordinate_space="normalized",
            format="vibeedit.face-tracks+json",
            provenance={"generator": "vibeedit.vision.track_faces", "implementationVersion": VERSION, "runtime": "opencv", "runtimeVersion": cv2.__version__, "parameters": {"sampleEveryFrames": sample_every_frames}, "sourceIdentities": [source_hash], "cacheKey": key, "cacheHit": False},
        )

    def segment(self, path: str | Path, output: str | Path, *, duration_frames: int, prompt: JSONObject | None = None) -> Mask:
        provider = _sam_provider()
        if not provider:
            raise RuntimeError("segmentation is unavailable; run `vibeedit doctor` for SAM setup guidance")
        if duration_frames < 1:
            raise ValueError("duration_frames must be at least one")
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        command, manifest = provider
        parameters = prompt or {"mode": "automatic-subject"}
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        model = {key: manifest[key] for key in ["id", "version", "weightsSha256"]}
        if manifest.get("sourceRevision"):
            model["sourceRevision"] = manifest["sourceRevision"]
        declared_runtime = manifest.get("runtimeVersions") if isinstance(manifest.get("runtimeVersions"), dict) else {}
        key = cache_key("vision.segmentation", {"sourceSha256": source_hash, "model": model, "parameters": parameters, "durationFrames": duration_frames}, implementation_version=VERSION, runtime_versions={"provider": manifest["id"], "model": manifest["version"], **declared_runtime})
        cache_hit = bool(declared_runtime) and destination.suffix == ".json" and restore_cached_artifact("vision.segmentation", key, destination)
        if not cache_hit:
            result = subprocess.run([*command, "segment", str(source), str(destination), json.dumps(parameters, sort_keys=True, separators=(",", ":"))], capture_output=True, text=True, check=False)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "SAM segmentation runner failed")
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("SAM segmentation runner returned without a non-empty artifact")
        runtime = {}
        if destination.suffix == ".json":
            try:
                payload = json.loads(destination.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise RuntimeError("SAM segmentation runner returned invalid JSON") from error
            if isinstance(payload, dict) and isinstance(payload.get("runtime"), dict):
                runtime = {str(key): str(value) for key, value in payload["runtime"].items() if isinstance(value, (str, int, float, bool))}
            if cache_hit and (runtime != {str(key): str(value) for key, value in declared_runtime.items()} or len(payload.get("frames", [])) != duration_frames):
                (cache_root() / "artifacts" / "vision" / "segmentation" / f"{key}{destination.suffix}").unlink(missing_ok=True)
                destination.unlink()
                return self.segment(source, output, duration_frames=duration_frames, prompt=prompt)
        key = cache_key("vision.segmentation", {"sourceSha256": source_hash, "model": model, "parameters": parameters, "durationFrames": duration_frames}, implementation_version=VERSION, runtime_versions={"provider": manifest["id"], "model": manifest["version"], **runtime})
        if not cache_hit and destination.is_file():
            store_cached_artifact("vision.segmentation", key, destination)
        return Mask(
            id=destination.stem,
            kind="rle" if destination.suffix == ".json" else "image_sequence",
            start_frame=0,
            duration_frames=duration_frames,
            artifact_uri=str(destination),
            format="vibeedit.sam-mask+json" if destination.suffix == ".json" else "image/png",
            provenance={"generator": "vibeedit.vision.segment", "implementationVersion": VERSION, "model": manifest["id"], "modelVersion": manifest["version"], "runtime": "external-runner", "runtimeVersions": runtime, "parameters": parameters, "sourceIdentities": [source_hash], "cacheKey": key, "cacheHit": cache_hit},
        )


def _opencv_faces(path: str | Path) -> list[Detection]:
    import cv2

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"could not decode image: {path}")
    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
    if cascade.empty():
        raise RuntimeError("OpenCV face cascade is unavailable")
    height, width = image.shape[:2]
    faces = cascade.detectMultiScale(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    return [Detection("face", 1.0, float(x / width), float(y / height), float(w / width), float(h / height)) for x, y, w, h in faces]


def _opencv_bodies(path: str | Path) -> list[Detection]:
    import cv2

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"could not decode image: {path}")
    height, width = image.shape[:2]
    detector = cv2.HOGDescriptor()
    detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    boxes, weights = detector.detectMultiScale(image, winStride=(8, 8), padding=(8, 8), scale=1.05)
    return [Detection("person", float(weight), float(x / width), float(y / height), float(w / width), float(h / height)) for (x, y, w, h), weight in zip(boxes, weights)]


def _onnx_objects(path: str | Path, model: Path, *, minimum_confidence: float = 0.35) -> list[Detection]:
    import numpy
    import onnxruntime
    from PIL import Image

    with Image.open(path) as source:
        image = source.convert("RGB")
    values = numpy.expand_dims(numpy.asarray(image, dtype=numpy.uint8), axis=0)
    session = onnxruntime.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    outputs = dict(zip((item.name for item in session.get_outputs()), session.run(None, {session.get_inputs()[0].name: values})))
    count = int(outputs["num_detections"][0])
    return [
        Detection(_coco_label(int(class_id)), float(score), *_normalized_box(box))
        for box, class_id, score in zip(outputs["detection_boxes"][0][:count], outputs["detection_classes"][0][:count], outputs["detection_scores"][0][:count])
        if float(score) >= minimum_confidence
    ]


def _normalized_box(box) -> tuple[float, float, float, float]:
    x = max(0.0, min(1.0, float(box[1])))
    y = max(0.0, min(1.0, float(box[0])))
    right = max(x, min(1.0, float(box[3])))
    bottom = max(y, min(1.0, float(box[2])))
    return x, y, right - x, bottom - y


def _coco_label(identifier: int) -> str:
    return {
        1: "person", 2: "bicycle", 3: "car", 4: "motorcycle", 5: "airplane", 6: "bus", 7: "train", 8: "truck", 9: "boat", 10: "traffic light", 11: "fire hydrant", 13: "stop sign", 14: "parking meter", 15: "bench", 16: "bird", 17: "cat", 18: "dog", 19: "horse", 20: "sheep", 21: "cow", 22: "elephant", 23: "bear", 24: "zebra", 25: "giraffe", 27: "backpack", 28: "umbrella", 31: "handbag", 32: "tie", 33: "suitcase", 34: "frisbee", 35: "skis", 36: "snowboard", 37: "sports ball", 38: "kite", 39: "baseball bat", 40: "baseball glove", 41: "skateboard", 42: "surfboard", 43: "tennis racket", 44: "bottle", 46: "wine glass", 47: "cup", 48: "fork", 49: "knife", 50: "spoon", 51: "bowl", 52: "banana", 53: "apple", 54: "sandwich", 55: "orange", 56: "broccoli", 57: "carrot", 58: "hot dog", 59: "pizza", 60: "donut", 61: "cake", 62: "chair", 63: "couch", 64: "potted plant", 65: "bed", 67: "dining table", 70: "toilet", 72: "tv", 73: "laptop", 74: "mouse", 75: "remote", 76: "keyboard", 77: "cell phone", 78: "microwave", 79: "oven", 80: "toaster", 81: "sink", 82: "refrigerator", 84: "book", 85: "clock", 86: "vase", 87: "scissors", 88: "teddy bear", 89: "hair drier", 90: "toothbrush",
    }.get(identifier, f"coco-{identifier}")


def _apple_request(runner: Path, operation: str, path: str | Path) -> JSONObject:
    result = subprocess.run([*_runner_command(runner), operation, str(path)], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"Apple Vision {operation} request failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Apple Vision runner returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Apple Vision runner returned a non-object response")
    return payload


def _apple_provider() -> tuple[Path, set[str]] | None:
    configured = os.environ.get("VIBEEDIT_APPLE_VISION_RUNNER")
    runner = Path(configured) if configured else cache_root() / "runtimes" / "apple-vision" / "vibeedit-apple-vision"
    if not runner.is_file() or (os.name != "nt" and not os.access(runner, os.X_OK)):
        return None
    result = subprocess.run([*_runner_command(runner), "capabilities"], capture_output=True, text=True, check=False)
    if result.returncode:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    capabilities = payload.get("capabilities") if isinstance(payload, dict) else None
    if not isinstance(capabilities, list) or any(not isinstance(item, str) for item in capabilities):
        return None
    declared = set(capabilities) & {"face", "body", "pose", "object"}
    return (runner, declared) if declared else None


def _runner_command(runner: Path) -> tuple[str, ...]:
    return (sys.executable, str(runner)) if os.name == "nt" and runner.suffix.casefold() == ".py" else (str(runner),)


def _assign_track_ids(detections: list[Detection], previous: dict[int, tuple[float, float]], next_id: int) -> tuple[list[JSONObject], dict[int, tuple[float, float]], int]:
    available = dict(previous)
    tracked = []
    current = {}
    for detection in sorted(detections, key=lambda item: (item.x, item.y, item.width, item.height)):
        center = (detection.x + detection.width / 2, detection.y + detection.height / 2)
        candidates = sorted(((abs(center[0] - value[0]) + abs(center[1] - value[1]), track_id) for track_id, value in available.items()))
        track_id = candidates[0][1] if candidates and candidates[0][0] <= 0.2 else next_id
        if track_id == next_id:
            next_id += 1
        available.pop(track_id, None)
        current[track_id] = center
        tracked.append({"trackId": track_id, **detection.to_spec()})
    return tracked, current, next_id


def _sam_provider() -> tuple[tuple[str, ...], JSONObject] | None:
    runner_value = os.environ.get("VIBEEDIT_SAM_RUNNER")
    manifest_value = os.environ.get("VIBEEDIT_SAM_MODEL_MANIFEST")
    packaged = not runner_value or not manifest_value
    if not runner_value or not manifest_value:
        installed = cache_root() / "models" / "sam2.1-hiera-tiny" / "model.json"
        if installed.is_file():
            manifest_value = str(installed)
            try:
                runner_value = str(json.loads(installed.read_text(encoding="utf-8"))["runner"])
            except (KeyError, OSError, json.JSONDecodeError):
                return None
        else:
            return None
    if packaged and any(importlib.util.find_spec(module) is None for module in ["numpy", "cv2", "torch", "torchvision", "hydra", "iopath", "tqdm"]):
        return None
    runner = Path(runner_value)
    manifest_path = Path(manifest_value)
    if not runner.is_file() or not manifest_path.is_file() or (not packaged and os.name != "nt" and not os.access(runner, os.X_OK)):
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("capability") not in {"sam.2.1", "sam.3.1"}:
        return None
    if not all(isinstance(manifest.get(key), str) and manifest[key] for key in ("id", "version", "license")):
        return None
    if not isinstance(manifest.get("weightsSha256"), str) or len(manifest["weightsSha256"]) != 64 or any(character not in "0123456789abcdefABCDEF" for character in manifest["weightsSha256"]):
        return None
    if packaged:
        checkpoint = Path(str(manifest.get("checkpoint", "")))
        source = Path(str(manifest.get("source", "")))
        if not checkpoint.is_file() or checkpoint.stat().st_size != manifest.get("weightsBytes") or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != manifest.get("weightsSha256") or not (source / "sam2").is_dir():
            return None
        command = manifest.get("runnerCommand")
        if not isinstance(command, list) or len(command) != 2 or any(not isinstance(value, str) or not value for value in command) or not Path(command[0]).is_file() or Path(command[1]) != runner:
            return None
        return tuple(command), manifest
    return _runner_command(runner), manifest


def _object_provider() -> tuple[Path, JSONObject] | None:
    manifest_path = cache_root() / "models" / "ssd-mobilenet-v1-12" / "model.json"
    if not manifest_path.is_file() or any(importlib.util.find_spec(module) is None for module in ["numpy", "PIL", "onnxruntime"]):
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    model = Path(str(manifest.get("checkpoint", "")))
    if manifest.get("capability") != "vision.object" or manifest.get("id") != "ssd-mobilenet-v1-12" or manifest.get("weightsSha256") != "b8fba5e404077d4048d27fcd1667e85e27e192eb9bf51e696c46a3acd7d21058":
        return None
    if not model.is_file() or model.stat().st_size != manifest.get("weightsBytes") or hashlib.sha256(model.read_bytes()).hexdigest() != manifest.get("weightsSha256"):
        return None
    return model, manifest
