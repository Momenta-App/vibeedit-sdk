from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
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
WORK_DIR = ROOT / "fan_Edit_Data/agent-artifacts/effect-building-pool/reverse-curtain-subject-reveal"
CONTACT_DIR = ROOT / "tmp/effect-building-pool-contact"
DEFAULT_SOURCE = ROOT / "fan_Edit_Data/workspace/media/20068a78-dc1d-446c-9154-f32b17a66766/Creed 2.mp4"
RECIPE_PATH = OUT_DIR / "effect-reverse-curtain-subject-reveal.recipe.json"
DEFAULT_OUTPUT_NAME = "008__effect-reverse-curtain-subject-reveal-over.mp4"

DEFAULT_RECIPE = {
    "id": "effect-reverse-curtain-subject-reveal",
    "title": "Reverse Curtain Subject Reveal",
    "defaults": {
        "width": 640,
        "height": 360,
        "fps": 30,
        "durationSeconds": 3.2,
        "sourceStartSeconds": 3900.0,
        "sourceEndSeconds": 3901.939708333333,
        "backgroundStartSeconds": 4500.0,
        "backgroundEndSeconds": 4501.3,
        "backgroundMode": "random_frame_stutter",
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
        "maskSource": "apple_vision",
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
        "stutterRangesSeconds": [[4963.0, 4971.0], [5013.8, 5029.5], [4494.8, 4508.9]],
    },
    "agentUsage": {
        "summary": "A real moving hard-edge subject alpha from a long-enough Creed character moment is combined with a center-opening black curtain reveal.",
        "layerRule": "subject_over_curtain keeps the cutout visible above black bars; subject_under_curtain places the cutout behind the bars and reveals it only where the curtain has opened.",
        "backgroundRule": "Use backgroundMode=source for a normal moving background or backgroundMode=random_frame_stutter after reading the vibeedit-random-frame-stutter skill contract: one unique random source still per output frame behind the subject.",
        "maskRule": "Preferred production route is maskSource=external_alpha with a reviewed hard-edge SAM2.1 alpha. Apple Vision person segmentation is only the local fallback when no reviewed external alpha exists.",
    },
}


def main() -> None:
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    CONTACT_DIR.mkdir(parents=True, exist_ok=True)
    recipe, config = load_config(args)
    source = Path(args.input).expanduser().resolve() if args.input else DEFAULT_SOURCE
    metadata = probe_video(source)
    subject_frames = read_source_window(source, metadata, config["sourceStartSeconds"], config["sourceEndSeconds"], config)
    masks = load_or_build_masks(subject_frames, config)
    background_frames = build_background_frames(source, metadata, config)
    output_frames, trace = compose_frames(subject_frames, masks, background_frames, config, metadata)
    output = OUT_DIR / args.output_name
    write_mp4(output, output_frames, config)
    contact = write_contact_sheet(output, output_frames, trace, config)
    matte_contact = write_matte_contact_sheet(subject_frames, masks, config)
    validation = validate_render(output_frames, masks, trace, config)
    if not args.no_library_update:
        write_recipe(recipe, config, source, metadata, output, contact, matte_contact, validation)
        update_manifest(output, source, config, contact, matte_contact, validation)
        update_readme()
    print(json.dumps({
        "output": str(output),
        "recipe": str(RECIPE_PATH),
        "contactSheet": str(contact),
        "matteContactSheet": str(matte_contact),
        "layerMode": config["layerMode"],
        "backgroundMode": config["backgroundMode"],
        "validation": validation,
    }, indent=2))


def parse_args():
    parser = argparse.ArgumentParser(description="Render a reverse curtain reveal with a masked character cutout.")
    parser.add_argument("--input")
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--layer-mode", choices=["subject_over_curtain", "subject_under_curtain"])
    parser.add_argument("--background-mode", choices=["source", "stutter", "random_frame_stutter"])
    parser.add_argument("--orientation", choices=["horizontal", "vertical"])
    parser.add_argument("--speed", type=float)
    parser.add_argument("--open-start", type=float)
    parser.add_argument("--open-duration", type=float)
    parser.add_argument("--source-start", type=float)
    parser.add_argument("--source-end", type=float)
    parser.add_argument("--background-start", type=float)
    parser.add_argument("--background-end", type=float)
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
    parser.add_argument("--mask-source", choices=["apple_vision", "external_alpha"])
    parser.add_argument("--external-alpha")
    parser.add_argument("--no-library-update", action="store_true")
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


