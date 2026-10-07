#!/usr/bin/env python3
"""Independent VFR/source mapping, repeated seeks, fractional PTS and audio gates."""

from __future__ import annotations

import argparse
import json
import math
import struct
import subprocess
import sys
import tempfile
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python/src"))
from vibeedit.browser_render import CEFService, render_browser_job

p = argparse.ArgumentParser()
p.add_argument(
    "--report", type=Path, default=Path("browser-renderer/evidence/media-timing.json")
)
p.add_argument(
    "--h264", action="store_true", help="Exercise reported CEF input normalization"
)
a = p.parse_args()
source_name = "vfr.mp4" if a.h264 else "vfr.webm"
report = {"tests": []}
with tempfile.TemporaryDirectory(prefix="vibeedit-media-gates-") as temporary:
    root = Path(temporary)
    colors = [(240, 30, 30), (30, 240, 30), (30, 30, 240), (240, 200, 30)]
    durations = [0.08, 0.16, 0.04, 0.2]
    for i, color in enumerate(colors):
        Image.new("RGB", (160, 90), color).save(root / f"{i}.png")
    (root / "frames.txt").write_text(
        "".join(
            f"file '{i}.png'\nduration {duration}\n"
            for i, duration in enumerate(durations)
        )
        + "file '3.png'\n"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(root / "frames.txt"),
            "-fps_mode",
            "vfr",
            *(
                [
                    "-c:v",
                    "libx264",
                    "-crf",
                    "0",
                    "-pix_fmt",
                    "yuv420p",
                    "-vf",
                    "scale=out_color_matrix=bt709",
                    "-colorspace",
                    "bt709",
                    "-color_primaries",
                    "bt709",
                    "-color_trc",
                    "iec61966-2-1",
                ]
                if a.h264
                else ["-c:v", "libvpx-vp9", "-lossless", "1"]
            ),
            str(root / source_name),
        ],
        check=True,
    )
    pts = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_frames",
                "-show_entries",
                "frame=pts_time",
                "-of",
                "json",
                str(root / source_name),
            ]
        )
    )["frames"]
    timeline = [float(frame["pts_time"]) for frame in pts]
    with wave.open(str(root / "pulse.wav"), "w") as output:
        output.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        output.writeframes(
            b"".join(
                struct.pack(
                    "<h",
                    round(10000 * math.sin(2 * math.pi * 660 * n / 48000))
                    if n < 2400
                    else 0,
                )
                for n in range(48000)
            )
        )
    (root / "index.html").write_text(
        '<style>body{margin:0;background:#102030}video{width:50%;height:100%;object-fit:fill;position:absolute}#b{left:50%}</style><video id="a" muted loop preload="auto" src="vfr.webm"></video><video id="b" muted loop preload="auto" data-source-offset=".16" data-source-rate=".5" src="vfr.webm"></video>'.replace(
            "vfr.webm", source_name
        )
    )
    manifest = {
        "entry": "index.html",
        "width": 320,
        "height": 180,
        "frames": 60,
        "frameRate": {"numerator": 30000, "denominator": 1001},
        "audio": [{"path": "pulse.wav", "start": 0.25}],
    }
    job = root / "job.json"
    job.write_text(json.dumps(manifest))
    raw = root / "frames.bgra"
    screens = root / "reference"
    movie = root / "video.mp4"
    with CEFService() as service:
        result = render_browser_job(
            job, movie, backend="cef", service=service, raw=raw, screenshots=screens
        )
    pixels = np.memmap(raw, mode="r", dtype=np.uint8, shape=(60, 180, 320, 4))
    checks = []
    duration = float(
        json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_format",
                    "-of",
                    "json",
                    str(root / source_name),
                ]
            )
        )["format"]["duration"]
    )
    for frame in range(60):
        time = float(Fraction(frame * 1001, 30000))
        for x, offset, rate in [(80, 0, 1), (240, 0.16, 0.5)]:
            target = (offset + time * rate) % duration
            index = max(i for i, t in enumerate(timeline) if t <= target + 1e-7)
            expected = colors[min(index, 3)]
            actual = pixels[frame, 90, x, [2, 1, 0]].astype(int)
            error = int(np.abs(actual - np.array(expected)).max())
            checks.append(error)
    report["tests"].append(
        {
            "name": ("H264-normalized-" if a.h264 else "")
            + "VFR-two-videos-loop-offset-rate-repeated-frames",
            "maximumChannelError": max(checks),
            "threshold": 4,
            "passed": max(checks) <= 4,
            "sourcePTS": timeline,
            "render": result,
        }
    )
    audio = root / "audio.pcm"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(movie),
            "-map",
            "0:a",
            "-ar",
            "48000",
            "-ac",
            "1",
            "-f",
            "s16le",
            str(audio),
        ],
        check=True,
    )
    samples = np.fromfile(audio, dtype="<i2")
    nonzero = np.flatnonzero(np.abs(samples) > 1500)
    onset = float(nonzero[0] / 48000)
    report["tests"].append(
        {
            "name": "audio-delayed-pulse-sync",
            "expectedSeconds": 0.25,
            "measuredSeconds": onset,
            "toleranceSeconds": 0.005,
            "passed": abs(onset - 0.25) < 0.005,
        }
    )
    # Independent truth at the 24fps / 30000:1001 rounded-PTS boundary.
    for frame in range(24):
        Image.new("RGB", (160, 90), colors[frame % 4]).save(
            root / f"constant-{frame:03d}.png"
        )
    constant_name = "constant.mp4" if a.h264 else "constant.webm"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-framerate",
            "24",
            "-i",
            str(root / "constant-%03d.png"),
            *(
                [
                    "-c:v",
                    "libx264",
                    "-crf",
                    "0",
                    "-pix_fmt",
                    "yuv420p",
                    "-vf",
                    "scale=out_color_matrix=bt709",
                    "-colorspace",
                    "bt709",
                    "-color_primaries",
                    "bt709",
                    "-color_trc",
                    "iec61966-2-1",
                ]
                if a.h264
                else ["-c:v", "libvpx-vp9", "-lossless", "1"]
            ),
            str(root / constant_name),
        ],
        check=True,
    )
    inspected = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_frames",
                "-show_format",
                "-show_entries",
                "frame=pts_time:format=duration",
                "-of",
                "json",
                str(root / constant_name),
            ]
        )
    )
    source_pts = [float(frame["pts_time"]) for frame in inspected["frames"]]
    source_duration = float(inspected["format"]["duration"])
    (root / "index.html").write_text(
        f'<style>body{{margin:0;background:black}}video{{width:320px;height:180px;object-fit:fill}}</style><video muted loop preload="auto" src="{constant_name}"></video>'
    )
    job.write_text(json.dumps(manifest))
    result = render_browser_job(
        job, root / "fractional.mp4", backend="cef", raw=root / "fractional.bgra"
    )
    fractional = np.memmap(
        root / "fractional.bgra", mode="r", dtype=np.uint8, shape=(60, 180, 320, 4)
    )
    expected = [
        colors[
            max(
                index
                for index, pts in enumerate(source_pts)
                if pts <= float(Fraction(frame * 1001, 30000)) % source_duration + 1e-7
            )
            % 4
        ]
        for frame in range(60)
    ]
    error = int(
        np.abs(
            fractional[:, 90, 160][:, [2, 1, 0]].astype(int) - np.array(expected)
        ).max()
    )
    report["tests"].append(
        {
            "name": "24fps-source-to-fractional-output-boundary",
            "maximumChannelError": error,
            "threshold": 4,
            "passed": error <= 4,
            "sourcePTS": source_pts,
            "render": result,
        }
    )
    # Display-matrix orientation is compared against FFmpeg's independent autorotate.
    with tempfile.TemporaryDirectory(prefix="vibeedit-orientation-") as temporary:
        root = Path(temporary)
        image = Image.new("RGB", (160, 90), (240, 30, 30))
        image.paste((30, 240, 30), (80, 0, 160, 45))
        image.paste((30, 30, 240), (0, 45, 80, 90))
        image.paste((240, 200, 30), (80, 45, 160, 90))
        image.save(root / "quadrants.png")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-loop",
                "1",
                "-i",
                str(root / "quadrants.png"),
                "-t",
                "1",
                *(
                    [
                        "-c:v",
                        "libx264",
                        "-crf",
                        "0",
                        "-pix_fmt",
                        "yuv420p",
                        "-vf",
                        "scale=out_color_matrix=bt709",
                        "-colorspace",
                        "bt709",
                        "-color_primaries",
                        "bt709",
                        "-color_trc",
                        "iec61966-2-1",
                    ]
                    if a.h264
                    else ["-c:v", "libvpx-vp9", "-lossless", "1", "-pix_fmt", "yuv420p"]
                ),
                str(root / "source.mp4"),
            ],
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(root / "source.mp4"),
                "-c",
                "copy",
                "-metadata:s:v:0",
                "rotate=90",
                str(root / "rotated.mp4"),
            ],
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(root / "rotated.mp4"),
                "-frames:v",
                "1",
                str(root / "rotated.png"),
            ],
            check=True,
        )
        (root / "index.html").write_text(
            '<style>body{margin:0;background:#102030}video{width:320px;height:180px;object-fit:fill}</style><video muted preload="auto" src="rotated.mp4"></video>'
        )
        job = root / "job.json"
        job.write_text(
            json.dumps(
                {"entry": "index.html", "width": 320, "height": 180, "frames": 4}
            )
        )
        raw = root / "frames.bgra"
        result = render_browser_job(job, root / "output.mp4", backend="cef", raw=raw)
        pixels = np.memmap(raw, mode="r", dtype=np.uint8, shape=(4, 180, 320, 4))
        expected = np.array(
            Image.open(root / "rotated.png").convert("RGB").resize((320, 180))
        )
        errors = [
            int(
                np.abs(
                    pixels[0, y, x, [2, 1, 0]].astype(int) - expected[y, x].astype(int)
                ).max()
            )
            for y in [45, 135]
            for x in [80, 240]
        ]
        report["tests"].append(
            {
                "name": ("H264-normalized" if a.h264 else "VP9-MP4")
                + "-display-matrix-rotation-SDR-color",
                "maximumChannelError": max(errors),
                "threshold": 4,
                "passed": max(errors) <= 4,
                "render": result,
            }
        )
report["passed"] = all(test["passed"] for test in report["tests"])
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
