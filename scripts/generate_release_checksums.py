from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate GitHub-release and workflow-artifact SHA-256 manifests")
    parser.add_argument("--npm-dir", type=Path, required=True)
    parser.add_argument("--python-dir", type=Path, required=True)
    parser.add_argument("--flat-output", type=Path, required=True)
    parser.add_argument("--tree-output", type=Path, required=True)
    args = parser.parse_args(argv)

    files = [
        *(('npm', path) for path in _files(args.npm_dir)),
        *(('python', path) for path in _files(args.python_dir)),
    ]
    names = [path.name for _, path in files]
    if len(names) != len(set(names)):
        parser.error("release artifact filenames must be unique across npm and Python outputs")

    args.flat_output.parent.mkdir(parents=True, exist_ok=True)
    args.tree_output.parent.mkdir(parents=True, exist_ok=True)
    args.flat_output.write_text("".join(f"{_sha256(path)}  {path.name}\n" for _, path in files), encoding="utf-8")
    args.tree_output.write_text("".join(f"{_sha256(path)}  {directory}/{path.name}\n" for directory, path in files), encoding="utf-8")
    return 0


def _files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise FileNotFoundError(f"release artifact directory is missing: {directory}")
    files = sorted(path for path in directory.iterdir() if path.is_file() and not path.name.startswith("."))
    if not files:
        raise FileNotFoundError(f"release artifact directory is empty: {directory}")
    if any("\n" in path.name or "\r" in path.name for path in files):
        raise ValueError(f"release artifact filename contains a newline: {directory}")
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
