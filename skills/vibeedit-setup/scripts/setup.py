#!/usr/bin/env python3
"""Exact-wheel project bootstrap. No account, global install or hidden source clone."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import venv
from pathlib import Path


def fetch(location, maximum):
    if urllib.parse.urlsplit(location).scheme == "https":
        with urllib.request.urlopen(location, timeout=60) as response:
            data = response.read(maximum + 1)
    elif not urllib.parse.urlsplit(location).scheme:
        with Path(location).open("rb") as stream:
            data = stream.read(maximum + 1)
    else:
        raise ValueError("Use a local file or HTTPS; insecure download is unsupported")
    if len(data) > maximum:
        raise ValueError("Download exceeds declared safe size")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--harness", choices=("codex", "claude", "agents"), required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise ValueError("Python 3.11+ is required; preserve this project and install a supported Python")
    manifest = json.loads(fetch(args.manifest, 1_000_000))
    if manifest.get("schemaVersion") != "vibeedit.release.v1":
        raise ValueError("Unsupported release manifest")
    wheel = manifest["artifacts"]["pythonWheel"]
    dependencies = manifest["artifacts"]["coreRequirements"]
    for record in (wheel, dependencies):
        if not isinstance(record.get("sha256"), str) or len(record["sha256"]) != 64 or any(c not in '0123456789abcdef' for c in record["sha256"]) or type(record.get("byteLength")) is not int or not 0 < record["byteLength"] <= 256 * 1024**2:
            raise ValueError("Missing bounded exact artifact digest/length")
    requirements = fetch(dependencies["url"], min(dependencies["byteLength"], 1_000_000))
    if len(requirements) != dependencies["byteLength"] or hashlib.sha256(requirements).hexdigest() != dependencies["sha256"]:
        raise ValueError("Core dependency lock checksum/length mismatch")
    project = Path(args.project).resolve()
    root = project / ".vibeedit" / "tools" / (wheel["sha256"] + "-" + dependencies["sha256"][:16])
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "setup.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError(f"Setup is active or interrupted. Inspect {lock}, verify its PID is no longer running, then remove only that lock and retry") from None
    with os.fdopen(descriptor, "w") as stream:
        stream.write(str(os.getpid()))
    try:
        environment = root / "venv"
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        complete = root / "complete.json"
        if not complete.exists():
            if not python.is_file():
                venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(environment)
            raw = fetch(wheel["url"], wheel["byteLength"])
            if len(raw) != wheel["byteLength"] or hashlib.sha256(raw).hexdigest() != wheel["sha256"]:
                raise ValueError("Wheel checksum/length mismatch; capability was not published")
            filename = urllib.parse.unquote(urllib.parse.urlsplit(wheel["url"]).path.split("/")[-1])
            if "/" in filename or "\\" in filename or not filename.endswith(".whl"):
                raise ValueError("Invalid wheel filename")
            archive = root / filename
            archive.write_bytes(raw)
            locked = root / "install.requirements.txt"
            locked.write_bytes(requirements + f"\n{archive.as_uri()} --hash=sha256:{wheel['sha256']}\n".encode())
            subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "--only-binary=:all:", "-r", str(locked)], check=True, stdout=sys.stderr, timeout=180)
            version = subprocess.check_output([str(python), "-c", "from importlib.metadata import version;print(version('vibeedit'))"], text=True, timeout=30).strip()
            if version != manifest["versions"]["python"]:
                raise ValueError("Installed wheel version does not match the release manifest")
            complete.write_text(json.dumps({"sha256": wheel["sha256"], "coreRequirementsSha256": dependencies["sha256"], "version": version}))
        marker = json.loads(complete.read_text())
        if marker != {"sha256": wheel["sha256"], "coreRequirementsSha256": dependencies["sha256"], "version": manifest["versions"]["python"]}:
            raise ValueError("Existing setup marker differs from this exact release")
        command = [str(python), "-m", "vibeedit"]
        doctor = json.loads(subprocess.check_output([*command, "doctor", "--json"], text=True, timeout=60))
        status = json.loads(subprocess.check_output([*command, "skills", "check", "vibeedit-setup", "--harness", args.harness, "--json"], cwd=project, text=True, timeout=30))
        if not status.get("installed"):
            subprocess.run([*command, "skills", "install", "vibeedit-setup", "--harness", args.harness, "--json"], cwd=project, stdout=sys.stderr, check=True, timeout=30)
        receipt = {"schemaVersion": "vibeedit.setupReceipt.v1", "ok": True, "releaseId": manifest["id"], "wheelSha256": wheel["sha256"], "command": command, "project": str(project), "doctor": doctor, "modifiedSkillPreserved": status.get("modified", False)}
        (root / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, indent=2))
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"schemaVersion": "vibeedit.setupReceipt.v1", "ok": False, "error": str(error)}))
        raise SystemExit(1)
