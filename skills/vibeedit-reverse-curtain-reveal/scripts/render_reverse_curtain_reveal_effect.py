from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np


def find_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "fan_Edit_Data").exists():
            return parent
    return Path(__file__).resolve().parents[1]


ROOT = find_root()
OUT_DIR = ROOT / "fan_Edit_Data/agent-artifacts/effect-building-pool/production-set-flat"
ANALYSIS_DIR = ROOT / "fan_Edit_Data/agent-artifacts/effect-building-pool/reverse-curtain-reveal"
CONTACT_DIR = ROOT / "tmp/effect-building-pool-contact"
DEFAULT_INPUT = ROOT / "fan_Edit_Data/workspace/media/d590e8b0-fa30-4e69-b19b-563874ff531f/Creed 1.mp4"
RECIPE_PATH = OUT_DIR / "effect-reverse-curtain-reveal.recipe.json"
DEFAULT_OUTPUT_NAME = "007__effect-reverse-curtain-reveal-horizontal.mp4"

DEFAULT_RECIPE = {
    "id": "effect-reverse-curtain-reveal",
    "title": "Reverse Curtain Reveal",
    "defaults": {
        "width": 640,
        "height": 360,
        "fps": 30,
        "durationSeconds": 3.2,
        "sourceStartSeconds": 28.08,
        "orientation": "horizontal",
        "speed": 1.0,
        "openStartSeconds": 0.0,
        "openDurationSeconds": 2.2,
        "holdFinalSeconds": 0.8,
        "easing": "smoothstep",
        "barColor": [0, 0, 0],
        "featherPixels": 0,
    },
    "agentUsage": {
        "summary": "A black screen opens from the center to reveal the background video, like two black curtains/bars pulling away from the middle.",
        "orientationRule": "orientation=horizontal reveals a center vertical strip that widens left/right. orientation=vertical reveals a center horizontal strip that widens up/down.",
        "speedRule": "Higher speed opens faster by dividing openDurationSeconds. Use 1.5-3.0 for fan-edit pacing, or lower than 1.0 for slow cinematic reveals.",
        "timingRule": "Use openStartSeconds to delay the reveal, openDurationSeconds for base timing, and holdFinalSeconds to keep the fully revealed video on screen.",
    },
}


def main() -> None:
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    CONTACT_DIR.mkdir(parents=True, exist_ok=True)
    recipe, config = load_config(args)
    input_path = Path(args.input).expanduser().resolve() if args.input else DEFAULT_INPUT
    metadata = probe_video(input_path)
    frames, trace = render_frames(input_path, metadata, config)
    output = OUT_DIR / args.output_name
    write_mp4(output, frames, config)
    contact = write_contact_sheet(output, frames, trace, config)
    validation = validate_render(frames, trace, config)
    if not args.no_manifest:
        write_recipe(recipe, config, input_path, metadata, output, contact, validation)
        update_manifest(output, input_path, config, contact, validation)
        update_readme()
    print(json.dumps({
        "output": str(output),
        "recipe": str(RECIPE_PATH),
        "contactSheet": str(contact),
        "orientation": config["orientation"],
        "durationSeconds": config["durationSeconds"],
        "openDurationSecondsEffective": effective_open_duration(config),
        "validation": validation,
    }, indent=2))


def parse_args():
    parser = argparse.ArgumentParser(description="Render a reverse crush / curtain reveal effect.")
    parser.add_argument("--input")
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--orientation", choices=["horizontal", "vertical"])
    parser.add_argument("--direction", choices=["horizontal", "vertical"], help="Alias for --orientation.")
    parser.add_argument("--speed", type=float)
    parser.add_argument("--open-duration", type=float)
    parser.add_argument("--open-start", type=float)
    parser.add_argument("--hold-final", type=float)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--source-start", type=float)
    parser.add_argument("--easing", choices=["linear", "smoothstep", "ease-out-cubic"])
    parser.add_argument("--feather-pixels", type=int)
    parser.add_argument("--bar-color", help="Comma-separated RGB, for example 0,0,0")
    parser.add_argument("--no-manifest", action="store_true")
    return parser.parse_args()


