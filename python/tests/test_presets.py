import hashlib
import json

import pytest

from vibeedit import apply_media_preset
from vibeedit import build_media_preset_plan
from vibeedit import get_media_preset
from vibeedit import list_media_presets
from vibeedit import render_transition_preset
from vibeedit.data import data_path


def _sample_frames(numpy):
    left = numpy.zeros((24, 32, 4), dtype=numpy.uint8)
    left[:, :, 0] = numpy.arange(32, dtype=numpy.uint8)[None, :] * 7
    left[:, :, 1] = numpy.arange(24, dtype=numpy.uint8)[:, None] * 10
    left[:, :, 2] = 128
    left[:, :, 3] = 255
    right = numpy.zeros_like(left)
    right[:, :, 0] = 20
    right[:, :, 1] = 80
    right[:, :, 2] = 220
    right[:, :, 3] = 255
    return left, right


def test_imported_catalog_is_complete_and_public():
    presets = list_media_presets()
    assert len(presets) == 333
    assert {kind: len(list_media_presets(kind)) for kind in ("filter", "effect", "transition")} == {
        "filter": 200,
        "effect": 112,
        "transition": 21,
    }
    assert len({preset["id"] for preset in presets}) == 333
    assert all(preset["id"].startswith(("vibeedit://effect/", "vibeedit://transition/")) for preset in presets)
    assert all(preset["qualityTier"] == "professional" for preset in presets)
    assert all(preset["productionReview"]["status"] == "reviewed" for preset in presets)
    assert all(preset["deterministicFlow"]["entrypoint"].startswith("vibeedit.presets.") for preset in presets)


def test_all_imported_effects_execute_deterministically():
    numpy = pytest.importorskip("numpy")
    image, _ = _sample_frames(numpy)
    for preset in [*list_media_presets("filter"), *list_media_presets("effect")]:
        first = apply_media_preset(image, preset["id"], progress=0.4)
        second = apply_media_preset(image, preset["id"], progress=0.4)
        assert first.shape == image.shape
        assert first.dtype == numpy.uint8
        assert numpy.array_equal(first, second), preset["id"]


def test_all_imported_transitions_execute_deterministically():
    numpy = pytest.importorskip("numpy")
    left, right = _sample_frames(numpy)
    for preset in list_media_presets("transition"):
        first = render_transition_preset(left, right, preset["id"], progress=0.55)
        second = render_transition_preset(left, right, preset["id"], progress=0.55)
        assert first.shape == left.shape
        assert first.dtype == numpy.uint8
        assert numpy.array_equal(first, second), preset["id"]


def test_representative_preset_golden_frames_and_perceptual_delta():
    numpy = pytest.importorskip("numpy")
    left, right = _sample_frames(numpy)
    cases = {
        "vibeedit://effect/filters-cinematic-teal-orange": "d2f531e14a8c77b63ed1a22ff899b8b84812bc725a351ce15b29b01b81de05b9",
        "vibeedit://effect/effects-freecut-invert": "bee93b2aac346080b42ce7a94d07e729759de62c171ab2026bb65dd18d28486a",
    }
    for identifier, expected in cases.items():
        output = apply_media_preset(left, identifier, progress=0.4)
        assert hashlib.sha256(output.tobytes()).hexdigest() == expected
        assert numpy.mean(numpy.abs(output.astype(float) - left.astype(float))) > 2
    transitions = {
        "vibeedit://transition/transitions-core-cross-dissolve": "70511c2794accd4e6685d95024634b02f22afc635f91bcdbf7540b550ee0f52d",
        "vibeedit://transition/transitions-core-film-burn": "b8820dbb0da119f430c5f61c6f413e5bd1419c4b7810b99ecf7aebcb3f40d162",
        "vibeedit://transition/transitions-core-push-left": "c04598efc281528be32f87a5381f38e3d67237828c24218e48f44310f444fca8",
    }
    for identifier, expected in transitions.items():
        output = render_transition_preset(left, right, identifier, progress=0.55)
        assert hashlib.sha256(output.tobytes()).hexdigest() == expected
        assert numpy.mean(numpy.abs(output.astype(float) - left.astype(float))) > 20
        assert numpy.mean(numpy.abs(output.astype(float) - right.astype(float))) > 20


def test_public_adapter_validates_ids_and_parameters():
    identifier = "vibeedit://effect/filters-cinematic-teal-orange"
    assert get_media_preset(identifier)["id"] == identifier
    assert build_media_preset_plan(identifier, parameter_overrides={"intensity": 0.42})["settings"]["intensity"] == 0.42
    with pytest.raises(ValueError, match="vibeedit://"):
        get_media_preset("filters-cinematic-teal-orange")
    with pytest.raises(ValueError, match="Unsupported parameter"):
        build_media_preset_plan(identifier, parameter_overrides={"unknown": 1})


def test_generated_validation_report_matches_packaged_runtime():
    report = json.loads(data_path("catalog", "preset-validation.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["cases"] == 333
    assert report["counts"] == {"effects": 112, "filters": 200, "transitions": 21}
    assert report["fidelity"]["status"] == "passed"
    assert report["fidelity"]["files"] >= 7
    assert len(report["aggregateSha256"]) == 64
    for source in report["source"]["files"]:
        assert len(source["sha256"]) == 64
        assert source["identical"] is True
        assert source["packageSha256"] == source["sha256"]


def test_catalog_exposes_every_imported_preset():
    catalog = json.loads(data_path("catalog", "catalog.json").read_text(encoding="utf-8"))
    items = {item["id"]: item for item in catalog["items"]}
    for preset in list_media_presets():
        item = items[preset["id"]]
        assert item["validation"][0]["status"] == "passed"
        assert item["preview"]["status"] == "missing"
        assert item["provenance"]["implementation"] == "python/src/vibeedit_media/preset_catalog.py"
        assert item["provenance"]["fidelity"] == "byte-identical-canonical-clone"
        assert item["provenance"]["canonicalId"] == preset["sourceId"]
