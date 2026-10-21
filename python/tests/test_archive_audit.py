from pathlib import Path
import runpy

import pytest


audit = runpy.run_path(str(Path(__file__).parents[2] / "scripts/audit_release_artifacts.py"))


def test_sdist_root_readme_is_distinct_from_nested_readmes():
    files = {
        "vibeedit-0.2.0b2/README.md": b"root",
        "vibeedit-0.2.0b2/companion/README.md": b"companion",
        "vibeedit-0.2.0b2/browser-renderer/README.md": b"renderer",
    }
    assert audit["_sdist_name"](files, "README.md") == "vibeedit-0.2.0b2/README.md"
    assert audit["_sdist_name"](files, "companion/README.md") == "vibeedit-0.2.0b2/companion/README.md"
    del files["vibeedit-0.2.0b2/README.md"]
    with pytest.raises(RuntimeError, match="missing or ambiguous"):
        audit["_sdist_name"](files, "README.md")


def test_sdist_rejects_multiple_package_roots():
    with pytest.raises(RuntimeError, match="one top-level package directory"):
        audit["_sdist_name"]({"one/README.md": b"one", "two/README.md": b"two"}, "README.md")


@pytest.mark.parametrize("label,prefix", [("wheel", "vibeedit/data"), ("sdist", "vibeedit-0.2.0b2"), ("npm", "package")])
def test_every_archive_rejects_operator_launch_records(label, prefix):
    with pytest.raises(RuntimeError, match="excluded operator launch records"):
        audit["_scan"](label, {f"{prefix}/docs/launch/STATE.md": b"private"})
