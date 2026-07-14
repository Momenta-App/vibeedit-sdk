#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).with_name("negative_text.py")
MIN_RENDER_HEIGHT = 30


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    cases = [
        ("ultra_landscape", "ultra", "center", 1280, 720),
        ("max_square", "max", "center", 1080, 1080),
        ("medium_center", "medium", "center", 1280, 720),
        ("small_center", "small", "center", 1280, 720),
        ("extra_small_center", "extra-small", "center", 1280, 720),
    ]
    words_path = out_dir / "words.json"
    words_path.write_text(
        json.dumps(
            [
                {"time": 0.0, "text": "x"},
                {"time": 0.42, "text": "negative"},
                {"time": 1.60, "text": "longer text sample"},
            ],
            indent=2,
        )
    )
    for case_id, mode, placement, width, height in cases:
        case_dir = out_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        command = [
            "python3",
            str(SCRIPT),
            "--words-json",
            str(words_path),
            "--mode",
            mode,
            "--placement",
            placement,
            "--width",
            str(width),
            "--height",
            str(height),
            "--duration",
            "2.8",
            "--clear-after",
            "0.55",
            "--out-dir",
            str(case_dir),
            "--validate",
        ]
        if args.no_video:
            command.append("--no-video")
        subprocess.run(command, check=True)
        results.append(validate_case(case_id, case_dir / "layout.json", mode, placement, width, height))
    results.append(validate_caption_ingest(out_dir, args.no_video))
    results.append(validate_srt_ingest(out_dir, args.no_video))
    results.append(validate_ultra_vertical_rejection(out_dir))
    summary = {"pass": all(item["pass"] for item in results), "cases": results}
    (out_dir / "gauntlet-report.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "gauntlet-report.md").write_text(markdown_report(summary))
    if not summary["pass"]:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NEGATIVE text renderer gauntlet.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--no-video", action="store_true")
    return parser.parse_args()


def validate_case(case_id: str, layout_path: Path, mode: str, placement: str, width: int, height: int) -> dict[str, object]:
    layout = json.loads(layout_path.read_text())
    failures = []
    if layout["mode"] != mode:
        failures.append(f"mode {layout['mode']} != {mode}")
    if layout["placement"] != placement:
        failures.append(f"placement {layout['placement']} != {placement}")
    if layout["width"] != width or layout["height"] != height:
        failures.append("dimensions do not match request")
    if layout["effects"]:
        failures.append("effects list is not empty")
    if layout.get("blend_mode") != "difference":
        failures.append("default blend mode is not difference")
    for word in layout["words"]:
        if word["text"] != word["text"].upper():
            failures.append(f"{word['text']} is not uppercase")
        if mode != "ultra" and (word["scale_x"] != 1.0 or word["scale_y"] != 1.0):
            failures.append(f"{word['text']} distorted outside ultra")
        if mode != "ultra" and word["height"] < MIN_RENDER_HEIGHT:
            failures.append(f"{word['text']} fell below extra-small minimum")
    if any(first["clear_time"] > second["time"] for first, second in zip(layout["words"], layout["words"][1:], strict=False)):
        failures.append("word intervals overlap")
    if any(word["placement"] != "center" for word in layout["words"]):
        failures.append("not all words are centered")
    if layout["words"][-1]["clear_time"] > layout["words"][-1]["time"] + layout["clear_after"] + 0.001:
        failures.append("last word does not clear after timeout")
    if mode == "ultra" and not all(word["width"] >= width * 0.98 and word["height"] >= height * 0.98 for word in layout["words"]):
        failures.append("ultra words do not fill the screen")
    return {"id": case_id, "pass": not failures, "failures": failures, "layout": str(layout_path)}


def validate_caption_ingest(out_dir: Path, no_video: bool) -> dict[str, object]:
    caption_path = out_dir / "captions.json"
    caption_path.write_text(
        json.dumps(
            {
                "segments": [
                    {"start": 0.0, "end": 0.9, "text": "word by word"},
                    {"words": [{"start": 1.2, "end": 1.5, "text": "exact"}]},
                ]
            },
            indent=2,
        )
    )
    case_dir = out_dir / "caption_ingest"
    command = [
        "python3",
        str(SCRIPT),
        "--captions-json",
        str(caption_path),
        "--mode",
        "extra-small",
        "--duration",
        "2.0",
        "--clear-after",
        "0.32",
        "--out-dir",
        str(case_dir),
        "--validate",
    ]
    if no_video:
        command.append("--no-video")
    subprocess.run(command, check=True)
    layout = json.loads((case_dir / "layout.json").read_text())
    texts = [word["text"] for word in layout["words"]]
    failures = []
    if texts != ["WORD", "BY", "WORD", "EXACT"]:
        failures.append(f"unexpected caption split output: {texts}")
    if any(word["height"] < MIN_RENDER_HEIGHT for word in layout["words"]):
        failures.append("caption ingest produced text below extra-small minimum")
    return {"id": "caption_ingest", "pass": not failures, "failures": failures, "layout": str(case_dir / "layout.json")}


def validate_srt_ingest(out_dir: Path, no_video: bool) -> dict[str, object]:
    srt_path = out_dir / "captions.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:00,900\nstay centered\n\n")
    case_dir = out_dir / "srt_ingest"
    command = [
        "python3",
        str(SCRIPT),
        "--captions-file",
        str(srt_path),
        "--mode",
        "small",
        "--duration",
        "1.4",
        "--clear-after",
        "0.32",
        "--out-dir",
        str(case_dir),
        "--validate",
    ]
    if no_video:
        command.append("--no-video")
    subprocess.run(command, check=True)
    layout = json.loads((case_dir / "layout.json").read_text())
    texts = [word["text"] for word in layout["words"]]
    failures = []
    if texts != ["STAY", "CENTERED"]:
        failures.append(f"unexpected srt output: {texts}")
    return {"id": "srt_ingest", "pass": not failures, "failures": failures, "layout": str(case_dir / "layout.json")}


def validate_ultra_vertical_rejection(out_dir: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--text",
            "VERTICAL",
            "--mode",
            "ultra",
            "--width",
            "720",
            "--height",
            "1280",
            "--out-dir",
            str(out_dir / "ultra_vertical_reject"),
            "--no-video",
        ],
        text=True,
        capture_output=True,
    )
    return {
        "id": "ultra_vertical_reject",
        "pass": result.returncode != 0 and "ultra mode only supports" in (result.stderr + result.stdout),
        "failures": [] if result.returncode != 0 else ["ultra vertical command unexpectedly succeeded"],
        "layout": "",
    }


def markdown_report(summary: dict[str, object]) -> str:
    lines = ["# NEGATIVE Text Gauntlet", "", f"Overall: {'PASS' if summary['pass'] else 'FAIL'}", ""]
    for case in summary["cases"]:
        lines.append(f"## {case['id']}")
        lines.append(f"- Status: {'PASS' if case['pass'] else 'FAIL'}")
        if case["failures"]:
            lines.append("- Failures:")
            lines.extend(f"  - {failure}" for failure in case["failures"])
        if case.get("layout"):
            lines.append(f"- Layout: `{case['layout']}`")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
