import hashlib
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
    assert len(components) == 50
    assert len({component["id"] for component in components}) == 50
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
    assert report["cases"] == 50
    assert len(report["javascriptSha256"]) == 64
    assert len(report["pythonSha256"]) == 64


def test_canonical_text_runtime_is_manifest_bound():
    components = list_motion_components()
    assert len([component for component in components if component.get("canonical")]) == 30
    root = data_path("catalog", "text-runtime")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == "vibeedit.canonical-text-runtime.v1"
    assert len(manifest["files"]) == 151
    for record in manifest["files"]:
        payload = (root / record["path"]).read_bytes()
        assert len(payload) == record["bytes"], record["path"]
        assert hashlib.sha256(payload).hexdigest() == record["sha256"], record["path"]


def test_canonical_seeking_uses_canvas_frame_rate():
    spec = _spec("vibeedit://text/mogrt-elegant")
    spec["canvas"]["frameRate"] = {"numerator": 24, "denominator": 1}
    assert 'data-vibeedit-time="0.500000"' in document_for_frame(spec, 12, "http://127.0.0.1:1234/")


def test_every_registered_text_effect_has_a_verified_hash_bound_preview():
    catalog = json.loads(data_path("catalog", "catalog.json").read_text(encoding="utf-8"))
    assets = json.loads(data_path("catalog", "assets.json").read_text(encoding="utf-8"))
    text = [item for item in catalog["items"] if item["id"].startswith("vibeedit://text/")]
    by_path = {asset["path"]: asset for asset in assets["assets"]}

    assert len(text) == 52
    assert len({item["id"] for item in text}) == 52
    for item in text:
        assert item["preview"]["status"] == "verified", item["id"]
        assert item["preview"]["mediaType"] == "video/mp4", item["id"]
        asset_path = f"catalog/{item['preview']['uri']}"
        assert asset_path in by_path, item["id"]
        asset = by_path[asset_path]
        payload = data_path(asset_path).read_bytes()
        assert len(payload) == asset["bytes"], item["id"]
        assert hashlib.sha256(payload).hexdigest() == asset["sha256"], item["id"]
        assert asset["redistribution"] == "verified", item["id"]
        assert asset["decodable"] is True, item["id"]
