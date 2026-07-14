#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont


DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 24
DEFAULT_CLEAR_AFTER = 0.75
DEFAULT_WORD_GAP = 0.24
MIN_FONT_SIZE = 40
MIN_RENDER_HEIGHT = 30
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]
MODES = {"ultra", "max", "medium", "small", "extra-small"}
PLACEMENTS = {"center"}
BLEND_MODES = {"difference", "normal"}
MODE_LIMITS = {
    "max": (0.94, 0.86),
    "medium": (0.36, 0.18),
    "small": (0.22, 0.10),
    "extra-small": (0.12, 0.055),
}


@dataclass
class WordEvent:
    time: float
    text: str


@dataclass
class WordLayout:
    time: float
    clear_time: float
    text: str
    x: int
    y: int
    width: int
    height: int
    font_size: int
    scale_x: float
    scale_y: float
    placement: str
    mode: str


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    words = load_words(args)
    duration = args.duration if args.duration is not None else infer_duration(words, args.clear_after)
    layouts = build_layouts(words, args.mode, args.placement, args.width, args.height, args.clear_after)
    layout = {
        "width": args.width,
        "height": args.height,
        "fps": args.fps,
        "duration": duration,
        "mode": args.mode,
        "placement": args.placement,
        "clear_after": args.clear_after,
        "blend_mode": args.blend_mode,
        "flat_style": True,
        "effects": [],
        "words": [asdict(item) for item in layouts],
    }
    (out_dir / "layout.json").write_text(json.dumps(layout, indent=2))
    report = validate_layout(layout)
    (out_dir / "validation-report.json").write_text(json.dumps(report, indent=2))
    if args.validate and not report["pass"]:
        raise SystemExit(1)
    background_dir = None
    if args.background_video:
        background_dir = out_dir / "background_frames"
        extract_background_frames(Path(args.background_video), background_dir, args.clip_start, duration, args.width, args.height, args.fps)
    render_contact_sheet(layouts, out_dir / "contact-sheet.jpg", args.width, args.height, duration, args.fps, parse_color(args.plate_color), parse_color(args.text_color), background_dir, args.blend_mode)
    if not args.no_video:
        render_video(
            layouts,
            out_dir / "review.mp4",
            args.width,
            args.height,
            duration,
            args.fps,
            parse_color(args.plate_color),
            parse_color(args.text_color),
            background_dir,
            args.blend_mode,
            Path(args.background_video) if args.background_video and not args.no_background_audio else None,
            args.clip_start,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render NEGATIVE flat all-caps timestamped word text.")
    parser.add_argument("--words-json", help="JSON list of {'time': seconds, 'text': word/caption}.")
    parser.add_argument("--captions-json", help="JSON captions/transcript source. Supports words, captions, lyrics, and segments arrays.")
    parser.add_argument("--captions-file", help="Caption/transcript file. Supports .json, .srt, .vtt, and .lrc.")
    parser.add_argument("--text", action="append", default=[], help="Fallback word/caption text. Repeatable.")
    parser.add_argument("--word-gap", type=float, default=DEFAULT_WORD_GAP, help="Fallback seconds between generated word timings.")
    parser.add_argument("--mode", choices=sorted(MODES), default="medium")
    parser.add_argument("--placement", choices=sorted(PLACEMENTS), default="center")
    parser.add_argument("--blend-mode", choices=sorted(BLEND_MODES), default="difference")
    parser.add_argument("--clear-after", type=float, default=DEFAULT_CLEAR_AFTER)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--plate-color", default="#000000")
    parser.add_argument("--text-color", default="#ffffff")
    parser.add_argument("--background-video", help="Optional source video to render behind the text.")
    parser.add_argument("--clip-start", type=float, default=0.0)
    parser.add_argument("--no-background-audio", action="store_true", help="Do not mux source audio when --background-video is used.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--no-video", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def load_words(args: argparse.Namespace) -> list[WordEvent]:
    if args.mode == "ultra" and args.width < args.height:
        raise ValueError("ultra mode only supports square or landscape outputs where width >= height")
    if args.captions_json:
        words = events_from_json(json.loads(Path(args.captions_json).read_text()), args.word_gap)
    elif args.captions_file:
        words = events_from_caption_file(Path(args.captions_file), args.word_gap)
    elif args.words_json:
        data = json.loads(Path(args.words_json).read_text())
        words = events_from_json(data, args.word_gap)
    else:
        words = []
        for index, text in enumerate(args.text or ["NEGATIVE"]):
            words.extend(split_text_to_events(index * 0.45, None, str(text), args.word_gap))
    words = sorted(words, key=lambda item: item.time)
    if not words:
        raise ValueError("At least one word is required")
    if any(word.time < 0 for word in words):
        raise ValueError("Word times must be non-negative")
    return words


def events_from_caption_file(path: Path, word_gap: float) -> list[WordEvent]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return events_from_json(json.loads(path.read_text()), word_gap)
    if suffix in {".srt", ".vtt"}:
        return events_from_subtitle_text(path.read_text(), word_gap)
    if suffix == ".lrc":
        return events_from_lrc(path.read_text(), word_gap)
    raise ValueError(f"Unsupported caption file extension: {suffix}")


def events_from_json(data: Any, word_gap: float) -> list[WordEvent]:
    if isinstance(data, list):
        return [event for item in data for event in events_from_json_item(item, word_gap)]
    if not isinstance(data, dict):
        raise ValueError("Caption JSON must be a list or object")
    if isinstance(data.get("words"), list):
        return [event for item in data["words"] for event in events_from_json_item(item, word_gap)]
    if isinstance(data.get("segments"), list):
        return [event for segment in data["segments"] for event in events_from_segment(segment, word_gap)]
    if isinstance(data.get("captions"), list):
        return [event for item in data["captions"] for event in events_from_json_item(item, word_gap)]
    if isinstance(data.get("lyrics"), list):
        return [event for item in data["lyrics"] for event in events_from_json_item(item, word_gap)]
    return events_from_json_item(data, word_gap)


def events_from_segment(segment: Any, word_gap: float) -> list[WordEvent]:
    if not isinstance(segment, dict):
        return []
    transcript = segment.get("transcript")
    if isinstance(transcript, dict) and isinstance(transcript.get("words"), list):
        return [event for item in transcript["words"] for event in events_from_json_item(item, word_gap)]
    if isinstance(segment.get("words"), list):
        return [event for item in segment["words"] for event in events_from_json_item(item, word_gap)]
    return events_from_json_item(segment, word_gap)


def events_from_json_item(item: Any, word_gap: float) -> list[WordEvent]:
    if isinstance(item, str):
        return split_text_to_events(0.0, None, item, word_gap)
    if not isinstance(item, dict):
        return []
    text = item.get("text", item.get("word", item.get("caption", item.get("value", ""))))
    start = item.get("time", item.get("start", item.get("start_time", item.get("start_ms", item.get("startMs", 0.0)))))
    end = item.get("end", item.get("end_time", item.get("end_ms", item.get("endMs"))))
    return split_text_to_events(normalize_time_value(start), normalize_time_value(end) if end is not None else None, str(text), word_gap)


def split_text_to_events(start: float, end: float | None, text: str, word_gap: float) -> list[WordEvent]:
    tokens = [normalize_text(token) for token in re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?", text)]
    tokens = [token for token in tokens if token]
    if not tokens:
        return []
    if len(tokens) == 1:
        return [WordEvent(time=start, text=tokens[0])]
    step = max(0.04, (end - start) / len(tokens)) if end is not None and end > start else word_gap
    return [WordEvent(time=start + index * step, text=token) for index, token in enumerate(tokens)]


def normalize_time_value(value: Any) -> float:
    time = float(value)
    return time / 1000 if abs(time) > 10000 else time


def events_from_subtitle_text(text: str, word_gap: float) -> list[WordEvent]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    events = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip() and line.strip().upper() != "WEBVTT"]
        timing = next((line for line in lines if "-->" in line), "")
        if not timing:
            continue
        start_text, end_text = [part.strip().split()[0] for part in timing.split("-->", 1)]
        caption = " ".join(line for line in lines if line != timing and not line.isdigit())
        events.extend(split_text_to_events(parse_subtitle_time(start_text), parse_subtitle_time(end_text), caption, word_gap))
    return events


def parse_subtitle_time(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def events_from_lrc(text: str, word_gap: float) -> list[WordEvent]:
    events = []
    for line in text.splitlines():
        matches = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", line)
        lyric = re.sub(r"\[[^\]]+\]", "", line).strip()
        for minutes, seconds in matches:
            events.extend(split_text_to_events(int(minutes) * 60 + float(seconds), None, lyric, word_gap))
    return events


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().upper())


def infer_duration(words: list[WordEvent], clear_after: float) -> float:
    return max(1.0, words[-1].time + clear_after + 0.35)


def build_layouts(words: list[WordEvent], mode: str, placement: str, width: int, height: int, clear_after: float) -> list[WordLayout]:
    if mode == "ultra" and width < height:
        raise ValueError("ultra mode only supports square or landscape outputs where width >= height")
    placement = "center"
    layouts = []
    for index, word in enumerate(words):
        next_time = words[index + 1].time if index + 1 < len(words) else None
        clear_time = min(word.time + clear_after, next_time) if next_time is not None else word.time + clear_after
        layouts.append(layout_word(word.text, word.time, clear_time, mode, placement, width, height))
    return layouts


def layout_word(text: str, time: float, clear_time: float, mode: str, placement: str, width: int, height: int) -> WordLayout:
    font_path = first_existing_font()
    placement = "center"
    if mode == "ultra":
        image, font_size = render_text_image(text, font_path, 320)
        scaled_width = max(1, int(width * 1.02))
        scaled_height = max(1, int(height * 1.02))
        x = (width - scaled_width) // 2
        y = (height - scaled_height) // 2
        return WordLayout(time, clear_time, text, x, y, scaled_width, scaled_height, font_size, scaled_width / image.width, scaled_height / image.height, placement, mode)
    max_width_ratio, max_height_ratio = MODE_LIMITS[mode]
    target_width = int(width * max_width_ratio)
    target_height = int(height * max_height_ratio)
    image, font_size = fit_text(text, font_path, target_width, target_height)
    x, y = place_box(image.width, image.height, width, height, placement)
    return WordLayout(time, clear_time, text, x, y, image.width, image.height, font_size, 1.0, 1.0, placement, mode)


def first_existing_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return FONT_CANDIDATES[-1]


def fit_text(text: str, font_path: str, target_width: int, target_height: int) -> tuple[Image.Image, int]:
    best: tuple[Image.Image, int] | None = None
    low, high = MIN_FONT_SIZE, 720
    while low <= high:
        mid = (low + high) // 2
        image, _ = render_text_image(text, font_path, mid)
        if image.width <= target_width and image.height <= target_height:
            best = (image, mid)
            low = mid + 1
        else:
            high = mid - 1
    if best:
        return best
    return render_text_image(text, font_path, MIN_FONT_SIZE)


def render_text_image(text: str, font_path: str, font_size: int) -> tuple[Image.Image, int]:
    font = ImageFont.truetype(font_path, font_size)
    probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    box = draw.textbbox((0, 0), text, font=font)
    width = max(1, box[2] - box[0])
    height = max(1, box[3] - box[1])
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(image).text((-box[0], -box[1]), text, font=font, fill=(255, 255, 255, 255))
    return image, font_size


def place_box(box_width: int, box_height: int, width: int, height: int, placement: str) -> tuple[int, int]:
    x, y = (width - box_width) // 2, (height - box_height) // 2
    return max(0, min(width - box_width, x)), max(0, min(height - box_height, y))


def render_frame(
    layouts: list[WordLayout],
    t: float,
    width: int,
    height: int,
    plate_color: tuple[int, int, int],
    text_color: tuple[int, int, int],
    background: Image.Image | None = None,
    blend_mode: str = "difference",
) -> Image.Image:
    frame = background.convert("RGB") if background else Image.new("RGB", (width, height), plate_color)
    active = active_layout(layouts, t)
    if not active:
        return frame
    font_path = first_existing_font()
    image, _ = render_text_image(active.text, font_path, active.font_size)
    if active.scale_x != 1.0 or active.scale_y != 1.0:
        image = image.resize((active.width, active.height), Image.Resampling.BICUBIC)
    alpha = image.getchannel("A")
    solid = Image.new("RGB", image.size, text_color)
    if blend_mode == "difference":
        region = frame.crop((active.x, active.y, active.x + active.width, active.y + active.height))
        frame.paste(ImageChops.difference(region, solid), (active.x, active.y), alpha)
    else:
        rgba = Image.new("RGBA", image.size, (*text_color, 255))
        rgba.putalpha(alpha)
        frame.paste(rgba.convert("RGB"), (active.x, active.y), rgba)
    return frame


def active_layout(layouts: list[WordLayout], t: float) -> WordLayout | None:
    active = [item for item in layouts if item.time <= t < item.clear_time]
    return active[-1] if active else None


def render_contact_sheet(
    layouts: list[WordLayout],
    path: Path,
    width: int,
    height: int,
    duration: float,
    fps: int,
    plate_color: tuple[int, int, int],
    text_color: tuple[int, int, int],
    background_dir: Path | None = None,
    blend_mode: str = "difference",
) -> None:
    samples = sorted(set([0.0, duration - 1 / fps] + [item.time for item in layouts] + [min(duration, item.clear_time + 0.04) for item in layouts]))[:12]
    thumbs = [
        render_frame(layouts, sample, width, height, plate_color, text_color, load_background_frame(background_dir, int(sample * fps)), blend_mode).resize((320, 180), Image.Resampling.LANCZOS)
        for sample in samples
    ]
    sheet = Image.new("RGB", (320 * 3, 180 * math.ceil(len(thumbs) / 3)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for index, thumb in enumerate(thumbs):
        x = (index % 3) * 320
        y = (index // 3) * 180
        sheet.paste(thumb, (x, y))
        draw.text((x + 6, y + 6), f"{samples[index]:.2f}s", fill=(220, 220, 220))
    sheet.save(path, quality=92)


def render_video(
    layouts: list[WordLayout],
    path: Path,
    width: int,
    height: int,
    duration: float,
    fps: int,
    plate_color: tuple[int, int, int],
    text_color: tuple[int, int, int],
    background_dir: Path | None = None,
    blend_mode: str = "difference",
    background_video: Path | None = None,
    clip_start: float = 0.0,
) -> None:
    frames_dir = path.with_suffix("")
    if frames_dir.exists():
        for frame in frames_dir.glob("*.jpg"):
            frame.unlink()
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(math.ceil(duration * fps)))
    for index in range(frame_count):
        render_frame(layouts, index / fps, width, height, plate_color, text_color, load_background_frame(background_dir, index), blend_mode).save(frames_dir / f"{index:05d}.jpg", quality=95)
    silent_path = path.with_name(f"{path.stem}.silent{path.suffix}")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "%05d.jpg"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(silent_path if background_video else path),
        ],
        check=True,
    )
    if background_video:
        mux_background_audio(silent_path, background_video, path, clip_start, duration)


def extract_background_frames(source: Path, frames_dir: Path, clip_start: float, duration: float, width: int, height: int, fps: int) -> None:
    if frames_dir.exists():
        for frame in frames_dir.glob("*.jpg"):
            frame.unlink()
    frames_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{clip_start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-vf",
            f"scale={width}:-2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps={fps}",
            str(frames_dir / "%05d.jpg"),
        ],
        check=True,
    )


def mux_background_audio(silent_video: Path, source: Path, out_path: Path, clip_start: float, duration: float) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(silent_video),
            "-ss",
            f"{clip_start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0?",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(out_path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        silent_video.replace(out_path)


def load_background_frame(background_dir: Path | None, index: int) -> Image.Image | None:
    if background_dir is None:
        return None
    path = background_dir / f"{index + 1:05d}.jpg"
    if not path.exists():
        return None
    return Image.open(path).convert("RGB")


def parse_color(value: str) -> tuple[int, int, int]:
    if value.startswith("#") and len(value) == 7:
        return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
    parts = [int(part) for part in value.split(",")]
    if len(parts) != 3 or any(part < 0 or part > 255 for part in parts):
        raise ValueError("Color must be #RRGGBB or r,g,b")
    return parts[0], parts[1], parts[2]


def validate_layout(layout: dict[str, Any]) -> dict[str, Any]:
    failures = []
    words = layout["words"]
    if layout["mode"] == "ultra" and layout["width"] < layout["height"]:
        failures.append("ultra mode was used on a vertical output")
    for index, word in enumerate(words):
        if word["text"] != word["text"].upper():
            failures.append(f"word {index} is not uppercase")
        if word["clear_time"] <= word["time"]:
            failures.append(f"word {index} clear_time is not after time")
        bleed = 0.04 if layout["mode"] == "ultra" else 0.0
        if (
            word["x"] < -layout["width"] * bleed
            or word["y"] < -layout["height"] * bleed
            or word["x"] + word["width"] > layout["width"] * (1 + bleed)
            or word["y"] + word["height"] > layout["height"] * (1 + bleed)
        ):
            failures.append(f"word {index} is outside frame")
        if layout["mode"] != "ultra" and (abs(word["scale_x"] - 1.0) > 0.001 or abs(word["scale_y"] - 1.0) > 0.001):
            failures.append(f"word {index} is distorted outside ultra mode")
        if layout["mode"] != "ultra" and word["height"] < MIN_RENDER_HEIGHT:
            failures.append(f"word {index} is smaller than the extra-small minimum")
    for first, second in zip(words, words[1:], strict=False):
        if first["clear_time"] > second["time"]:
            failures.append(f"word '{first['text']}' overlaps next word '{second['text']}' in time")
        if second["time"] <= first["time"]:
            failures.append("word timestamps are not strictly increasing")
    return {
        "pass": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "word_count": len(words),
        "mode": layout["mode"],
        "flat_style": layout.get("flat_style") is True and layout.get("effects") == [],
    }


if __name__ == "__main__":
    main()
