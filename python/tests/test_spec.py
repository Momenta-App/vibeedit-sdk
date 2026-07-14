import json
from pathlib import Path

import pytest

from vibeedit import Canvas, Composition, CompositionValidationError, FrameRate, MotionComponent, Placement, Track
from vibeedit.data import data_path
from vibeedit.validation import canonical_json, validate_composition


def test_fixtures_validate_and_canonicalize():
    for path in sorted(data_path("schema", "fixtures").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        validate_composition(value)
        assert canonical_json(value) == canonical_json(json.loads(canonical_json(value)))


def test_composition_public_api_matches_schema(tmp_path: Path):
    composition = Composition(
        "public-api",
        Canvas(640, 360, FrameRate(60_000, 2_002)),
        90,
        created_at="2026-07-13T00:00:00Z",
    )
    motion = composition.timeline.add_track(Track("M1", "motion", 10))
    motion.add(MotionComponent("title", Placement(0, 90), "vibeedit://text/negative", {"text": "MOVE"}))
    path = composition.write(tmp_path / "composition.json")
    assert json.loads(path.read_text())["canvas"]["frameRate"] == {"numerator": 30000, "denominator": 1001}


def test_unknown_fields_are_rejected():
    value = json.loads(data_path("schema", "fixtures", "minimal.json").read_text())
    value["unknown"] = True
    with pytest.raises(CompositionValidationError, match="Additional properties"):
        validate_composition(value)

