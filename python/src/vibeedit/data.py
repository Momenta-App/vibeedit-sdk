from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def package_root() -> Path:
    root = Path(__file__).resolve().parents[3]
    if (root / "schema" / "composition.schema.json").is_file():
        return root
    return Path(files("vibeedit").joinpath("data"))


def data_path(*parts: str) -> Path:
    return package_root().joinpath(*parts)

