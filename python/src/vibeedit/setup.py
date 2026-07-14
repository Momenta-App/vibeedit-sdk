from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import importlib.util
import shutil
import tarfile
import urllib.request
from importlib.metadata import version
from pathlib import Path

from vibeedit.cache import cache_root
from vibeedit.data import data_path
from vibeedit.spec import JSONObject
from vibeedit.vision import CapabilityRouter


SAM_SOURCE = {
    "revision": "2b90b9f5ceec907a1c18123530e92e794ad901a4",
    "url": "https://github.com/facebookresearch/sam2/archive/2b90b9f5ceec907a1c18123530e92e794ad901a4.tar.gz",
    "sha256": "1f2fbfad3ffa38110368abac76c6ef9df9c282a66d5c2807bc94abf4d2fb30f8",
    "bytes": 55_645_345,
}
SAM_TINY = {
    "id": "sam2.1-hiera-tiny",
    "version": "2024-09-29",
    "url": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt",
    "sha256": "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69",
    "bytes": 156_008_466,
}
OBJECT_MODEL = {
    "id": "ssd-mobilenet-v1-12",
    "version": "019281f3fcb151a90e491f3b2f0273f9f31bd6be",
    "url": "https://huggingface.co/onnxmodelzoo/ssd_mobilenet_v1_12/resolve/019281f3fcb151a90e491f3b2f0273f9f31bd6be/ssd_mobilenet_v1_12.onnx?download=true",
    "sha256": "b8fba5e404077d4048d27fcd1667e85e27e192eb9bf51e696c46a3acd7d21058",
    "bytes": 29_461_455,
}


def install_setup_dependencies(*, browser: bool = False, effects: bool = False, vision: bool = False, sam: bool = False) -> JSONObject:
    packages = []
    if browser and importlib.util.find_spec("playwright") is None:
        packages.append("playwright==1.61.0")
    if effects and any(importlib.util.find_spec(module) is None for module in ["numpy", "PIL"]):
        packages.extend([
            "numpy==2.4.6" if sys.version_info[:2] == (3, 11) else "numpy==2.5.1",
            "pillow==11.3.0",
        ])
    vision_modules = ["numpy", "PIL", "cv2", *(["onnxruntime"] if _onnx_runtime_supported() else [])]
    if vision and any(importlib.util.find_spec(module) is None for module in vision_modules):
        packages.extend([
            "numpy==2.4.6" if sys.version_info[:2] == (3, 11) else "numpy==2.5.1",
            "pillow==11.3.0",
            "opencv-python-headless==4.13.0.92",
            *(["onnxruntime==1.27.0"] if _onnx_runtime_supported() else []),
        ])
    if sam and any(importlib.util.find_spec(module) is None for module in ["numpy", "PIL", "cv2", "torch", "torchvision", "hydra", "iopath", "tqdm"]):
        packages.extend([
            "numpy==2.4.6" if sys.version_info[:2] == (3, 11) else "numpy==2.5.1",
            "pillow==11.3.0",
            "opencv-python-headless==4.13.0.92",
            "torch==2.12.0",
            "torchvision==0.27.0",
            "hydra-core==1.3.2",
            "iopath==0.1.10",
            "tqdm==4.67.1",
        ])
    if not packages:
        return {"installed": [], "changed": False}
    uv = shutil.which("uv")
    packages = list(dict.fromkeys(packages))
    command = [uv, "pip", "install", "--python", sys.executable, *packages] if uv else [sys.executable, "-m", "pip", "install", *packages]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "optional runtime installation failed")
    importlib.invalidate_caches()
    return {"installed": packages, "changed": True}


