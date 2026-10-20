from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from fractions import Fraction

import cv2
import numpy as np


DEFAULT_OUTPUT_NAME = "008__effect-reverse-curtain-subject-reveal-over.mp4"

DEFAULT_RECIPE = {
    "id": "effect-reverse-curtain-subject-reveal",
    "title": "Reverse Curtain Subject Reveal",
    "defaults": {
        "width": 640,
        "height": 360,
        "fps": 30,
        "durationSeconds": 3.2,
        "sourceStartSeconds": 0.0,
        "sourceEndSeconds": 0.0,
        "backgroundStartSeconds": 0.0,
        "backgroundEndSeconds": 0.0,
        "backgroundMode": "source",
        "layerMode": "subject_over_curtain",
        "orientation": "vertical",
        "speed": 1.0,
        "openStartSeconds": 0.0,
        "openDurationSeconds": 3.0,
        "easing": "smoothstep",
        "barColor": [0, 0, 0],
        "maskThreshold": 22,
        "maskDilate": 0,
        "maskBlur": 0,
        "maskOpen": 0,
        "maskKeepLargest": True,
        "maskSource": "external_alpha",
        "externalAlpha": None,
        "subjectScale": 1.0,
        "subjectYOffset": 0,
        "subjectShadowStrength": 0.0,
        "subjectShadowOffsetY": 8,
        "subjectRimStrength": 0.0,
        "subjectMinPlaybackSpeed": 0.5,
        "backgroundSeed": 20260707,
        "stutterFrames": 28,
        "stutterHoldFrames": 1,
        "stutterUniqueEveryFrame": True,
        "stutterRangesSeconds": [],
    },
    "agentUsage": {
        "summary": "A reviewed moving alpha from a sufficiently long source window is combined with a center-opening black curtain reveal.",
        "layerRule": "subject_over_curtain keeps the cutout visible above black bars; subject_under_curtain places the cutout behind the bars and reveals it only where the curtain has opened.",
        "backgroundRule": "Use backgroundMode=source for a normal moving background or backgroundMode=random_frame_stutter one unique random source still per output frame behind the subject.",
        "maskRule": "Requires a source-aligned reviewed external hard-edge alpha. No segmentation fallback.",
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
    if config["sourceStartSeconds"] < 0 or config["sourceEndSeconds"] > metadata["durationSeconds"]:
        raise ValueError("Source window must cover the render without a final-frame hold")
    source_sha = hashlib.file_digest(source.open("rb"), "sha256").hexdigest()
    alpha = within(project, config["externalAlpha"], exists=True)
    config["externalAlpha"] = str(alpha)
    config["alphaSha256"] = hashlib.file_digest(alpha.open("rb"), "sha256").hexdigest()
    config["sourceFps"] = metadata["fps"]
    subject_frames = read_source_window(source, metadata, config["sourceStartSeconds"], config["sourceEndSeconds"], config)
    masks = load_or_build_masks(subject_frames, config)
    background_frames = build_background_frames(source, metadata, config)
    frames, trace = compose_frames(subject_frames, masks, background_frames, config, metadata)
    validation = validate_render(frames, masks, trace, config)
    matte = write_matte_contact_sheet(subject_frames, masks, config)
    output = run / args.output_name
    write_mp4(output, frames, config)
    contact = write_contact_sheet(output, frames, trace, config)
    receipt = {"schemaVersion": "1", "status": "needs-editorial-review", "source": str(source.relative_to(project)), "sourceSha256": source_sha,
               "sourceMetadata": metadata, "clock": "original-source-seconds", "config": {key: value for key, value in config.items() if key != "workDir"},
               "output": str(output.relative_to(project)), "outputSha256": hashlib.file_digest(output.open("rb"), "sha256").hexdigest(),
               "contactSheet": str(contact.relative_to(project)), "validation": validation, "trace": trace, "audio": "silent; mix approved source audio through the SDK"}
    receipt["config"]["externalAlpha"] = str(alpha.relative_to(project))
    receipt["matteContactSheet"] = str(matte.relative_to(project))
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
    parser = argparse.ArgumentParser(description="Render a reverse curtain reveal with a masked character cutout.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--input", required=True, help="Project-relative original source")
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--layer-mode", choices=["subject_over_curtain", "subject_under_curtain"])
    parser.add_argument("--background-mode", choices=["source", "stutter", "random_frame_stutter"])
    parser.add_argument("--orientation", choices=["horizontal", "vertical"])
    parser.add_argument("--speed", type=float)
    parser.add_argument("--open-start", type=float)
    parser.add_argument("--open-duration", type=float)
    parser.add_argument("--source-start", type=float, required=True)
    parser.add_argument("--source-end", type=float, required=True)
    parser.add_argument("--background-start", type=float, required=True)
    parser.add_argument("--background-end", type=float, required=True)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--subject-scale", type=float)
    parser.add_argument("--subject-y-offset", type=int)
    parser.add_argument("--subject-shadow-strength", type=float)
    parser.add_argument("--subject-shadow-offset-y", type=int)
    parser.add_argument("--subject-rim-strength", type=float)
    parser.add_argument("--subject-min-playback-speed", type=float)
    parser.add_argument("--mask-open", type=int)
    parser.add_argument("--mask-keep-largest", action="store_true")
    parser.add_argument("--mask-allow-components", action="store_true")
    parser.add_argument("--mask-source", choices=["external_alpha"])
    parser.add_argument("--external-alpha", required=True)
    return parser.parse_args()


def load_config(args):
    recipe = json.loads(args.recipe.read_text()) if args.recipe and args.recipe.exists() else DEFAULT_RECIPE
    config = {**DEFAULT_RECIPE["defaults"], **recipe.get("defaults", {}), **recipe.get("config", {})}
    for attr, key in [
        ("layer_mode", "layerMode"),
        ("background_mode", "backgroundMode"),
        ("orientation", "orientation"),
        ("speed", "speed"),
        ("open_start", "openStartSeconds"),
        ("source_start", "sourceStartSeconds"),
        ("source_end", "sourceEndSeconds"),
        ("background_start", "backgroundStartSeconds"),
        ("background_end", "backgroundEndSeconds"),
        ("duration", "durationSeconds"),
        ("fps", "fps"),
        ("width", "width"),
        ("height", "height"),
        ("subject_scale", "subjectScale"),
        ("subject_y_offset", "subjectYOffset"),
        ("subject_shadow_strength", "subjectShadowStrength"),
        ("subject_shadow_offset_y", "subjectShadowOffsetY"),
        ("subject_rim_strength", "subjectRimStrength"),
        ("subject_min_playback_speed", "subjectMinPlaybackSpeed"),
        ("mask_open", "maskOpen"),
        ("mask_source", "maskSource"),
        ("external_alpha", "externalAlpha"),
    ]:
        value = getattr(args, attr)
        if value is not None:
            config[key] = value
    if args.mask_keep_largest:
        config["maskKeepLargest"] = True
    if args.mask_allow_components:
        config["maskKeepLargest"] = False
    if args.open_duration is not None:
        config["openDurationSeconds"] = args.open_duration
    if config["sourceEndSeconds"] <= config["sourceStartSeconds"]:
        raise ValueError("source end must be after source start")
    if config["speed"] <= 0:
        raise ValueError("speed must be greater than 0")
    if config["subjectMinPlaybackSpeed"] < 0:
        raise ValueError("subject min playback speed cannot be negative")
    if not (0 <= config["backgroundStartSeconds"] < config["backgroundEndSeconds"]):
        raise ValueError("Choose an explicit increasing background window")
    if config["openDurationSeconds"] <= 0 or config["subjectScale"] <= 0:
        raise ValueError("Open duration and subject scale must be positive")
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


def read_source_window(path: Path, metadata: dict, start: float, end: float, config: dict):
    capture = cv2.VideoCapture(str(path))
    if start < 0 or end > metadata["durationSeconds"] or end <= start:
        raise ValueError("Source/background window is outside original source duration")
    start_frame = round(start * metadata["fps"])
    end_frame = max(start_frame + 1, round(end * metadata["fps"]))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frames = []
    for frame_number in range(start_frame, min(end_frame, metadata["frames"])):
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(center_crop_resize(frame, config["width"], config["height"]))
    capture.release()
    if not frames:
        raise RuntimeError("Could not read source subject frames")
    return frames


def load_or_build_masks(frames, config: dict):
    if config.get("maskSource") == "external_alpha":
        if not config.get("externalAlpha"):
            raise ValueError("externalAlpha is required when maskSource=external_alpha")
        return load_external_alpha_masks(Path(config["externalAlpha"]).expanduser(), len(frames), config)
    raise ValueError("A reviewed external alpha is required; select the model explicitly using vibeedit models run")


def load_external_alpha_masks(path: Path, expected_count: int, config: dict):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open external alpha {path}")
    if abs(capture.get(cv2.CAP_PROP_FPS) - config["sourceFps"]) > 0.001:
        capture.release()
        raise ValueError("Alpha FPS must match the original source FPS and start at the selected source window")
    masks = []
    while len(masks) < expected_count:
        ok, frame = capture.read()
        if not ok:
            break
        if frame.ndim == 3 and frame.shape[2] == 4:
            mask = frame[:, :, 3]
        elif frame.ndim == 3:
            mask = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            mask = frame
        mask = center_crop_resize(mask, config["width"], config["height"])
        masks.append(clean_mask(mask, config))
    capture.release()
    if not masks:
        raise RuntimeError(f"External alpha had no readable frames: {path}")
    if len(masks) != expected_count:
        raise ValueError("External alpha has too few frames; refusing to hold the final mask")
    return masks


def clean_mask(mask, config: dict):
    _, cleaned = cv2.threshold(mask, config["maskThreshold"], 255, cv2.THRESH_BINARY)
    if config.get("maskOpen", 0) > 1:
        size = int(config["maskOpen"]) | 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)
    if config.get("maskKeepLargest"):
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, 8)
        if component_count > 1:
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            cleaned = np.where(labels == largest, 255, 0).astype(np.uint8)
    if config["maskDilate"]:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (config["maskDilate"], config["maskDilate"]))
        cleaned = cv2.dilate(cleaned, kernel, iterations=1)
    if config["maskBlur"]:
        blur = config["maskBlur"] | 1
        cleaned = cv2.GaussianBlur(cleaned, (blur, blur), 0)
    return cleaned