def load_config(args):
    recipe = json.loads(args.recipe.read_text()) if args.recipe and args.recipe.exists() else DEFAULT_RECIPE
    config = {**DEFAULT_RECIPE["defaults"], **recipe.get("defaults", {}), **recipe.get("config", {})}
    if args.orientation is not None:
        config["orientation"] = args.orientation
    if args.direction is not None:
        config["orientation"] = args.direction
    if args.speed is not None:
        config["speed"] = args.speed
    if args.open_duration is not None:
        config["openDurationSeconds"] = args.open_duration
    if args.open_start is not None:
        config["openStartSeconds"] = args.open_start
    if args.hold_final is not None:
        config["holdFinalSeconds"] = args.hold_final
    if args.duration is not None:
        config["durationSeconds"] = args.duration
    if args.fps is not None:
        config["fps"] = args.fps
    if args.width is not None:
        config["width"] = args.width
    if args.height is not None:
        config["height"] = args.height
    if args.source_start is not None:
        config["sourceStartSeconds"] = args.source_start
    if args.easing is not None:
        config["easing"] = args.easing
    if args.feather_pixels is not None:
        config["featherPixels"] = args.feather_pixels
    if args.bar_color is not None:
        config["barColor"] = [int(part) for part in args.bar_color.split(",")]
    if config["speed"] <= 0:
        raise ValueError("speed must be greater than 0")
    if config["durationSeconds"] <= 0:
        raise ValueError("durationSeconds must be greater than 0")
    if effective_open_duration(config) <= 0:
        raise ValueError("openDurationSeconds divided by speed must be greater than 0")
    if config["orientation"] not in {"horizontal", "vertical"}:
        raise ValueError("orientation must be horizontal or vertical")
    if len(config["barColor"]) != 3:
        raise ValueError("barColor must contain three RGB values")
    return recipe, config


