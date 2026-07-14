"""Python approximations of FreeCut GPU effects.

The FreeCut source effects are WebGPU shaders. This module keeps the same
effect-id vocabulary but implements deterministic NumPy frame transforms so
agents can preview, tune, and render the same families in Python workflows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from vibeedit_media.images import ImageInput
from vibeedit_media.images import to_numpy_image
from vibeedit_media.optional import require_numpy


@dataclass(frozen=True)
class FreecutEffect:
    id: str
    name: str
    category: str
    default_params: dict[str, float | int | bool | str]


FREECUT_EFFECTS: tuple[FreecutEffect, ...] = (
    FreecutEffect("gpu-brightness", "Brightness", "color", {"amount": 0.0}),
    FreecutEffect("gpu-contrast", "Contrast", "color", {"amount": 1.0}),
    FreecutEffect("gpu-exposure", "Exposure", "color", {"exposure": 0.0, "offset": 0.0, "gamma": 1.0}),
    FreecutEffect("gpu-hue-shift", "Hue Shift", "color", {"shift": 0.0, "span": 1.0, "flow": 0.0}),
    FreecutEffect("gpu-invert", "Invert", "color", {}),
    FreecutEffect(
        "gpu-levels",
        "Levels",
        "color",
        {"inputBlack": 0.0, "inputWhite": 1.0, "gamma": 1.0, "outputBlack": 0.0, "outputWhite": 1.0},
    ),
    FreecutEffect("gpu-saturation", "Saturation", "color", {"amount": 1.0}),
    FreecutEffect("gpu-temperature", "Temperature", "color", {"temperature": 0.0, "tint": 0.0}),
    FreecutEffect("gpu-grayscale", "Grayscale", "color", {"amount": 1.0}),
    FreecutEffect("gpu-sepia", "Sepia", "color", {"amount": 0.55}),
    FreecutEffect("gpu-curves", "Curves", "color", {"shadowY": 0.12, "highlightY": 0.92, "gamma": 1.0}),
    FreecutEffect("gpu-color-wheels", "Color Wheels", "color", {"shadows": 0.0, "highlights": 0.0, "saturation": 0.0, "contrast": 1.0}),
    FreecutEffect("gpu-secondary-qualifier", "Secondary Qualifier", "color", {"hueCenter": 120.0, "hueWidth": 40.0, "strength": 1.0, "saturation": 20.0}),
    FreecutEffect("gpu-power-window", "Power Window", "color", {"centerX": 0.5, "centerY": 0.5, "sizeX": 0.55, "sizeY": 0.55, "feather": 0.25, "strength": 1.0, "exposure": 0.25}),
    FreecutEffect("gpu-gradient-map", "Gradient Map", "color", {"amount": 0.65}),
    FreecutEffect("gpu-lut", "LUT (.cube)", "color", {"intensity": 1.0}),
    FreecutEffect("gpu-gaussian-blur", "Gaussian Blur", "blur", {"radius": 8.0, "samples": 16}),
    FreecutEffect("gpu-box-blur", "Box Blur", "blur", {"radius": 6}),
    FreecutEffect("gpu-motion-blur", "Motion Blur", "blur", {"amount": 24.0, "angle": 0.0, "samples": 24}),
    FreecutEffect("gpu-radial-blur", "Radial Blur", "blur", {"amount": 0.35, "centerX": 0.5, "centerY": 0.5, "samples": 24}),
    FreecutEffect("gpu-zoom-blur", "Zoom Blur", "blur", {"amount": 0.22, "centerX": 0.5, "centerY": 0.5, "samples": 24}),
    FreecutEffect("gpu-pixelate", "Pixelate", "distort", {"pixelSize": 18}),
    FreecutEffect("gpu-rgb-split", "RGB Split", "distort", {"amount": 0.012, "angle": 0.0}),
    FreecutEffect("gpu-twirl", "Twirl", "distort", {"amount": 2.5, "radius": 0.65, "centerX": 0.5, "centerY": 0.5}),
    FreecutEffect("gpu-wave", "Wave", "distort", {"amplitudeX": 0.015, "amplitudeY": 0.02, "frequencyX": 6.0, "frequencyY": 4.0}),
    FreecutEffect(
        "gpu-trigger-wave",
        "Trigger Wave",
        "distort",
        {"strength": 0.045, "radius": 0.95, "frequency": 22.0, "decay": 0.07, "phase": 0.0, "speed": 0.9, "centerX": 0.5, "centerY": 0.5, "chroma": 0.009, "scanlineMix": 0.24},
    ),
    FreecutEffect("gpu-bulge", "Bulge/Pinch", "distort", {"amount": 0.55, "radius": 0.55, "centerX": 0.5, "centerY": 0.5}),
    FreecutEffect("gpu-kaleidoscope", "Kaleidoscope", "distort", {"segments": 8, "rotation": 0.0}),
    FreecutEffect("gpu-mirror", "Mirror", "distort", {"horizontal": True, "vertical": False}),
    FreecutEffect("gpu-fluted-glass", "Fluted Glass", "distort", {"size": 0.42, "angle": 0.0, "distortion": 0.38, "shift": 0.2, "blur": 0.12}),
    FreecutEffect("gpu-blocks", "Blocks", "distort", {"blockSize": 34, "depth": 0.28, "studSize": 0.35, "gap": 0.05}),
    FreecutEffect("gpu-droste", "Droste", "distort", {"strength": 0.55, "scale": 1.7, "centerX": 0.5, "centerY": 0.5, "spin": 0.0}),
    FreecutEffect("gpu-vignette", "Vignette", "stylize", {"amount": 0.45, "size": 0.45, "softness": 0.35, "roundness": 1.0}),
    FreecutEffect("gpu-grain", "Film Grain", "stylize", {"amount": 0.08, "size": 1.2, "speed": 1.0}),
    FreecutEffect("gpu-sharpen", "Sharpen", "stylize", {"amount": 0.55, "radius": 1.5}),
    FreecutEffect("gpu-posterize", "Posterize", "stylize", {"levels": 6}),
    FreecutEffect("gpu-glow", "Glow", "stylize", {"amount": 0.45, "threshold": 0.62, "radius": 12.0, "softness": 0.45}),
    FreecutEffect("gpu-edge-detect", "Edge Detect", "stylize", {"strength": 1.0, "invert": False}),
    FreecutEffect("gpu-scanlines", "Scanlines", "stylize", {"density": 8.0, "opacity": 0.28, "speed": 0.6}),
    FreecutEffect("gpu-color-glitch", "Color Glitch", "stylize", {"intensity": 0.5, "speed": 1.0}),
    FreecutEffect("gpu-block-glitch", "Block Glitch", "stylize", {"coverage": 0.35, "intensity": 0.55, "blockSize": 34, "speed": 1.0}),
    FreecutEffect("gpu-crt", "CRT", "stylize", {"curvature": 0.35, "scanlines": 0.35, "vignette": 0.35, "chroma": 0.5}),
    FreecutEffect("gpu-halftone", "Halftone", "stylize", {"size": 0.42, "radius": 0.75, "contrast": 0.65, "originalColors": False, "inverted": False}),
    FreecutEffect("gpu-dither", "Dither", "stylize", {"cellSize": 4, "palette": "bw", "threshold": 0.5}),
    FreecutEffect("gpu-threshold", "Threshold", "stylize", {"threshold": 0.52, "softness": 0.04, "invert": False}),
    FreecutEffect("gpu-ascii", "ASCII", "stylize", {"cellSize": 10, "contrast": 1.0, "amount": 1.0}),
    FreecutEffect("gpu-vhs", "VHS", "stylize", {"bleed": 0.5, "waviness": 0.4, "noise": 0.2, "scanline": 0.2, "speed": 1.0}),
    FreecutEffect("gpu-chroma-key", "Chroma Key", "keying", {"keyColor": "green", "tolerance": 0.25, "softness": 0.12, "spillSuppression": 0.55}),
)

EFFECT_APP_EFFECTS: tuple[FreecutEffect, ...] = (
    FreecutEffect("effect-app-depth-of-field", "Depth of field", "blur", {"radius": 10, "focusX": 0.5, "focusY": 0.48, "focusSize": 0.32, "feather": 0.35}),
    FreecutEffect("effect-app-circular-blur", "Circular blur", "blur", {"amount": 0.18, "centerX": 0.5, "centerY": 0.5, "samples": 18}),
    FreecutEffect("effect-app-gaussian-blur", "Gaussian blur", "blur", {"radius": 8}),
    FreecutEffect("effect-app-motion-blur", "Motion blur", "blur", {"amount": 18, "angle": 0, "samples": 18}),
    FreecutEffect("effect-app-radial-blur", "Radial blur", "blur", {"amount": 0.34, "centerX": 0.5, "centerY": 0.5, "samples": 24}),
    FreecutEffect("effect-app-blur-sharp", "Blur/sharp", "blur", {"blur": 3, "sharpen": 0.82}),
    FreecutEffect("effect-app-zoom-blur", "Zoom blur", "blur", {"amount": 0.24, "centerX": 0.5, "centerY": 0.5, "samples": 24}),
    FreecutEffect("effect-app-camera-shake", "Camera shake", "blur", {"amount": 0.02, "rotation": 0.018, "motion": 12}),
    FreecutEffect("effect-app-color-grading", "Color grading", "color", {"temperature": 0.18, "contrast": 1.12, "saturation": 1.12}),
    FreecutEffect("effect-app-thermal", "Thermal", "color", {"contrast": 1.0}),
    FreecutEffect("effect-app-curves", "Curves", "color", {"shadowY": 0.1, "highlightY": 0.96, "gamma": 0.88}),
    FreecutEffect("effect-app-color-balance", "Color balance", "color", {"red": 0.08, "green": 0.02, "blue": -0.08}),
    FreecutEffect("effect-app-gradient-map", "Gradient map", "color", {"amount": 0.78}),
    FreecutEffect("effect-app-color-temperature", "Color temperature", "color", {"temperature": 0.24, "tint": 0.04}),
    FreecutEffect("effect-app-dither", "Dither", "color", {"cellSize": 4, "palette": "green", "threshold": 0.5}),
    FreecutEffect("effect-app-hue-curves", "Hue curves", "color", {"shift": 0.18, "span": 1.05, "flow": 0.0}),
    FreecutEffect("effect-app-duotone", "Duotone", "color", {"amount": 1.0}),
    FreecutEffect("effect-app-hue-saturation", "Hue/saturation", "color", {"shift": -0.04, "span": 1.0, "saturation": 1.65}),
    FreecutEffect("effect-app-levels", "Levels", "color", {"inputBlack": 0.08, "inputWhite": 0.92, "gamma": 0.92, "outputBlack": 0.0, "outputWhite": 1.0}),
    FreecutEffect("effect-app-exposure", "Exposure", "color", {"exposure": 0.28, "offset": 0.0, "gamma": 1.0}),
    FreecutEffect("effect-app-monochrome", "Monochrome", "color", {"amount": 1.0, "tint": "green"}),
    FreecutEffect("effect-app-color-matrix", "Color matrix", "color", {"amount": 1.0}),
    FreecutEffect("effect-app-rgb-gain", "RGB Gain", "color", {"red": 1.18, "green": 1.02, "blue": 0.86}),
    FreecutEffect("effect-app-contrast", "Contrast", "color", {"amount": 1.45}),
    FreecutEffect("effect-app-elastic-grid", "Elastic grid", "distort", {"amplitudeX": 0.02, "amplitudeY": 0.018, "frequencyX": 4.5, "frequencyY": 6.0}),
    FreecutEffect("effect-app-reeded-glass", "Reeded glass", "distort", {"size": 0.32, "angle": 0.0, "distortion": 0.42, "shift": 0.2, "blur": 0.12}),
    FreecutEffect("effect-app-cubify", "Cubify", "distort", {"blockSize": 26, "depth": 0.28, "studSize": 0.35, "gap": 0.05}),
    FreecutEffect("effect-app-glitch", "Glitch", "distort", {"coverage": 0.35, "intensity": 0.62, "blockSize": 18, "speed": 1.0}),
    FreecutEffect("effect-app-perspective", "Perspective", "distort", {"tilt": 0.2, "shade": 0.22}),
    FreecutEffect("effect-app-pinch", "Pinch", "distort", {"amount": 0.62, "radius": 0.55, "centerX": 0.5, "centerY": 0.5}),
    FreecutEffect("effect-app-polar-to-rectangular", "Polar to rectangular", "distort", {"amount": 1.0}),
    FreecutEffect("effect-app-rectangular-to-polar", "Rectangular to polar", "distort", {"amount": 1.0}),
    FreecutEffect("effect-app-ripple", "Ripple", "distort", {"amplitudeX": 0.016, "amplitudeY": 0.012, "frequencyX": 7.0, "frequencyY": 5.0}),
    FreecutEffect("effect-app-transform", "Transform", "distort", {"scaleX": 0.9, "scaleY": 1.08, "rotation": -0.08}),
    FreecutEffect("effect-app-swirl", "Swirl", "distort", {"amount": 2.2, "radius": 0.66, "centerX": 0.5, "centerY": 0.5}),
    FreecutEffect("effect-app-risograph", "Risograph", "stylize", {"amount": 1.0}),
    FreecutEffect("effect-app-vhs", "VHS", "stylize", {"bleed": 0.55, "waviness": 0.5, "noise": 0.22, "scanline": 0.26, "speed": 1.0}),
    FreecutEffect("effect-app-ascii", "ASCII", "stylize", {"cellSize": 9, "contrast": 1.2, "amount": 1.0}),
    FreecutEffect("effect-app-halftone-screen", "Halftone screen", "stylize", {"size": 0.38, "radius": 0.8, "contrast": 0.65, "originalColors": False, "inverted": False}),
    FreecutEffect("effect-app-emboss", "Emboss", "stylize", {"strength": 1.0}),
    FreecutEffect("effect-app-bloom", "Bloom", "stylize", {"amount": 0.62, "threshold": 0.54, "radius": 14.0, "softness": 0.45}),
    FreecutEffect("effect-app-star-glow", "Star glow", "stylize", {"amount": 0.55, "threshold": 0.64, "radius": 16.0, "softness": 0.45}),
    FreecutEffect("effect-app-motion-trails", "Motion trails", "stylize", {"amount": 18, "angle": 150, "samples": 10}),
    FreecutEffect("effect-app-led-screen", "LED screen", "stylize", {"pixelSize": 8, "opacity": 0.34}),
    FreecutEffect("effect-app-ntsc", "NTSC", "stylize", {"bleed": 0.6, "waviness": 0.35, "noise": 0.18, "scanline": 0.32, "speed": 1.0}),
    FreecutEffect("effect-app-rgb-shift", "RGB Shift", "stylize", {"amount": 0.018, "angle": 0.0}),
    FreecutEffect("effect-app-crt-screen", "CRT screen", "stylize", {"curvature": 0.35, "scanlines": 0.42, "vignette": 0.42, "chroma": 0.55}),
    FreecutEffect("effect-app-modulation", "Modulation", "stylize", {"amplitudeX": 0.012, "amplitudeY": 0.0, "frequencyX": 12.0, "frequencyY": 2.0}),
    FreecutEffect("effect-app-threshold", "Threshold", "stylize", {"threshold": 0.54, "softness": 0.02, "invert": False}),
    FreecutEffect("effect-app-vignette", "Vignette", "stylize", {"amount": 0.62, "size": 0.42, "softness": 0.45, "roundness": 1.0}),
    FreecutEffect("effect-app-stripe", "Stripe", "stylize", {"width": 8, "gap": 20, "opacity": 0.32}),
    FreecutEffect("effect-app-frame-drop", "Frame drop", "stylize", {"bands": 12, "opacity": 0.18}),
    FreecutEffect("effect-app-text", "Text", "generate", {"opacity": 0.74}),
    FreecutEffect("effect-app-noise", "Noise", "generate", {"amount": 1.0, "size": 1.0, "speed": 1.0}),
    FreecutEffect("effect-app-ink-bleed", "Ink bleed", "generate", {"threshold": 0.5, "softness": 0.04, "bleed": 4}),
    FreecutEffect("effect-app-paper-scan", "Paper scan", "generate", {"grain": 0.12, "scanline": 0.12}),
    FreecutEffect("effect-app-blob-tracker", "Blob Tracker", "generate", {"strength": 1.0}),
    FreecutEffect("effect-app-layer-mix", "Layer Mix", "custom", {"amount": 0.55, "shift": 0.33}),
    FreecutEffect("effect-app-texture-blur", "Texture Blur", "custom", {"radius": 5, "grain": 0.12}),
    FreecutEffect("effect-app-displacement", "Displacement", "custom", {"strength": 0.026, "frequency": 7.0}),
    FreecutEffect("effect-app-classic-film", "Classic Film", "film", {"grain": 0.08, "warmth": 0.1, "contrast": 1.08}),
    FreecutEffect("effect-app-vintage-film", "Vintage Film", "film", {"grain": 0.1, "sepia": 0.42, "contrast": 1.08}),
    FreecutEffect("effect-app-black-white", "Black & White", "film", {"amount": 1.0, "contrast": 1.12}),
    FreecutEffect("effect-app-film-grain", "Film Grain", "film", {"amount": 0.12, "size": 1.2, "speed": 1.0}),
    FreecutEffect("effect-app-halation", "Halation", "film", {"amount": 0.58, "threshold": 0.58, "radius": 16.0}),
)

FREECUT_EFFECTS = FREECUT_EFFECTS + EFFECT_APP_EFFECTS

FREECUT_PRESETS: dict[str, tuple[tuple[str, dict[str, float | int | bool | str]], ...]] = {
    "trigger-wave-layer": (
        ("gpu-trigger-wave", {"strength": 0.045, "radius": 0.95, "frequency": 22, "decay": 0.07, "speed": 0.9, "chroma": 0.009, "scanlineMix": 0.24}),
        ("gpu-rgb-split", {"amount": 0.006, "angle": 0}),
        ("gpu-scanlines", {"density": 8, "opacity": 0.16, "speed": 0.6}),
        ("gpu-grain", {"amount": 0.05, "size": 1.2, "speed": 0.8}),
    ),
    "crt": (("gpu-crt", {"curvature": 0.35, "scanlines": 0.35, "vignette": 0.35, "chroma": 0.5}), ("gpu-grain", {"amount": 0.06}), ("gpu-saturation", {"amount": 1.1})),
    "retro-tv": (("gpu-vhs", {"bleed": 0.5, "waviness": 0.4, "noise": 0.2, "scanline": 0.2}), ("gpu-crt", {"curvature": 0.3, "scanlines": 0.3, "vignette": 0.35, "chroma": 0.4})),
    "vintage": (("gpu-sepia", {"amount": 0.4}), ("gpu-contrast", {"amount": 1.1}), ("gpu-brightness", {"amount": -0.1})),
    "noir": (("gpu-grayscale", {"amount": 1}), ("gpu-contrast", {"amount": 1.3})),
    "cold": (("gpu-hue-shift", {"shift": 0.5}), ("gpu-saturation", {"amount": 0.8})),
    "warm": (("gpu-sepia", {"amount": 0.2}), ("gpu-saturation", {"amount": 1.2})),
    "dramatic": (("gpu-contrast", {"amount": 1.5}), ("gpu-saturation", {"amount": 1.3})),
    "faded": (("gpu-contrast", {"amount": 0.8}), ("gpu-brightness", {"amount": 0.1}), ("gpu-saturation", {"amount": 0.7})),
}


def list_freecut_effects(category: str | None = None) -> list[dict[str, Any]]:
    effects = [
        {
            "id": effect.id,
            "name": effect.name,
            "category": effect.category,
            "defaultParams": effect.default_params,
        }
        for effect in FREECUT_EFFECTS
    ]
    if category is None:
        return effects
    return [effect for effect in effects if effect["category"] == category]


def get_freecut_effect(effect_id: str) -> dict[str, Any]:
    for effect in list_freecut_effects():
        if effect["id"] == effect_id:
            return effect
    raise KeyError(f"Unknown FreeCut effect '{effect_id}'")


def apply_freecut_effect(
    image: ImageInput,
    effect_id: str,
    *,
    params: dict[str, float | int | bool | str] | None = None,
    progress: float = 0.0,
):
    np = require_numpy()
    effect = _effect(effect_id)
    settings = {**effect.default_params, **(params or {})}
    array = to_numpy_image(image, "RGBA")
    rgb = _as_float(array[:, :, :3])
    alpha = array[:, :, 3:4]
    result = _dispatch(rgb, effect.id, settings, max(0.0, min(1.0, progress)))
    return np.concatenate([_finish(result), alpha], axis=2)


def apply_freecut_preset(image: ImageInput, preset_id: str, *, progress: float = 0.0):
    if preset_id not in FREECUT_PRESETS:
        raise KeyError(f"Unknown FreeCut preset '{preset_id}'")
    result = image
    for effect_id, params in FREECUT_PRESETS[preset_id]:
        result = apply_freecut_effect(result, effect_id, params=params, progress=progress)
    return result


def apply_freecut_effect_to_frames(
    frames,
    effect_id: str,
    *,
    params: dict[str, float | int | bool | str] | None = None,
):
    frame_list = list(frames)
    total = max(len(frame_list) - 1, 1)
    return [apply_freecut_effect(frame, effect_id, params=params, progress=index / total) for index, frame in enumerate(frame_list)]


def write_freecut_effect_video(
    frames,
    effect_id: str,
    path,
    *,
    params: dict[str, float | int | bool | str] | None = None,
    fps: int = 24,
    codec: str = "libx264",
    audio: bool = False,
    **kwargs,
):
    from vibeedit_media.movie import write_video

    return write_video(apply_freecut_effect_to_frames(frames, effect_id, params=params), path, fps=fps, codec=codec, audio=audio, **kwargs)


def _effect(effect_id: str) -> FreecutEffect:
    for effect in FREECUT_EFFECTS:
        if effect.id == effect_id:
            return effect
    raise KeyError(f"Unknown FreeCut effect '{effect_id}'")


def _dispatch(rgb, effect_id: str, params: dict[str, float | int | bool | str], progress: float):
    if effect_id.startswith("effect-app-"):
        return _dispatch_effect_app(rgb, effect_id, params, progress)
    if effect_id == "gpu-brightness":
        return rgb + float(params["amount"])
    if effect_id == "gpu-contrast":
        return (rgb - 0.5) * float(params["amount"]) + 0.5
    if effect_id == "gpu-exposure":
        return (rgb * (2 ** float(params["exposure"])) + float(params["offset"])) ** (1 / max(float(params["gamma"]), 0.05))
    if effect_id == "gpu-hue-shift":
        return _hue_shift(rgb, float(params["shift"]) + float(params["flow"]) * progress, float(params["span"]))
    if effect_id == "gpu-invert":
        return 1 - rgb
    if effect_id == "gpu-levels":
        adjusted = (rgb - float(params["inputBlack"])) / max(float(params["inputWhite"]) - float(params["inputBlack"]), 0.001)
        adjusted = _np().maximum(adjusted, 0) ** (1 / max(float(params["gamma"]), 0.05))
        return float(params["outputBlack"]) + adjusted * (float(params["outputWhite"]) - float(params["outputBlack"]))
    if effect_id == "gpu-saturation":
        return _saturate(rgb, float(params["amount"]))
    if effect_id == "gpu-temperature":
        return rgb + _np().array([float(params["temperature"]) * 0.1 + float(params["tint"]) * 0.05, -float(params["tint"]) * 0.1, -float(params["temperature"]) * 0.1 + float(params["tint"]) * 0.05])
    if effect_id == "gpu-grayscale":
        return _mix(rgb, _luma(rgb), float(params["amount"]))
    if effect_id == "gpu-sepia":
        sepia = _np().stack([rgb[:, :, 0] * 0.393 + rgb[:, :, 1] * 0.769 + rgb[:, :, 2] * 0.189, rgb[:, :, 0] * 0.349 + rgb[:, :, 1] * 0.686 + rgb[:, :, 2] * 0.168, rgb[:, :, 0] * 0.272 + rgb[:, :, 1] * 0.534 + rgb[:, :, 2] * 0.131], axis=2)
        return _mix(rgb, sepia, float(params["amount"]))
    if effect_id == "gpu-curves":
        return _curves(rgb, params)
    if effect_id == "gpu-color-wheels":
        return _color_wheels(rgb, params)
    if effect_id == "gpu-secondary-qualifier":
        return _secondary_qualifier(rgb, params)
    if effect_id == "gpu-power-window":
        return _power_window(rgb, params)
    if effect_id in {"gpu-gradient-map", "gpu-lut"}:
        return _gradient_map(rgb, float(params.get("amount", params.get("intensity", 1))))
    if effect_id in {"gpu-gaussian-blur", "gpu-box-blur"}:
        return _box_blur(rgb, max(1, int(float(params["radius"]))))
    if effect_id == "gpu-motion-blur":
        return _motion_blur(rgb, int(float(params["amount"])), math.radians(float(params["angle"])), int(float(params["samples"])))
    if effect_id == "gpu-radial-blur":
        return _radial_blur(rgb, float(params["amount"]), float(params["centerX"]), float(params["centerY"]), int(float(params["samples"])))
    if effect_id == "gpu-zoom-blur":
        return _zoom_blur(rgb, float(params["amount"]), float(params["centerX"]), float(params["centerY"]), int(float(params["samples"])))
    if effect_id == "gpu-pixelate":
        return _pixelate(rgb, int(float(params["pixelSize"])))
    if effect_id == "gpu-rgb-split":
        return _rgb_split(rgb, float(params["amount"]), math.radians(float(params["angle"])))
    if effect_id == "gpu-twirl":
        return _twirl(rgb, params)
    if effect_id == "gpu-wave":
        return _wave(rgb, params, progress)
    if effect_id == "gpu-trigger-wave":
        return _trigger_wave(rgb, params, progress)
    if effect_id == "gpu-bulge":
        return _bulge(rgb, params)
    if effect_id == "gpu-kaleidoscope":
        return _kaleidoscope(rgb, int(float(params["segments"])), float(params["rotation"]))
    if effect_id == "gpu-mirror":
        return _mirror(rgb, bool(params["horizontal"]), bool(params["vertical"]))
    if effect_id == "gpu-fluted-glass":
        return _fluted_glass(rgb, params, progress)
    if effect_id == "gpu-blocks":
        return _blocks(rgb, params)
    if effect_id == "gpu-droste":
        return _droste(rgb, params, progress)
    if effect_id == "gpu-vignette":
        return _vignette(rgb, params)
    if effect_id == "gpu-grain":
        return _grain(rgb, float(params["amount"]), float(params["size"]), progress)
    if effect_id == "gpu-sharpen":
        return _sharpen(rgb, float(params["amount"]), int(max(1, float(params["radius"]))))
    if effect_id == "gpu-posterize":
        return _np().floor(rgb * max(2, int(float(params["levels"])))) / max(1, int(float(params["levels"])) - 1)
    if effect_id == "gpu-glow":
        return _glow(rgb, params)
    if effect_id == "gpu-edge-detect":
        return _edge_detect(rgb, float(params["strength"]), bool(params["invert"]))
    if effect_id == "gpu-scanlines":
        return _scanlines(rgb, params, progress)
    if effect_id == "gpu-color-glitch":
        return _color_glitch(rgb, params, progress)
    if effect_id == "gpu-block-glitch":
        return _block_glitch(rgb, params, progress)
    if effect_id == "gpu-crt":
        return _crt(rgb, params, progress)
    if effect_id == "gpu-halftone":
        return _halftone(rgb, params)
    if effect_id == "gpu-dither":
        return _dither(rgb, int(float(params["cellSize"])))
    if effect_id == "gpu-threshold":
        return _threshold(rgb, float(params["threshold"]), float(params["softness"]), bool(params["invert"]))
    if effect_id == "gpu-ascii":
        return _ascii(rgb, int(float(params["cellSize"])), float(params["contrast"]), float(params["amount"]))
    if effect_id == "gpu-vhs":
        return _vhs(rgb, params, progress)
    if effect_id == "gpu-chroma-key":
        return _chroma_key(rgb, params)
    raise ValueError(f"Unhandled FreeCut effect '{effect_id}'")


def _dispatch_effect_app(rgb, effect_id: str, params: dict[str, float | int | bool | str], progress: float):
    if effect_id == "effect-app-depth-of-field":
        return _depth_of_field(rgb, params)
    if effect_id == "effect-app-circular-blur":
        return _spin_blur(rgb, float(params["amount"]), float(params["centerX"]), float(params["centerY"]), int(float(params["samples"])))
    if effect_id == "effect-app-gaussian-blur":
        return _box_blur(rgb, max(1, int(float(params["radius"]))))
    if effect_id == "effect-app-motion-blur":
        return _motion_blur(rgb, int(float(params["amount"])), math.radians(float(params["angle"])), int(float(params["samples"])))
    if effect_id == "effect-app-radial-blur":
        return _radial_blur(rgb, float(params["amount"]), float(params["centerX"]), float(params["centerY"]), int(float(params["samples"])))
    if effect_id == "effect-app-blur-sharp":
        return _sharpen(_box_blur(rgb, int(float(params["blur"]))), float(params["sharpen"]), 1)
    if effect_id == "effect-app-zoom-blur":
        return _zoom_blur(rgb, float(params["amount"]), float(params["centerX"]), float(params["centerY"]), int(float(params["samples"])))
    if effect_id == "effect-app-camera-shake":
        return _camera_shake(rgb, params, progress)
    if effect_id == "effect-app-color-grading":
        graded = _saturate(rgb + _np().array([0.04, 0.015, -0.035]), float(params["saturation"]))
        return (graded - 0.5) * float(params["contrast"]) + 0.5
    if effect_id == "effect-app-thermal":
        return _thermal(rgb, float(params["contrast"]))
    if effect_id == "effect-app-curves":
        return _curves(rgb, params)
    if effect_id == "effect-app-color-balance":
        return rgb + _np().array([float(params["red"]), float(params["green"]), float(params["blue"])])
    if effect_id == "effect-app-gradient-map":
        return _effect_gradient_map(rgb, float(params["amount"]), ((0.02, 0.05, 0.16), (0.16, 0.72, 0.79), (0.96, 0.86, 0.42), (1.0, 0.28, 0.2)))
    if effect_id == "effect-app-color-temperature":
        return rgb + _np().array([float(params["temperature"]) * 0.12 + float(params["tint"]) * 0.04, -float(params["tint"]) * 0.08, -float(params["temperature"]) * 0.1 + float(params["tint"]) * 0.04])
    if effect_id == "effect-app-dither":
        return _dither_palette(rgb, int(float(params["cellSize"])), str(params["palette"]))
    if effect_id == "effect-app-hue-curves":
        return _hue_shift(rgb, float(params["shift"]) + float(params["flow"]) * progress, float(params["span"]))
    if effect_id == "effect-app-duotone":
        return _effect_gradient_map(rgb, float(params["amount"]), ((0.03, 0.03, 0.02), (1.0, 0.28, 0.5), (0.96, 0.94, 0.86)))
    if effect_id == "effect-app-hue-saturation":
        return _saturate(_hue_shift(rgb, float(params["shift"]), float(params["span"])), float(params["saturation"]))
    if effect_id == "effect-app-levels":
        return _dispatch(rgb, "gpu-levels", params, progress)
    if effect_id == "effect-app-exposure":
        return _dispatch(rgb, "gpu-exposure", params, progress)
    if effect_id == "effect-app-monochrome":
        return _tinted_monochrome(rgb, str(params["tint"]))
    if effect_id == "effect-app-color-matrix":
        return _color_matrix(rgb)
    if effect_id == "effect-app-rgb-gain":
        return rgb * _np().array([float(params["red"]), float(params["green"]), float(params["blue"])])
    if effect_id == "effect-app-contrast":
        return _dispatch(rgb, "gpu-contrast", params, progress)
    if effect_id == "effect-app-elastic-grid":
        return _wave(rgb, params, progress)
    if effect_id == "effect-app-reeded-glass":
        return _fluted_glass(rgb, params, progress)
    if effect_id == "effect-app-cubify":
        return _blocks(rgb, params)
    if effect_id == "effect-app-glitch":
        return _block_glitch(rgb, params, progress)
    if effect_id == "effect-app-perspective":
        return _perspective_shade(rgb, params)
    if effect_id == "effect-app-pinch":
        return _bulge(rgb, params)
    if effect_id == "effect-app-polar-to-rectangular":
        return _polar_to_rectangular(rgb)
    if effect_id == "effect-app-rectangular-to-polar":
        return _rectangular_to_polar(rgb)
    if effect_id == "effect-app-ripple":
        return _wave(rgb, params, progress)
    if effect_id == "effect-app-transform":
        return _transform_sample(rgb, params)
    if effect_id == "effect-app-swirl":
        return _twirl(rgb, params)
    if effect_id == "effect-app-risograph":
        return _risograph(rgb)
    if effect_id == "effect-app-vhs":
        return _vhs(rgb, params, progress)
    if effect_id == "effect-app-ascii":
        return _ascii(rgb, int(float(params["cellSize"])), float(params["contrast"]), float(params["amount"]))
    if effect_id == "effect-app-halftone-screen":
        return _halftone(rgb, params)
    if effect_id == "effect-app-emboss":
        return _emboss(rgb, float(params["strength"]))
    if effect_id == "effect-app-bloom":
        return _glow(rgb, params)
    if effect_id == "effect-app-star-glow":
        return _star_glow(rgb, params)
    if effect_id == "effect-app-motion-trails":
        return _motion_blur(rgb, int(float(params["amount"])), math.radians(float(params["angle"])), int(float(params["samples"])))
    if effect_id == "effect-app-led-screen":
        return _led_screen(rgb, int(float(params["pixelSize"])), float(params["opacity"]))
    if effect_id == "effect-app-ntsc":
        return _crt(_vhs(rgb, params, progress), {"curvature": 0.2, "scanlines": 0.2, "vignette": 0.25, "chroma": 0.25}, progress)
    if effect_id == "effect-app-rgb-shift":
        return _rgb_split(rgb, float(params["amount"]), math.radians(float(params["angle"])))
    if effect_id == "effect-app-crt-screen":
        return _crt(rgb, params, progress)
    if effect_id == "effect-app-modulation":
        return _wave(rgb, params, progress)
    if effect_id == "effect-app-threshold":
        return _threshold(rgb, float(params["threshold"]), float(params["softness"]), bool(params["invert"]))
    if effect_id == "effect-app-vignette":
        return _vignette(rgb, params)
    if effect_id == "effect-app-stripe":
        return _stripe(rgb, params)
    if effect_id == "effect-app-frame-drop":
        return _frame_drop(rgb, params, progress)
    if effect_id == "effect-app-text":
        return _text_overlay(rgb, float(params["opacity"]))
    if effect_id == "effect-app-noise":
        return _grain(_np().zeros_like(rgb) + 0.08, float(params["amount"]) * 0.35, float(params["size"]), progress)
    if effect_id == "effect-app-ink-bleed":
        return _box_blur(_threshold(rgb, float(params["threshold"]), float(params["softness"]), False), int(float(params["bleed"])))
    if effect_id == "effect-app-paper-scan":
        return _scanlines(_grain(_saturate(_dispatch(rgb, "gpu-sepia", {"amount": 0.28}, progress), 0.72), float(params["grain"]), 1.0, progress), {"density": 7, "opacity": float(params["scanline"]), "speed": 0.0}, progress)
    if effect_id == "effect-app-blob-tracker":
        return _blob_tracker(rgb)
    if effect_id == "effect-app-layer-mix":
        return _mix(rgb, _hue_shift(_np().roll(rgb, round(rgb.shape[1] * 0.04), axis=1), float(params["shift"]), 1.0), float(params["amount"]))
    if effect_id == "effect-app-texture-blur":
        return _grain(_box_blur(rgb, int(float(params["radius"]))), float(params["grain"]), 1.0, progress)
    if effect_id == "effect-app-displacement":
        return _displacement(rgb, params, progress)
    if effect_id == "effect-app-classic-film":
        return _film(rgb, params, progress, "classic")
    if effect_id == "effect-app-vintage-film":
        return _film(rgb, params, progress, "vintage")
    if effect_id == "effect-app-black-white":
        return _np().repeat(((_luma(rgb) - 0.5) * float(params["contrast"]) + 0.5), 3, axis=2)
    if effect_id == "effect-app-film-grain":
        return _grain(rgb, float(params["amount"]), float(params["size"]), progress)
    if effect_id == "effect-app-halation":
        return rgb + _box_blur(rgb * (_luma(rgb) > float(params["threshold"])), max(1, round(float(params["radius"]) / 4))) * float(params["amount"])
    raise ValueError(f"Unhandled Effect.app effect '{effect_id}'")


def _depth_of_field(rgb, params):
    x, y, width, height = _coords(rgb.shape)
    blurred = _box_blur(rgb, max(1, int(float(params["radius"]))))
    dx = (x / width - float(params["focusX"])) / max(float(params["focusSize"]), 0.001)
    dy = (y / height - float(params["focusY"])) / max(float(params["focusSize"]), 0.001)
    focus = _np().clip((_np().sqrt(dx * dx + dy * dy) - 0.45) / max(float(params["feather"]), 0.001), 0, 1)[:, :, None]
    return _mix(rgb, blurred, focus)


def _spin_blur(rgb, amount: float, center_x: float, center_y: float, samples: int):
    x, y, width, height = _coords(rgb.shape)
    cx = center_x * width
    cy = center_y * height
    dx = x - cx
    dy = y - cy
    dist = _np().sqrt(dx * dx + dy * dy)
    base_angle = _np().arctan2(dy, dx)
    result = _np().zeros_like(rgb)
    for index in range(samples):
        angle = base_angle + (index / max(samples - 1, 1) - 0.5) * amount
        result += _sample(rgb, cx + _np().cos(angle) * dist, cy + _np().sin(angle) * dist)
    return result / samples


def _camera_shake(rgb, params, progress: float):
    amount = float(params["amount"])
    shift_x = round(math.sin(progress * math.tau * 7) * rgb.shape[1] * amount)
    shift_y = round(math.cos(progress * math.tau * 5) * rgb.shape[0] * amount)
    return _motion_blur(_np().roll(_np().roll(rgb, shift_y, axis=0), shift_x, axis=1), int(float(params["motion"])), 0, 8)


def _thermal(rgb, contrast: float):
    value = _np().clip(_luma(rgb)[:, :, 0] * contrast, 0, 1)
    red = _np().clip(value * 2.9, 0, 1)
    green = _np().sin(value * math.pi)
    blue = _np().clip(1 - value * 2.1, 0, 1)
    return _np().stack([red, green, blue], axis=2)


def _effect_gradient_map(rgb, amount: float, palette):
    np = _np()
    value = _luma(rgb)[:, :, 0]
    scaled = value * (len(palette) - 1)
    index = np.floor(scaled).astype(int).clip(0, len(palette) - 1)
    next_index = (index + 1).clip(0, len(palette) - 1)
    mix = (scaled - index)[:, :, None]
    colors = np.array(palette)
    mapped = colors[index] * (1 - mix) + colors[next_index] * mix
    return _mix(rgb, mapped, amount)


def _dither_palette(rgb, cell_size: int, palette_name: str):
    np = _np()
    gray = _luma(rgb)[:, :, 0]
    matrix = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
    y, x = np.indices(gray.shape)
    threshold = matrix[y % 4, x % 4] - 0.5
    value = np.clip(gray + threshold / max(cell_size, 1), 0, 0.999)
    palette = np.array(
        [(0.03, 0.03, 0.02), (0.85, 1.0, 0.33), (0.94, 0.92, 0.84)]
        if palette_name == "green"
        else [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
    )
    return palette[np.floor(value * len(palette)).astype(int)]


def _tinted_monochrome(rgb, tint: str):
    color = _np().array([0.8, 0.96, 0.86]) if tint == "green" else _np().array([1.0, 1.0, 1.0])
    return _luma(rgb) * color


def _color_matrix(rgb):
    matrix = _np().array([[1.18, -0.08, 0.04], [0.05, 1.05, 0.0], [-0.08, 0.0, 1.16]])
    return rgb @ matrix.T


def _perspective_shade(rgb, params):
    x, y, width, height = _coords(rgb.shape)
    shade = 1 - ((x / width) * 0.2 + (y / height) * float(params["shade"]))[:, :, None]
    return rgb * shade


def _polar_to_rectangular(rgb):
    x, y, width, height = _coords(rgb.shape)
    theta = x / width * math.tau
    radius = y / height * min(width, height) * 0.65
    return _sample(rgb, width / 2 + _np().cos(theta) * radius, height / 2 + _np().sin(theta) * radius)


def _rectangular_to_polar(rgb):
    x, y, width, height = _coords(rgb.shape)
    dx = x - width / 2
    dy = y - height / 2
    radius = _np().sqrt(dx * dx + dy * dy) / (min(width, height) * 0.68)
    theta = (_np().arctan2(dy, dx) + math.pi) / math.tau
    return _sample(rgb, theta * width, radius * height)


def _transform_sample(rgb, params):
    x, y, width, height = _coords(rgb.shape)
    cx = width / 2
    cy = height / 2
    angle = -float(params["rotation"])
    dx = (x - cx) / max(float(params["scaleX"]), 0.001)
    dy = (y - cy) / max(float(params["scaleY"]), 0.001)
    return _sample(rgb, cx + dx * math.cos(angle) - dy * math.sin(angle), cy + dx * math.sin(angle) + dy * math.cos(angle))


def _risograph(rgb):
    mapped = _effect_gradient_map(rgb, 1.0, ((0.96, 0.9, 0.78), (1.0, 0.35, 0.24), (0.09, 0.36, 0.32), (0.06, 0.06, 0.05)))
    y, x = _np().indices(rgb.shape[:2])
    dots = (((x + y) % 7) < 2)[:, :, None] * 0.12
    return mapped * (1 - dots)


def _emboss(rgb, strength: float):
    gray = _luma(rgb)[:, :, 0]
    raised = 0.5 + (_np().roll(gray, -1, axis=0) + _np().roll(gray, -1, axis=1) - _np().roll(gray, 1, axis=0) - _np().roll(gray, 1, axis=1)) * strength
    return _np().repeat(raised[:, :, None], 3, axis=2)


def _star_glow(rgb, params):
    glow = _glow(rgb, params)
    bright = (_luma(rgb) > float(params["threshold"])).astype(float)
    rays = _box_blur(_np().repeat(bright, 3, axis=2), 1)
    rays = rays + _np().roll(rays, 6, axis=0) + _np().roll(rays, -6, axis=0) + _np().roll(rays, 6, axis=1) + _np().roll(rays, -6, axis=1)
    return glow + rays * float(params["amount"]) * 0.25


def _led_screen(rgb, pixel_size: int, opacity: float):
    pixelated = _pixelate(rgb, pixel_size)
    y, x = _np().indices(rgb.shape[:2])
    mask = (((x % pixel_size) - pixel_size / 2) ** 2 + ((y % pixel_size) - pixel_size / 2) ** 2) < (pixel_size * 0.32) ** 2
    return pixelated * (1 - opacity * (1 - mask[:, :, None]))


def _stripe(rgb, params):
    y, x = _np().indices(rgb.shape[:2])
    stripe = (((x + y * 0.25) % int(float(params["gap"]))) < int(float(params["width"])))[:, :, None]
    return _mix(rgb, rgb * _np().array([1.0, 0.42, 0.32]), stripe * float(params["opacity"]))


def _frame_drop(rgb, params, progress: float):
    result = rgb.copy()
    y = _np().indices(rgb.shape[:2])[0]
    bands = ((y + round(progress * 60)) % max(2, int(float(params["bands"])))) < 4
    result[bands] *= 1 - float(params["opacity"])
    return result


def _text_overlay(rgb, opacity: float):
    result = rgb.copy()
    height, width = rgb.shape[:2]
    y0 = round(height * 0.72)
    y1 = round(height * 0.84)
    result[y0:y1, round(width * 0.08) : round(width * 0.92)] = _mix(result[y0:y1, round(width * 0.08) : round(width * 0.92)], _np().array([0.85, 1.0, 0.33]), opacity)
    return result


def _blob_tracker(rgb):
    result = rgb.copy()
    height, width = rgb.shape[:2]
    for x0, y0, x1, y1 in [(0.28, 0.32, 0.5, 0.48), (0.32, 0.46, 0.72, 0.76), (0.42, 0.7, 0.72, 0.92)]:
        _draw_rect(result, round(width * x0), round(height * y0), round(width * x1), round(height * y1), _np().array([0.85, 1.0, 0.33]))
    return result


def _draw_rect(image, x0: int, y0: int, x1: int, y1: int, color):
    image[max(0, y0) : min(image.shape[0], y0 + 2), max(0, x0) : min(image.shape[1], x1)] = color
    image[max(0, y1 - 2) : min(image.shape[0], y1), max(0, x0) : min(image.shape[1], x1)] = color
    image[max(0, y0) : min(image.shape[0], y1), max(0, x0) : min(image.shape[1], x0 + 2)] = color
    image[max(0, y0) : min(image.shape[0], y1), max(0, x1 - 2) : min(image.shape[1], x1)] = color


def _displacement(rgb, params, progress: float):
    x, y, width, height = _coords(rgb.shape)
    strength = float(params["strength"]) * width
    offset = _np().sin((x / width * float(params["frequency"]) + y / height * 3 + progress) * math.tau) * strength
    return _sample(rgb, x + offset, y + _np().cos(x / width * math.tau * 4) * strength * 0.4)


def _film(rgb, params, progress: float, mode: str):
    result = rgb
    if mode == "vintage":
        result = _dispatch(result, "gpu-sepia", {"amount": float(params["sepia"])}, progress)
    if mode == "classic":
        result = result + _np().array([float(params["warmth"]), float(params["warmth"]) * 0.45, -float(params["warmth"]) * 0.4])
    result = (result - 0.5) * float(params["contrast"]) + 0.5
    return _grain(result, float(params["grain"]), 1.2, progress)


def _sample(image, x, y):
    np = _np()
    height, width = image.shape[:2]
    return image[np.clip(y.round().astype(int), 0, height - 1), np.clip(x.round().astype(int), 0, width - 1)]


def _coords(shape):
    np = _np()
    height, width = shape[:2]
    y, x = np.mgrid[0:height, 0:width]
    return x.astype(float), y.astype(float), width, height


def _hue_shift(rgb, shift: float, span: float):
    hsv = _rgb_to_hsv(rgb)
    hsv[:, :, 0] = (hsv[:, :, 0] * span + shift) % 1
    return _hsv_to_rgb(hsv)


def _rgb_to_hsv(rgb):
    np = _np()
    maxc = rgb.max(axis=2)
    minc = rgb.min(axis=2)
    delta = maxc - minc
    hue = np.zeros_like(maxc)
    mask = delta > 1e-6
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    hue = np.where(mask & (maxc == r), ((g - b) / np.maximum(delta, 1e-6)) % 6, hue)
    hue = np.where(mask & (maxc == g), ((b - r) / np.maximum(delta, 1e-6)) + 2, hue)
    hue = np.where(mask & (maxc == b), ((r - g) / np.maximum(delta, 1e-6)) + 4, hue)
    saturation = np.where(maxc > 1e-6, delta / np.maximum(maxc, 1e-6), 0)
    return np.stack([hue / 6, saturation, maxc], axis=2)


def _hsv_to_rgb(hsv):
    np = _np()
    h = hsv[:, :, 0] * 6
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    c = v * s
    x = c * (1 - np.abs(h % 2 - 1))
    m = v - c
    z = np.zeros_like(h)
    rgb = np.zeros_like(hsv)
    rgb[(0 <= h) & (h < 1)] = np.stack([c, x, z], 2)[(0 <= h) & (h < 1)]
    rgb[(1 <= h) & (h < 2)] = np.stack([x, c, z], 2)[(1 <= h) & (h < 2)]
    rgb[(2 <= h) & (h < 3)] = np.stack([z, c, x], 2)[(2 <= h) & (h < 3)]
    rgb[(3 <= h) & (h < 4)] = np.stack([z, x, c], 2)[(3 <= h) & (h < 4)]
    rgb[(4 <= h) & (h < 5)] = np.stack([x, z, c], 2)[(4 <= h) & (h < 5)]
    rgb[(5 <= h) & (h < 6)] = np.stack([c, z, x], 2)[(5 <= h) & (h < 6)]
    return rgb + m[:, :, None]


def _curves(rgb, params):
    gamma = float(params.get("gamma", 1))
    shadow = float(params.get("shadowY", 0.12))
    highlight = float(params.get("highlightY", 0.92))
    return (rgb ** (1 / max(gamma, 0.05))) * (highlight - shadow) + shadow


def _color_wheels(rgb, params):
    luma = _luma(rgb)
    shadow_mask = 1 - luma
    high_mask = luma
    result = rgb + shadow_mask * float(params.get("shadows", 0)) / 100 - high_mask * float(params.get("highlights", 0)) / 100
    result = _saturate(result, 1 + float(params.get("saturation", 0)) / 100)
    return (result - 0.5) * float(params.get("contrast", 1)) + 0.5


def _secondary_qualifier(rgb, params):
    hsv = _rgb_to_hsv(rgb)
    center = float(params["hueCenter"]) / 360
    width = float(params["hueWidth"]) / 360
    distance = _np().minimum(abs(hsv[:, :, 0:1] - center), 1 - abs(hsv[:, :, 0:1] - center))
    mask = _np().clip(1 - distance / max(width, 0.001), 0, 1) * float(params["strength"])
    corrected = _saturate(rgb, 1 + float(params["saturation"]) / 100)
    return _mix(rgb, corrected, mask)


def _power_window(rgb, params):
    x, y, width, height = _coords(rgb.shape)
    cx = float(params["centerX"]) * width
    cy = float(params["centerY"]) * height
    sx = max(1, float(params["sizeX"]) * width)
    sy = max(1, float(params["sizeY"]) * height)
    distance = ((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2
    mask = _np().clip((1 - distance) / max(float(params["feather"]), 0.001), 0, 1)[:, :, None] * float(params["strength"])
    return _mix(rgb, rgb * (2 ** float(params["exposure"])), mask)


def _gradient_map(rgb, amount: float):
    y = _luma(rgb)
    cool = _np().array([0.05, 0.12, 0.22])
    warm = _np().array([1.0, 0.82, 0.45])
    return _mix(rgb, cool * (1 - y) + warm * y, amount)


def _box_blur(rgb, radius: int):
    result = _np().zeros_like(rgb)
    count = 0
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            result += _np().roll(_np().roll(rgb, y, axis=0), x, axis=1)
            count += 1
    return result / count


def _motion_blur(rgb, amount: int, angle: float, samples: int):
    result = _np().zeros_like(rgb)
    for index in range(samples):
        offset = (index / max(samples - 1, 1) - 0.5) * amount
        result += _np().roll(_np().roll(rgb, round(math.sin(angle) * offset), axis=0), round(math.cos(angle) * offset), axis=1)
    return result / samples


def _radial_blur(rgb, amount: float, center_x: float, center_y: float, samples: int):
    x, y, width, height = _coords(rgb.shape)
    cx = center_x * width
    cy = center_y * height
    result = _np().zeros_like(rgb)
    for index in range(samples):
        t = index / max(samples - 1, 1) * amount * 0.2
        result += _sample(rgb, x + (cx - x) * t, y + (cy - y) * t)
    return result / samples


def _zoom_blur(rgb, amount: float, center_x: float, center_y: float, samples: int):
    x, y, width, height = _coords(rgb.shape)
    cx = center_x * width
    cy = center_y * height
    result = _np().zeros_like(rgb)
    for index in range(samples):
        scale = 1 + amount * index / max(samples - 1, 1) * 0.5
        result += _sample(rgb, (x - cx) / scale + cx, (y - cy) / scale + cy)
    return result / samples


def _pixelate(rgb, pixel_size: int):
    np = _np()
    height, width = rgb.shape[:2]
    y = (np.arange(height) // max(1, pixel_size) * max(1, pixel_size)).clip(0, height - 1)
    x = (np.arange(width) // max(1, pixel_size) * max(1, pixel_size)).clip(0, width - 1)
    return rgb[y[:, None], x[None, :]]


def _rgb_split(rgb, amount: float, angle: float):
    offset = max(1, round(amount * rgb.shape[1]))
    dx = round(math.cos(angle) * offset)
    dy = round(math.sin(angle) * offset)
    return _np().stack([
        _np().roll(_np().roll(rgb[:, :, 0], dy, axis=0), dx, axis=1),
        rgb[:, :, 1],
        _np().roll(_np().roll(rgb[:, :, 2], -dy, axis=0), -dx, axis=1),
    ], axis=2)


def _twirl(rgb, params):
    x, y, width, height = _coords(rgb.shape)
    cx = float(params["centerX"]) * width
    cy = float(params["centerY"]) * height
    radius = float(params["radius"]) * min(width, height)
    dx = x - cx
    dy = y - cy
    dist = _np().sqrt(dx * dx + dy * dy)
    factor = _np().clip((radius - dist) / max(radius, 1), 0, 1) ** 2
    angle = _np().arctan2(dy, dx) + float(params["amount"]) * factor
    return _sample(rgb, cx + _np().cos(angle) * dist, cy + _np().sin(angle) * dist)


def _wave(rgb, params, progress: float):
    x, y, width, height = _coords(rgb.shape)
    sx = _np().sin(x / width * float(params["frequencyX"]) * math.tau + progress * math.tau) * float(params["amplitudeX"]) * width
    sy = _np().sin(y / height * float(params["frequencyY"]) * math.tau + progress * math.tau) * float(params["amplitudeY"]) * height
    return _sample(rgb, x + sx, y + sy)


def _trigger_wave(rgb, params, progress: float):
    x, y, width, height = _coords(rgb.shape)
    cx = float(params.get("centerX", 0.5)) * width
    cy = float(params.get("centerY", 0.5)) * height
    dist = _np().sqrt(((x - cx) / width) ** 2 + ((y - cy) / height) ** 2)
    phase = progress * float(params.get("speed", 1)) + float(params.get("phase", 0))
    wave = _np().sin((dist * float(params["frequency"]) - phase) * math.tau) * _np().exp(-dist / max(float(params["decay"]), 0.001))
    offset = wave * float(params["strength"]) * min(width, height)
    result = _sample(rgb, x + offset, y + offset)
    return _rgb_split(result, float(params.get("chroma", 0)), 0)


def _bulge(rgb, params):
    x, y, width, height = _coords(rgb.shape)
    cx = float(params["centerX"]) * width
    cy = float(params["centerY"]) * height
    radius = float(params["radius"]) * min(width, height)
    dx = x - cx
    dy = y - cy
    dist = _np().sqrt(dx * dx + dy * dy)
    factor = _np().where(dist < radius, (dist / max(radius, 1)) ** float(params["amount"]), 1)
    return _sample(rgb, cx + dx * factor, cy + dy * factor)


def _kaleidoscope(rgb, segments: int, rotation: float):
    x, y, width, height = _coords(rgb.shape)
    dx = x - width / 2
    dy = y - height / 2
    angle = (_np().arctan2(dy, dx) + rotation) % (math.tau / max(1, segments))
    angle = abs(angle - math.pi / max(1, segments))
    dist = _np().sqrt(dx * dx + dy * dy)
    return _sample(rgb, width / 2 + _np().cos(angle) * dist, height / 2 + _np().sin(angle) * dist)


def _mirror(rgb, horizontal: bool, vertical: bool):
    result = rgb.copy()
    if horizontal:
        result[:, result.shape[1] // 2 :] = result[:, result.shape[1] // 2 :: -1][:, : result.shape[1] - result.shape[1] // 2]
    if vertical:
        result[result.shape[0] // 2 :, :] = result[result.shape[0] // 2 :: -1, :][: result.shape[0] - result.shape[0] // 2]
    return result


def _fluted_glass(rgb, params, progress: float):
    x, y, width, height = _coords(rgb.shape)
    angle = math.radians(float(params["angle"]))
    coord = x * math.cos(angle) + y * math.sin(angle)
    offset = _np().sin(coord / max(float(params["size"]) * 40, 1) + progress * math.tau) * float(params["distortion"]) * 24
    sampled = _sample(rgb, x + offset * math.cos(angle), y + offset * math.sin(angle))
    return _mix(sampled, _box_blur(sampled, max(1, round(float(params["blur"]) * 6))), float(params["blur"]))


def _blocks(rgb, params):
    pixelated = _pixelate(rgb, int(float(params["blockSize"])))
    depth = float(params["depth"])
    y, x = _np().indices(rgb.shape[:2])
    shade = ((x % max(1, int(float(params["blockSize"])))) + (y % max(1, int(float(params["blockSize"]))))) / max(1, int(float(params["blockSize"])) * 2)
    return _np().clip(pixelated + (shade[:, :, None] - 0.5) * depth, 0, 1)


def _droste(rgb, params, progress: float):
    x, y, width, height = _coords(rgb.shape)
    cx = float(params["centerX"]) * width
    cy = float(params["centerY"]) * height
    dx = x - cx
    dy = y - cy
    dist = _np().sqrt(dx * dx + dy * dy)
    angle = _np().arctan2(dy, dx) + float(params["spin"]) + progress * float(params["strength"])
    scale = max(float(params["scale"]), 1.001)
    folded = _np().mod(_np().log(_np().maximum(dist, 1)) / math.log(scale), 1)
    new_dist = folded * min(width, height) * 0.5
    return _sample(rgb, cx + _np().cos(angle) * new_dist, cy + _np().sin(angle) * new_dist)


def _vignette(rgb, params):
    x, y, width, height = _coords(rgb.shape)
    dx = (x / width - 0.5) * 2
    dy = (y / height - 0.5) * 2 / max(float(params["roundness"]), 0.1)
    dist = _np().sqrt(dx * dx + dy * dy)
    vig = 1 - _np().clip((dist - float(params["size"])) / max(float(params["softness"]), 0.001), 0, 1) * float(params["amount"])
    return rgb * vig[:, :, None]


def _grain(rgb, amount: float, size: float, progress: float):
    rng = _np().random.default_rng(round(progress * 10000) + round(size * 100))
    noise = rng.normal(0, amount, rgb.shape[:2])[:, :, None]
    return rgb + noise * (1 - _luma(rgb) * 0.5)


def _sharpen(rgb, amount: float, radius: int):
    blur = _box_blur(rgb, radius)
    return rgb + (rgb - blur) * amount


def _glow(rgb, params):
    bright = rgb * (_luma(rgb) > float(params["threshold"]))
    return rgb + _box_blur(bright, max(1, round(float(params["radius"]) / 4))) * float(params["amount"]) * 2


def _edge_detect(rgb, strength: float, invert: bool):
    gray = _luma(rgb)[:, :, 0]
    gx = abs(_np().roll(gray, 1, axis=1) - _np().roll(gray, -1, axis=1))
    gy = abs(_np().roll(gray, 1, axis=0) - _np().roll(gray, -1, axis=0))
    edge = _np().clip((gx + gy) * strength * 4, 0, 1)
    if invert:
        edge = 1 - edge
    return _np().repeat(edge[:, :, None], 3, axis=2)


def _scanlines(rgb, params, progress: float):
    y = _np().arange(rgb.shape[0])[:, None]
    scan = 1 - float(params["opacity"]) * (1 - (_np().sin((y / rgb.shape[0] + progress * float(params["speed"]) * 0.1) * float(params["density"]) * 100) * 0.5 + 0.5))
    return rgb * scan[:, :, None]


def _color_glitch(rgb, params, progress: float):
    result = _rgb_split(rgb, float(params["intensity"]) * 0.02, progress * math.tau)
    return _block_offsets(result, float(params["intensity"]), round(float(params["speed"]) * progress * 1000))


def _block_glitch(rgb, params, progress: float):
    return _block_offsets(_pixelate(rgb, int(float(params["blockSize"]))), float(params["intensity"]) * float(params["coverage"]), round(progress * float(params["speed"]) * 1000))


def _block_offsets(rgb, intensity: float, seed: int):
    rng = _np().random.default_rng(seed)
    result = rgb.copy()
    height = rgb.shape[0]
    for _ in range(max(1, round(40 * intensity))):
        band_height = rng.integers(2, max(3, height // 12))
        y = rng.integers(0, max(1, height - band_height))
        offset = rng.integers(-round(70 * intensity) - 1, round(70 * intensity) + 2)
        result[y : y + band_height] = _np().roll(result[y : y + band_height], offset, axis=1)
    return result


def _crt(rgb, params, progress: float):
    result = _rgb_split(rgb, float(params["chroma"]) * 0.012, 0)
    result = _scanlines(result, {"density": 8, "opacity": float(params["scanlines"]) * 0.5, "speed": 1}, progress)
    return _vignette(result, {"amount": float(params["vignette"]), "size": 0.35, "softness": 1.15, "roundness": 1.0})


def _halftone(rgb, params):
    gray = _luma(rgb)
    cell = max(2, round(float(params["size"]) * 24))
    y, x = _np().indices(rgb.shape[:2])
    dot = ((x % cell - cell / 2) ** 2 + (y % cell - cell / 2) ** 2) < (gray[:, :, 0] * cell * float(params["radius"])) ** 2
    result = _np().repeat(dot[:, :, None], 3, axis=2).astype(float)
    if bool(params["inverted"]):
        result = 1 - result
    return _mix(result, rgb, 1 if bool(params["originalColors"]) else 0)


def _dither(rgb, cell_size: int):
    gray = _luma(rgb)[:, :, 0]
    matrix = _np().array([[0, 2], [3, 1]]) / 4
    y, x = _np().indices(gray.shape)
    threshold = matrix[y % 2, x % 2]
    return _np().repeat((gray > threshold)[:, :, None], 3, axis=2).astype(float)


def _threshold(rgb, threshold: float, softness: float, invert: bool):
    gray = _luma(rgb)
    matte = _np().clip((gray - threshold + softness) / max(softness * 2, 0.001), 0, 1)
    if invert:
        matte = 1 - matte
    return _np().repeat(matte, 3, axis=2)


def _ascii(rgb, cell_size: int, contrast: float, amount: float):
    gray = _luma(rgb)
    levels = _np().floor(_pixelate(gray, cell_size) * 8) / 7
    return _mix(rgb, _np().repeat(_np().clip((levels - 0.5) * contrast + 0.5, 0, 1), 3, axis=2), amount)


def _vhs(rgb, params, progress: float):
    height = rgb.shape[0]
    y = _np().arange(height)[:, None]
    waviness = _np().sin(y / 18 + progress * math.tau * float(params["speed"])) * float(params["waviness"]) * 10
    result = _np().empty_like(rgb)
    for row in range(height):
        result[row] = _np().roll(rgb[row], round(waviness[row, 0]), axis=0)
    result = _rgb_split(result, float(params["bleed"]) * 0.01, 0)
    result = _grain(result, float(params["noise"]) * 0.12, 1.2, progress)
    return _scanlines(result, {"density": 7, "opacity": float(params["scanline"]), "speed": float(params["speed"])}, progress)


def _chroma_key(rgb, params):
    key = _np().array([0.0, 1.0, 0.0]) if params["keyColor"] == "green" else _np().array([0.0, 0.0, 1.0])
    dist = _np().sqrt(((rgb - key) ** 2).sum(axis=2, keepdims=True))
    mask = _np().clip((dist - float(params["tolerance"])) / max(float(params["softness"]), 0.001), 0, 1)
    despilled = rgb.copy()
    despilled[:, :, 1:2] = _np().minimum(despilled[:, :, 1:2], _np().maximum(despilled[:, :, 0:1], despilled[:, :, 2:3]) + (1 - float(params["spillSuppression"])) * 0.25)
    return _mix(despilled, rgb, mask)


def _saturate(rgb, amount: float):
    gray = _luma(rgb)
    return gray + (rgb - gray) * amount


def _luma(rgb):
    return (rgb[:, :, 0:1] * 0.2126) + (rgb[:, :, 1:2] * 0.7152) + (rgb[:, :, 2:3] * 0.0722)


def _mix(left, right, amount):
    return left * (1 - amount) + right * amount


def _as_float(array):
    if array.dtype.kind == "f" and array.max(initial=0) <= 1:
        return array.astype(float)
    return array.astype(float) / 255


def _finish(array):
    return (_np().clip(array, 0, 1) * 255).round().astype("uint8")


def _np():
    return require_numpy()
