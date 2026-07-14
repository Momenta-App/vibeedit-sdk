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
SCRIPT = ROOT / ".agents/skills/vibeedit-reverse-curtain-subject-reveal/scripts/render_reverse_curtain_subject_reveal_effect.py"
OUT_DIR = ROOT / "fan_Edit_Data/agent-artifacts/effect-building-pool/production-set-flat"


def main() -> None:
    under = run_render(
        "subject_under_curtain",
        "stutter",
        "008__effect-reverse-curtain-subject-reveal-under-stutter.mp4",
        library=False,
    )
    over = run_render(
        "subject_over_curtain",
        "source",
        "008__effect-reverse-curtain-subject-reveal-over.mp4",
        library=True,
    )
    probes = [probe(OUT_DIR / over["outputName"]), probe(OUT_DIR / under["outputName"])]
    if not validation_passed(over["validation"]) or not validation_passed(under["validation"]):
        raise RuntimeError(json.dumps({"over": over, "under": under}, indent=2))
    print(json.dumps({"ok": True, "over": over, "under": under, "probes": probes}, indent=2))


def run_render(layer_mode: str, background_mode: str, output_name: str, library: bool):
    command = [
        "python3", str(SCRIPT),
        "--layer-mode", layer_mode,
        "--background-mode", background_mode,
        "--output-name", output_name,
    ]
    if not library:
        command.append("--no-library-update")
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    return {
        "output": payload["output"],
        "outputName": Path(payload["output"]).name,
        "contactSheet": payload["contactSheet"],
        "matteContactSheet": payload["matteContactSheet"],
        "layerMode": payload["layerMode"],
        "backgroundMode": payload["backgroundMode"],
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
    return all(value for key, value in validation.items() if isinstance(value, bool)) and validation["maskCoverageAverage"] > 0.015


if __name__ == "__main__":
    main()
