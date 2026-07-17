from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_assets.py <workdir>")
    workdir = Path(sys.argv[1])
    workdir.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to generate benchmark assets")
    video = workdir / "source.mp4"
    audio = workdir / "music.wav"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-threads", "1", "-map_metadata", "-1", str(video)], check=True)
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=10", "-c:a", "pcm_s16le", "-map_metadata", "-1", str(audio)], check=True)
    version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    result = {
        "schemaVersion": "1.0.0",
        "generator": version,
        "assets": [
            {"id": "source", "path": str(video), "bytes": video.stat().st_size, "sha256": hashlib.sha256(video.read_bytes()).hexdigest()},
            {"id": "music", "path": str(audio), "bytes": audio.stat().st_size, "sha256": hashlib.sha256(audio.read_bytes()).hexdigest()},
        ],
    }
    (workdir / "assets.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
