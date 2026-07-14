import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from vibeedit import setup as vibeedit_setup
from vibeedit.sam_runner import _box
from vibeedit.sam_runner import _prompt_box
from vibeedit.sam_runner import _rle


def test_sam_extra_declares_video_decode_runtime():
    configuration = __import__("tomllib").loads((Path(__file__).parents[2] / "pyproject.toml").read_text())
    requirements = configuration["project"]["optional-dependencies"]["sam"]
    assert any(requirement.startswith("opencv-python-headless==") for requirement in requirements)


def test_sam_setup_extracts_only_checksum_verified_payloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        payload = b"# package\n"
        member = tarfile.TarInfo("sam2-test/sam2/__init__.py")
        member.size = len(payload)
        output.addfile(member, io.BytesIO(payload))
    checkpoint = tmp_path / "tiny.pt"
    checkpoint.write_bytes(b"controlled-checkpoint")
    monkeypatch.setattr(vibeedit_setup, "SAM_SOURCE", {"revision": "test", "url": archive.as_uri(), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "bytes": archive.stat().st_size})
    monkeypatch.setattr(vibeedit_setup, "SAM_TINY", {"id": "sam2.1-hiera-tiny", "version": "test", "url": checkpoint.as_uri(), "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(), "bytes": checkpoint.stat().st_size})
    result = vibeedit_setup._setup_sam(tmp_path)
    assert result["available"] is True
    assert (tmp_path / "models" / "sam2.1-hiera-tiny" / "source" / "sam2" / "__init__.py").is_file()
    manifest = __import__("json").loads(Path(result["manifest"]).read_text())
    assert manifest["runnerCommand"][0] == __import__("sys").executable
    assert manifest["runner"].endswith("sam-runner.py")


def test_object_setup_installs_only_checksum_verified_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    model = tmp_path / "controlled.onnx"
    model.write_bytes(b"controlled-object-model")
    monkeypatch.setattr(vibeedit_setup, "_onnx_runtime_supported", lambda: True)
    monkeypatch.setattr(vibeedit_setup, "OBJECT_MODEL", {"id": "ssd-mobilenet-v1-12", "version": "test", "url": model.as_uri(), "sha256": hashlib.sha256(model.read_bytes()).hexdigest(), "bytes": model.stat().st_size})
    result = vibeedit_setup._setup_object_model(tmp_path / "cache")
    assert result["available"] is True
    assert Path(result["manifest"]).is_file()


def test_object_setup_degrades_without_a_supported_onnx_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vibeedit_setup, "_onnx_runtime_supported", lambda: False)
    result = vibeedit_setup._setup_object_model(tmp_path / "cache")
    assert result["available"] is False
    assert result["status"] == "unsupported-platform"
    assert not (tmp_path / "cache" / "models").exists()


def test_sam_runner_box_and_rle_contract():
    numpy = pytest.importorskip("numpy")
    assert _box([0.25, 0.25, 0.75, 0.75], 100, 80) == [25, 20, 75, 60]
    assert _prompt_box({"boxNormalized": [0.1, 0.2, 0.9, 0.8]}, 100, 80) == [10, 16, 90, 64]
    assert _prompt_box({"box": [10, 20, 90, 70]}, 100, 80) == [10, 20, 90, 70]
    assert _rle(numpy.array([[0, 0, 1], [1, 0, 0]], dtype=numpy.uint8)) == [2, 2, 2]


def test_apple_vision_setup_builds_capability_declaring_runner(tmp_path: Path):
    if __import__("platform").system() != "Darwin" or __import__("shutil").which("swift") is None:
        pytest.skip("Apple Vision setup requires macOS and Swift")
    result = vibeedit_setup._setup_apple_vision(tmp_path)
    runner = Path(result["runner"])
    assert result["capabilities"] == ["face", "body", "pose"]
    assert runner.is_file()
    assert len(result["sha256"]) == 64
