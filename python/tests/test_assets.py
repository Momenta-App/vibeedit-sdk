import hashlib
import json
import shutil
import subprocess

import pytest

from vibeedit.data import data_path


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="FFprobe is optional on the test host")
def test_all_distributed_media_assets_match_provenance_and_decode():
    assets = json.loads(data_path("catalog", "assets.json").read_text())["assets"]
    assert assets
    for asset in assets:
        path = data_path(asset["path"])
        assert path.is_file() and path.stat().st_size == asset["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
        assert asset["redistribution"] == "verified"
        assert asset["commercialOutputAllowed"] is True
        result = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
        probe = json.loads(result.stdout)
        assert probe["streams"]
        assert abs(float(probe["format"]["duration"]) - asset["durationSeconds"]) <= 0.05
        if asset["category"] == "procedural-sfx":
            assert any(stream["codec_type"] == "audio" for stream in probe["streams"])
            assert isinstance(asset["loudnessLufs"], float)
        if asset["category"] == "preview-video":
            assert any(stream["codec_type"] == "video" for stream in probe["streams"])