def build_background_frames(path: Path, metadata: dict, config: dict):
    total = round(config["durationSeconds"] * config["fps"])
    if config["backgroundMode"] in {"stutter", "random_frame_stutter"}:
        return build_stutter_background(path, metadata, total, config)
    source = read_source_window(path, metadata, config["backgroundStartSeconds"], config["backgroundEndSeconds"], config)
    return [source[round(index * (len(source) - 1) / max(1, total - 1))].copy() for index in range(total)]


def build_stutter_background(path: Path, metadata: dict, total: int, config: dict):
    rng = np.random.default_rng(config["backgroundSeed"])
    candidates = []
    for start, end in config["stutterRangesSeconds"]:
        start_frame = round(start * metadata["fps"])
        end_frame = round(end * metadata["fps"])
        candidates.extend(range(max(0, start_frame), min(metadata["frames"] - 1, end_frame)))
    if not candidates:
        start = max(0.0, min(config["backgroundStartSeconds"], metadata["durationSeconds"]))
        end = max(start + 0.5, min(config["backgroundEndSeconds"], metadata["durationSeconds"]))
        start_frame = round(start * metadata["fps"])
        end_frame = max(start_frame + 1, round(end * metadata["fps"]))
        candidates.extend(range(max(0, start_frame), min(metadata["frames"] - 1, end_frame)))
    if not candidates:
        raise ValueError("No frames in the explicit background window")
    sample_count = total if config.get("stutterUniqueEveryFrame", True) and config["stutterHoldFrames"] == 1 else max(config["stutterFrames"], 1)

    if len(candidates) < sample_count:
        raise RuntimeError(f"Random frame stutter needs {sample_count} unique source frames, but only {len(candidates)} are available")
    chosen = rng.choice(candidates, size=sample_count, replace=False)
    capture = cv2.VideoCapture(str(path))
    frames = []
    for frame_number in chosen:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))
        ok, frame = capture.read()
        if ok:
            frames.append(center_crop_resize(frame, config["width"], config["height"]))
    capture.release()
    if not frames:
        raise RuntimeError("Could not build stutter background")
    if config.get("stutterUniqueEveryFrame", True) and len(frames) < sample_count:
        raise RuntimeError(f"Random frame stutter read {len(frames)} frames, expected {sample_count} unique frames")
    output = []
    index = 0
    while len(output) < total:
        output.extend([frames[index % len(frames)]] * config["stutterHoldFrames"])
        index += 1
    return output[:total]


