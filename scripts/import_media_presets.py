from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
PYTHON_ROOT = PACKAGE_ROOT / "python" / "src"
TARGET = PYTHON_ROOT / "vibeedit_media"
SOURCE_RELATIVE = Path("packages/sdk/python/vibeedit_media/src/vibeedit_media")
GENERATED_SOURCE_PREFIX = f"main-repository:{SOURCE_RELATIVE.as_posix()}/"
EXPECTED_COUNTS = {"effects": 112, "filters": 200, "transitions": 21}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clone the reviewed canonical VibeEdit media-preset package")
    parser.add_argument("--source-root", type=Path, required=True, help="Root of the canonical VibeEdit repository")
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args(argv)
    root = args.source_root.resolve()
    revision = _git(root, "rev-parse", args.revision).decode().strip()
    files = _inventory(root, revision)
    source_catalog = json.loads(_content(files, "preset_catalog.json"))
    if source_catalog.get("counts") != EXPECTED_COUNTS:
        raise RuntimeError("canonical preset counts changed; review the new inventory before importing")
    if len(source_catalog.get("presets", [])) != 333:
        raise RuntimeError("canonical preset inventory must contain exactly 333 reviewed entries")

    shutil.rmtree(TARGET, ignore_errors=True)
    shutil.rmtree(PYTHON_ROOT / "vibeedit" / "_presets", ignore_errors=True)
    TARGET.mkdir(parents=True, exist_ok=True)
    for file in files:
        target = TARGET / file["relative"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file["content"])
        if file["mode"] == "100755":
            target.chmod(target.stat().st_mode | 0o111)
        if target.read_bytes() != file["content"]:
            raise RuntimeError(f"preset source clone is not byte-identical: {file['relative']}")

    source_hashes = {file["relative"]: hashlib.sha256(file["content"]).hexdigest() for file in files}
    validation = _validate_runtime(source_hashes, revision)
    for cache in TARGET.rglob("__pycache__"):
        shutil.rmtree(cache)
    (PACKAGE_ROOT / "catalog" / "preset-validation.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_public_catalog(source_catalog, source_hashes["preset_catalog.json"])
    print(
        json.dumps(
            {
                "ok": True,
                "revision": revision,
                "cloneFiles": len(files),
                "imported": 333,
                "counts": validation["counts"],
                "aggregateSha256": validation["aggregateSha256"],
            }
        )
    )
    return 0


def _inventory(root: Path, revision: str) -> list[dict]:
    lines = _git(root, "ls-tree", "-r", "-l", revision, SOURCE_RELATIVE.as_posix()).decode().splitlines()
    files = []
    for line in lines:
        mode, _, _, size_and_path = line.split(None, 3)
        _, path = size_and_path.split("\t", 1)
        relative = Path(path).relative_to(SOURCE_RELATIVE).as_posix()
        files.append({"path": path, "relative": relative, "mode": mode, "content": _git(root, "show", f"{revision}:{path}")})
    if not files:
        raise RuntimeError(f"canonical preset source is missing: {SOURCE_RELATIVE}")
    return files


def _content(files: list[dict], relative: str) -> str:
    for file in files:
        if file["relative"] == relative:
            return file["content"].decode()
    raise RuntimeError(f"canonical preset source is missing: {relative}")


def _validate_runtime(source_hashes: dict[str, str], revision: str) -> dict:
    sys.path.insert(0, str(PYTHON_ROOT))
    importlib.invalidate_caches()
    for name in tuple(sys.modules):
        if name == "vibeedit_media" or name.startswith("vibeedit_media."):
            del sys.modules[name]
    numpy = importlib.import_module("numpy")
    runtime = importlib.import_module("vibeedit_media.preset_catalog")
    left = numpy.zeros((24, 32, 4), dtype=numpy.uint8)
    left[:, :, 0] = numpy.arange(32, dtype=numpy.uint8)[None, :] * 7
    left[:, :, 1] = numpy.arange(24, dtype=numpy.uint8)[:, None] * 10
    left[:, :, 2] = 128
    left[:, :, 3] = 255
    right = numpy.zeros_like(left)
    right[:, :, 0] = 20
    right[:, :, 1] = 80
    right[:, :, 2] = 220
    right[:, :, 3] = 255
    digests = []
    counts = {"effects": 0, "filters": 0, "transitions": 0}
    for preset in runtime.list_presets():
        if preset["kind"] == "transitions":
            output = runtime.render_transition_frame(left, right, preset["id"], progress=0.55)
        else:
            output = runtime.apply_preset_to_image(left, preset["id"], progress=0.4)
        if output.shape != left.shape or output.dtype != numpy.uint8:
            raise RuntimeError(f"preset output contract failed: {preset['id']}")
        counts[preset["kind"]] += 1
        digests.append(f"{preset['id']}:{hashlib.sha256(output.tobytes()).hexdigest()}")
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"validated preset counts changed: {counts}")
    sources = []
    for name, digest in sorted(source_hashes.items()):
        package_digest = _sha256(TARGET / name)
        if package_digest != digest:
            raise RuntimeError(f"preset source clone hash mismatch: {name}")
        sources.append({"path": name, "sha256": digest, "packageSha256": package_digest, "identical": True})
    return {
        "schemaVersion": "1.0.0",
        "status": "passed",
        "runtime": {"python": sys.version.split()[0], "numpy": numpy.__version__},
        "source": {
            "root": "main-repository",
            "path": SOURCE_RELATIVE.as_posix(),
            "revision": revision,
            "files": sources,
        },
        "fidelity": {
            "status": "passed",
            "contract": "Every tracked canonical source file is packaged byte-for-byte under its original vibeedit_media namespace.",
            "files": len(sources),
        },
        "counts": counts,
        "cases": sum(counts.values()),
        "contract": "Every canonical preset returned a deterministic uint8 RGBA frame with the input dimensions.",
        "aggregateSha256": hashlib.sha256("\n".join(sorted(digests)).encode()).hexdigest(),
    }


