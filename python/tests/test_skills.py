import json
from pathlib import Path

import pytest

from vibeedit import check_skill, install_skill, list_skills, remove_skill, update_skill
from vibeedit.data import data_path
from vibeedit.skills import _checksum


def test_skill_lifecycle_preserves_user_changes(tmp_path: Path):
    installed = install_skill("vibeedit-workspace", harness="codex", root=tmp_path)
    assert check_skill("vibeedit-workspace", harness="codex", root=tmp_path)["modified"] is False
    (Path(installed["destination"]) / "SKILL.md").write_text("user edit\n", encoding="utf-8")
    assert check_skill("vibeedit-workspace", harness="codex", root=tmp_path)["modified"] is True
    with pytest.raises(RuntimeError, match="user-modified"):
        update_skill("vibeedit-workspace", harness="codex", root=tmp_path)
    with pytest.raises(RuntimeError, match="user-modified"):
        remove_skill("vibeedit-workspace", harness="codex", root=tmp_path)


def test_all_release_safe_skills_install_across_harnesses(tmp_path: Path):
    skills = list_skills()
    assert len([s for s in skills if s["source"].get("kind") != "sdk-owned"]) == 44
    assert any(s["name"] == "vibeedit-setup" for s in skills)
    for index, skill in enumerate(skills):
        harness = ("agents", "codex", "claude", "opencode")[index % 4]
        root = tmp_path / str(index)
        install_skill(skill["id"], harness=harness, root=root)
        assert check_skill(skill["name"], harness=harness, root=root)["modified"] is False
        assert remove_skill(skill["id"], harness=harness, root=root)["removed"] is True


def test_bundled_skills_preserve_donor_identity_and_explicit_adaptations():
    report = json.loads(data_path("skills", "migration-report.json").read_text(encoding="utf-8"))
    records = {item["name"]: item for item in report["selected"]}
    assert len(records) == 44
    assert "byte-identical clones" in report["policy"]
    for skill in [s for s in list_skills() if s["source"].get("kind") != "sdk-owned"]:
        record = records[skill["name"]]
        root = data_path("skills", skill["path"])
        assert record["sourceSha256"] == skill["source"]["sha256"]
        assert record["packageSha256"] == skill["checksum"] == _checksum(root)
        if record["sourceSha256"] != record["packageSha256"]:
            assert record["adaptation"] == skill["adaptation"]
            assert skill["adaptation"]["parentSha256"] == record["sourceSha256"]
