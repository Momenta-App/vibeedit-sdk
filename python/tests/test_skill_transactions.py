"""Crash tests mutate real directories in disposable roots; no filesystem is mocked."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vibeedit.skills import _checksum, _lock, check_skill, install_skill, remove_skill, update_skill

REPO = Path(__file__).resolve().parents[2]
NAME = "vibeedit-workspace"


def child_python(root, code):
    return subprocess.run([sys.executable, "-c", code, str(root)], cwd=REPO, env={**os.environ, "PYTHONPATH": str(REPO / "python/src")}, capture_output=True, text=True, timeout=20)


def child_node(root, code):
    return subprocess.run(["node", "--input-type=module", "-e", code, str(root)], cwd=REPO, capture_output=True, text=True, timeout=20)


def crash_python(root, action="update"):
    result = child_python(root, f'''
import os, sys
from vibeedit import skills
original = os.replace
def replace(source, destination):
    original(source, destination)
    if str(destination).endswith(".vibeedit-previous"):
        os._exit(71)
skills.os.replace = replace
skills.{action}_skill("{NAME}", harness="codex", root=sys.argv[1])
''')
    assert result.returncode == 71, result.stderr


def test_python_update_crash_recovers_in_node(tmp_path):
    installed = install_skill(NAME, harness="codex", root=tmp_path)
    # A prior release has a different version and content, with its own valid receipt.
    previous = Path(installed["destination"])
    (previous / "SKILL.md").write_text("known prior release content\n")
    tracker = json.loads((previous / ".vibeedit-install.json").read_text())
    tracker.update(version="0.0.0-prior", checksum=_checksum(previous, {".vibeedit-install.json"}))
    (previous / ".vibeedit-install.json").write_text(json.dumps(tracker))
    assert check_skill(NAME, harness="codex", root=tmp_path)["modified"] is False
    crash_python(tmp_path)
    assert not Path(installed["destination"]).exists()
    result = child_node(tmp_path, '''
import { checkSkill } from "./src/skills.js";
console.log(JSON.stringify(checkSkill("vibeedit-workspace", {harness:"codex", cwd:process.argv[1]})));
''')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["modified"] is False
    assert json.loads(result.stdout)["version"] != "0.0.0-prior"
    assert (previous / "SKILL.md").read_text() != "known prior release content\n"
    assert check_skill(NAME, harness="codex", root=tmp_path)["modified"] is False
    assert not list(Path(installed["destination"]).parent.glob(".*.vibeedit-*"))


def test_node_update_crash_recovers_in_python(tmp_path):
    install_skill(NAME, harness="codex", root=tmp_path)
    result = child_node(tmp_path, '''
import fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
const original = fs.renameSync;
fs.renameSync = (source, destination) => {
  original(source, destination);
  if (destination.endsWith(".vibeedit-previous")) process.exit(72);
};
syncBuiltinESMExports();
const { updateSkill } = await import("./src/skills.js");
updateSkill("vibeedit-workspace", {harness:"codex", cwd:process.argv[1]});
''')
    assert result.returncode == 72, result.stderr
    assert check_skill(NAME, harness="codex", root=tmp_path)["modified"] is False
    assert remove_skill(NAME, harness="codex", root=tmp_path)["removed"] is True


def test_partial_stage_preserves_old_install_and_quarantines_partial_copy(tmp_path):
    installed = install_skill(NAME, harness="codex", root=tmp_path)
    result = child_python(tmp_path, '''
import os, sys
from pathlib import Path
from vibeedit import skills
original = skills.shutil.copytree
def copy(source, destination, *args, **kwargs):
    original(source, destination, *args, **kwargs)
    (Path(destination) / "SKILL.md").write_text("interrupted partial copy")
    os._exit(73)
skills.shutil.copytree = copy
skills.update_skill("vibeedit-workspace", harness="codex", root=sys.argv[1])
''')
    assert result.returncode == 73, result.stderr
    assert check_skill(NAME, harness="codex", root=tmp_path)["modified"] is False
    quarantines = list(Path(installed["destination"]).parent.glob(".*.vibeedit-stage.aborted-*"))
    assert len(quarantines) == 1
    assert (quarantines[0] / "SKILL.md").read_text() == "interrupted partial copy"
    assert update_skill(NAME, harness="codex", root=tmp_path)["action"] == "updated"


def test_modified_backup_after_crash_is_preserved_and_fails_closed(tmp_path):
    installed = install_skill(NAME, harness="codex", root=tmp_path)
    crash_python(tmp_path)
    parent = Path(installed["destination"]).parent
    previous = parent / f".{NAME}.vibeedit-previous"
    (previous / "SKILL.md").write_text("user rescued changes\n")
    with pytest.raises(RuntimeError, match="user-modified skill backup"):
        check_skill(NAME, harness="codex", root=tmp_path)
    result = child_node(tmp_path, '''
import { checkSkill } from "./src/skills.js";
checkSkill("vibeedit-workspace", {harness:"codex", cwd:process.argv[1]});
''')
    assert result.returncode != 0 and "user-modified skill backup" in result.stderr
    assert (previous / "SKILL.md").read_text() == "user rescued changes\n"
    assert (parent / f".{NAME}.vibeedit-stage").is_dir()
    assert (parent / f".{NAME}.vibeedit-operation.json").is_file()


def test_remove_crash_finishes_in_other_runtime(tmp_path):
    install_skill(NAME, harness="codex", root=tmp_path)
    crash_python(tmp_path, action="remove")
    result = child_node(tmp_path, '''
import { checkSkill } from "./src/skills.js";
console.log(JSON.stringify(checkSkill("vibeedit-workspace", {harness:"codex", cwd:process.argv[1]})));
''')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["installed"] is False


def test_cross_language_lock_refuses_live_owner(tmp_path):
    destination = tmp_path / ".codex/skills" / NAME
    with _lock(destination):
        result = child_node(tmp_path, '''
import { checkSkill } from "./src/skills.js";
checkSkill("vibeedit-workspace", {harness:"codex", cwd:process.argv[1]});
''')
        assert result.returncode != 0 and "skill operation locked" in result.stderr
    assert not destination.exists()


def test_symlink_harness_and_installed_content_fail_closed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".codex").symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink"):
        install_skill(NAME, harness="codex", root=tmp_path)
    assert not list(outside.iterdir())
    (tmp_path / ".codex").unlink()
    installed = install_skill(NAME, harness="codex", root=tmp_path)
    (Path(installed["destination"]) / "extra").symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink"):
        remove_skill(NAME, harness="codex", root=tmp_path)
    assert Path(installed["destination"]).is_dir()


def test_checksum_order_and_nested_tracker_parity(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a/file").write_text("nested")
    (tmp_path / "a.txt").write_text("sibling")
    (tmp_path / "a/.vibeedit-install.json").write_text("must count")
    (tmp_path / ".vibeedit-install.json").write_text("exclude root tracker")
    result = child_node(tmp_path, '''
import { treeChecksum } from "./src/skills.js";
console.log(treeChecksum(process.argv[1], new Set([".vibeedit-install.json"])));
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == _checksum(tmp_path, {".vibeedit-install.json"})


def test_unknown_lock_format_is_never_reclaimed(tmp_path):
    lock = tmp_path / ".codex/skills" / f".{NAME}.vibeedit-lock"
    lock.mkdir(parents=True)
    (lock / "owner.json").write_text(json.dumps({"pid": 2147483647}))
    (lock / "retain.txt").write_text("unknown owner data")
    with pytest.raises(RuntimeError, match="unknown owner"):
        check_skill(NAME, harness="codex", root=tmp_path)
    result = child_node(tmp_path, '''
import { checkSkill } from "./src/skills.js";
checkSkill("vibeedit-workspace", {harness:"codex", cwd:process.argv[1]});
''')
    assert result.returncode != 0 and "unknown owner" in result.stderr
    assert (lock / "retain.txt").read_text() == "unknown owner data"


def test_interpreter_bytecode_does_not_break_or_enter_skill_installations(tmp_path):
    import py_compile
    from vibeedit.data import data_path
    source = data_path('skills', 'vibeedit-setup')
    before = _checksum(source)
    py_compile.compile(str(source / 'scripts/setup.py'), doraise=True)
    assert list((source / 'scripts/__pycache__').glob('*.pyc'))
    assert _checksum(source) == before
    installed = install_skill('vibeedit-setup', harness='codex', root=tmp_path)
    destination = Path(installed['destination'])
    assert not list(destination.rglob('*.pyc')) and not list(destination.rglob('__pycache__'))
    py_compile.compile(str(destination / 'scripts/setup.py'), doraise=True)
    assert check_skill('vibeedit-setup', harness='codex', root=tmp_path)['modified'] is False
    result = child_node(tmp_path, '''
import { checkSkill, installSkill } from './src/skills.js';
const checked=checkSkill('vibeedit-setup',{harness:'codex',cwd:process.argv[1]});
const installed=installSkill('vibeedit-setup',{harness:'claude',cwd:process.argv[1]});
console.log(JSON.stringify({checked,installed}));
''')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['checked']['modified'] is False
    node_destination = Path(json.loads(result.stdout)['installed']['destination'])
    assert not list(node_destination.rglob('*.pyc')) and not list(node_destination.rglob('__pycache__'))
