"""Image effects backed by NumPy and OpenCV."""

from __future__ import annotations

from vibeedit_media.images import ImageInput
from vibeedit_media.images import to_numpy_image
from vibeedit_media.optional import require_cv2
from vibeedit_media.optional import require_numpy


def invert_image(image: ImageInput):
    np = require_numpy()
    return 255 - np.asarray(to_numpy_image(image, "RGBA"))


def grayscale_image(image: ImageInput):
    cv2 = require_cv2()
    gray = cv2.cvtColor(to_numpy_image(image, "RGBA"), cv2.COLOR_RGBA2GRAY)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGBA)


def blur_image(image: ImageInput, radius: int = 5):
    cv2 = require_cv2()
    if radius <= 0:
        raise ValueError("radius must be greater than zero")
    kernel = radius if radius % 2 == 1 else radius + 1
    return cv2.GaussianBlur(to_numpy_image(image, "RGBA"), (kernel, kernel), 0)


def canny_edges(image: ImageInput, threshold1: int = 100, threshold2: int = 200):
    cv2 = require_cv2()
    gray = cv2.cvtColor(to_numpy_image(image, "RGBA"), cv2.COLOR_RGBA2GRAY)
    edges = cv2.Canny(gray, threshold1, threshold2)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2RGBA)


def apply_effect(image: ImageInput, effect: str, **kwargs):
    effects = {
        "blur": blur_image,
        "canny": canny_edges,
        "edges": canny_edges,
        "grayscale": grayscale_image,
        "invert": invert_image,
    }
    if effect not in effects:
        raise ValueError(f"Unsupported effect '{effect}'. Expected one of: {', '.join(sorted(effects))}")
    return effects[effect](image, **kwargs)
