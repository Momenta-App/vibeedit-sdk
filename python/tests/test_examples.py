import shutil
from pathlib import Path

import pytest

from vibeedit import probe
from vibeedit import create_example
from vibeedit import render_example
from vibeedit.data import data_path


def test_python_api_creates_a_packaged_example_without_overwriting(tmp_path: Path):
    directory = create_example("basic-generated", tmp_path)
    assert (directory / "composition.json").is_file()
    with pytest.raises(FileExistsError):
        create_example("basic-generated", tmp_path)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
@pytest.mark.parametrize("identifier", ["fan-edit", "beat-synchronized", "sound-design-layering", "mask-subject-effect", "multiple-transitions"])
def test_portable_workflow_example_renders_from_clean_copy(tmp_path: Path, identifier: str):
    directory = tmp_path / identifier
    shutil.copytree(data_path("examples", identifier), directory)
    output = render_example(directory)
    assert output and output.is_file() and output.stat().st_size > 0


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg is optional on the test host")
@pytest.mark.parametrize("identifier", ["face-follow-text", "transparent-motion-overlay"])
def test_browser_workflow_example_renders_from_clean_copy(tmp_path: Path, identifier: str):
    pytest.importorskip("playwright")
    directory = tmp_path / identifier
    shutil.copytree(data_path("examples", identifier), directory)
    output = render_example(directory)
    assert output and output.is_file() and output.stat().st_size > 0
    if identifier == "transparent-motion-overlay":
        video = next(stream for stream in probe(output)["streams"] if stream["codec_type"] == "video")
        assert video["codec_name"] == "vp9"
        assert video.get("tags", {}).get("alpha_mode") == "1"


def test_sam_example_degrades_with_actionable_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VIBEEDIT_SAM_RUNNER", raising=False)
    monkeypatch.delenv("VIBEEDIT_SAM_MODEL_MANIFEST", raising=False)
    directory = tmp_path / "sam-segmentation"
    shutil.copytree(data_path("examples", "sam-segmentation"), directory)
    assert render_example(directory) is None
    evidence = (directory / "segmentation-unavailable.json").read_text()
    assert "vibeedit setup --sam" in evidence
    assert __import__("json").loads((directory / "composition.json").read_text())["verification"]["hasAudio"] is False