def compose_frames(subject_frames, masks, background_frames, config: dict, metadata: dict):
    total = round(config["durationSeconds"] * config["fps"])
    frames = []
    trace = []
    for frame_index in range(total):
        source_index = subject_source_index(frame_index, len(subject_frames), config, metadata)
        subject, mask = fit_subject(subject_frames[source_index], masks[source_index], config)
        background = color_grade_background(background_frames[frame_index])
        composite = alpha_blend(background, subject, mask)
        progress = reveal_progress(frame_index / config["fps"], config)
        curtain = apply_curtain(background, progress, config)
        if config["layerMode"] == "subject_over_curtain":
            frame = composite_subject(curtain, subject, mask, config)
        else:
            frame = apply_curtain(composite, progress, config)
        frames.append(frame)
        trace.append({"frame": frame_index, "progress": round(progress, 5), "sourceFrameIndex": source_index})
    return frames, trace


def subject_source_index(frame_index: int, frame_count: int, config: dict, metadata: dict):
    if frame_count <= 1:
        return 0
    min_speed = float(config.get("subjectMinPlaybackSpeed") or 0.0)
    if frame_count <= round((round(config["durationSeconds"] * config["fps"]) - 1) / config["fps"] * metadata["fps"] * min_speed):
        raise ValueError("Subject source window is too short at the minimum playback speed; no final-frame hold allowed")
    if min_speed <= 0:
        return round(frame_index * (frame_count - 1) / max(1, round(config["durationSeconds"] * config["fps"]) - 1))
    elapsed_seconds = frame_index / config["fps"]
    source_fps = float(metadata.get("fps") or config["fps"])
    return min(frame_count - 1, round(elapsed_seconds * source_fps * min_speed))


