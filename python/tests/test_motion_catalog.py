import json

from vibeedit import list_motion_components
from vibeedit.data import data_path
from vibeedit.motion import document_for_frame


def _spec(identifier):
    return {
        "canvas": {"width": 640, "height": 360},
        "timeline": {"tracks": [{"order": 0, "items": [{"id": "motion", "kind": "motion", "placement": {"startFrame": 0, "durationFrames": 60}, "componentId": identifier, "props": {}}]}]},
    }


def test_all_portable_motion_components_seek_deterministically():
    components = list_motion_components()
    assert len(components) == 74
    assert len({component["id"] for component in components}) == 74
    for component in components:
        early = document_for_frame(_spec(component["id"]), 2)
        late = document_for_frame(_spec(component["id"]), 42)
        assert early == document_for_frame(_spec(component["id"]), 2)
        assert early != late
        assert "data-vibeedit-component=" in early
        assert "<script" not in early
        assert "http://" not in early and "https://" not in early


def test_motion_validation_report_records_both_runtimes():
    report = json.loads(data_path("catalog", "motion-validation.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["cases"] == 74
    assert len(report["javascriptSha256"]) == 64
    assert len(report["pythonSha256"]) == 64
