import json
from pathlib import Path

import pytest

from vibeedit import check_skill, install_skill, list_skills, remove_skill, update_skill
from vibeedit.data import data_path
from vibeedit.skills import _checksum


def test_skill_lifecycle_preserves_user_changes(tmp_path: Path):
    installed = install_skill("vibeedit-workspace", harness="codex", root=tmp_path)
    assert check_skill("vibeedit-workspace", harness="codex", root=tmp_path)["modified"] is False
    (Path(installed["destination"]) / "SKILL.md").write_text("user edit\n")
    assert check_skill("vibeedit-workspace", harness="codex", root=tmp_path)["modified"] is True
    with pytest.raises(RuntimeError, match="user-modified"):
        update_skill("vibeedit-workspace", harness="codex", root=tmp_path)
    with pytest.raises(RuntimeError, match="user-modified"):
        remove_skill("vibeedit-workspace", harness="codex", root=tmp_path)


def test_all_release_safe_skills_install_across_harnesses(tmp_path: Path):
    skills = list_skills()
    assert len(skills) == 44
    for index, skill in enumerate(skills):
        harness = ("agents", "codex", "claude", "opencode")[index % 4]
        root = tmp_path / str(index)
        install_skill(skill["id"], harness=harness, root=root)
        assert check_skill(skill["name"], harness=harness, root=root)["modified"] is False
        assert remove_skill(skill["id"], harness=harness, root=root)["removed"] is True


def test_all_bundled_skills_are_byte_identical_canonical_clones():
    report = json.loads(data_path("skills", "migration-report.json").read_text(encoding="utf-8"))
    records = {item["name"]: item for item in report["selected"]}
    assert len(records) == 44
    assert "byte-identical clones" in report["policy"]
    for skill in list_skills():
        record = records[skill["name"]]
        root = data_path("skills", skill["path"])
        assert record["sourceSha256"] == record["packageSha256"] == skill["checksum"] == _checksum(root)
        assert skill["source"]["sha256"] == skill["checksum"]
