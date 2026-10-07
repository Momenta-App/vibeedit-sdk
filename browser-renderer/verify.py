#!/usr/bin/env python3
"""Run built-artifact gates sequentially; never race a build with a warm host."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--full", action="store_true")
p.add_argument("--label", default="final")
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
evidence = root / "browser-renderer/evidence"
evidence.mkdir(exist_ok=True)
report = {"started": time.time(), "runs": []}
commands = [
    (
        "integration",
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_browser_render.py",
            "tests/test_cli.py",
            "tests/test_render.py",
            "-q",
            "--basetemp=/private/var/tmp/vibeedit-renderer-qualified-tests-20261004",
        ],
        root / "python",
    ),
    (
        "conformance",
        [
            sys.executable,
            "browser-renderer/conformance.py",
            *[
                f"browser-renderer/examples/{name}/job.json"
                for name in ["basic", "corpus", "features", "gpu"]
            ],
            "--report",
            "browser-renderer/evidence/conformance-final.json",
        ],
        root,
    ),
    ("media", [sys.executable, "browser-renderer/media_check.py"], root),
    (
        "normalized-media",
        [
            sys.executable,
            "browser-renderer/media_check.py",
            "--h264",
            "--report",
            "browser-renderer/evidence/normalized-media-timing.json",
        ],
        root,
    ),
    ("browser-color", [sys.executable, "browser-renderer/color_roundtrip.py"], root),
    ("reliability", [sys.executable, "browser-renderer/reliability.py"], root),
    ("gpu-recovery", [sys.executable, "browser-renderer/gpu_recovery.py"], root),
    ("service", [sys.executable, "browser-renderer/service_check.py"], root),
    ("memory", [sys.executable, "browser-renderer/memory_check.py"], root),
    ("alpha", [sys.executable, "browser-renderer/alpha_check.py"], root),
    (
        "quality",
        [
            sys.executable,
            "browser-renderer/quality.py",
            "browser-renderer/examples/corpus/job.json",
            "--report",
            "browser-renderer/evidence/quality-final.json",
        ],
        root,
    ),
    (
        "profile",
        [
            sys.executable,
            "browser-renderer/profile.py",
            "--report",
            "browser-renderer/evidence/profile-final.json",
        ],
        root,
    ),
]
if a.full:
    commands += [
        (
            "benchmark",
            [
                sys.executable,
                "browser-renderer/benchmark.py",
                "--frames",
                "900",
                "--repeats",
                "2",
                "--report",
                "browser-renderer/evidence/benchmark-final.json",
            ],
            root,
        ),
        (
            "soak",
            [
                sys.executable,
                "browser-renderer/soak.py",
                "--seconds",
                "600",
                "--report",
                "browser-renderer/evidence/soak-final.json",
            ],
            root,
        ),
    ]
for name, command, cwd in commands:
    if name != "integration":
        if "--report" not in command:
            command += ["--report", f"browser-renderer/evidence/{name}-{a.label}.json"]
        else:
            command[command.index("--report") + 1] = (
                f"browser-renderer/evidence/{name}-{a.label}.json"
            )
    print(name, flush=True)
    started = time.monotonic()
    with (evidence / f"{name}-{a.label}.log").open("w") as log:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env={**os.environ, "VIBEEDIT_CEF_INTEGRATION": "1"},
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    report["runs"].append(
        {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "exitCode": completed.returncode,
            "seconds": time.monotonic() - started,
        }
    )
    report["passed"] = all(run["exitCode"] == 0 for run in report["runs"])
    (evidence / f"verification-{a.label}.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    if completed.returncode:
        raise SystemExit(completed.returncode)
print(json.dumps(report, indent=2))