def fit_subject(frame, mask, config: dict):
    if abs(config["subjectScale"] - 1.0) < 0.001 and config["subjectYOffset"] == 0:
        return frame, mask
    height, width = frame.shape[:2]
    scale = config["subjectScale"]
    resized_frame = cv2.resize(frame, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_CUBIC)
    resized_mask = cv2.resize(mask, (resized_frame.shape[1], resized_frame.shape[0]), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros_like(frame)
    mask_canvas = np.zeros_like(mask)
    x = (width - resized_frame.shape[1]) // 2
    y = height - resized_frame.shape[0] + config["subjectYOffset"]
    paste(canvas, resized_frame, x, y)
    paste(mask_canvas, resized_mask, x, y)
    return canvas, mask_canvas


def paste(canvas, image, x: int, y: int):
    height, width = canvas.shape[:2]
    image_h, image_w = image.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(width, x + image_w)
    y1 = min(height, y + image_h)
    if x1 <= x0 or y1 <= y0:
        return
    canvas[y0:y1, x0:x1] = image[y0 - y : y1 - y, x0 - x : x1 - x]


def reveal_progress(seconds: float, config: dict):
    raw = (seconds - config["openStartSeconds"]) / (config["openDurationSeconds"] / config["speed"])
    value = float(np.clip(raw, 0.0, 1.0))
    if config["easing"] == "linear":
        return value
    if config["easing"] == "ease-out-cubic":
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
        mask[:, start : start + visible] = 1
        return mask
    visible = max(0, min(height, round(height * progress)))
    start = (height - visible) // 2
    mask[start : start + visible, :] = 1
    return mask


def alpha_blend(background, foreground, mask):
    alpha = (mask.astype(np.float32) / 255.0)[:, :, None]
    return np.clip(foreground.astype(np.float32) * alpha + background.astype(np.float32) * (1 - alpha), 0, 255).astype(np.uint8)


def composite_subject(background, subject, mask, config: dict):
    base = add_subject_shadow(background, mask, config)
    foreground = add_subject_rim(subject, mask, config)
    return alpha_blend(base, foreground, mask)


def add_subject_shadow(frame, mask, config: dict):
    strength = float(config.get("subjectShadowStrength") or 0.0)
    if strength <= 0:
        return frame
    offset = int(config.get("subjectShadowOffsetY") or 0)
    shadow = np.zeros_like(mask)
    paste(shadow, mask, 0, offset)
    shadow = cv2.GaussianBlur(shadow, (21, 21), 0).astype(np.float32) / 255.0
    shaded = frame.astype(np.float32) * (1.0 - np.clip(shadow[:, :, None] * strength, 0.0, 0.82))
    return np.clip(shaded, 0, 255).astype(np.uint8)


def add_subject_rim(subject, mask, config: dict):
    strength = float(config.get("subjectRimStrength") or 0.0)
    if strength <= 0:
        return subject
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    edge = cv2.dilate(mask, kernel, iterations=1).astype(np.float32) - cv2.erode(mask, kernel, iterations=1).astype(np.float32)
    edge = cv2.GaussianBlur(np.clip(edge, 0, 255).astype(np.uint8), (5, 5), 0).astype(np.float32) / 255.0
    lifted = subject.astype(np.float32) + edge[:, :, None] * 255.0 * strength
    return np.clip(lifted, 0, 255).astype(np.uint8)


def color_grade_background(frame):
    graded = frame.astype(np.float32) * np.array([0.82, 0.88, 1.02], dtype=np.float32)
    return np.clip(graded * 0.72 + 6, 0, 255).astype(np.uint8)


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


def write_contact_sheet(output: Path, frames, trace, config: dict):
    sample_indexes = sorted(set([0, len(frames) // 6, len(frames) // 3, len(frames) // 2, (len(frames) * 2) // 3, len(frames) - 1]))
    thumbs = []
    for index in sample_indexes:
        thumb = cv2.resize(frames[index], (160, 90), interpolation=cv2.INTER_AREA)
        cv2.putText(thumb, f"f{index} p{trace[index]['progress']:.2f}", (5, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(thumb)
    sheet = np.vstack([np.hstack(thumbs[:3]), np.hstack(thumbs[3:6])])
    cv2.putText(sheet, f"{output.name} {config['layerMode']} bg={config['backgroundMode']}", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    path = Path(config["workDir"]) / f"{output.stem}_contact_sheet.jpg"
    cv2.imwrite(str(path), sheet)
    return path


def write_matte_contact_sheet(subject_frames, masks, config: dict):
    thumbs = []
    for index in np.linspace(0, len(subject_frames) - 1, min(6, len(subject_frames)), dtype=int):
        preview = alpha_blend(np.zeros_like(subject_frames[index]), subject_frames[index], masks[index])
        thumb = cv2.resize(preview, (160, 90), interpolation=cv2.INTER_AREA)
        cv2.putText(thumb, f"src{index}", (5, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(thumb)
    while len(thumbs) < 6:
        thumbs.append(np.zeros((90, 160, 3), dtype=np.uint8))
    sheet = np.vstack([np.hstack(thumbs[:3]), np.hstack(thumbs[3:6])])
    label = "external_alpha"
    path = Path(config["workDir"]) / f"{label}_subject_matte_contact_sheet.jpg"
    cv2.imwrite(str(path), sheet)
    return path


def validate_render(frames, masks, trace, config: dict):
    progress = [entry["progress"] for entry in trace]
    mask_coverage = [float(np.mean(mask > 8)) for mask in masks]
    source_indexes = [entry["sourceFrameIndex"] for entry in trace]
    subject_holds_last_frame = False
    if len(masks) > 1 and max(source_indexes) == len(masks) - 1:
        subject_holds_last_frame = source_indexes.index(len(masks) - 1) < len(source_indexes) - 1
    return {
        "startsBlackOrSubjectOnly": float(np.mean(frames[0])) < (32 if config["layerMode"] == "subject_over_curtain" else 2),
        "endsRevealed": progress[-1] >= 0.99 and float(np.mean(frames[-1])) > 5.0,
        "progressMonotonic": all(progress[index] <= progress[index + 1] for index in range(len(progress) - 1)),
        "usesVideoCutout": len(set(source_indexes)) >= min(16, len(masks)),
        "subjectHasNoEndHold": not subject_holds_last_frame,
        "subjectUniqueFrameIndexes": len(set(source_indexes)),
        "subjectFinalSourceFrameIndex": max(source_indexes),
        "maskCoverageMin": round(min(mask_coverage), 5),
        "maskCoverageMax": round(max(mask_coverage), 5),
        "maskCoverageAverage": round(float(np.mean(mask_coverage)), 5),
        "frames": len(frames),
        "uniqueSourceFrameIndexes": len(set(source_indexes)),
        "sourceMaskFrames": len(masks),
    }



if __name__ == "__main__":
    main()
