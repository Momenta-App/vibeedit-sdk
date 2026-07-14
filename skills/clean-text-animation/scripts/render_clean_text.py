#!/usr/bin/env python3
import argparse
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def main():
    args = parse_args()
    width, height = parse_size(args.size)
    fps = args.fps
    words = args.text.split()
    if not words:
        raise SystemExit("--text must contain at least one word")

    output = Path(args.output)
    frames_dir = Path(args.frames_dir) if args.frames_dir else output.with_suffix("").parent / f"{output.stem}-frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    font = fit_font(words, args.font, args.font_size, width, args.margin)
    metrics = measure_words(words, font, args.tracking)
    target = shimmer_target(args.shimmer, words)
    total_frames = max(1, math.ceil((args.duration + args.hold) * fps))
    base_y = int(height * args.baseline)
    starts = [1 / fps + index * args.stagger_frames / fps for index in range(len(words))]
    entry_duration = max(args.entry_duration, args.stagger_frames / fps)
    positions = word_positions(metrics, width)

    for frame in range(total_frames):
        t = frame / fps
        image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        for index, word in enumerate(words):
            progress = clamp((t - starts[index]) / entry_duration)
            if progress <= 0:
                continue

            eased = ease_out_back(progress)
            rise = args.last_rise if index == len(words) - 1 else args.rise
            y = base_y + rise * (1 - eased)
            alpha = int(255 * clamp(progress / args.fade_duration))

            if progress < 0.9 and args.trail:
                layer = draw_trails(layer, word, font, positions[index], base_y, rise, progress, args.color)

            if target == index and args.shimmer != "none" and args.shimmer_start <= t <= args.shimmer_start + args.shimmer_duration:
                shimmer_progress = clamp((t - args.shimmer_start) / args.shimmer_duration)
                layer = Image.alpha_composite(
                    layer,
                    clipped_shimmer_word(word, font, width, height, positions[index], y, alpha, shimmer_progress, args.color),
                )
                continue

            layer = Image.alpha_composite(layer, text_layer(word, font, width, height, positions[index], y, (*args.color, alpha)))

        Image.alpha_composite(image, layer).convert("RGB").save(frames_dir / f"frame_{frame + 1:02d}.png")

    run_ffmpeg(frames_dir, fps, output)
    if args.preview:
        write_preview(output, args.preview, min(args.duration * 0.4, args.duration + args.hold - 0.05))
    if args.contact_sheet:
        write_contact_sheet(frames_dir, Path(args.contact_sheet), width, height, fps)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--frames-dir")
    parser.add_argument("--preview")
    parser.add_argument("--contact-sheet")
    parser.add_argument("--shimmer", default="none")
    parser.add_argument("--size", default="720x1280")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument("--hold", type=float, default=0.4)
    parser.add_argument("--font", default="/System/Library/Fonts/Avenir.ttc")
    parser.add_argument("--font-size", type=int, default=47)
    parser.add_argument("--margin", type=int, default=44)
    parser.add_argument("--tracking", type=int, default=4)
    parser.add_argument("--baseline", type=float, default=0.484)
    parser.add_argument("--stagger-frames", type=int, default=2)
    parser.add_argument("--entry-duration", type=float, default=0.32)
    parser.add_argument("--fade-duration", type=float, default=0.24)
    parser.add_argument("--rise", type=int, default=38)
    parser.add_argument("--last-rise", type=int, default=54)
    parser.add_argument("--shimmer-start", type=float, default=0.24)
    parser.add_argument("--shimmer-duration", type=float, default=0.27)
    parser.add_argument("--no-trail", dest="trail", action="store_false")
    parser.add_argument("--color", default="0a182d")
    parser.set_defaults(trail=True)
    args = parser.parse_args()
    args.color = parse_hex(args.color)
    return args


def parse_size(value):
    width, height = value.lower().split("x", 1)
    return int(width), int(height)


def parse_hex(value):
    text = value.removeprefix("#")
    if len(text) != 6:
        raise SystemExit("--color must be a 6-digit hex color")
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))


def fit_font(words, font_path, font_size, width, margin):
    size = font_size
    while size >= 12:
        font = load_font(font_path, size)
        metrics = measure_words(words, font, 4)
        if sum(item["width"] for item in metrics) <= width - margin * 2:
            return font
        size -= 1
    return load_font(font_path, 12)


