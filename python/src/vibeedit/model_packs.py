"""Optional, integrity-pinned local models. No weights ship in VibeEdit archives."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from vibeedit.cache import cache_root
from vibeedit.model_runners import transnet
from vibeedit.setup import SAM_SOURCE, SAM_TINY

RUNNER_VERSION = "vibeedit.models.v1"
PINS = json.loads((Path(__file__).parent / "model_runners" / "pins.json").read_text())
PACKS = {
    "transnet": {
        "model": "TransNetV2", "revision": transnet.COMMIT, "license": "MIT",
        "termsUrl": f"https://github.com/soCzech/TransNetV2/blob/{transnet.COMMIT}/LICENSE",
        "downloadBytes": sum(x[1] for x in transnet.FILES.values()),
        "diskEstimateBytes": 3_000_000_000, "memoryEstimateBytes": 4_000_000_000,
        "dependencies": ["tensorflow==2.21.0"], "device": "cpu",
        "artifacts": [{"path": k, "bytes": v[1], "sha256": v[2], "sourceRevision": transnet.COMMIT} for k, v in transnet.FILES.items()],
        "limits": "Visual cut candidates, not semantic scenes. Native-density decode is bounded, not constant-memory streaming.",
    },
    "sam21": {
        "model": "sam2.1-hiera-tiny", "revision": "2b90b9f5ceec907a1c18123530e92e794ad901a4",
        "license": "Apache-2.0", "termsUrl": "https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/LICENSE",
        "downloadBytes": 211653811, "diskEstimateBytes": 6_000_000_000 if platform.system() == "Darwin" else 25_000_000_000, "memoryEstimateBytes": 6_000_000_000,
        "dependencies": ["torch==2.12.0", "torchvision==0.27.0", "numpy==2.5.1", "pillow==11.3.0", "opencv-python-headless==4.13.0.92", "hydra-core==1.3.2", "iopath==0.1.10", "tqdm==4.67.1"],
        "artifacts": [SAM_SOURCE, SAM_TINY],
        "device": "auto", "limits": "Tiny is a preview-oriented model. Box-prompted independent image inference; no implicit identity tracking across hard cuts or automatic final-quality claim.",
    },
    "sam31-mlx": {
        "model": "sam3.1-bf16", "revision": PINS["mlx-community/sam3.1-bf16"]["revision"],
        "source": "mlx-vlm==0.7.6", "runtimeArtifact": PINS["mlx-vlm-runtime"], "license": "SAM License (weights); MIT (mlx-vlm); MIT (CLIP tokenizer)",
        "termsUrl": PINS["sam-license"]["url"],
        "downloadBytes": sum(f["bytes"] for k in ["mlx-community/sam3.1-bf16", "openai/clip-vit-base-patch32"] for f in PINS[k]["files"]) + PINS["sam-license"]["bytes"],
        "diskEstimateBytes": 8_000_000_000, "memoryEstimateBytes": 16_000_000_000,
        "dependencies": ["mlx-vlm==0.7.6"], "device": "mlx-metal",
        "artifacts": [*PINS["mlx-community/sam3.1-bf16"]["files"], *PINS["openai/clip-vit-base-patch32"]["files"], PINS["sam-license"]],
        "limits": "Apple Silicon only. Sparse per-frame text/box detection, not temporal propagation or certified identity. Review cuts, occlusions and contacts. Custom SAM terms apply; VibeEdit MIT terms do not relicense weights.",
    },
}


def _checked(command, **options):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600, **options)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Optional model setup exceeded 600 seconds. Verified downloads/partial runtime are retained; inspect the original setup before retrying the same pack.") from None
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:] or "Model runtime setup failed; retry the same pack without replacing the system Python")
    return result


def _root(cache=None):
    return Path(cache).expanduser().resolve() if cache else cache_root().resolve() / "model-packs"


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
    os.replace(stream.name, path)


def _python(runtime):
    return runtime / "env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _supported(name, *, system=None, machine=None, macos=None):
    system = platform.system() if system is None else system
    machine = platform.machine().lower() if machine is None else machine.lower()
    if system == "Darwin" and machine not in {"arm64", "aarch64"}:
        return "The pinned TensorFlow/Torch/MLX packs do not publish macOS Intel runtimes. Core VibeEdit remains independent; no older runtime/model was substituted."
    if name == "sam31-mlx" and not (system == "Darwin" and machine in {"arm64", "aarch64"}):
        return "SAM 3.1 MLX requires Apple Silicon macOS. This pack does not substitute SAM 2.1."
    if system == "Darwin":
        version = platform.mac_ver()[0] if macos is None else macos
        minimum = 12 if name == "transnet" else 14
        if not version or int(version.split(".")[0]) < minimum:
            return f"This pinned model runtime requires macOS {minimum} or newer; detected {version or 'unknown'}. Core editing is a separate capability."
    if system == "Windows" and machine not in {"amd64", "x86_64"}:
        return "The pinned TensorFlow/Torch packs require Windows x86_64; this architecture is unqualified."
    if system == "Linux" and machine not in {"amd64", "x86_64", "aarch64", "arm64"}:
        return "The pinned TensorFlow/Torch Linux wheels target x86_64/aarch64; this architecture is unqualified."
    if system not in {"Darwin", "Linux", "Windows"}:
        return "This operating system is unqualified for the pinned model runtimes; no substitute was installed."
    return None


@contextmanager
def _lease(root, *, resource_root=None):
    """One package-owned heavy model/setup owner across the user's model caches."""
    root.mkdir(parents=True, exist_ok=True)
    shared = Path(resource_root) if resource_root is not None else Path.home() / ("AppData/Local/VibeEdit" if os.name == "nt" else "Library/Caches/VibeEdit" if platform.system() == "Darwin" else ".cache/vibeedit") / "model-execution"
    shared.mkdir(parents=True, exist_ok=True)
    lock = shared / ".model.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError(f"Model execution is busy or an interrupted shared lease remains at {lock}. Inspect owner.json and the original process before removing that lease; do not start duplicate inference.") from None
    _write(lock / "owner.json", {"pid": os.getpid(), "leaseCreatedUnix": time.time(), "cache": str(root), "runnerVersion": RUNNER_VERSION})
    try:
        yield
    finally:
        (lock / "owner.json").unlink(missing_ok=True)
        lock.rmdir()