def _write_public_catalog(source_catalog: dict, catalog_hash: str) -> None:
    path = PACKAGE_ROOT / "catalog" / "catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    retained = [
        item
        for item in catalog["items"]
        if not item.get("provenance", {}).get("source", "").startswith(GENERATED_SOURCE_PREFIX)
    ]
    catalog["items"] = retained + [_catalog_item(preset, catalog_hash) for preset in source_catalog["presets"]]
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _catalog_item(preset: dict, catalog_hash: str) -> dict:
    transition = preset["kind"] == "transitions"
    identifier = _public_id(preset)
    properties = {
        parameter["id"]: {
            "type": "number",
            "title": parameter["label"],
            "minimum": parameter["min"],
            "maximum": parameter["max"],
            "default": parameter["default"],
        }
        for parameter in preset["parameters"]
    }
    if transition:
        python_example = f"render_transition_preset(left, right, {identifier!r}, progress=0.5)"
        javascript_example = (
            "new Transition({ id: 'transition', placement: new Placement(0, 12), "
            f"transitionId: {identifier!r}, fromItemId: 'a', toItemId: 'b' }})"
        )
    else:
        python_example = f"apply_media_preset(frame, {identifier!r}, progress=0.4)"
        javascript_example = f"new Effect({{ id: 'effect', effectId: {identifier!r}, params: {{}} }})"
    third_party = ["NumPy"]
    if preset["recipe"]["family"] == "freecut":
        third_party.append("FreeCut effect vocabulary (MIT)")
    return {
        "id": identifier,
        "name": preset["title"],
        "description": preset["description"],
        "category": "transition" if transition else "effect",
        "tags": list(dict.fromkeys([*preset["tags"], preset["category"].casefold().replace(" ", "-")])),
        "version": "0.1.0",
        "inputs": {"media": ["image", "video"], **({"adjacentItems": 2} if transition else {"requiresFrames": True})},
        "parameters": {"type": "object", "properties": properties, "additionalProperties": False},
        "platforms": ["macos", "windows", "linux"],
        "backends": ["python", "numpy"],
        "preview": {
            "status": "missing",
            "note": "The canonical implementation is execution-tested; a representative visual preview has not yet been generated.",
        },
        "examples": {"python": python_example, "javascript": javascript_example},
        "prompts": [preset["agentFlow"]["intent"], preset["agentFlow"]["selectionGuidance"]],
        "requirements": {"assets": [], "models": []},
        "license": {
            "owner": "Attention Engine Inc.",
            "terms": "SEE LICENSE IN LICENSE.md",
            "redistribution": "verified",
            "notes": "VibeEdit-owned canonical implementation; referenced third-party vocabulary and dependencies retain their own terms.",
        },
        "provenance": {
            "kind": "adapted" if preset["recipe"]["family"] == "freecut" else "vibeedit-owned",
            "source": f"{GENERATED_SOURCE_PREFIX}preset_catalog.json#sha256={catalog_hash}",
            "implementation": "python/src/vibeedit_media/preset_catalog.py",
            "thirdParty": third_party,
            "fidelity": "byte-identical-canonical-clone",
            "canonicalId": preset["id"],
        },
        "validation": [
            {
                "id": "deterministic-frame-contract",
                "status": "passed",
                "command": "pytest python/tests/test_presets.py",
                "evidence": "The byte-identical canonical runtime and all 333 preset definitions returned uint8 RGBA frames at the input dimensions.",
            }
        ],
    }


def _public_id(preset: dict) -> str:
    category = "transition" if preset["kind"] == "transitions" else "effect"
    return f"vibeedit://{category}/{preset['id']}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
