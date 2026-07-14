from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from vibeedit.spec import JSONObject


@dataclass(frozen=True)
class Capability:
    id: str
    available: bool
    provider: str | None
    version: str | None
    detail: str
    setup: str | None = None

    def to_spec(self) -> JSONObject:
        return {
            "id": self.id,
            "available": self.available,
            "provider": self.provider,
            "version": self.version,
            "detail": self.detail,
            "setup": self.setup,
        }


def doctor() -> JSONObject:
    system = platform.system().lower()
    machine = platform.machine().lower()
    ffmpeg = _command("ffmpeg")
    ffprobe = _command("ffprobe")
    playwright = _module("playwright")
    numpy = _module("numpy")
    pillow = _module("PIL")
    from vibeedit.vision import CapabilityRouter
    from vibeedit.vision import _sam_provider
    capabilities = [
        Capability("media.render", ffmpeg[0] and ffprobe[0], "ffmpeg" if ffmpeg[0] else None, ffmpeg[1], "FFmpeg and FFprobe command-line tools", "Install FFmpeg and ensure ffmpeg/ffprobe are on PATH."),
        Capability("media.presets", numpy[0] and pillow[0], "numpy+pillow" if numpy[0] and pillow[0] else None, numpy[1], "333 deterministic image/effect/transition presets", 'Install with: pip install "vibeedit[effects]" or run vibeedit setup --effects.'),
        Capability("motion.html", playwright[0], "playwright" if playwright[0] else None, playwright[1], "Deterministic browser motion rendering", 'Install with: pip install "vibeedit[browser]"; then run vibeedit setup --browser.'),
    ]
    capabilities.extend(Capability(item["id"], item["available"], item["provider"], None, item["detail"], item["setup"]) for item in CapabilityRouter().status())
    segmentation = next(item for item in capabilities if item.id == "vision.segmentation")
    sam = _sam_provider()
    capabilities.extend([
        Capability("sam.2.1", bool(sam and sam[1]["capability"] == "sam.2.1"), segmentation.provider if sam and sam[1]["capability"] == "sam.2.1" else None, sam[1]["version"] if sam and sam[1]["capability"] == "sam.2.1" else None, "SAM 2.1 through the checksum-declared optional provider" if sam and sam[1]["capability"] == "sam.2.1" else "Approved checksum-pinned SAM 2.1 provider is not installed", None if sam and sam[1]["capability"] == "sam.2.1" else 'Install with: pip install "vibeedit[sam]"; then run vibeedit setup --sam.'),
        Capability("sam.3.1", bool(sam and sam[1]["capability"] == "sam.3.1"), segmentation.provider if sam and sam[1]["capability"] == "sam.3.1" else None, sam[1]["version"] if sam and sam[1]["capability"] == "sam.3.1" else None, "SAM 3.1 through a user-configured checksum-declared provider" if sam and sam[1]["capability"] == "sam.3.1" else "SAM 3.1 is quarantined until code, weights, checksum, license, and platform validation pass", None if sam and sam[1]["capability"] == "sam.3.1" else "No supported automatic setup is published yet."),
    ])
    return {
        "version": 1,
        "platform": {"system": system, "machine": machine, "python": sys.version.split()[0]},
        "ready": all(item.available for item in capabilities if item.id == "media.render"),
        "capabilities": [item.to_spec() for item in capabilities],
    }


def write_doctor(path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(doctor(), indent=2) + "\n", encoding="utf-8")
    return output


def _command(name: str) -> tuple[bool, str | None]:
    executable = shutil.which(name)
    if not executable:
        return False, None
    result = subprocess.run([executable, "-version"], capture_output=True, text=True, check=False)
    first = (result.stdout or result.stderr).splitlines()
    return result.returncode == 0, first[0] if first else "available"


def _module(name: str) -> tuple[bool, str | None]:
    if importlib.util.find_spec(name) is None:
        return False, None
    try:
        module = __import__(name)
    except ImportError:
        return False, None
    return True, str(getattr(module, "__version__", "available"))