def probe_video(path: Path):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open {path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    return {"fps": fps, "frames": frames, "width": width, "height": height, "durationSeconds": frames / fps}


def render_frames(path: Path, metadata: dict, config: dict):
    capture = cv2.VideoCapture(str(path))
    total_frames = round(config["durationSeconds"] * config["fps"])
    source_start = round(config["sourceStartSeconds"] * metadata["fps"])
    capture.set(cv2.CAP_PROP_POS_FRAMES, source_start)
    current_source_frame = source_start - 1
    current_frame = None
    frames = []
    trace = []
    for frame_index in range(total_frames):
        source_frame = min(metadata["frames"] - 1, source_start + round(frame_index * metadata["fps"] / config["fps"]))
        while current_source_frame < source_frame:
            ok, current_frame = capture.read()
            current_source_frame += 1
            if not ok:
                raise RuntimeError(f"Could not read source frame {source_frame}")
        if current_frame is None:
            raise RuntimeError(f"Could not read source frame {source_frame}")
        resized = center_crop_resize(current_frame, config["width"], config["height"])
        progress = reveal_progress(frame_index / config["fps"], config)
        frames.append(apply_curtain(resized, progress, config))
        trace.append({"frame": frame_index, "sourceFrame": source_frame, "progress": round(progress, 5)})
    capture.release()
    return frames, trace


def reveal_progress(seconds: float, config: dict) -> float:
    raw = (seconds - config["openStartSeconds"]) / effective_open_duration(config)
    return ease(float(np.clip(raw, 0.0, 1.0)), config["easing"])


def effective_open_duration(config: dict) -> float:
    return config["openDurationSeconds"] / config["speed"]


def ease(value: float, mode: str) -> float:
    if mode == "linear":
        return value
    if mode == "ease-out-cubic":
        return 1 - (1 - value) ** 3
    return value * value * (3 - 2 * value)


def apply_curtain(frame, progress: float, config: dict):
    if progress <= 0:
        return solid_frame(config)
    if progress >= 1:
        return frame.copy()
    mask = curtain_mask(frame.shape[1], frame.shape[0], progress, config)
    bars = solid_frame(config).astype(np.float32)
    source = frame.astype(np.float32)
    return np.clip(source * mask[:, :, None] + bars * (1 - mask[:, :, None]), 0, 255).astype(np.uint8)


def curtain_mask(width: int, height: int, progress: float, config: dict):
    mask = np.zeros((height, width), dtype=np.float32)
    if config["orientation"] == "horizontal":
        visible = max(0, min(width, round(width * progress)))
        start = (width - visible) // 2
        end = start + visible
        mask[:, start:end] = 1
        return feather_mask(mask, config["featherPixels"])
    visible = max(0, min(height, round(height * progress)))
    start = (height - visible) // 2
    end = start + visible
    mask[start:end, :] = 1
    return feather_mask(mask, config["featherPixels"])


def feather_mask(mask, feather_pixels: int):
    if feather_pixels <= 0:
        return mask
    kernel = feather_pixels * 2 + 1
    return cv2.GaussianBlur(mask, (kernel, kernel), 0)


def solid_frame(config: dict):
    color = np.array(config["barColor"], dtype=np.uint8)[::-1]
    return np.tile(color, (config["height"], config["width"], 1))


def center_crop_resize(frame, width: int, height: int):
    source_h, source_w = frame.shape[:2]
    scale = max(width / source_w, height / source_h)
    resized = cv2.resize(frame, (round(source_w * scale), round(source_h * scale)), interpolation=cv2.INTER_AREA)
    x0 = max(0, (resized.shape[1] - width) // 2)
    y0 = max(0, (resized.shape[0] - height) // 2)
    return resized[y0 : y0 + height, x0 : x0 + width]


def write_mp4(path: Path, frames, config: dict):
    process = subprocess.Popen(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{config['width']}x{config['height']}",
            "-r", str(config["fps"]),
            "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(path),
        ],
        stdin=subprocess.PIPE,
    )
    assert process.stdin is not None
    for frame in frames:
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError(f"ffmpeg failed writing {path}")


def write_contact_sheet(output: Path, frames, trace: list[dict], config: dict):
    sample_indexes = sorted(set([0, len(frames) // 5, len(frames) // 3, len(frames) // 2, (len(frames) * 2) // 3, len(frames) - 1]))
    thumbs = []
    for index in sample_indexes:
        thumb = cv2.resize(frames[index], (160, 90), interpolation=cv2.INTER_AREA)
        cv2.putText(thumb, f"f{index} p{trace[index]['progress']:.2f}", (5, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(thumb)
    while len(thumbs) < 6:
        thumbs.append(np.zeros((90, 160, 3), dtype=np.uint8))
    sheet = np.vstack([np.hstack(thumbs[:3]), np.hstack(thumbs[3:6])])
    cv2.putText(sheet, f"{output.name} {config['orientation']} speed={config['speed']}", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    path = CONTACT_DIR / f"{output.stem}_contact_sheet.jpg"
    cv2.imwrite(str(path), sheet)
    return path


def validate_render(frames, trace: list[dict], config: dict):
    first_mean = float(np.mean(frames[0]))
    final_mean = float(np.mean(frames[-1]))
    mid_index = len(frames) // 2
    center_mean, edge_mean = center_edge_means(frames[mid_index], config)
    progress_values = [entry["progress"] for entry in trace]
    return {
        "startsBlack": first_mean < 2.0,
        "endsRevealed": progress_values[-1] >= 0.99 and final_mean > 5.0,
        "middleCenterBrighterThanBars": center_mean > edge_mean + 3.0,
        "progressMonotonic": all(progress_values[index] <= progress_values[index + 1] for index in range(len(progress_values) - 1)),
        "firstFrameMean": round(first_mean, 4),
        "middleCenterMean": round(center_mean, 4),
        "middleEdgeMean": round(edge_mean, 4),
        "finalFrameMean": round(final_mean, 4),
    }


def center_edge_means(frame, config: dict):
    height, width = frame.shape[:2]
    if config["orientation"] == "horizontal":
        center = frame[:, width // 2 - 10 : width // 2 + 10]
        edge = np.hstack([frame[:, :20], frame[:, -20:]])
        return float(np.mean(center)), float(np.mean(edge))
    center = frame[height // 2 - 10 : height // 2 + 10, :]
    edge = np.vstack([frame[:20, :], frame[-20:, :]])
    return float(np.mean(center)), float(np.mean(edge))


def write_recipe(recipe: dict, config: dict, input_path: Path, metadata: dict, output: Path, contact: Path, validation: dict):
    payload = {
        **recipe,
        "defaults": config,
        "rendered": {
            "sourceClip": str(input_path),
            "sourceMetadata": metadata,
            "output": str(output),
            "contactSheet": str(contact),
            "durationSeconds": config["durationSeconds"],
            "effectiveOpenDurationSeconds": round(effective_open_duration(config), 4),
            "validation": validation,
        },
    }
    RECIPE_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    (ANALYSIS_DIR / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")


def update_manifest(output: Path, input_path: Path, config: dict, contact: Path, validation: dict):
    manifest_path = OUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"purpose": "Production effect building pool: accepted reusable effects.", "items": []}
    item = {
        "group": "reveal",
        "id": "effect-reverse-curtain-reveal",
        "title": "Reverse Curtain Reveal",
        "file": output.name,
        "recipeFile": RECIPE_PATH.name,
        "sourceClip": str(input_path),
        "sourceStartSeconds": config["sourceStartSeconds"],
        "durationSeconds": config["durationSeconds"],
        "width": config["width"],
        "height": config["height"],
        "fps": config["fps"],
        "contactSheet": str(contact),
        "libraryStatus": "production",
        "skillName": "vibeedit-reverse-curtain-reveal",
        "skillFile": str(ROOT / ".agents/skills/vibeedit-reverse-curtain-reveal/SKILL.md"),
        "recipe": {
            "orientation": config["orientation"],
            "speed": config["speed"],
            "openStartSeconds": config["openStartSeconds"],
            "openDurationSeconds": config["openDurationSeconds"],
            "effectiveOpenDurationSeconds": round(effective_open_duration(config), 4),
            "easing": config["easing"],
            "barColor": config["barColor"],
            "featherPixels": config["featherPixels"],
            "agentUsage": DEFAULT_RECIPE["agentUsage"],
            "validation": validation,
        },
    }
    manifest["items"] = [existing for existing in manifest.get("items", []) if existing.get("id") != item["id"]] + [item]
    manifest["count"] = len(manifest["items"])
    manifest["contactSheets"] = sorted(set([
        *(value for value in manifest.get("contactSheets", []) if "reverse-curtain-reveal" not in value),
        str(contact),
    ]))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def update_readme():
    readme = OUT_DIR / "README.md"
    existing = readme.read_text() if readme.exists() else "# Effect Building Pool - Production Set\n"
    marker = "## Reverse Curtain Reveal\n"
    section = (
        "## Reverse Curtain Reveal\n\n"
        "Recipe file: `effect-reverse-curtain-reveal.recipe.json`\n\n"
        "Default render: `007__effect-reverse-curtain-reveal-horizontal.mp4`\n\n"
        "Use this when the screen should start black and the source video should be revealed from the center by two opening bars.\n\n"
        "Reusable controls:\n"
        "- `orientation`: `horizontal` opens left/right from the center; `vertical` opens up/down from the center.\n"
        "- `speed`: higher values open faster while preserving the same total render duration.\n"
        "- `openStartSeconds`, `openDurationSeconds`, and `holdFinalSeconds`: tune timing for beats or slower cinematic reveals.\n"
        "- `easing`: `smoothstep`, `linear`, or `ease-out-cubic`.\n\n"
        "Render with defaults:\n\n"
        "```bash\npython3 .agents/skills/vibeedit-reverse-curtain-reveal/scripts/render_reverse_curtain_reveal_effect.py\n```\n\n"
        "Render the vertical option:\n\n"
        "```bash\npython3 .agents/skills/vibeedit-reverse-curtain-reveal/scripts/render_reverse_curtain_reveal_effect.py --orientation vertical --output-name 007__effect-reverse-curtain-reveal-vertical.mp4 --no-manifest\n```\n"
    )
    if marker in existing:
        existing = existing[: existing.index(marker)].rstrip() + "\n\n" + section
    else:
        existing = existing.rstrip() + "\n\n" + section
    readme.write_text(existing.rstrip() + "\n")


if __name__ == "__main__":
    main()
