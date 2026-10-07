"""Explicit setup for the packaged CEF host; rendering never downloads runtimes."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from vibeedit.cache import cache_root
from vibeedit.data import data_path
from vibeedit.version import VERSION

CEF_VERSION = "144.0.30+g9e70dde+chromium-144.0.7559.257"
ARCHIVE = f"cef_binary_{CEF_VERSION}_macosarm64.tar.bz2"
CEF_SHA256 = "74a0b4495ff0985105e64a584efbb1ac1375bb97a3c6e92050dd4ac7277c9960"
HOST_RELATIVE = "build/Release/VibeEditRenderer.app/Contents/MacOS/VibeEditRenderer"
BRIDGE_RELATIVE = "surface-bridge/target/release/libvibeedit_cef_surface_bridge.dylib"


def native_paths() -> tuple[Path, Path]:
    source = data_path("browser-renderer")
    if (source / HOST_RELATIVE).is_file():
        return source / HOST_RELATIVE, source / BRIDGE_RELATIVE
    runtime = cache_root() / "cef" / VERSION
    return runtime / HOST_RELATIVE, runtime / BRIDGE_RELATIVE


def native_status() -> dict:
    host, bridge = native_paths()
    supported = (
        sys.platform == "darwin"
        and platform.machine() == "arm64"
        and int(platform.mac_ver()[0].split(".")[0]) >= 15
    )
    return {
        "id": "browser.cef",
        "available": supported and host.is_file() and bridge.is_file(),
        "provider": "cef+metal+videotoolbox",
        "version": CEF_VERSION,
        "detail": "Accelerated opaque H.264 export; macOS 15+ ARM64. Runtime setup is explicit.",
        "setup": "vibeedit setup --cef (requires Xcode command-line tools, CMake, Ninja and Rust)",
        "required": True,
    }


def setup_cef() -> dict:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise RuntimeError("CEF acceleration requires macOS ARM64; use setup --browser and --backend screenshot here.")
    if int(platform.mac_ver()[0].split(".")[0]) < 15:
        raise RuntimeError("CEF acceleration requires macOS 15 or newer.")
    tools = {name: shutil.which(name) for name in ("cmake", "ninja", "clang++", "cargo")}
    if not tools["cargo"] and (Path.home() / ".cargo/bin/cargo").is_file():
        tools["cargo"] = str(Path.home() / ".cargo/bin/cargo")
    missing = [name for name, executable in tools.items() if not executable]
    if missing:
        raise RuntimeError("CEF setup requires Xcode command-line tools, CMake, Ninja and Rust; missing: " + ", ".join(missing))
    source = data_path("browser-renderer")
    inputs = [*sorted((source / "host").rglob("*")), *sorted((source / "surface-bridge/src").rglob("*")),
              source / "surface-bridge/Cargo.toml", source / "surface-bridge/Cargo.lock", source / "surface-bridge/build.rs"]
    if not inputs or not all(path.is_file() for path in inputs):
        raise RuntimeError("Packaged CEF build sources are incomplete; reinstall VibeEdit.")
    digest = hashlib.sha256()
    for path in inputs:
        digest.update(path.relative_to(source).as_posix().encode() + b"\0" + path.read_bytes())
    source_sha = digest.hexdigest()
    parent = cache_root() / "cef"
    parent.mkdir(parents=True, exist_ok=True)
    runtime = parent / VERSION
    import fcntl

    # Serialize explicit installers; publish only a complete, successful build.
    with (parent / "setup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest_path = runtime / "runtime.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("sourceSha256") == source_sha and all(
                (runtime / relative).is_file() and _sha256(runtime / relative) == manifest.get(key)
                for relative, key in ((HOST_RELATIVE, "hostSha256"), (BRIDGE_RELATIVE, "bridgeSha256"))
            ):
                return {**native_status(), "status": "already-built", "sourceSha256": source_sha}
        # Use the checksum-pinned archive cache shared with the original prototype.
        downloads = Path.home() / "Library/Caches/vibeedit/cef"
        downloads.mkdir(parents=True, exist_ok=True)
        archive = downloads / ARCHIVE
        if not archive.is_file():
            with tempfile.NamedTemporaryFile(dir=downloads, suffix=".partial", delete=False) as temporary:
                temporary_path = Path(temporary.name)
            try:
                with urllib.request.urlopen("https://cef-builds.spotifycdn.com/" + ARCHIVE, timeout=60) as response, temporary_path.open("wb") as output:
                    shutil.copyfileobj(response, output)
                if _sha256(temporary_path) != CEF_SHA256:
                    raise RuntimeError("Pinned CEF archive checksum mismatch; refusing to build.")
                temporary_path.replace(archive)
            finally:
                temporary_path.unlink(missing_ok=True)
        if _sha256(archive) != CEF_SHA256:
            raise RuntimeError("Pinned CEF archive checksum mismatch; remove the invalid cached archive and retry.")
        cef = downloads / ARCHIVE.removesuffix(".tar.bz2")
        if not cef.is_dir():
            with tempfile.TemporaryDirectory(dir=downloads, prefix="cef-extract-") as temporary:
                with tarfile.open(archive, "r:bz2") as bundle:
                    bundle.extractall(temporary, filter="data")
                (Path(temporary) / cef.name).replace(cef)
        with tempfile.TemporaryDirectory(dir=parent, prefix="cef-build-") as temporary:
            stage = Path(temporary) / "runtime"
            shutil.copytree(source / "host", stage / "host")
            shutil.copytree(source / "surface-bridge/src", stage / "surface-bridge/src")
            for name in ("Cargo.toml", "Cargo.lock", "build.rs"):
                shutil.copy2(source / "surface-bridge" / name, stage / "surface-bridge" / name)
            _run([tools["cmake"], "-G", "Ninja", "-S", str(stage / "host"), "-B", str(stage / "build"),
                  f"-DCEF_ROOT={cef}", "-DCMAKE_BUILD_TYPE=Release", "-DUSE_SANDBOX=OFF"], stage)
            _run([tools["cmake"], "--build", str(stage / "build"), "-j", str(min(8, os.cpu_count() or 1))], stage)
            _run([tools["cargo"], "build", "--release", "--locked", "--manifest-path", str(stage / "surface-bridge/Cargo.toml")], stage / "surface-bridge")
            manifest = {"version": VERSION, "cefVersion": CEF_VERSION, "cefArchiveSha256": CEF_SHA256,
                        "sourceSha256": source_sha, "hostSha256": _sha256(stage / HOST_RELATIVE),
                        "bridgeSha256": _sha256(stage / BRIDGE_RELATIVE)}
            (stage / "runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
            # Preserve CEF notices alongside the cached runtime.
            shutil.copy2(cef / "LICENSE.txt", stage / "CEF-LICENSE.txt")
            if runtime.exists():
                raise RuntimeError("Existing CEF runtime differs or is damaged; remove that version's cache and rerun setup --cef.")
            stage.replace(runtime)
    return {**native_status(), "status": "built", "sourceSha256": source_sha}


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _run(arguments: list, directory: Path) -> None:
    # Keep successful --json CLI output machine-readable while displaying build progress.
    try:
        result = subprocess.run(arguments, cwd=directory, stdout=sys.stderr, stderr=sys.stderr, check=False, timeout=1800)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("CEF build exceeded its 30-minute deadline") from error
    if result.returncode:
        raise RuntimeError(f"CEF build command failed ({result.returncode}): {arguments[0]}")
