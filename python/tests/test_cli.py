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
    assert payload["readiness"]["level"] in {"core-ready", "core-unavailable"}
    assert "meaning" in payload["readiness"]
    assert any(item["id"] == "media.render" for item in payload["capabilities"])


def test_catalog_search_supports_token_efficient_results(capsys):
    assert main(["catalog", "search", "text", "--compact", "--limit", "2", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 2
    assert set(payload[0]) == {"id", "name", "intent", "category", "requiredCapability", "backends", "determinism", "parameterCount", "preview", "compatibility", "estimatedSetupCost", "estimatedRenderCost", "setupRequirements", "confidence", "reason"}


def test_catalog_search_filters_category_capability_and_platform(capsys):
    assert main(["catalog", "search", "impact", "--category", "sfx", "--capability", "audio", "--platform", "current", "--compact", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["id"] for item in payload] == ["vibeedit://sfx/impact-procedural"]


def test_examples_list_explains_requirements(capsys):
    assert main(["examples", "list", "--details", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(item["id"] == "basic-generated" and item["recommended"] for item in payload)
    assert all("requirements" in item and "description" in item for item in payload)


def test_missing_composition_has_actionable_json_error(capsys):
    assert main(["render", "missing.json", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "CompositionSpec not found: missing.json"
    assert "vibeedit init" in payload["hint"]


def test_setup_requires_an_explicit_capability(capsys):
    assert main(["setup", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "No optional capability selected"
    assert "--browser" in payload["hint"]


def test_revision_plan_explains_bounded_work(tmp_path: Path, capsys):
    previous = json.loads((Path(__file__).parents[2] / "schema" / "fixtures" / "mixed.json").read_text())
    previous["durationFrames"] = 30
    previous["timeline"]["tracks"][1]["items"][0]["placement"] = {"startFrame": 10, "durationFrames": 10}
    previous["verification"]["durationFrames"] = 30
    revised = json.loads(json.dumps(previous))
    revised["timeline"]["tracks"][1]["items"][0]["props"]["text"] = "REVISED"
    previous_path = tmp_path / "previous.json"
    revised_path = tmp_path / "revised.json"
    previous_path.write_text(json.dumps(previous))
    revised_path.write_text(json.dumps(revised))

    assert main(["revision", "plan", str(previous_path), str(revised_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dirtyFrameRanges"] == [{"startFrame": 10, "endFrame": 20}]
    assert payload["executionStatus"] == "verified-frame-cache"


def test_doctor_human_output_is_a_summary(capsys):
    assert main(["doctor"]) in {0, 1}
    output = capsys.readouterr().out
    assert output.startswith("VibeEdit doctor:")
    assert "Use `vibeedit doctor --json`" in output


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
