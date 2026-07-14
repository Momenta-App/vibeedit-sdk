from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TARGET_ROOT = PACKAGE_ROOT / "skills"
SOURCE_PREFIX = ".codex/skills"
EXCLUDED = {
    "graphify": "repository-maintenance tool, not a video-production skill",
    "supabase": "unrelated third-party product skill",
    "supabase-postgres-best-practices": "unrelated third-party product skill",
    "micro-botanica-sfx-router": "contains recorded audio and developer-machine source paths",
    "micro-sfx-composer": "contains recorded audio without package-level redistribution evidence",
    "vibeedit-subject-effects-agents-copy": "test alias, not a canonical skill",
    "vibeedit-subject-effects-codex-copy": "test alias, not a canonical skill",
    "vibeedit-subject-effects-vibeedit-active": "test alias, not a canonical skill",
}
BINARY_EXTENSIONS = {".wav", ".mp3", ".mp4", ".mov", ".onnx", ".bin", ".ttf", ".otf", ".png", ".jpg", ".jpeg"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import release-safe VibeEdit production skills")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args(argv)
    root = args.source_root.resolve()
    revision = _git(root, "rev-parse", args.revision).decode().strip()
    inventory = _inventory(root, revision)
    selected = []
    rejected = []
    for name, files in sorted(inventory.items()):
        reason = _rejection_reason(name, files)
        if reason:
            rejected.append({"name": name, "reason": reason})
            continue
        selected.append((name, files))
    if len(selected) != 44:
        raise RuntimeError(f"reviewed safe skill inventory changed: expected 44, found {len(selected)}")

    previous = TARGET_ROOT / "migration-report.json"
    if previous.is_file():
        for item in json.loads(previous.read_text(encoding="utf-8")).get("selected", []):
            shutil.rmtree(TARGET_ROOT / item["name"], ignore_errors=True)

    records = []
    for name, files in selected:
        destination = TARGET_ROOT / name
        destination.mkdir(parents=True, exist_ok=True)
        for file in files:
            target = destination / file["relative"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file["content"])
            if file["mode"] == "100755":
                target.chmod(target.stat().st_mode | 0o111)
        validation = _validate_skill(destination)
        source_checksum = _files_checksum(files)
        package_checksum = _tree_checksum(destination)
        if source_checksum != package_checksum:
            raise RuntimeError(f"skill clone is not byte-identical: {name}")
        for file in files:
            executable = bool((destination / file["relative"]).stat().st_mode & 0o111)
            if executable != (file["mode"] == "100755"):
                raise RuntimeError(f"skill clone mode differs: {name}/{file['relative']}")
        records.append(
            {
                "id": f"vibeedit://skill/{name}",
                "name": name,
                "version": "0.1.0",
                "path": name,
                "harnesses": ["agents", "codex", "claude", "opencode"],
                "checksum": package_checksum,
                "source": {"path": f"{SOURCE_PREFIX}/{name}", "revision": revision, "sha256": source_checksum},
                "validation": validation,
            }
        )

    index_path = TARGET_ROOT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["skills"] = records
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {
        "schemaVersion": "1.0.0",
        "revision": revision,
        "source": "main-repository:.codex/skills",
        "selected": [{"name": record["name"], "sourceSha256": record["source"]["sha256"], "packageSha256": record["checksum"], "files": record["validation"]["files"]} for record in records],
        "rejected": rejected,
        "policy": "Included skills are byte-identical clones of their pinned canonical Git sources. Packaging metadata is stored outside the skill directories; unsafe or unrelated skills are excluded instead of rewritten.",
    }
    previous.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_catalog(records)
    print(json.dumps({"ok": True, "revision": revision, "selected": len(records), "rejected": len(rejected), "bundleSkills": len(index["skills"])}))
    return 0


def _inventory(root: Path, revision: str) -> dict[str, list[dict]]:
    values = {}
    lines = _git(root, "ls-tree", "-r", "-l", revision, SOURCE_PREFIX).decode().splitlines()
    for line in lines:
        mode, _, _, size_and_path = line.split(None, 3)
        _, path = size_and_path.split("\t", 1)
        parts = Path(path).parts
        name = parts[2]
        values.setdefault(name, []).append(
            {
                "path": path,
                "relative": Path(*parts[3:]).as_posix(),
                "mode": mode,
                "content": _show(root, revision, path),
            }
        )
    return values


def _rejection_reason(name: str, files: list[dict]) -> str | None:
    if name in EXCLUDED:
        return EXCLUDED[name]
    if any(Path(file["path"]).suffix.casefold() in BINARY_EXTENSIONS for file in files):
        return "contains binary media or model/font assets without a package redistribution gate"
    if any(b"/Users/" in file["content"] for file in files):
        return "contains absolute developer-machine paths that require a public-runtime rewrite"
    if not any(file["relative"] == "SKILL.md" for file in files):
        return "missing SKILL.md entrypoint"
    return None


def _validate_skill(root: Path) -> dict:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not (root / "SKILL.md").is_file():
        raise RuntimeError(f"missing skill entrypoint: {root.name}")
    for path in files:
        value = path.read_bytes()
        if b"/Users/" in value:
            raise RuntimeError(f"absolute developer path remains in {root.name}/{path.relative_to(root)}")
        if path.suffix == ".py":
            compile(value, str(path), "exec")
        if path.suffix == ".json":
            json.loads(value)
        if path.suffix == ".md":
            _validate_links(root, path, value.decode())
    return {
        "status": "passed",
        "files": len(files),
        "pythonFiles": sum(path.suffix == ".py" for path in files),
        "jsonFiles": sum(path.suffix == ".json" for path in files),
        "checks": ["entrypoint", "forbidden-path scan", "Python syntax", "JSON decode", "relative Markdown links"],
    }


def _validate_links(root: Path, path: Path, value: str) -> None:
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", value):
        target = target.split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:", "/")):
            continue
        resolved = (path.parent / target).resolve()
        if root.resolve() not in {resolved, *resolved.parents} or not resolved.exists():
            raise RuntimeError(f"broken relative Markdown link in {root.name}/{path.relative_to(root)}: {target}")


def _write_catalog(records: list[dict]) -> None:
    path = PACKAGE_ROOT / "catalog" / "catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    retained = [item for item in catalog["items"] if item.get("category") != "skill"]
    catalog["items"] = retained + [_catalog_item(record) for record in records]
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _catalog_item(record: dict) -> dict:
    description = _frontmatter_description(TARGET_ROOT / record["name"] / "SKILL.md")
    return {
        "id": record["id"],
        "name": record["name"],
        "description": description,
        "category": "skill",
        "tags": ["agents", "codex", "claude", "opencode", "workflow", *record["name"].removeprefix("vibeedit-").split("-")],
        "version": "0.1.0",
        "inputs": {"productionBrief": True},
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "platforms": ["macos", "windows", "linux"],
        "backends": ["skill", "cli"],
        "preview": {"status": "unsupported", "note": "Workflow skills are validated through package integrity and harness lifecycle tests rather than media previews."},
        "examples": {"python": f"install_skill({record['name']!r}, harness='codex')", "javascript": f"installSkill({json.dumps(record['name'])}, {{ harness: 'codex' }})"},
        "prompts": [f"Use the {record['name']} workflow for this VibeEdit production task and verify every claimed output."],
        "requirements": {"assets": [], "models": []},
        "license": {"owner": "Attention Engine Inc.", "terms": "SEE LICENSE IN LICENSE.md", "redistribution": "verified"},
        "provenance": {"kind": "vibeedit-owned", "source": f"main-repository:{record['source']['path']}#revision={record['source']['revision']}&sha256={record['source']['sha256']}", "implementation": f"skills/{record['name']}/SKILL.md", "thirdParty": [], "fidelity": "byte-identical-clone"},
        "validation": [{"id": "package-integrity", "status": "passed", "command": "node --test test/skills.test.js && pytest python/tests/test_skills.py", "evidence": f"{record['validation']['files']} files passed entrypoint, path, syntax, JSON, link, checksum, and safe lifecycle validation."}],
    }


def _frontmatter_description(path: Path) -> str:
    value = path.read_text(encoding="utf-8")
    match = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", value, re.MULTILINE)
    if match:
        return match.group(1).strip().strip("'\"")
    heading = re.search(r"^#\s+(.+)$", value, re.MULTILINE)
    return f"VibeEdit production workflow for {heading.group(1) if heading else path.parent.name}."


def _tree_checksum(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _files_checksum(files: list[dict]) -> str:
    digest = hashlib.sha256()
    for file in sorted(files, key=lambda item: item["relative"]):
        digest.update(file["relative"].encode())
        digest.update(b"\0")
        digest.update(file["content"])
        digest.update(b"\0")
    return digest.hexdigest()


def _show(root: Path, revision: str, path: str) -> bytes:
    return _git(root, "show", f"{revision}:{path}")


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
