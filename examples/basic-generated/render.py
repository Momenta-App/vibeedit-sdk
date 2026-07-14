from pathlib import Path

from vibeedit import render, verify_output


root = Path(__file__).parent
output = render(root / "composition.json", root / "basic-generated.mp4")
report = verify_output(output, {"width": 640, "height": 360, "hasVideo": True, "hasAudio": True, "durationFrames": 60, "maxDurationDriftFrames": 1})
if not report.passed:
    raise SystemExit("\n".join(report.errors))
print(output)

