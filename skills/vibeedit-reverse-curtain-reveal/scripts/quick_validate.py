from __future__ import annotations

import json
import subprocess
from pathlib import Path


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "fan_Edit_Data").exists():
            return parent
    return Path(__file__).resolve().parents[4]


ROOT = find_root()
SCRIPT = ROOT / ".agents/skills/vibeedit-reverse-curtain-reveal/scripts/render_reverse_curtain_reveal_effect.py"
OUT_DIR = ROOT / "fan_Edit_Data/agent-artifacts/effect-building-pool/production-set-flat"


def main() -> None:
    vertical = run_render("vertical", "007__effect-reverse-curtain-reveal-vertical.mp4", manifest=False)
    horizontal = run_render("horizontal", "007__effect-reverse-curtain-reveal-horizontal.mp4", manifest=True)
    probes = [probe(OUT_DIR / horizontal["outputName"]), probe(OUT_DIR / vertical["outputName"])]
    if not validation_passed(horizontal["validation"]) or not validation_passed(vertical["validation"]):
        raise RuntimeError(json.dumps({"horizontal": horizontal, "vertical": vertical}, indent=2))
    print(json.dumps({
        "ok": True,
        "horizontal": horizontal,
        "vertical": vertical,
        "probes": probes,
    }, indent=2))


def run_render(orientation: str, output_name: str, manifest: bool):
    command = [
        "python3", str(SCRIPT),
        "--orientation", orientation,
        "--output-name", output_name,
    ]
    if not manifest:
        command.append("--no-manifest")
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    return {
        "output": payload["output"],
        "outputName": Path(payload["output"]).name,
        "contactSheet": payload["contactSheet"],
        "orientation": payload["orientation"],
        "validation": payload["validation"],
    }


def probe(path: Path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration,nb_frames",
            "-of", "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return {"file": path.name, **json.loads(result.stdout)["streams"][0]}


def validation_passed(validation: dict):
    return all(value for key, value in validation.items() if isinstance(value, bool))


if __name__ == "__main__":
    main()
