import shutil
import subprocess
from pathlib import Path

from vibeedit import render
from vibeedit import verify_output


root = Path(__file__).parent
ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    raise SystemExit("ffmpeg is required; run vibeedit doctor")
(root / "sources").mkdir(exist_ok=True)
subprocess.run(
    [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "gradients=size=640x360:rate=30:duration=3:c0=0x111827:c1=0x312e81:x0=0:y0=0:x1=640:y1=360", "-f", "lavfi", "-i", "sine=frequency=196:sample_rate=48000:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(root / "sources" / "source.mp4")],
    check=True,
)
output = render(root / "composition.json", root / "portable-motion-showcase.mp4")
report = verify_output(output, {"width": 640, "height": 360, "hasVideo": True, "hasAudio": True, "durationFrames": 90, "maxDurationDriftFrames": 1})
if not report.passed:
    raise SystemExit("\n".join(report.errors))
print(output)
