import importlib.util
from pathlib import Path

import pytest

from vibeedit.data import data_path
from vibeedit.capabilities import doctor
from vibeedit.vision import CapabilityRouter
from vibeedit.vision import Detection
from vibeedit.vision import _assign_track_ids
from vibeedit.vision import _coco_label
from vibeedit.vision import _normalized_box


def test_sam21_is_checksum_pinned_and_sam31_remains_quarantined():
    manifest = __import__("json").loads(data_path("runtime-models", "manifest.json").read_text())
    models = {item["capability"]: item for item in manifest["models"]}
    assert models["sam.2.1"]["status"] == "optional-download"
    assert all(len(file["sha256"]) == 64 and file["bytes"] > 0 for file in models["sam.2.1"]["files"])
    assert models["sam.3.1"]["status"] == "quarantined"


def test_router_does_not_infer_capabilities_from_platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "empty-cache"))
    monkeypatch.delenv("VIBEEDIT_APPLE_VISION_RUNNER", raising=False)
    monkeypatch.delenv("VIBEEDIT_SAM_RUNNER", raising=False)
    monkeypatch.delenv("VIBEEDIT_SAM_MODEL_MANIFEST", raising=False)
    statuses = {item["id"]: item for item in CapabilityRouter().status()}
    assert statuses["vision.pose"]["available"] is False
    assert statuses["vision.segmentation"]["available"] is False
    assert statuses["vision.body"]["available"] is (importlib.util.find_spec("cv2") is not None)


def test_apple_runner_uses_only_explicit_capabilities(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runner = tmp_path / "apple-vision.py"
    runner.write_text("""#!/usr/bin/env python3
import json, sys
if sys.argv[1] == "capabilities": print(json.dumps({"capabilities":["face","body","pose"]}))
elif sys.argv[1] == "pose": print(json.dumps({"poses":[]}))
else: print(json.dumps({"detections":[]}))
""")
    runner.chmod(0o755)
    image = tmp_path / "image.png"
    image.write_bytes(b"controlled")
    monkeypatch.setenv("VIBEEDIT_APPLE_VISION_RUNNER", str(runner))
    statuses = {item["id"]: item for item in CapabilityRouter().status()}
    assert statuses["vision.face"]["provider"] == "apple-vision"
    assert statuses["vision.body"]["provider"] == "apple-vision"
    assert statuses["vision.pose"]["available"] is True
    assert statuses["vision.object"]["available"] is False
    assert CapabilityRouter().detect_faces(image) == []
    assert CapabilityRouter().detect_bodies(image) == []
    assert CapabilityRouter().detect_poses(image) == []
    with pytest.raises(RuntimeError, match="general object detection is unavailable"):
        CapabilityRouter().detect_objects(image)


def test_opencv_face_provider_executes_on_real_image(tmp_path: Path):
    cv2 = pytest.importorskip("cv2")
    import numpy

    path = tmp_path / "blank.png"
    cv2.imwrite(str(path), numpy.zeros((128, 128, 3), dtype=numpy.uint8))
    assert CapabilityRouter().detect_faces(path) == []


def test_opencv_body_provider_executes_on_real_image(tmp_path: Path):
    cv2 = pytest.importorskip("cv2")
    import numpy

    path = tmp_path / "blank.png"
    cv2.imwrite(str(path), numpy.zeros((256, 128, 3), dtype=numpy.uint8))
    assert CapabilityRouter().detect_bodies(path) == []


def test_face_track_assignment_is_stable():
    first, previous, next_id = _assign_track_ids([Detection("face", 1, 0.1, 0.1, 0.2, 0.2)], {}, 1)
    second, _, _ = _assign_track_ids([Detection("face", 1, 0.12, 0.1, 0.2, 0.2)], previous, next_id)
    assert first[0]["trackId"] == second[0]["trackId"] == 1


def test_coco_object_labels_are_stable():
    assert _coco_label(1) == "person"
    assert _coco_label(62) == "chair"
    assert _coco_label(999) == "coco-999"
    assert _normalized_box([-0.2, -0.1, 1.4, 1.2]) == (0.0, 0.0, 1.0, 1.0)


def test_opencv_face_tracker_writes_artifact_and_reuses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cv2 = pytest.importorskip("cv2")
    import numpy

    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "cache"))
    source = tmp_path / "blank.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (128, 128))
    if not writer.isOpened():
        pytest.skip("OpenCV video writer is unavailable")
    for _ in range(10):
        writer.write(numpy.zeros((128, 128, 3), dtype=numpy.uint8))
    writer.release()
    artifact = CapabilityRouter().track_faces(source, tmp_path / "tracks.json", sample_every_frames=2)
    payload = __import__("json").loads(Path(artifact.artifact_uri).read_text())
    assert artifact.duration_frames == 10
    assert len(payload["frames"]) == 5
    assert artifact.provenance["cacheKey"]
    assert artifact.provenance["cacheHit"] is False
    cached = CapabilityRouter().track_faces(source, tmp_path / "tracks-cached.json", sample_every_frames=2)
    assert cached.provenance["cacheHit"] is True
    assert cached.provenance["cacheKey"] == artifact.provenance["cacheKey"]
    assert Path(cached.artifact_uri).read_bytes() == Path(artifact.artifact_uri).read_bytes()


