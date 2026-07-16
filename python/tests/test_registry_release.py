import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "validate_registry_release",
    Path(__file__).parents[2] / "scripts" / "validate_registry_release.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_registry_release_validator_binds_all_archives_to_prerelease_tag(tmp_path: Path):
    python = tmp_path / "python"
    npm = tmp_path / "npm"
    python.mkdir()
    npm.mkdir()
    wheel = python / "vibeedit-0.1.0b1-py3-none-any.whl"
    sdist = python / "vibeedit-0.1.0b1.tar.gz"
    archive = npm / "vibeedit-0.1.0-beta.1.tgz"

    with zipfile.ZipFile(wheel, "w") as value:
        value.writestr("vibeedit-0.1.0b1.dist-info/METADATA", "Name: vibeedit\nVersion: 0.1.0b1\n")
    write_tar(sdist, "vibeedit-0.1.0b1/pyproject.toml", b'[project]\nname = "vibeedit"\nversion = "0.1.0b1"\n')
    write_tar(archive, "package/package.json", json.dumps({"name": "vibeedit", "version": "0.1.0-beta.1"}).encode())

    paths = [wheel, sdist, archive]
    (tmp_path / "SHA256SUMS.release").write_text("".join(f"{MODULE.digest(path)}  {path.name}\n" for path in paths))
    (tmp_path / "archive-audit.json").write_text(json.dumps({
        "status": "passed",
        "forbiddenEntries": 0,
        "archives": {
            name: {"name": path.name, "bytes": path.stat().st_size, "sha256": MODULE.digest(path)}
            for name, path in zip(["wheel", "sdist", "npm"], paths)
        },
    }))

    result = MODULE.inspect_release(tmp_path, "v0.1.0-beta.1")
    assert result["ok"] is True
    assert result["npmVersion"] == "0.1.0-beta.1"
    assert result["pythonVersion"] == "0.1.0b1"


def test_registry_release_validator_rejects_non_prerelease_tag():
    with pytest.raises(ValueError, match="must be a prerelease"):
        MODULE.versions_for_tag("v0.1.0")


def write_tar(path: Path, name: str, content: bytes):
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