def probe_model_pack(name, cache=None, *, candidate=False):
    runtime = _root(cache) / name
    unsupported = _supported(name)
    manifest = runtime / ("candidate.json" if candidate else "installed.json")
    if unsupported:
        return {"id": name, "available": False, "status": "unsupported-platform", "reason": unsupported}
    if not manifest.is_file() or not _python(runtime).is_file():
        return {"id": name, "available": False, "status": "not-installed", "retry": f"vibeedit models setup {name} --json"}
    record = json.loads(manifest.read_text())
    if record["definitionSha256"] != _definition_digest(name):
        return {"id": name, "available": False, "status": "definition-changed", "retry": f"vibeedit models setup {name} --json"}
    bad = [x["path"] for x in record["files"] if not (runtime / x["path"]).is_file() or (runtime / x["path"]).stat().st_size != x["bytes"] or _digest(runtime / x["path"]) != x["sha256"]]
    if bad:
        return {"id": name, "available": False, "status": "integrity-failed", "files": bad, "retry": f"Inspect altered cache files then rerun vibeedit models setup {name}"}
    try:
        result = subprocess.run([str(_python(runtime)), "-m", "vibeedit.model_runners.segment", "probe", name], env=_env(), capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"id": name, "available": False, "status": "runtime-timeout", "reason": "Runtime import/device probe exceeded 180 seconds. Inspect local security/runtime diagnostics, then retry the same pack; no inference was submitted."}
    if result.returncode:
        return {"id": name, "available": False, "status": "runtime-failed", "reason": result.stderr[-2000:]}
    device = json.loads(result.stdout)
    key, expected = {"transnet": ("tensorflow", "2.21.0"), "sam21": ("torch", "2.12.0"), "sam31-mlx": ("mlx-vlm", "0.7.6")}[name]
    if str(device.get(key, "")).split("+")[0] != expected:
        return {"id": name, "available": False, "status": "runtime-version-mismatch", "runtime": device, "expected": {key: expected}, "retry": f"vibeedit models setup {name} --json"}
    if name == "sam31-mlx" and not device.get("metalAvailable"):
        return {"id": name, "available": False, "status": "unsupported-device", "runtime": device, "reason": "MLX Metal is unavailable; no CPU or SAM2 substitution was made"}
    return {"id": name, "available": True, "status": "installed", "qualification": "inference-and-visual-review-required", "runtime": device, "manifest": str(manifest)}


