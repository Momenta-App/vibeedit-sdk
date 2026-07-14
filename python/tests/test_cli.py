import json
from pathlib import Path

from vibeedit.cli import main


def test_init_and_validate(tmp_path: Path, capsys):
    path = tmp_path / "composition.json"
    assert main(["init", str(path), "--width", "320", "--height", "180", "--frames", "12", "--json"]) == 0
    assert main(["validate", str(path), "--json"]) == 0
    lines = capsys.readouterr().out
    assert '"ok": true' in lines


def test_doctor_json(capsys):
    result = main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert result in {0, 1}
    assert payload["version"] == 1
    assert any(item["id"] == "media.render" for item in payload["capabilities"])

