#!/usr/bin/env python3
"""Validate exact GitHub-release archives before a registry publication."""

from __future__ import annotations

import argparse
import email.parser
import hashlib
import json
import re
import tarfile
import tomllib
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    arguments = parser.parse_args()
    print(json.dumps(inspect_release(arguments.directory, arguments.tag), indent=2))
    return 0


def inspect_release(directory: Path, tag: str) -> dict[str, object]:
    npm_version, python_version = versions_for_tag(tag)
    wheel = only(directory / "python", "*.whl")
    sdist = only(directory / "python", "*.tar.gz")
    npm = only(directory / "npm", "*.tgz")
    archives = [wheel, sdist, npm]

    if metadata_version(wheel) != python_version:
        raise ValueError("wheel version does not match the release tag")
    if sdist_version(sdist) != python_version:
        raise ValueError("source-distribution version does not match the release tag")
    if npm_metadata(npm) != {"name": "vibeedit", "version": npm_version}:
        raise ValueError("npm package identity does not match the release tag")

    expected = {path.name: digest(path) for path in archives}
    checksums = read_checksums(directory / "SHA256SUMS.release")
    if checksums != expected:
        raise ValueError("release checksum manifest does not exactly match the three archives")

    audit = json.loads((directory / "archive-audit.json").read_text())
    if audit.get("status") != "passed" or audit.get("forbiddenEntries") != 0:
        raise ValueError("archive audit is not a clean pass")
    audited = {
        value["name"]: {"bytes": value["bytes"], "sha256": value["sha256"]}
        for value in audit.get("archives", {}).values()
    }
    actual = {path.name: {"bytes": path.stat().st_size, "sha256": expected[path.name]} for path in archives}
    if audited != actual:
        raise ValueError("archive audit identities do not match the downloaded archives")

    return {
        "ok": True,
        "tag": tag,
        "npmVersion": npm_version,
        "pythonVersion": python_version,
        "archives": actual,
    }


def versions_for_tag(tag: str) -> tuple[str, str]:
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)-(alpha|beta|rc)\.(\d+)", tag)
    if not match:
        raise ValueError("release tag must be a prerelease such as v0.1.0-beta.1")
    base, stage, number = match.groups()
    python_stage = {"alpha": "a", "beta": "b", "rc": "rc"}[stage]
    return tag.removeprefix("v"), f"{base}{python_stage}{number}"


def only(directory: Path, pattern: str) -> Path:
    values = list(directory.glob(pattern))
    if len(values) != 1:
        raise ValueError(f"expected exactly one {pattern} in {directory}, found {len(values)}")
    return values[0]


def metadata_version(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("wheel must contain exactly one METADATA file")
        message = email.parser.Parser().parsestr(archive.read(metadata[0]).decode())
    if message["Name"] != "vibeedit":
        raise ValueError("wheel project name is not vibeedit")
    return message["Version"]


def sdist_version(path: Path) -> str:
    with tarfile.open(path, "r:gz") as archive:
        pyprojects = [member for member in archive.getmembers() if member.name.count("/") == 1 and member.name.endswith("/pyproject.toml")]
        if len(pyprojects) != 1:
            raise ValueError("source distribution must contain exactly one root pyproject.toml")
        project = tomllib.loads(archive.extractfile(pyprojects[0]).read().decode())
    if project["project"]["name"] != "vibeedit":
        raise ValueError("source-distribution project name is not vibeedit")
    return project["project"]["version"]


def npm_metadata(path: Path) -> dict[str, str]:
    with tarfile.open(path, "r:gz") as archive:
        package = archive.extractfile("package/package.json")
        if package is None:
            raise ValueError("npm archive has no package/package.json")
        value = json.load(package)
    return {"name": value.get("name"), "version": value.get("version")}


def read_checksums(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        checksum, name = line.split(maxsplit=1)
        name = name.removeprefix("*")
        if Path(name).name != name or name in values:
            raise ValueError("checksum manifest must use unique flat filenames")
        values[name] = checksum
    return values


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
