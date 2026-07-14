import shutil
import subprocess
from pathlib import Path

from vibeedit import render, verify_output


root = Path(__file__).parent
ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    raise SystemExit("ffmpeg is required; run vibeedit doctor")
(root / "sources").mkdir(exist_ok=True)
subprocess.run(
    [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x360:rate=30:duration=3",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=220:sample_rate=48000:duration=3",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(root / "sources" / "source.mp4"),
    ],
    check=True,
)
output = render(root / "composition.json", root / "mixed-python-html.mp4")
report = verify_output(output, {"width": 640, "height": 360, "hasVideo": True, "hasAudio": True, "durationFrames": 90, "maxDurationDriftFrames": 1})
if not report.passed:
    raise SystemExit("\n".join(report.errors))
print(output)
