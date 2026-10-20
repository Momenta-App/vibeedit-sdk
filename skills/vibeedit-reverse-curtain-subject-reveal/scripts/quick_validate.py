"""Validate a project-local receipt and its exact rendered bytes; never re-run inference."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--receipt", required=True, help="Project-relative run receipt")
    args = parser.parse_args()
    project = args.project.resolve(strict=True)
    receipt_path = scoped(project, args.receipt)
    receipt = json.loads(receipt_path.read_text())
    for label, digest in [("source", "sourceSha256"), ("output", "outputSha256")]:
        if hashlib.file_digest(scoped(project, receipt[label]).open("rb"), "sha256").hexdigest() != receipt[digest]:
            raise ValueError(label + " bytes differ from receipt")
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,nb_frames", "-of", "json", str(scoped(project, receipt["output"]))], check=True, capture_output=True, text=True)
    stream = json.loads(result.stdout)["streams"][0]
    checks = receipt["validation"]
    passed = all(value for value in checks.values() if isinstance(value, bool))
    if "maskCoverageAverage" in checks:
        passed = passed and checks["maskCoverageAverage"] > 0.015
        alpha = scoped(project, receipt["config"]["externalAlpha"])
        passed = passed and hashlib.file_digest(alpha.open("rb"), "sha256").hexdigest() == receipt["config"]["alphaSha256"]
    passed = passed and stream["width"] == receipt["config"]["width"] and stream["height"] == receipt["config"]["height"] and int(stream["nb_frames"]) == checks["frames"]
    print(json.dumps({"ok": passed, "editorialReview": "required", "checks": checks, "stream": stream}, indent=2))
    if not passed:
        raise SystemExit(1)


def scoped(project, value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Use project-relative paths")
    for parent in [project / path, *(project / path).parents]:
        if parent == project:
            break
        if parent.is_symlink():
            raise ValueError("Symlink path is not allowed")
    result = (project / path).resolve(strict=True)
    result.relative_to(project)
    return result


if __name__ == "__main__":
    main()