def load_font(font_path, size):
    try:
        return ImageFont.truetype(font_path, size, index=2)
    except TypeError:
        return ImageFont.truetype(font_path, size)


def measure_words(words, font, tracking):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    return [
        {
            "word": word,
            "width": draw.textbbox((0, 0), word, font=font)[2] - draw.textbbox((0, 0), word, font=font)[0] + tracking,
        }
        for word in words
    ]


def word_positions(metrics, width):
    total = sum(item["width"] for item in metrics)
    x = (width - total) / 2
    positions = []
    for item in metrics:
        positions.append(x)
        x += item["width"]
    return positions


def shimmer_target(value, words):
    if value == "none":
        return None
    if value == "last":
        return len(words) - 1
    if value.startswith("index:"):
        index = int(value.split(":", 1)[1])
        if 0 <= index < len(words):
            return index
        raise SystemExit("shimmer index is out of range")
    if value.startswith("word:"):
        target = value.split(":", 1)[1].lower()
        for index, word in enumerate(words):
            if word.lower() == target:
                return index
        raise SystemExit("shimmer word was not found in text")
    raise SystemExit("--shimmer must be none, last, index:N, or word:TEXT")


def clamp(value):
    return max(0, min(1, value))


def ease_out_back(t):
    c1 = 1.45
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def text_layer(word, font, width, height, x, y, fill, blur=0):
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((x, y), word, font=font, fill=fill)
    if blur:
        return layer.filter(ImageFilter.GaussianBlur(blur))
    return layer


def draw_trails(layer, word, font, x, base_y, rise, progress, color):
    for offset in (0.16, 0.09):
        trail_progress = clamp(progress - offset)
        if trail_progress <= 0:
            continue
        y = base_y + rise * (1 - ease_out_back(trail_progress)) + 5
        layer = Image.alpha_composite(layer, text_layer(word, font, layer.width, layer.height, x, y, (*color, 32), blur=1.7))
    return layer


def word_mask(word, font, width, height, x, y):
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).text((x, y), word, font=font, fill=255)
    return mask


def clipped_shimmer_word(word, font, width, height, x, y, alpha, progress, color):
    mask = word_mask(word, font, width, height, x, y)
    bbox = mask.getbbox()
    if not bbox:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))

    layer = Image.new("RGBA", (width, height), (*color, alpha))
    draw = ImageDraw.Draw(layer)
    left, top, right, bottom = bbox
    sweep_center = left - 42 + progress * ((right - left) + 84)

    for px in range(left, right):
        distance = abs(px - sweep_center)
        if distance > 36:
            continue
        strength = 1 - distance / 36
        if px < sweep_center:
            shimmer = (
                int(42 * (1 - strength) + 92 * strength),
                int(128 * (1 - strength) + 226 * strength),
                int(238 * (1 - strength) + 255 * strength),
                alpha,
            )
        else:
            shimmer = (
                int(70 * (1 - strength) + 212 * strength),
                int(150 * (1 - strength) + 245 * strength),
                int(190 * (1 - strength) + 88 * strength),
                alpha,
            )
        draw.line((px, top - 4, px, bottom + 4), fill=shimmer, width=1)

    core = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(core).rectangle((sweep_center - 4, top - 3, sweep_center + 4, bottom + 3), fill=(255, 255, 255, int(alpha * 0.85)))
    layer = Image.alpha_composite(layer, core)
    layer.putalpha(Image.eval(mask, lambda value: int(value * alpha / 255)))
    return layer


def run_ffmpeg(frames_dir, fps, output):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%02d.png"),
            "-vf",
            "format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def write_preview(video, preview, timestamp):
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{timestamp:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(preview)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def write_contact_sheet(frames_dir, output, width, height, fps):
    frames = sorted(frames_dir.glob("frame_*.png"))
    label_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 18)
    cell_width, cell_height = 360, 190
    columns = 5
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    crop = (0, int(height * 0.41), width, int(height * 0.56))
    for index, frame in enumerate(frames):
        image = Image.open(frame).convert("RGB")
        cell = Image.new("RGB", (cell_width, cell_height), "white")
        cell.paste(image.crop(crop).resize((cell_width, 170)), (0, 20))
        ImageDraw.Draw(cell).text((8, 2), f"{index:02d} / {index / fps:.2f}s", font=label_font, fill=(220, 0, 0))
        sheet.paste(cell, ((index % columns) * cell_width, (index // columns) * cell_height))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=95)


if __name__ == "__main__":
    main()