def test_checksum_declared_external_sam_provider_executes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import json

    runner = tmp_path / "sam-runner.py"
    runner.write_text("#!/usr/bin/env python3\nimport json, pathlib, sys\npathlib.Path(sys.argv[3]).write_text(json.dumps({'format':'rle','counts':[1,2,3]}))\n")
    runner.chmod(0o755)
    manifest = tmp_path / "model.json"
    manifest.write_text(json.dumps({"id": "test-sam-2.1", "capability": "sam.2.1", "version": "test-1", "license": "test-only", "weightsSha256": "a" * 64}))
    source = tmp_path / "source.mp4"
    source.write_bytes(b"controlled-test-source")
    monkeypatch.setenv("VIBEEDIT_SAM_RUNNER", str(runner))
    monkeypatch.setenv("VIBEEDIT_SAM_MODEL_MANIFEST", str(manifest))
    status = {item["id"]: item for item in CapabilityRouter().status()}
    assert status["vision.segmentation"]["available"] is True
    artifact = CapabilityRouter().segment(source, tmp_path / "mask.json", duration_frames=30)
    assert artifact.duration_frames == 30
    assert artifact.provenance["model"] == "test-sam-2.1"
    assert Path(artifact.artifact_uri).is_file()


def test_external_sam_runtime_versions_enter_provenance_and_cache_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runner = tmp_path / "sam-runner.py"
    runner.write_text("#!/usr/bin/env python3\nimport json, pathlib, sys\npathlib.Path(sys.argv[3]).write_text(json.dumps({'runtime':{'device':'mps','torch':'test'},'frames':[{'frame':0,'rle':[1]}]}))\n")
    runner.chmod(0o755)
    manifest = tmp_path / "model.json"
    manifest.write_text(__import__("json").dumps({"id": "test-sam-2.1", "capability": "sam.2.1", "version": "test-1", "license": "test-only", "weightsSha256": "a" * 64, "runtimeVersions": {"device": "mps", "torch": "test"}}))
    source = tmp_path / "source.mp4"
    source.write_bytes(b"controlled-test-source")
    monkeypatch.setenv("VIBEEDIT_SAM_RUNNER", str(runner))
    monkeypatch.setenv("VIBEEDIT_SAM_MODEL_MANIFEST", str(manifest))
    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path / "cache"))
    artifact = CapabilityRouter().segment(source, tmp_path / "mask.json", duration_frames=1)
    assert artifact.provenance["runtimeVersions"] == {"device": "mps", "torch": "test"}
    assert artifact.provenance["cacheHit"] is False
    runner.write_text("#!/bin/sh\nexit 9\n")
    cached = CapabilityRouter().segment(source, tmp_path / "mask-2.json", duration_frames=1)
    assert cached.provenance["cacheHit"] is True
    assert artifact.provenance["cacheKey"] == cached.provenance["cacheKey"]
    assert Path(cached.artifact_uri).read_bytes() == Path(artifact.artifact_uri).read_bytes()


def test_external_sam_requires_checksum_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runner = tmp_path / "sam-runner"
    runner.write_text("#!/bin/sh\nexit 0\n")
    runner.chmod(0o755)
    manifest = tmp_path / "model.json"
    manifest.write_text('{"id":"unsafe","capability":"sam.2.1","version":"1","license":"unknown"}')
    monkeypatch.setenv("VIBEEDIT_SAM_RUNNER", str(runner))
    monkeypatch.setenv("VIBEEDIT_SAM_MODEL_MANIFEST", str(manifest))
    assert next(item for item in CapabilityRouter().status() if item["id"] == "vision.segmentation")["available"] is False


def test_external_sam31_label_cannot_bypass_quarantine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runner = tmp_path / "sam31-runner"
    runner.write_text("#!/bin/sh\nexit 0\n")
    runner.chmod(0o755)
    manifest = tmp_path / "sam31-model.json"
    manifest.write_text(__import__("json").dumps({"id": "unverified-sam-3.1", "capability": "sam.3.1", "version": "3.1", "license": "declared-but-unaudited", "weightsSha256": "a" * 64}))
    monkeypatch.setenv("VIBEEDIT_SAM_RUNNER", str(runner))
    monkeypatch.setenv("VIBEEDIT_SAM_MODEL_MANIFEST", str(manifest))

    statuses = {item["id"]: item for item in CapabilityRouter().status()}
    assert statuses["vision.segmentation"]["available"] is False
    capabilities = {item["id"]: item for item in doctor()["capabilities"]}
    assert capabilities["sam.3.1"]["available"] is False
    assert capabilities["sam.3.1"]["provider"] is None