def _definition_digest(name):
    return hashlib.sha256(json.dumps({"pack": PACKS[name], "pins": PINS if name == "sam31-mlx" else {}, "runner": RUNNER_VERSION, "runnerSourceSha256": _digest(Path(__file__).parent / "model_runners" / ("transnet.py" if name == "transnet" else "segment.py"))}, sort_keys=True).encode()).hexdigest()


def _env():
    # Supply the installed package location to isolated runtimes without changing
    # their dependencies or fetching a different VibeEdit from a registry.
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}


def setup_model_pack(name, cache=None):
    if name not in PACKS:
        raise ValueError(f"Unknown model pack: {name}")
    if _supported(name):
        return {"schemaVersion": RUNNER_VERSION, "ok": False, **probe_model_pack(name, cache)}
    root = _root(cache)
    with _lease(root):
        runtime = root / name
        runtime.mkdir(parents=True, exist_ok=True)
        if (runtime / "installed.json").is_file():
            existing = probe_model_pack(name, cache)
            if existing["available"]:
                return {"schemaVersion": RUNNER_VERSION, "ok": True, "reused": True, **existing}
        required = PACKS[name]["diskEstimateBytes"]
        free = shutil.disk_usage(runtime).free
        if free < required:
            raise RuntimeError(f"Insufficient model-cache disk: {free} bytes free, conservative setup estimate {required}. Select an existing volume with --cache PATH; no partial capability was published.")
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError("Model packs use isolated Python 3.12 environments. Install uv, then retry this exact models setup command.")
        if not _python(runtime).is_file():
            _checked([uv, "venv", "--python", "3.12", str(runtime / "env")])
        dependencies = [f"mlx-vlm @ {PINS['mlx-vlm-runtime']['url']}#sha256={PINS['mlx-vlm-runtime']['sha256']}" if name == "sam31-mlx" and p == "mlx-vlm==0.7.6" else p for p in PACKS[name]["dependencies"]]
        _checked([uv, "pip", "install", "--python", str(_python(runtime)), "jsonschema==4.26.0", *dependencies])
        files = []
        if name == "transnet":
            transnet.setup(runtime / "artifacts")
            files = [{"path": "artifacts/" + p, "bytes": v[1], "sha256": v[2]} for p, v in transnet.FILES.items()]
        if name == "sam21":
            # Keep the existing public provider and its pinned source/weight verifier.
            command = "from vibeedit.setup import _setup_sam; from pathlib import Path; import sys; _setup_sam(Path(sys.argv[1]))"
            _checked([str(_python(runtime)), "-c", command, str(runtime)], env=_env())
            files = [{"path": "models/sam2.1-hiera-tiny/sam2-source.tar.gz", "bytes": SAM_SOURCE["bytes"], "sha256": SAM_SOURCE["sha256"]}, {"path": "models/sam2.1-hiera-tiny/sam2.1_hiera_tiny.pt", "bytes": SAM_TINY["bytes"], "sha256": SAM_TINY["sha256"]}]
        if name == "sam31-mlx":
            from vibeedit.setup import _download_verified
            for repo, prefix in [("mlx-community/sam3.1-bf16", "artifacts"), ("openai/clip-vit-base-patch32", "tokenizer")]:
                for f in PINS[repo]["files"]:
                    target = runtime / prefix / f["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    _download_verified(f["url"], target, f["sha256"], f["bytes"])
                    files.append({"path": str(target.relative_to(runtime)), "bytes": f["bytes"], "sha256": f["sha256"]})
            f = PINS["sam-license"]
            _download_verified(f["url"], runtime / f["path"], f["sha256"], f["bytes"])
            files.append({k: f[k] for k in ["path", "bytes", "sha256"]})
        if name == "sam21":
            files.extend({"path": str(p.relative_to(runtime)), "bytes": p.stat().st_size, "sha256": _digest(p)} for p in sorted((runtime / "models/sam2.1-hiera-tiny/source").rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
        freeze = _checked([uv, "pip", "freeze", "--python", str(_python(runtime))])
        (runtime / "requirements.lock").write_text(freeze.stdout)
        files.append({"path": "requirements.lock", "bytes": (runtime / "requirements.lock").stat().st_size, "sha256": _digest(runtime / "requirements.lock")})
        record = {"schemaVersion": RUNNER_VERSION, "id": name, "definitionSha256": _definition_digest(name), "definition": PACKS[name], "files": files, "runnerVersion": RUNNER_VERSION, "platform": platform.platform(), "qualification": "setup-only; real inference and mask review required"}
        _write(runtime / "candidate.json", record)
        result = probe_model_pack(name, cache, candidate=True)
        if result["available"]:
            (runtime / "candidate.json").replace(runtime / "installed.json")
            result["manifest"] = str(runtime / "installed.json")
        return {"schemaVersion": RUNNER_VERSION, "ok": result["available"], **result}


def _resource_snapshot():
    system = platform.system()
    volume = Path("/System/Volumes/Data") if system == "Darwin" else Path(Path.home().anchor)
    snapshot = {"system": system, "volume": str(volume), "diskFreeBytes": shutil.disk_usage(volume).free, "load": list(os.getloadavg()[:2]) if hasattr(os, "getloadavg") else None, "memoryFreePercent": None}
    try:
        if system == "Darwin":
            result = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=10)
            match = re.search(r"System-wide memory free percentage:\s*(\d+)%", result.stdout)
            if result.returncode == 0 and match:
                snapshot["memoryFreePercent"] = int(match.group(1))
        if system == "Linux":
            values = {line.split(":")[0]: int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith(("MemTotal:", "MemAvailable:"))}
            if values.get("MemTotal") and "MemAvailable" in values:
                snapshot["memoryFreePercent"] = 100 * values["MemAvailable"] / values["MemTotal"]
        if system == "Windows":
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("memoryLoad", ctypes.c_ulong), *[(name, ctypes.c_ulonglong) for name in ("totalPhysical", "availablePhysical", "totalPageFile", "availablePageFile", "totalVirtual", "availableVirtual", "availableExtendedVirtual")]]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                snapshot["memoryFreePercent"] = 100 - status.memoryLoad
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        snapshot["memoryProbeError"] = str(error)
    return snapshot


def _validate_resources(snapshot):
    reasons = []
    if snapshot["diskFreeBytes"] < 25 * 1024 ** 3:
        reasons.append("system-volume free space is below 25 GiB")
    if snapshot["memoryFreePercent"] is None:
        reasons.append("available-memory probe is unknown")
    elif snapshot["memoryFreePercent"] < 15:
        reasons.append("available memory is below 15%")
    if snapshot["load"] is not None and any(value > 10 for value in snapshot["load"]):
        reasons.append("one/five-minute load is above 10")
    if reasons:
        raise RuntimeError("Heavy model admission blocked: " + "; ".join(reasons) + ". Wait for resource headroom and retry the same job; no model was started. Snapshot: " + json.dumps(snapshot))
    return snapshot


def run_model_pack(name, source, output, *, cache=None, prompt=None, frames=None, max_frames=1200, threshold=.5):
    if prompt is not None and not isinstance(prompt, dict):
        raise ValueError("Model prompt must be a JSON object with explicit target parameters")
    root = _root(cache)
    with _lease(root):
        resources = _validate_resources(_resource_snapshot())
        probe = probe_model_pack(name, cache)
        if not probe["available"]:
            raise RuntimeError(json.dumps(probe))
        runtime = root / name
        source = Path(source).resolve(strict=True)
        output = Path(output).resolve()
        if name == "transnet":
            command = [str(_python(runtime)), "-m", "vibeedit.model_runners.transnet", "--cache", str(runtime / "artifacts"), "detect", str(source), "--output", str(output), "--max-frames", str(max_frames), "--threshold", str(threshold)]
        else:
            command = [str(_python(runtime)), "-m", "vibeedit.model_runners.segment", "run", name, str(runtime), str(source), str(output), json.dumps(prompt or {}), json.dumps(frames), str(max_frames)]
        result = subprocess.run(command, env=_env(), capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr[-4000:] or "Local model failed. Source/composition were not changed; inspect partial output before retrying.")
        return {"schemaVersion": RUNNER_VERSION, "ok": True, "id": name, "output": str(output), "sha256": _digest(output), "qualification": "needs-review", "resources": resources, "receipt": json.loads(result.stdout.splitlines()[-1])}


def register_commands(subparsers):
    parser = subparsers.add_parser("models", help="Optional pinned local TransNet/SAM model packs")
    commands = parser.add_subparsers(dest="models_command", required=True)
    for operation in ["list", "setup", "probe", "run"]:
        command = commands.add_parser(operation)
        if operation != "list":
            command.add_argument("pack", choices=PACKS)
        command.add_argument("--cache", type=Path)
        command.add_argument("--json", action="store_true")
        if operation == "run":
            command.add_argument("source", type=Path)
            command.add_argument("--output", type=Path, required=True)
            command.add_argument("--prompt", default="{}", help="JSON boxNormalized (SAM2.1) or text/box (SAM3.1)")
            command.add_argument("--frames", help="Comma-separated source frame ordinals; sparse SAM selection")
            command.add_argument("--max-frames", type=int, default=1200)
            command.add_argument("--threshold", type=float, default=.5)
        command.set_defaults(handler=_handle)

    export = commands.add_parser("export", help="Export explicit reviewed candidates as a CompositionSpec mask artifact")
    export.add_argument("index", type=Path)
    export.add_argument("--review", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--id", default="reviewed-subject")
    export.add_argument("--composition-start-frame", type=int, default=0)
    export.add_argument("--json", action="store_true")
    export.set_defaults(handler=_handle)
    effect = commands.add_parser("effect", help="Render source-bound reviewed subject fills as a derived editable visual layer")
    effect.add_argument("index", type=Path)
    effect.add_argument("--review", type=Path, required=True)
    effect.add_argument("--source", type=Path, required=True)
    effect.add_argument("--output", type=Path, required=True, help="New output directory")
    effect.add_argument("--frame-map", type=Path, help="Explicit VFR-to-composition source frame mapping")
    effect.add_argument("--color", default="#ffffff")
    effect.add_argument("--max-frames", type=int, default=1200)
    effect.add_argument("--json", action="store_true")
    effect.set_defaults(handler=_handle)


def _handle(args):
    if args.models_command in {"export", "effect"}:
        from vibeedit.model_masks import export_masks, render_subject_effect
        if importlib.util.find_spec("PIL") is None:
            raise RuntimeError("Reviewed mask export/effects require Pillow. Run vibeedit setup --effects in this isolated project environment, then retry.")
        if args.models_command == "export":
            result = export_masks(args.index, args.review, args.output, mask_id=args.id, composition_start_frame=args.composition_start_frame)
        else:
            result = render_subject_effect(args.index, args.review, args.source, args.output, mapping=json.loads(args.frame_map.read_text()) if args.frame_map else None, color=args.color, max_frames=args.max_frames)
    elif args.models_command == "list":
        result = {"schemaVersion": RUNNER_VERSION, "ok": True, "packs": [{"id": k, **v, **probe_model_pack(k, args.cache)} for k, v in PACKS.items()]}
    elif args.models_command == "probe":
        result = {"schemaVersion": RUNNER_VERSION, "ok": True, **probe_model_pack(args.pack, args.cache)}
    elif args.models_command == "setup":
        result = setup_model_pack(args.pack, args.cache)
    else:
        result = run_model_pack(args.pack, args.source, args.output, cache=args.cache, prompt=json.loads(args.prompt), frames=[int(x) for x in args.frames.split(",")] if args.frames else None, max_frames=args.max_frames, threshold=args.threshold)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1
