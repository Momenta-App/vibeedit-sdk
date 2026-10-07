#!/usr/bin/env python3
"""Ordinary Python and FFmpeg authoring; outputs are browser-project assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import subprocess
import tarfile
import tempfile
import urllib.request
import wave
from pathlib import Path

from PIL import Image, ImageDraw

p = argparse.ArgumentParser()
p.add_argument("--footage", type=Path, required=True)
p.add_argument("--start", default="2")
args = p.parse_args()
root = Path(__file__).resolve().parent
media = root / "media"
media.mkdir(exist_ok=True)
with args.footage.open("rb") as stream:
    source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
subprocess.run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-ss",
        args.start,
        "-i",
        str(args.footage),
        "-t",
        "4",
        "-an",
        "-vf",
        "scale=640:360:force_original_aspect_ratio=increase,crop=640:360,setsar=1",
        "-c:v",
        "libvpx-vp9",
        "-b:v",
        "0",
        "-crf",
        "30",
        "-deadline",
        "realtime",
        "-cpu-used",
        "6",
        str(media / "footage.webm"),
    ],
    check=True,
)
for frame in range(48):
    image = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    x = 30 + frame * 5
    draw.ellipse((x - 30, 40, x + 30, 100), fill=(100, 245, 220, 180))
    draw.line((0, 130, 320, 130), fill=(255, 255, 255, 90), width=4)
    image.save(media / f"effect-{frame:03d}.png")
subprocess.run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-framerate",
        "24",
        "-i",
        str(media / "effect-%03d.png"),
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-b:v",
        "0",
        "-crf",
        "20",
        "-auto-alt-ref",
        "0",
        str(media / "effect.webm"),
    ],
    check=True,
)
with wave.open(str(media / "pulse.wav"), "w") as output:
    output.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
    output.writeframes(
        b"".join(
            struct.pack(
                "<h",
                round(math.sin(2 * math.pi * 660 * n / 48000) * 10000)
                if n % 48000 < 2400
                else 0,
            )
            for n in range(48000 * 4)
        )
    )
shutil.copyfile(
    root.parents[2] / "catalog/text-runtime/assets/fonts/Poppins-Bold.ttf",
    media / "Poppins-Bold.ttf",
)
with tempfile.TemporaryDirectory() as temporary:
    archive = Path(temporary) / "gsap.tgz"
    urllib.request.urlretrieve(
        "https://registry.npmjs.org/gsap/-/gsap-3.13.0.tgz", archive
    )
    assert (
        hashlib.sha256(archive.read_bytes()).hexdigest()
        == "b570ed74abe1fbd4bb0cf43b57bf21118de1c87323659014a84339b5b6c33665"
    )
    with tarfile.open(archive) as bundle:
        (media / "gsap.min.js").write_bytes(
            bundle.extractfile("package/dist/gsap.min.js").read()
        )
assets = {
    file.name: hashlib.sha256(file.read_bytes()).hexdigest()
    for file in media.iterdir()
    if file.is_file()
}
(media / "preparation.json").write_text(
    json.dumps(
        {
            "source": str(args.footage),
            "sourceSha256": source_hash,
            "normalization": {
                "container": "webm",
                "codec": "vp9",
                "sourceStart": args.start,
                "duration": 4,
                "dimensions": [640, 360],
                "audio": "separate generated WAV",
                "alpha": "Python RGBA sequence to VP9 alpha",
            },
            "assets": assets,
            "ffmpeg": subprocess.check_output(
                ["ffmpeg", "-version"], text=True
            ).splitlines()[0],
        },
        indent=2,
    )
    + "\n"
)
print(
    "Prepared footage, Python RGBA effect, WAV pulses, licensed repository font, and pinned GSAP bundle."
)