def read_source_window(path: Path, metadata: dict, start: float, end: float, config: dict):
    capture = cv2.VideoCapture(str(path))
    start_frame = round(start * metadata["fps"])
    end_frame = max(start_frame + 1, round(end * metadata["fps"]))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frames = []
    for frame_number in range(start_frame, min(end_frame + 1, metadata["frames"])):
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
    mask_dir = WORK_DIR / "apple_vision_masks"
    mask_dir.mkdir(parents=True, exist_ok=True)
    cache_manifest = mask_dir / "cache_manifest.json"
    cache_key = {
        "frameCount": len(frames),
        "width": config["width"],
        "height": config["height"],
        "sourceStartSeconds": config["sourceStartSeconds"],
        "sourceEndSeconds": config["sourceEndSeconds"],
        "maskThreshold": config["maskThreshold"],
        "maskDilate": config["maskDilate"],
        "maskBlur": config["maskBlur"],
    }
    masks = []
    existing = sorted(mask_dir.glob("mask_*.png"))
    if cache_manifest.exists() and json.loads(cache_manifest.read_text()).get("cacheKey") == cache_key and len(existing) >= len(frames):
        for path in existing[: len(frames)]:
            masks.append(cv2.imread(str(path), cv2.IMREAD_GRAYSCALE))
        return masks
    for path in existing:
        path.unlink()
    masks = build_apple_vision_person_masks(frames, config)
    for index, mask in enumerate(masks):
        cv2.imwrite(str(mask_dir / f"mask_{index:04d}.png"), mask)
    cache_manifest.write_text(json.dumps({"cacheKey": cache_key}, indent=2) + "\n")
    return masks


def load_external_alpha_masks(path: Path, expected_count: int, config: dict):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open external alpha {path}")
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
        mask = cv2.resize(mask, (config["width"], config["height"]), interpolation=cv2.INTER_LINEAR)
        masks.append(clean_mask(mask, config))
    capture.release()
    if not masks:
        raise RuntimeError(f"External alpha had no readable frames: {path}")
    while len(masks) < expected_count:
        masks.append(masks[-1].copy())
    return masks[:expected_count]


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


def build_apple_vision_person_masks(frames, config: dict):
    import Foundation
    import Quartz
    import Vision
    from Quartz import CVPixelBufferGetBaseAddress
    from Quartz import CVPixelBufferGetBytesPerRow
    from Quartz import CVPixelBufferGetHeight
    from Quartz import CVPixelBufferGetWidth
    from Quartz import CVPixelBufferLockBaseAddress
    from Quartz import CVPixelBufferUnlockBaseAddress
    from Quartz import kCVPixelBufferLock_ReadOnly

    masks = []
    with tempfile.TemporaryDirectory(prefix="reverse-curtain-subject-vision-") as tmp:
        tmp_dir = Path(tmp)
        for index, frame in enumerate(frames):
            frame_path = tmp_dir / f"frame_{index:04d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            request = Vision.VNGeneratePersonSegmentationRequest.alloc().initWithCompletionHandler_(None)
            request.setQualityLevel_(getattr(Vision, "VNGeneratePersonSegmentationRequestQualityLevelAccurate", 2))
            request.setOutputPixelFormat_(getattr(Quartz, "kCVPixelFormatType_OneComponent8", 1278226488))
            handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(Foundation.NSURL.fileURLWithPath_(str(frame_path)), {})
            ok, error = handler.performRequests_error_([request], None)
            if not ok:
                raise RuntimeError(f"Apple Vision person segmentation failed on frame {index}: {error}")
            results = request.results() or []
            if not results:
                masks.append(np.zeros(frame.shape[:2], dtype=np.uint8))
                continue
            pixel_buffer = results[0].pixelBuffer()
            width = CVPixelBufferGetWidth(pixel_buffer)
            height = CVPixelBufferGetHeight(pixel_buffer)
            bytes_per_row = CVPixelBufferGetBytesPerRow(pixel_buffer)
            CVPixelBufferLockBaseAddress(pixel_buffer, kCVPixelBufferLock_ReadOnly)
            base_address = CVPixelBufferGetBaseAddress(pixel_buffer)
            buffer = base_address.as_buffer(bytes_per_row * height)
            mask = np.frombuffer(buffer, dtype=np.uint8).reshape(height, bytes_per_row)[:, :width].copy()
            CVPixelBufferUnlockBaseAddress(pixel_buffer, kCVPixelBufferLock_ReadOnly)
            mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
            _, mask = cv2.threshold(mask, config["maskThreshold"], 255, cv2.THRESH_BINARY)
            if config["maskDilate"]:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (config["maskDilate"], config["maskDilate"]))
                mask = cv2.dilate(mask, kernel, iterations=1)
            if config["maskBlur"]:
                blur = config["maskBlur"] | 1
                mask = cv2.GaussianBlur(mask, (blur, blur), 0)
            masks.append(mask)
    return masks


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
        candidates.extend(range(max(1, metadata["frames"])))
    sample_count = total if config.get("stutterUniqueEveryFrame", True) and config["stutterHoldFrames"] == 1 else max(config["stutterFrames"], 1)
    if len(candidates) < sample_count:
        candidates = list(range(max(1, metadata["frames"])))
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
    path = CONTACT_DIR / f"{output.stem}_contact_sheet.jpg"
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
    label = "external_alpha" if config.get("maskSource") == "external_alpha" else "apple_vision"
    path = WORK_DIR / f"{label}_subject_matte_contact_sheet.jpg"
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


