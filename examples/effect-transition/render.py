import shutil
import subprocess
from pathlib import Path

from vibeedit import render, verify_output


root = Path(__file__).parent
ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    raise SystemExit("ffmpeg is required; run vibeedit doctor")
(root / "sources").mkdir(exist_ok=True)
for output, source in (("a.mp4", "testsrc2=size=320x180:rate=30:duration=2"), ("b.mp4", "smptebars=size=320x180:rate=30:duration=2")):
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(root / "sources" / output)], check=True)
output = render(root / "composition.json", root / "effect-transition.mp4")
report = verify_output(output, {"width": 320, "height": 180, "hasVideo": True, "hasAudio": True, "durationFrames": 108, "maxDurationDriftFrames": 1})
if not report.passed:
    raise SystemExit("\n".join(report.errors))
print(output)

