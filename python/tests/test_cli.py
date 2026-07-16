import json
from pathlib import Path
from unittest.mock import patch

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


def test_catalog_open_stays_in_background_by_default(capsys):
    with patch("vibeedit.cli.webbrowser.open") as browser:
        assert main(["catalog", "open", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    browser.assert_not_called()
    assert payload["opened"] is False
    assert Path(payload["path"]).is_file()


def test_catalog_open_requires_explicit_browser_flag(capsys):
    with patch("vibeedit.cli.webbrowser.open", return_value=True) as browser:
        assert main(["catalog", "open", "--browser", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    browser.assert_called_once()
    assert payload["opened"] is True