def write_recipe(recipe: dict, config: dict, source: Path, metadata: dict, output: Path, contact: Path, matte_contact: Path, validation: dict):
    payload = {
        **recipe,
        "defaults": config,
        "rendered": {
            "sourceClip": str(source),
            "sourceMetadata": metadata,
            "output": str(output),
            "contactSheet": str(contact),
            "matteContactSheet": str(matte_contact),
            "durationSeconds": config["durationSeconds"],
            "validation": validation,
            "selectedMoment": {
        "source": "Creed 2",
        "shotId": "manual_3900s_long_subject_window",
        "character": "Adonis Creed",
        "reason": "long-enough stable character window with enough source and mask frames to avoid holding the final subject frame",
            },
        },
    }
    RECIPE_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def update_manifest(output: Path, source: Path, config: dict, contact: Path, matte_contact: Path, validation: dict):
    manifest_path = OUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"purpose": "Production effect building pool: accepted reusable effects.", "items": []}
    item = {
        "group": "reveal",
        "id": "effect-reverse-curtain-subject-reveal",
        "title": "Reverse Curtain Subject Reveal",
        "file": output.name,
        "recipeFile": RECIPE_PATH.name,
        "sourceClip": str(source),
        "sourceStartSeconds": config["sourceStartSeconds"],
        "durationSeconds": config["durationSeconds"],
        "width": config["width"],
        "height": config["height"],
        "fps": config["fps"],
        "contactSheet": str(contact),
        "matteContactSheet": str(matte_contact),
        "libraryStatus": "production",
        "skillName": "vibeedit-reverse-curtain-subject-reveal",
        "skillFile": str(ROOT / ".agents/skills/vibeedit-reverse-curtain-subject-reveal/SKILL.md"),
        "recipe": {
            "layerMode": config["layerMode"],
            "backgroundMode": config["backgroundMode"],
            "orientation": config["orientation"],
            "speed": config["speed"],
            "subjectMinPlaybackSpeed": config["subjectMinPlaybackSpeed"],
            "maskRoute": mask_route_label(config),
            "maskSource": config["maskSource"],
            "externalAlpha": config.get("externalAlpha"),
            "maskSource": config["maskSource"],
            "externalAlpha": config.get("externalAlpha"),
            "validation": validation,
            "agentUsage": DEFAULT_RECIPE["agentUsage"],
        },
    }
    manifest["items"] = [existing for existing in manifest.get("items", []) if existing.get("id") != item["id"]] + [item]
    manifest["count"] = len(manifest["items"])
    manifest["contactSheets"] = sorted(set([*(value for value in manifest.get("contactSheets", []) if "reverse-curtain-subject-reveal" not in value), str(contact), str(matte_contact)]))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def update_readme():
    readme = OUT_DIR / "README.md"
    existing = readme.read_text() if readme.exists() else "# Effect Building Pool - Production Set\n"
    marker = "## Reverse Curtain Subject Reveal\n"
    section = (
        "## Reverse Curtain Subject Reveal\n\n"
        "Recipe file: `effect-reverse-curtain-subject-reveal.recipe.json`\n\n"
        "Default render: `021__sam21-creed-random-stutter-vertical-curtain-subject-over.mp4`\n\n"
        "This variant uses a reviewed SAM alpha matte from a long-enough Creed character video moment, slows that moving cutout by no more than the configured minimum playback speed, and combines it with a random-frame-stutter background plus a center-opening reverse curtain reveal.\n\n"
        "Layer modes:\n"
        "- `subject_over_curtain`: cutout stays above the black curtain bars.\n"
        "- `subject_under_curtain`: cutout sits behind the curtain bars and is revealed only through the opening.\n\n"
        "Background modes:\n"
        "- `source`: normal moving background video.\n"
        "- `random_frame_stutter`: one unique random source still per output frame, sampled without replacement when enough source frames exist.\n"
        "- `stutter`: compatibility alias for random-frame stutter.\n\n"
        "Mask modes:\n"
        "- `external_alpha`: preferred production route; use a reviewed hard-edge SAM2.1/SAM3 alpha video via `--external-alpha`.\n"
        "- `apple_vision`: local fallback person matte when no reviewed external alpha exists.\n\n"
        "Render defaults:\n\n"
        "```bash\npython3 .agents/skills/vibeedit-reverse-curtain-subject-reveal/scripts/render_reverse_curtain_subject_reveal_effect.py\n```\n"
    )
    if marker in existing:
        existing = existing[: existing.index(marker)].rstrip() + "\n\n" + section
    else:
        existing = existing.rstrip() + "\n\n" + section
    readme.write_text(existing.rstrip() + "\n")


def mask_route_label(config: dict):
    if config.get("maskSource") == "external_alpha":
        return f"External reviewed alpha: {config.get('externalAlpha')}"
    return "Apple Vision VNGeneratePersonSegmentationRequest accurate person matte"


if __name__ == "__main__":
    main()
