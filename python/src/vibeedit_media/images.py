"""Image and text helpers backed by Pillow and NumPy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vibeedit_media.optional import require_numpy
from vibeedit_media.optional import require_pillow
from vibeedit_media.optional import require_pillow_draw

ImageInput = str | Path | object
Color = tuple[int, int, int] | tuple[int, int, int, int]


def open_image(path: str | Path, mode: str = "RGBA"):
    Image = require_pillow()
    return Image.open(path).convert(mode)


def to_pil_image(image: ImageInput, mode: str = "RGBA"):
    Image = require_pillow()
    if isinstance(image, str | Path):
        return open_image(image, mode)
    if hasattr(image, "convert") and hasattr(image, "save"):
        return image.convert(mode)

    np = require_numpy()
    array = np.asarray(image)
    if array.dtype != np.uint8:
        array = array.clip(0, 255).astype(np.uint8)
    return Image.fromarray(array).convert(mode)


def to_numpy_image(image: ImageInput, mode: str = "RGBA"):
    np = require_numpy()
    if isinstance(image, str | Path) or (hasattr(image, "convert") and hasattr(image, "save")):
        return np.asarray(to_pil_image(image, mode))

    array = np.asarray(image)
    if array.dtype != np.uint8:
        array = array.clip(0, 255).astype(np.uint8)
    if mode == "RGB" and array.ndim == 3 and array.shape[-1] == 4:
        return array[:, :, :3]
    if mode == "RGBA" and array.ndim == 3 and array.shape[-1] == 3:
        alpha = np.full((*array.shape[:2], 1), 255, dtype=np.uint8)
        return np.concatenate([array, alpha], axis=2)
    return array


def save_image(image: ImageInput, path: str | Path, mode: str = "RGBA") -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    to_pil_image(image, mode).save(destination)
    return destination


def resize_image(image: ImageInput, width: int, height: int, mode: str = "RGBA"):
    Image = require_pillow()
    return to_pil_image(image, mode).resize((width, height), Image.Resampling.LANCZOS)


def crop_image(image: ImageInput, box: tuple[int, int, int, int], mode: str = "RGBA"):
    return to_pil_image(image, mode).crop(box)


def render_text_image(
    text: str,
    width: int,
    height: int,
    color: Color = (255, 255, 255, 255),
    background: Color = (0, 0, 0, 0),
    font_size: int = 48,
    font_path: str | Path | None = None,
    anchor: str = "mm",
    position: tuple[int, int] | None = None,
):
    Image, ImageDraw, ImageFont = require_pillow_draw()
    image = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(image)
    draw.text(position or (width // 2, height // 2), text, fill=color, font=_load_font(ImageFont, font_path, font_size), anchor=anchor)
    return image


def composite_images(
    base: ImageInput,
    overlay: ImageInput,
    position: tuple[int, int] = (0, 0),
    opacity: float = 1.0,
    output: str = "numpy",
):
    Image = require_pillow()
    if not 0 <= opacity <= 1:
        raise ValueError("opacity must be between 0 and 1")

    base_image = to_pil_image(base, "RGBA")
    overlay_image = to_pil_image(overlay, "RGBA")
    if opacity < 1:
        overlay_image.putalpha(overlay_image.getchannel("A").point(lambda value: round(value * opacity)))

    canvas = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    canvas.paste(overlay_image, position, overlay_image)
    result = Image.alpha_composite(base_image, canvas)
    if output == "pil":
        return result
    if output == "numpy":
        return to_numpy_image(result, "RGBA")
    raise ValueError("output must be 'numpy' or 'pil'")


def _load_font(ImageFont: Any, font_path: str | Path | None, font_size: int):
    if font_path:
        return ImageFont.truetype(str(font_path), font_size)
    for candidate in (
        "DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, font_size)
        except OSError:
            pass
    return ImageFont.load_default()
