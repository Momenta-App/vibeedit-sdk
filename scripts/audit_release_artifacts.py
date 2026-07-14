from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path


TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".py", ".toml", ".ts", ".yaml", ".yml"}
FORBIDDEN_NAMES = ("__pycache__", "production-basics", "vibeedit/_presets")
FORBIDDEN_SUFFIXES = (".onnx", ".pt", ".pth", ".pyc", ".safetensors")
FORBIDDEN_TEXT = (
    re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"service[_-]?role[_-]?(key|secret)", re.IGNORECASE),
    re.compile(rb"BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit built VibeEdit release archives against pinned canonical sources")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--npm", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    for path in (args.wheel, args.sdist, args.npm):
        if not path.is_file():
            parser.error(f"archive is missing: {path}")

    with zipfile.ZipFile(args.wheel) as archive:
        wheel = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    with tarfile.open(args.sdist) as archive:
        sdist = _tar_files(archive)
    with tarfile.open(args.npm) as archive:
        npm = _tar_files(archive)

    migration = json.loads(wheel["vibeedit/data/skills/migration-report.json"])
    skill_index = json.loads(wheel["vibeedit/data/skills/index.json"])
    preset_report = json.loads(wheel["vibeedit/data/catalog/preset-validation.json"])
    if len(skill_index["skills"]) != 44 or len(migration["selected"]) != 44:
        raise RuntimeError("release-safe canonical skill count changed")
    if len(preset_report["source"]["files"]) != 16:
        raise RuntimeError("canonical preset source-file count changed")

    source_root = args.source_root.resolve()
    for skill in skill_index["skills"]:
        if skill.get("source", {}).get("sha256") != skill.get("checksum"):
            raise RuntimeError(f"skill source/package checksum differs: {skill['name']}")
        prefix = skill["source"]["path"]
        paths = _git(source_root, "ls-tree", "-r", "--name-only", skill["source"]["revision"], prefix).decode().splitlines()
        for path in paths:
            relative = Path(path).relative_to(prefix).as_posix()
            canonical = _git(source_root, "show", f"{skill['source']['revision']}:{path}")
            _equal(wheel, f"vibeedit/data/skills/{skill['name']}/{relative}", canonical)
            _equal(npm, f"package/skills/{skill['name']}/{relative}", canonical)
            _equal(sdist, _sdist_name(sdist, f"skills/{skill['name']}/{relative}"), canonical)

    preset_root = preset_report["source"]["path"]
    preset_revision = preset_report["source"]["revision"]
    for file in preset_report["source"]["files"]:
        canonical = _git(source_root, "show", f"{preset_revision}:{preset_root}/{file['path']}")
        digest = hashlib.sha256(canonical).hexdigest()
        if digest != file["sha256"] or file["sha256"] != file["packageSha256"] or file["identical"] is not True:
            raise RuntimeError(f"preset fidelity record differs: {file['path']}")
        _equal(wheel, f"vibeedit_media/{file['path']}", canonical)
        _equal(sdist, _sdist_name(sdist, f"python/src/vibeedit_media/{file['path']}"), canonical)

    for label, files in (("wheel", wheel), ("sdist", sdist), ("npm", npm)):
        _scan(label, files)

    result = {
        "schemaVersion": "1.0.0",
        "status": "passed",
        "sourceRevision": migration["revision"],
        "skillClonesVerified": 44,
        "presetSourceFilesVerified": 16,
        "forbiddenEntries": 0,
        "archives": {
            "wheel": _archive_record(args.wheel, wheel),
            "sdist": _archive_record(args.sdist, sdist),
            "npm": _archive_record(args.npm, npm),
        },
    }
    value = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value, encoding="utf-8")
    print(value, end="")
    return 0


def _tar_files(archive: tarfile.TarFile) -> dict[str, bytes]:
    files = {}
    for member in archive.getmembers():
        if not member.isfile():
            continue
        stream = archive.extractfile(member)
        if stream:
            files[member.name] = stream.read()
    return files


def _sdist_name(files: dict[str, bytes], relative: str) -> str:
    matches = [name for name in files if name.endswith(f"/{relative}")]
    if len(matches) != 1:
        raise RuntimeError(f"sdist entry is missing or ambiguous: {relative}")
    return matches[0]


def _equal(files: dict[str, bytes], name: str, expected: bytes) -> None:
    if files.get(name) != expected:
        raise RuntimeError(f"archive entry is missing or differs from canonical source: {name}")


def _scan(label: str, files: dict[str, bytes]) -> None:
    for name, value in files.items():
        if any(part in name for part in FORBIDDEN_NAMES) or name.endswith(FORBIDDEN_SUFFIXES):
            raise RuntimeError(f"{label} contains forbidden entry: {name}")
        if Path(name).suffix.casefold() not in TEXT_SUFFIXES:
            continue
        for pattern in FORBIDDEN_TEXT:
            if pattern.search(value):
                raise RuntimeError(f"{label} entry matches forbidden content {pattern.pattern!r}: {name}")


def _archive_record(path: Path, files: dict[str, bytes]) -> dict:
    return {
        "name": path.name,
        "bytes": path.stat().st_size,
        "entries": len(files),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
