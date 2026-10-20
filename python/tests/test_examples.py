import shutil
import subprocess
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
        # Metadata alone can advertise alpha even when all pixels are opaque.
        alpha = subprocess.check_output(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", str(output), "-vf", "alphaextract", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"])
        assert len(alpha) == 320 * 180 * 60
        assert min(alpha) == 0 and max(alpha) > 200
        middle = alpha[30 * 320 * 180:31 * 320 * 180]
        visible = [index for index, value in enumerate(middle) if value > 8]
        assert visible
        assert min(index % 320 for index in visible) > 4
        assert max(index % 320 for index in visible) < 315
        assert min(index // 320 for index in visible) > 4
        assert max(index // 320 for index in visible) < 175
        composites = []
        for color in ["red", "blue"]:
            pixels = subprocess.check_output(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s=320x180:r=30:d=2", "-c:v", "libvpx-vp9", "-i", str(output), "-filter_complex", "[0:v][1:v]overlay=shortest=1,select='eq(n,30)',format=rgb24", "-frames:v", "1", "-f", "rawvideo", "pipe:1"])
            assert len(pixels) == 320 * 180 * 3
            composites.append(pixels)
        assert composites[0][0] > 240 and composites[0][2] < 10
        assert composites[1][0] < 10 and composites[1][2] > 240
        assert composites[0] != composites[1]


def test_sam_example_degrades_with_actionable_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VIBEEDIT_SAM_RUNNER", raising=False)
    monkeypatch.delenv("VIBEEDIT_SAM_MODEL_MANIFEST", raising=False)
    directory = tmp_path / "sam-segmentation"
    shutil.copytree(data_path("examples", "sam-segmentation"), directory)
    assert render_example(directory) is None
    evidence = (directory / "segmentation-unavailable.json").read_text(encoding="utf-8")
    assert "vibeedit setup --sam" in evidence
    assert __import__("json").loads((directory / "composition.json").read_text(encoding="utf-8"))["verification"]["hasAudio"] is False
