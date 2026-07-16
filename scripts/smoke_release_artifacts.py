from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean-install and exercise exact VibeEdit release archives")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--npm", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-revision", default=os.environ.get("GITHUB_SHA"))
    args = parser.parse_args(argv)
    for path in (args.wheel, args.npm):
        if not path.is_file():
            parser.error(f"archive is missing: {path}")
    uv = shutil.which("uv")
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not uv or not npm or not node:
        parser.error("uv, npm, and node are required")

    with tempfile.TemporaryDirectory(prefix="vibeedit-release-smoke-") as temporary:
        root = Path(temporary)
        python = prepare_python(uv, args.wheel.resolve(), root)
        python_result = smoke_python(python, root)
        node_result = smoke_node(npm, node, args.npm.resolve(), root)

    result = {
        "schemaVersion": "1.0.0",
        "status": "passed",
        "sourceRevision": args.source_revision,
        "archives": {
            "wheel": archive_record(args.wheel),
            "npm": archive_record(args.npm),
        },
        "python": python_result,
        "node": node_result,
    }
    value = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(value, encoding="utf-8")
    print(value, end="")
    return 0


def prepare_python(uv: str, wheel: Path, root: Path) -> Path:
    environment = root / "python"
    run([uv, "venv", str(environment)])
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([uv, "pip", "install", "--python", str(python), f"{wheel}[browser]"])
    return python


def smoke_python(python: Path, root: Path) -> dict[str, object]:
    setup = run_json([str(python), "-m", "vibeedit.cli", "setup", "--browser", "--json"])
    doctor = run_json([str(python), "-m", "vibeedit.cli", "doctor", "--json"])
    if not setup.get("complete") or not doctor.get("ready"):
        raise RuntimeError("clean wheel setup or doctor did not report ready")

    examples = root / "examples"
    basic = Path(run_json([str(python), "-m", "vibeedit.cli", "examples", "create", "basic-generated", str(examples), "--json"])["path"])
    basic_output = root / "basic.mp4"
    run_json([str(python), "-m", "vibeedit.cli", "render", str(basic / "composition.json"), "--output", str(basic_output), "--json"])
    basic_report = run_json([str(python), "-m", "vibeedit.cli", "verify", str(basic_output), "--spec", str(basic / "composition.json"), "--json"])

    mixed = Path(run_json([str(python), "-m", "vibeedit.cli", "examples", "create", "mixed-python-html", str(examples), "--json"])["path"])
    run([str(python), str(mixed / "render.py")], cwd=mixed)
    mixed_report = run_json([str(python), "-m", "vibeedit.cli", "verify", str(mixed / "mixed-python-html.mp4"), "--spec", str(mixed / "composition.json"), "--json"])
    if not basic_report.get("passed") or not mixed_report.get("passed"):
        raise RuntimeError("clean wheel render verification failed")

    requests = "\n".join(
        json.dumps(value)
        for value in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_catalog", "arguments": {"query": "procedural"}}},
        )
    ) + "\n"
    mcp = run([str(python), "-m", "vibeedit.cli", "mcp"], input_value=requests).stdout.splitlines()
    responses = [json.loads(line) for line in mcp]
    tools = responses[1]["result"]["tools"]
    if len(tools) != 10 or not responses[2]["result"]["structuredContent"]:
        raise RuntimeError("clean wheel MCP smoke failed")

    catalog = run_json([str(python), "-m", "vibeedit.cli", "catalog", "open", "--no-browser", "--json"])
    skills_root = root / "skills"
    skills_root.mkdir()
    installed = run_json(
        [str(python), "-m", "vibeedit.cli", "skills", "install", "vibeedit-effects", "--harness", "codex", "--scope", "project", "--json"],
        cwd=skills_root,
    )
    checked = run_json(
        [str(python), "-m", "vibeedit.cli", "skills", "check", "vibeedit-effects", "--harness", "codex", "--scope", "project", "--json"],
        cwd=skills_root,
    )
    if catalog.get("opened") or installed.get("action") != "installed" or not checked.get("installed") or checked.get("modified"):
        raise RuntimeError("clean wheel catalog or skill lifecycle smoke failed")

    return {
        "version": run([str(python), "-m", "vibeedit.cli", "--version"]).stdout.strip(),
        "doctorReady": True,
        "browserSetupComplete": True,
        "catalogResolved": True,
        "skillInstalledUnmodified": True,
        "mcpTools": len(tools),
        "mcpCatalogCallPassed": True,
        "renders": [render_record("basic-generated", basic_report), render_record("mixed-python-html", mixed_report)],
    }


def smoke_node(npm: str, node: str, archive: Path, root: Path) -> dict[str, object]:
    directory = root / "node"
    directory.mkdir()
    run([npm, "init", "-y"], cwd=directory)
    run([npm, "install", str(archive), "--ignore-scripts"], cwd=directory)
    package = directory / "node_modules" / "vibeedit"
    run([node, str(package / "bin" / "vibeedit.js"), "validate", str(package / "schema" / "fixtures" / "minimal.json")], cwd=directory)
    run(
        [
            node,
            "--input-type=module",
            "-e",
            "import('vibeedit').then(m=>{if(new m.Composition({id:'artifact-smoke'}).id!=='artifact-smoke')process.exit(1)})",
        ],
        cwd=directory,
    )
    audit_process = run([npm, "audit", "--omit=dev", "--json"], cwd=directory, check=False)
    audit = json.loads(audit_process.stdout)
    vulnerabilities = audit.get("metadata", {}).get("vulnerabilities", {}).get("total")
    if audit_process.returncode or vulnerabilities != 0:
        raise RuntimeError("clean npm archive audit failed")
    return {
        "version": run([node, str(package / "bin" / "vibeedit.js"), "--version"], cwd=directory).stdout.strip(),
        "apiImported": True,
        "compositionConstructed": True,
        "schemaValidated": True,
        "productionVulnerabilities": vulnerabilities,
    }


def render_record(example: str, report: dict[str, object]) -> dict[str, object]:
    checks = {value["id"]: value for value in report["checks"]}
    return {
        "example": example,
        "passed": report["passed"],
        "width": checks["width"]["actual"],
        "height": checks["height"]["actual"],
        "durationFrames": checks["durationFrames"]["actual"],
        "durationDriftFrames": checks["durationFrames"]["drift"],
        "hasVideo": checks["hasVideo"]["actual"],
        "hasAudio": checks["hasAudio"]["actual"],
    }


def archive_record(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def run_json(command: list[str], *, cwd: Path | None = None) -> dict[str, object]:
    return json.loads(run(command, cwd=cwd).stdout)


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    input_value: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, input=input_value, capture_output=True, text=True, check=False)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"command failed: {command[0]}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
