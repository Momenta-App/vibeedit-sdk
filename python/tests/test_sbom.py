import json
import re
import tomllib
from pathlib import Path

from vibeedit.data import data_path


def test_sbom_covers_declared_runtime_dependencies_models_and_custom_license():
    root = Path(__file__).parents[2]
    python = tomllib.loads((root / "pyproject.toml").read_text())
    npm = json.loads((root / "package.json").read_text())
    sbom = json.loads(data_path("SBOM.spdx.json").read_text())
    names = {package["name"].lower() for package in sbom["packages"]}
    requirements = [*python["project"]["dependencies"], *(requirement for name, values in python["project"]["optional-dependencies"].items() if name != "test" for requirement in values)]
    declared = {re.split(r"[<>=;\[]", requirement, 1)[0].lower() for requirement in requirements}
    declared.update(name.lower() for name in [*npm["dependencies"], *npm.get("peerDependencies", {})])
    assert declared <= names
    models = json.loads(data_path("runtime-models", "manifest.json").read_text())["models"]
    assert {"ssd-mobilenet-v1-12", "sam2-source", "sam2.1-hiera-tiny"} <= names
    assert any(model["capability"] == "sam.2.1" and all(file["sha256"] for file in model["files"]) for model in models)
    assert any(item["licenseId"] == "LicenseRef-VibeEdit" and "Commercial use requires" in item["extractedText"] for item in sbom["hasExtractedLicensingInfos"])