def setup_capabilities(*, browser: bool = False, effects: bool = False, vision: bool = False, sam: bool = False) -> JSONObject:
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    results = []
    if browser:
        results.append(_setup_browser(root))
    if effects:
        numpy = importlib.util.find_spec("numpy") is not None
        pillow = importlib.util.find_spec("PIL") is not None
        results.append({"id": "media.presets", "available": numpy and pillow, "provider": "numpy+pillow" if numpy and pillow else None, "status": "available" if numpy and pillow else "missing", "required": True, "reason": "333 deterministic preset implementations require the effects extra"})
    if vision:
        results.append(_setup_apple_vision(root))
        results.append(_setup_object_model(root))
    if sam:
        results.append(_setup_sam(root))
    if vision:
        results.extend(CapabilityRouter().status())
    manifest = {"schemaVersion": "1.0.0", "results": results}
    (root / "setup.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _setup_browser(root: Path) -> JSONObject:
    try:
        playwright_version = version("playwright")
    except Exception as error:
        raise RuntimeError('browser setup requires: pip install "vibeedit[browser]"') from error
    result = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Playwright Chromium setup failed")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path)
    if not executable.is_file():
        raise RuntimeError("Playwright reported Chromium without an executable")
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    manifest = root / "browser.json"
    previous = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else None
    if previous and previous.get("version") == playwright_version and previous.get("sha256") and previous["sha256"] != digest:
        raise RuntimeError("installed Chromium executable checksum changed for the pinned Playwright version; remove the cache and retry setup")
    record = {"id": "motion.html", "available": True, "provider": "playwright-chromium", "version": playwright_version, "required": True, "executable": str(executable), "sha256": digest, "license": "Playwright Apache-2.0; Chromium notices apply"}
    manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def _setup_apple_vision(root: Path) -> JSONObject:
    if platform.system() != "Darwin":
        return {"id": "vision.apple_runner", "available": False, "provider": None, "status": "unsupported-platform", "required": False, "reason": "The native Apple Vision runner is available only on macOS; OpenCV remains available through the vision extra."}
    swift = shutil.which("swift")
    if not swift:
        return {"id": "vision.apple_runner", "available": False, "provider": None, "status": "missing-toolchain", "required": True, "reason": "Install the Apple Command Line Tools, then rerun `vibeedit setup --vision`."}
    source = data_path("apple-vision-runner")
    if not (source / "Package.swift").is_file():
        raise RuntimeError("the packaged Apple Vision runner source is missing")
    runtime = root / "runtimes" / "apple-vision"
    scratch = runtime / "build"
    runtime.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([swift, "build", "-c", "release", "--package-path", str(source), "--scratch-path", str(scratch)], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Apple Vision runner build failed")
    built = scratch / "release" / "vibeedit-apple-vision"
    if not built.is_file():
        raise RuntimeError("Swift completed without producing the Apple Vision runner")
    runner = runtime / "vibeedit-apple-vision"
    shutil.copy2(built, runner)
    runner.chmod(runner.stat().st_mode | 0o111)
    capabilities = subprocess.run([str(runner), "capabilities"], capture_output=True, text=True, check=False)
    if capabilities.returncode:
        raise RuntimeError(capabilities.stderr.strip() or "Apple Vision capability probe failed")
    try:
        declared = json.loads(capabilities.stdout)["capabilities"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Apple Vision runner returned an invalid capability declaration") from error
    if not isinstance(declared, list) or any(item not in {"face", "body", "pose", "object"} for item in declared):
        raise RuntimeError("Apple Vision runner declared an unsupported capability")
    digest = hashlib.sha256(runner.read_bytes()).hexdigest()
    record = {"schemaVersion": "1.0.0", "id": "vision.apple_runner", "available": True, "provider": "apple-vision", "status": "installed", "required": True, "capabilities": declared, "runner": str(runner), "sha256": digest, "license": "VibeEdit-owned source; see package LICENSE.md", "platform": platform.platform()}
    (runtime / "runtime.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def _setup_object_model(root: Path) -> JSONObject:
    if not _onnx_runtime_supported():
        return {"id": "vision.object_model", "available": False, "provider": None, "status": "unsupported-platform", "required": False, "reason": "ONNX Runtime 1.27 does not publish macOS Intel wheels; OpenCV face/body detection and the Apple Vision runner remain available."}
    runtime = root / "models" / OBJECT_MODEL["id"]
    model = runtime / "model.onnx"
    runtime.mkdir(parents=True, exist_ok=True)
    _download_verified(OBJECT_MODEL["url"], model, OBJECT_MODEL["sha256"], OBJECT_MODEL["bytes"])
    manifest = {
        "schemaVersion": "1.0.0",
        "id": OBJECT_MODEL["id"],
        "capability": "vision.object",
        "version": OBJECT_MODEL["version"],
        "license": "SSD-MobileNetV1 model card states MIT; ONNX Model Zoo repository metadata states Apache-2.0; COCO dataset terms apply",
        "weightsSha256": OBJECT_MODEL["sha256"],
        "weightsBytes": OBJECT_MODEL["bytes"],
        "checkpoint": str(model),
        "source": OBJECT_MODEL["url"],
    }
    path = runtime / "model.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"id": "vision.object_model", "available": True, "provider": OBJECT_MODEL["id"], "version": OBJECT_MODEL["version"], "status": "installed", "required": True, "bytes": OBJECT_MODEL["bytes"], "license": manifest["license"], "manifest": str(path)}


def _onnx_runtime_supported() -> bool:
    return platform.system() != "Darwin" or platform.machine().lower() != "x86_64"


def _setup_sam(root: Path) -> JSONObject:
    runtime = root / "models" / "sam2.1-hiera-tiny"
    source_archive = runtime / "sam2-source.tar.gz"
    checkpoint = runtime / "sam2.1_hiera_tiny.pt"
    source = runtime / "source"
    runtime.mkdir(parents=True, exist_ok=True)
    _download_verified(SAM_SOURCE["url"], source_archive, SAM_SOURCE["sha256"], SAM_SOURCE["bytes"])
    _download_verified(SAM_TINY["url"], checkpoint, SAM_TINY["sha256"], SAM_TINY["bytes"])
    if not (source / "sam2").is_dir():
        temporary = runtime / "source.extracting"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir()
        with tarfile.open(source_archive, "r:gz") as archive:
            for member in archive.getmembers():
                relative = Path(*Path(member.name).parts[1:])
                if not relative.parts or member.issym() or member.islnk() or ".." in relative.parts:
                    continue
                destination = (temporary / relative).resolve()
                if temporary.resolve() not in destination.parents:
                    raise RuntimeError("SAM source archive contains an unsafe path")
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                stream = archive.extractfile(member)
                if stream:
                    destination.write_bytes(stream.read())
        if source.exists():
            shutil.rmtree(source)
        temporary.rename(source)
    runner = runtime / "sam-runner.py"
    runner.write_text(f"import os\nos.environ['VIBEEDIT_SAM_RUNTIME'] = {str(runtime)!r}\nfrom vibeedit.sam_runner import main\nraise SystemExit(main())\n", encoding="utf-8")
    runtime_versions = {}
    if all(importlib.util.find_spec(module) is not None for module in ["cv2", "numpy", "torch"]):
        import cv2
        import numpy
        import torch

        runtime_versions = {
            "device": "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu",
            "torch": torch.__version__,
            "opencv": cv2.__version__,
            "numpy": numpy.__version__,
        }
    manifest = {
        "schemaVersion": "1.0.0",
        "id": SAM_TINY["id"],
        "capability": "sam.2.1",
        "version": SAM_TINY["version"],
        "license": "Apache-2.0 (Meta SAM 2 source and model checkpoint)",
        "weightsSha256": SAM_TINY["sha256"],
        "weightsBytes": SAM_TINY["bytes"],
        "sourceRevision": SAM_SOURCE["revision"],
        "sourceSha256": SAM_SOURCE["sha256"],
        "sourceBytes": SAM_SOURCE["bytes"],
        "runner": str(runner),
        "runnerCommand": [sys.executable, str(runner)],
        "checkpoint": str(checkpoint),
        "source": str(source),
        **({"runtimeVersions": runtime_versions} if runtime_versions else {}),
    }
    (runtime / "model.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"id": "sam.2.1", "available": True, "provider": SAM_TINY["id"], "version": SAM_TINY["version"], "status": "installed", "required": True, "bytes": SAM_SOURCE["bytes"] + SAM_TINY["bytes"], "license": manifest["license"], "manifest": str(runtime / "model.json")}


def _download_verified(url: str, destination: Path, expected_sha256: str, expected_bytes: int) -> None:
    if destination.is_file() and destination.stat().st_size == expected_bytes and hashlib.sha256(destination.read_bytes()).hexdigest() == expected_sha256:
        return
    temporary = destination.with_suffix(destination.suffix + ".download")
    temporary.unlink(missing_ok=True)
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > expected_bytes:
                raise RuntimeError(f"download exceeded declared size: {url}")
            digest.update(chunk)
            output.write(chunk)
    if size != expected_bytes or digest.hexdigest() != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"download checksum or size mismatch: {url}")
    temporary.replace(destination)
