from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_release_checksums_match_flat_github_assets_and_nested_workflow_artifacts(tmp_path: Path):
    npm = tmp_path / "npm"
    python = tmp_path / "python"
    npm.mkdir()
    python.mkdir()
    (python / ".gitignore").write_text("*\n", encoding="utf-8")
    (npm / "vibeedit-0.1.0-beta.3.tgz").write_bytes(b"npm archive")
    (python / "vibeedit-0.1.0b3-py3-none-any.whl").write_bytes(b"wheel archive")
    (python / "vibeedit-0.1.0b3.tar.gz").write_bytes(b"source archive")
    flat = tmp_path / "SHA256SUMS"
    tree = tmp_path / "SHA256SUMS.tree"

    subprocess.run(
        [
            sys.executable,
            ROOT / "scripts/generate_release_checksums.py",
            "--npm-dir",
            npm,
            "--python-dir",
            python,
            "--flat-output",
            flat,
            "--tree-output",
            tree,
        ],
        check=True,
    )

    assert _manifest(flat) == {
        "vibeedit-0.1.0-beta.3.tgz": _sha256(npm / "vibeedit-0.1.0-beta.3.tgz"),
        "vibeedit-0.1.0b3-py3-none-any.whl": _sha256(python / "vibeedit-0.1.0b3-py3-none-any.whl"),
        "vibeedit-0.1.0b3.tar.gz": _sha256(python / "vibeedit-0.1.0b3.tar.gz"),
    }
    assert _manifest(tree) == {
        "npm/vibeedit-0.1.0-beta.3.tgz": _sha256(npm / "vibeedit-0.1.0-beta.3.tgz"),
        "python/vibeedit-0.1.0b3-py3-none-any.whl": _sha256(python / "vibeedit-0.1.0b3-py3-none-any.whl"),
        "python/vibeedit-0.1.0b3.tar.gz": _sha256(python / "vibeedit-0.1.0b3.tar.gz"),
    }


def test_release_checksums_reject_duplicate_flat_filenames(tmp_path: Path):
    npm = tmp_path / "npm"
    python = tmp_path / "python"
    npm.mkdir()
    python.mkdir()
    (npm / "duplicate.tgz").write_bytes(b"npm")
    (python / "duplicate.tgz").write_bytes(b"python")

    result = subprocess.run(
        [
            sys.executable,
            ROOT / "scripts/generate_release_checksums.py",
            "--npm-dir",
            npm,
            "--python-dir",
            python,
            "--flat-output",
            tmp_path / "SHA256SUMS",
            "--tree-output",
            tmp_path / "SHA256SUMS.tree",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "must be unique" in result.stderr


def _manifest(path: Path) -> dict[str, str]:
    return {name: digest for digest, name in (line.split("  ", 1) for line in path.read_text(encoding="utf-8").splitlines())}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
