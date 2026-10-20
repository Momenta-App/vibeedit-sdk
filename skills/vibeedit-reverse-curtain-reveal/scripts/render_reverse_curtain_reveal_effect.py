from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from fractions import Fraction

import cv2
import numpy as np


DEFAULT_OUTPUT_NAME = "007__effect-reverse-curtain-reveal-horizontal.mp4"

DEFAULT_RECIPE = {
    "id": "effect-reverse-curtain-reveal",
    "title": "Reverse Curtain Reveal",
    "defaults": {
        "width": 640,
        "height": 360,
        "fps": 30,
        "durationSeconds": 3.2,
        "sourceStartSeconds": 0.0,
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
    project = Path(args.project).expanduser().resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project must be a directory")
    source = within(project, args.input, exists=True)
    if args.recipe:
        args.recipe = within(project, str(args.recipe), exists=True)
    recipe, config = load_config(args)
    if not (0 < config["fps"] <= 120 and 0 < config["width"] <= 3840 and 0 < config["height"] <= 2160 and 0 < config["durationSeconds"] <= 120):
        raise ValueError("Render bounds: <=3840x2160, <=120fps, <=120 seconds")
    if Path(args.output_name).name != args.output_name or not args.output_name.endswith(".mp4"):
        raise ValueError("--output-name must be a plain .mp4 filename")
    run = within(project, "artifacts/curtain/" + Path(args.output_name).stem)
    run.mkdir(parents=True, exist_ok=False)
    config["workDir"] = str(run)
    metadata = probe_video(source)
    if config["sourceStartSeconds"] < 0 or config["sourceStartSeconds"] + config["durationSeconds"] > metadata["durationSeconds"]:
        raise ValueError("Source window must cover the render without a final-frame hold")
    source_sha = hashlib.file_digest(source.open("rb"), "sha256").hexdigest()
    frames, trace = render_frames(source, metadata, config)
    validation = validate_render(frames, trace, config)
    output = run / args.output_name
    write_mp4(output, frames, config)
    contact = write_contact_sheet(output, frames, trace, config)
    receipt = {"schemaVersion": "1", "status": "needs-editorial-review", "source": str(source.relative_to(project)), "sourceSha256": source_sha,
               "sourceMetadata": metadata, "clock": "original-source-seconds", "config": {key: value for key, value in config.items() if key != "workDir"},
               "output": str(output.relative_to(project)), "outputSha256": hashlib.file_digest(output.open("rb"), "sha256").hexdigest(),
               "contactSheet": str(contact.relative_to(project)), "validation": validation, "trace": trace, "audio": "silent; mix approved source audio through the SDK"}
    (run / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


def within(project: Path, value: str, exists: bool = False) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Use project-relative paths")
    cursor = project
    for part in path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Symlinks are not allowed in project paths")
    path = (project / path).resolve(strict=exists)
    path.relative_to(project)
    return path


def parse_args():
    parser = argparse.ArgumentParser(description="Render a reverse crush / curtain reveal effect.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--input", required=True, help="Project-relative original source")
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
    parser.add_argument("--source-start", type=float, required=True)
    parser.add_argument("--easing", choices=["linear", "smoothstep", "ease-out-cubic"])
    parser.add_argument("--feather-pixels", type=int)
    parser.add_argument("--bar-color", help="Comma-separated RGB, for example 0,0,0")
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
    streams = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate,avg_frame_rate", "-of", "json", str(path)], check=True, capture_output=True, text=True).stdout)["streams"]
    if not streams or streams[0]["r_frame_rate"] == "0/0" or streams[0]["avg_frame_rate"] == "0/0" or Fraction(streams[0]["r_frame_rate"]) != Fraction(streams[0]["avg_frame_rate"]):
        raise ValueError("This OpenCV recipe requires CFR source metadata; prepare a source-clock-mapped proxy for VFR first")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open {path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    return {"fps": fps, "fpsRational": streams[0]["r_frame_rate"], "timingLimit": "CFR metadata gate; source ordinal mapping; VFR requires explicitly clock-mapped proxy", "frames": frames, "width": width, "height": height, "durationSeconds": frames / fps}


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
    path = Path(config["workDir"]) / f"{output.stem}_contact_sheet.jpg"
    cv2.imwrite(str(path), sheet)
    return path


def validate_render(frames, trace: list[dict], config: dict):
    first_mean = float(np.mean(frames[0]))
    final_mean = float(np.mean(frames[-1]))
    mid_index = min(range(len(trace)), key=lambda index: abs(trace[index]["progress"] - .5))
    center_mean, edge_mean = center_edge_means(frames[mid_index], config)
    progress_values = [entry["progress"] for entry in trace]
    return {
        "startsRequestedBarColor": bool(np.max(np.abs(frames[0].astype(float) - solid_frame(config).astype(float))) < 2),
        "endsRevealed": progress_values[-1] >= 0.99,
        "partialOpeningHasBars": bool(edge_mean <= float(np.mean(config["barColor"])) + 2),
        "frames": len(frames),
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



if __name__ == "__main__":
    main()
