import json
import re
import tomllib
from pathlib import Path

from vibeedit.data import data_path


def test_sbom_covers_declared_dependencies_models_fonts_and_separate_terms():
    root = Path(__file__).parents[2]
    python = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    npm = json.loads((root / "package.json").read_text(encoding="utf-8"))
    sbom = json.loads(data_path("SBOM.spdx.json").read_text(encoding="utf-8"))
    names = {package["name"].lower() for package in sbom["packages"]}
    requirements = [*python["project"]["dependencies"], *(requirement for name, values in python["project"]["optional-dependencies"].items() if name != "test" for requirement in values)]
    declared = {re.split(r"[<>=;\[]", requirement, 1)[0].lower() for requirement in requirements}
    declared.update(name.lower() for name in [*npm["dependencies"], *npm.get("peerDependencies", {})])
    assert declared <= names
    models = json.loads(data_path("runtime-models", "manifest.json").read_text(encoding="utf-8"))["models"]
    assert {"ssd-mobilenet-v1-12", "sam2-source", "sam2.1-hiera-tiny"} <= names
    assert any(model["capability"] == "sam.2.1" and all(file["sha256"] for file in model["files"]) for model in models)
    owned = next(package for package in sbom["packages"] if package["name"] == "vibeedit")
    assert owned["licenseDeclared"] == "MIT"
    assert {"transnet", "sam21", "sam31-mlx", "mlx-vlm", "@earendil-works/pi-coding-agent"} <= names
    assert any(item["licenseId"] == "LicenseRef-SAM" and item["extractedText"] for item in sbom["hasExtractedLicensingInfos"])
    fonts = json.loads((root / "scripts/font-policy.json").read_text(encoding="utf-8"))["fonts"]
    entries = {package["name"]: package for package in sbom["packages"]}
    for font in (f for f in fonts if f["filename"].endswith(".ttf")):
        assert entries[font["filename"]]["licenseDeclared"] == "OFL-1.1"
        assert entries[font["filename"]]["checksums"][0]["checksumValue"] == font["sha256"]
