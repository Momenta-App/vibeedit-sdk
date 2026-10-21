"""Exercise runtime upgrades without downloading Pi or starting a provider process."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from vibeedit import worker


@pytest.fixture
def installation(tmp_path, monkeypatch):
    companion = tmp_path / "bundled companion"
    companion.mkdir()
    (companion / "package.json").write_text('{"version":"0.2.0-beta.1"}', encoding="utf-8")
    (companion / "package-lock.json").write_text(json.dumps({
        "version": "0.2.0-beta.1",
        "packages": {"node_modules/@earendil-works/pi-coding-agent": {
            "version": worker.PI_VERSION, "integrity": worker.PI_INTEGRITY,
        }},
    }), encoding="utf-8")
    monkeypatch.setenv("VIBEEDIT_CONFIG_HOME", str(tmp_path / "private config"))
    monkeypatch.setattr(worker, "companion_path", lambda: companion)
    monkeypatch.setattr(worker.shutil, "which", lambda name: {
        "npm": "fixture-npm", "npm.cmd": "fixture-npm", "node": "fixture-node",
    }.get(name))
    state = {"installs": [], "fail": False}

    def run(command, **kwargs):
        if command == ["fixture-node", "--version"]:
            return subprocess.CompletedProcess(command, 0, stdout="v22.19.0\n")
        assert command == ["fixture-npm", "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"]
        stage = Path(kwargs["cwd"])
        state["installs"].append(stage)
        # Only the external installer boundary is simulated. The actual setup
        # code validates the staged Pi metadata and publishes its readiness file.
        if state["fail"]:
            (stage / "partial-install").write_text("interrupted", encoding="utf-8")
            return subprocess.CompletedProcess(command, 1)
        package = stage / "node_modules/@earendil-works/pi-coding-agent"
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({
            "version": worker.PI_VERSION, "bin": {"pi": "dist/cli.js"},
        }), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(worker.subprocess, "run", run)
    return companion, state


def test_lock_upgrade_installs_beside_legacy_runtime_and_reuses_exact_lock(installation):
    companion, state = installation
    legacy = worker.config_home() / "runtime" / f"pi-{worker.PI_VERSION}"
    legacy.mkdir(parents=True)
    (legacy / "ready.json").write_text('{"piVersion":"1.3.0","lockSha256":"old-lock"}', encoding="utf-8")
    (legacy / "session.jsonl").write_text('{"originalOperation":"unknown-send"}\n', encoding="utf-8")
    original = {p.name: p.read_bytes() for p in legacy.iterdir()}

    first = worker.setup_worker()
    first_runtime = Path(first["runtime"])
    digest = hashlib.sha256((companion / "package-lock.json").read_bytes()).hexdigest()
    assert first_runtime.name == f"pi-1.3.0-{digest}"
    assert first_runtime != legacy
    assert first["lockSha256"] == digest
    assert first["providerCalls"] == 0
    assert Path(worker._pi_command(first_runtime, require_ready=True)[1]).parts[-2:] == ("dist", "cli.js")
    assert worker.setup_worker()["reused"] is True
    assert len(state["installs"]) == 1
    first_ready = (first_runtime / "ready.json").read_bytes()

    # A release-metadata-only lock change must select a separate runtime even
    # though the upstream Pi version and archive integrity remain unchanged.
    lock = json.loads((companion / "package-lock.json").read_text(encoding="utf-8"))
    lock["version"] = "0.2.0-beta.2"
    (companion / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    second = worker.setup_worker()
    assert second["runtime"] != first["runtime"]
    assert second["piVersion"] == first["piVersion"] == "1.3.0"
    assert second["integrity"] == first["integrity"] == worker.PI_INTEGRITY
    assert worker.worker_runtime() == Path(second["runtime"])
    assert worker.setup_worker()["reused"] is True
    assert len(state["installs"]) == 2
    assert (first_runtime / "ready.json").read_bytes() == first_ready
    assert {p.name: p.read_bytes() for p in legacy.iterdir()} == original
    with pytest.raises(ValueError, match="different package lock"):
        worker._pi_command(first_runtime, require_ready=True)


def test_failed_upgrade_can_retry_without_removing_previous_runtime(installation):
    companion, state = installation
    previous = Path(worker.setup_worker()["runtime"])
    previous_ready = (previous / "ready.json").read_bytes()
    with (companion / "package-lock.json").open("a", encoding="utf-8") as output:
        output.write("\n")
    state["fail"] = True
    with pytest.raises(ValueError, match="dependency installation failed"):
        worker.setup_worker()
    assert not worker.worker_runtime().exists()
    assert not list(previous.parent.glob("*.staging-*"))
    assert (previous / "ready.json").read_bytes() == previous_ready
    state["fail"] = False
    assert worker.setup_worker()["runtime"] != str(previous)
    assert worker.setup_worker()["reused"] is True
    assert len(state["installs"]) == 3


def test_invalid_upstream_integrity_cannot_install_a_new_runtime(installation):
    companion, state = installation
    lock = json.loads((companion / "package-lock.json").read_text(encoding="utf-8"))
    lock["packages"]["node_modules/@earendil-works/pi-coding-agent"]["integrity"] = "changed"
    (companion / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity differs"):
        worker.setup_worker()
    assert not state["installs"]
    assert not worker.worker_runtime().exists()
