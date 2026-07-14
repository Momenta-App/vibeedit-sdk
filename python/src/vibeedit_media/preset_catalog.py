"""Python-backed filters, effects, and transitions preset catalog."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from vibeedit_media.freecut_effects import apply_freecut_effect
from vibeedit_media.freecut_effects import apply_freecut_preset
from vibeedit_media.images import ImageInput
from vibeedit_media.images import to_numpy_image
from vibeedit_media.optional import require_numpy


Preset = dict[str, Any]
STYLE_TINTS = {
    "teal-orange": (0.08, 0.01, -0.08),
    "bleach-bypass": (0.03, 0.03, 0.02),
    "kodak-print": (0.10, 0.04, -0.02),
    "fuji-cool": (-0.02, 0.05, 0.08),
    "arri-neutral": (0.01, 0.01, 0.01),
    "rec709-pop": (0.03, 0.02, 0.02),
    "neo-noir": (-0.02, -0.04, 0.08),
    "pastel-ad": (0.08, 0.05, 0.04),
    "golden-hour": (0.14, 0.06, -0.05),
    "moonlight": (-0.08, -0.02, 0.14),
    "cross-process": (0.10, -0.04, 0.10),
    "infrared": (0.18, -0.08, 0.08),
    "polaroid": (0.09, 0.05, 0.00),
    "vhs-clean": (0.03, -0.02, 0.08),
    "newsprint": (0.02, 0.02, -0.01),
    "cyanotype": (-0.10, -0.02, 0.18),
    "sepia-fiber": (0.15, 0.08, -0.08),
    "high-key": (0.05, 0.04, 0.03),
    "low-key": (-0.03, -0.02, 0.01),
    "chrome-slide": (0.05, 0.04, 0.09),
    "micro-jitter": (0.01, 0.01, 0.01),
    "impact-punch": (0.12, 0.08, 0.03),
    "rgb-split": (0.12, -0.04, 0.12),
    "scanline-tear": (-0.02, 0.02, 0.08),
    "datamosh-lite": (0.00, 0.08, 0.10),
    "film-dust": (0.08, 0.06, 0.02),
    "bloom-pulse": (0.14, 0.10, 0.05),
    "speed-lines": (0.03, 0.06, 0.12),
    "echo-trail": (0.04, 0.02, 0.10),
    "freeze-flash": (0.18, 0.18, 0.16),
    "lens-pulse": (0.08, 0.04, 0.10),
    "prism-warp": (0.14, -0.02, 0.16),
    "paper-rip": (0.12, 0.08, 0.02),
    "subject-glow": (0.10, 0.08, 0.03),
    "silhouette-pop": (-0.08, -0.06, -0.04),
    "halftone-burst": (0.12, 0.02, 0.06),
    "heat-haze": (0.16, 0.05, -0.04),
    "liquid-smear": (0.02, 0.08, 0.12),
    "time-echo-bars": (0.12, 0.04, 0.03),
    "ui-callout": (0.02, 0.05, 0.08),
    "cross-dissolve": (0.00, 0.00, 0.00),
    "dip-to-black": (-0.06, -0.06, -0.06),
    "dip-to-white": (0.16, 0.16, 0.16),
    "push-left": (0.03, 0.04, 0.08),
    "push-right": (0.03, 0.04, 0.08),
    "push-up": (0.02, 0.07, 0.05),
    "push-down": (0.02, 0.07, 0.05),
    "whip-pan": (0.06, 0.06, 0.10),
    "zoom-through": (0.08, 0.06, 0.04),
    "spin-match": (0.06, 0.02, 0.10),
    "luma-wipe": (0.05, 0.05, 0.05),
    "ink-spread": (-0.02, -0.01, 0.08),
    "radial-iris": (0.03, 0.02, 0.01),
    "venetian": (0.04, 0.04, 0.04),
    "pixel-sort": (0.00, 0.08, 0.12),
    "block-glitch": (0.10, -0.02, 0.12),
    "film-burn": (0.20, 0.09, -0.05),
    "gate-jump": (0.08, 0.06, 0.00),
    "paper-tear": (0.12, 0.08, 0.02),
    "light-sweep": (0.16, 0.12, 0.04),
    "vintage-film": (0.14, 0.07, -0.04),
    "damaged-reel": (0.10, 0.06, 0.00),
    "vhs-film": (0.03, -0.02, 0.08),
    "beat-freeze": (0.16, 0.14, 0.10),
    "match-flash": (0.20, 0.20, 0.18),
}


def load_catalog() -> dict[str, Any]:
    return json.loads(files("vibeedit_media").joinpath("preset_catalog.json").read_text(encoding="utf-8"))


def list_presets(kind: str | None = None) -> list[Preset]:
    presets = load_catalog()["presets"]
    if kind is None:
        return presets
    if kind not in {"filters", "effects", "transitions"}:
        raise ValueError("kind must be one of: filters, effects, transitions")
    return [preset for preset in presets if preset["kind"] == kind]


def get_preset(preset_id: str) -> Preset:
    for preset in load_catalog()["presets"]:
        if preset["id"] == preset_id:
            return preset
    raise KeyError(f"Unknown preset '{preset_id}'")


def build_agent_plan(preset_id: str, *, parameter_overrides: dict[str, float | int] | None = None) -> dict[str, Any]:
    preset = get_preset(preset_id)
    settings = _settings_for_preset(preset, parameter_overrides)
    return {
        "presetId": preset["id"],
        "kind": preset["kind"],
        "title": preset["title"],
        "settings": settings,
        "engine": preset["engine"],
        "recipe": preset["recipe"],
        "deterministicFlow": preset["deterministicFlow"],
        "agentFlow": preset["agentFlow"],
    }


def apply_preset_to_image(
    image: ImageInput,
    preset_id: str,
    *,
    parameter_overrides: dict[str, float | int] | None = None,
    progress: float = 0.5,
):
    """Apply a filter/effect preset to one RGBA image/frame.

    The implementation is deterministic and only accepts catalog-exposed
    settings. Agents can use the same preset id/settings to reproduce renders.
    """

    preset = get_preset(preset_id)
    if preset["kind"] not in {"filters", "effects"}:
        raise ValueError("apply_preset_to_image only supports filter and effect presets")
    return _apply_frame_operation(
        to_numpy_image(image, "RGBA"),
        preset["recipe"]["operation"],
        preset["recipe"]["style"],
        _settings_for_preset(preset, parameter_overrides),
        _clamp(progress),
    )


def render_transition_frame(
    from_image: ImageInput,
    to_image: ImageInput,
    preset_id: str,
    *,
    parameter_overrides: dict[str, float | int] | None = None,
    progress: float,
):
    """Render one deterministic transition frame between two images."""

    preset = get_preset(preset_id)
    if preset["kind"] != "transitions":
        raise ValueError("render_transition_frame only supports transition presets")
    left = to_numpy_image(from_image, "RGBA")
    right = _match_shape(to_numpy_image(to_image, "RGBA"), left)
    result = _apply_transition_operation(
        left,
        right,
        preset["recipe"]["operation"],
        preset["recipe"]["style"],
        _settings_for_preset(preset, parameter_overrides),
        _clamp(progress),
    )
    if result.dtype == _np().uint8:
        return result
    return _finish(result)


def _settings_for_preset(preset: Preset, parameter_overrides: dict[str, float | int] | None = None):
    metadata = {parameter["id"]: parameter for parameter in preset["parameters"]}
    overrides = parameter_overrides or {}
    unknown = sorted(set(overrides) - set(metadata))
    if unknown:
        raise ValueError(f"Unsupported parameter overrides for {preset['id']}: {', '.join(unknown)}")
    settings = {**preset["defaultSettings"], **overrides}
    out_of_range = [
        name
        for name, value in settings.items()
        if name in metadata and not metadata[name]["min"] <= value <= metadata[name]["max"]
    ]
    if out_of_range:
        raise ValueError(f"Parameter overrides out of range for {preset['id']}: {', '.join(sorted(out_of_range))}")
    return settings


def _apply_frame_operation(image, operation: str, style: str, settings: dict[str, float | int], progress: float):
    operations = {
        "color_grade": _color_grade,
        "tone_curve": _tone_curve,
        "film_emulation": _film_emulation,
        "broadcast_legalize": _broadcast_legalize,
        "natural_balance": _natural_balance,
        "split_tone": _split_tone,
        "analog_decay": _analog_decay,
        "skin_tone_protect": _skin_tone_protect,
        "scientific_enhance": _scientific_enhance,
        "monochrome_grade": _monochrome_grade,
        "motion_compensate": _motion_compensate,
        "camera_shake": _camera_shake,
        "digital_glitch": _digital_glitch,
        "light_sweep": _light_sweep,
        "directional_blur": _directional_blur,
        "mask_composite": _mask_composite,
        "focus_composite": _mask_composite,
        "texture_overlay": _texture_overlay,
        "temporal_sample": _temporal_sample,
        "warp": _warp,
        "text_composite": _text_composite,
        "slam_bar": _slam_bar,
        "freecut_effect": _freecut_effect,
        "freecut_preset": _freecut_preset,
    }
    if operation not in operations:
        raise ValueError(f"Unsupported preset operation '{operation}'")
    return operations[operation](image, style, settings, progress)


def _apply_transition_operation(left, right, operation: str, style: str, settings: dict[str, float | int], progress: float):
    operations = {
        "composite_transition": _composite_transition,
        "motion_transition": _motion_transition,
        "mask_transition": _mask_transition,
        "light_transition": _light_transition,
        "film_transition": _film_transition,
        "digital_transition": _digital_transition,
        "camera_transition": _camera_transition,
        "shape_wipe": _shape_wipe,
        "texture_transition": _texture_transition,
        "beat_transition": _beat_transition,
    }
    if operation not in operations:
        raise ValueError(f"Unsupported transition operation '{operation}'")
    return operations[operation](left, right, style, settings, progress)


def _color_grade(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    tint = _style_tint(style)
    contrast = float(settings.get("contrast", 1))
    warmth = float(settings.get("warmth", 0))
    intensity = float(settings.get("intensity", 1))
    graded = ((rgb - 0.5) * contrast) + 0.5
    graded = graded + tint * intensity * 0.18 + _np().array([warmth * 0.08, warmth * 0.02, -warmth * 0.06])
    return _merge_rgba(_mix(rgb, graded, intensity), alpha)


def _tone_curve(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    contrast = float(settings.get("contrast", 1))
    intensity = float(settings.get("intensity", 1))
    grain = float(settings.get("grain", 0))
    curved = rgb ** (1.0 / max(0.2, contrast))
    curved = _add_grain(curved, grain * intensity, style)
    return _merge_rgba(_mix(rgb, curved, intensity), alpha)


def _film_emulation(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    intensity = float(settings.get("intensity", 1))
    grain = float(settings.get("grain", 0))
    halation = float(settings.get("halation", 0))
    bloom = _soft_light(rgb, radius=3)
    film = _add_grain(rgb + bloom * halation * 0.28 + _style_tint(style) * 0.12, grain, style)
    return _merge_rgba(_mix(rgb, film, intensity), alpha)


def _broadcast_legalize(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    saturation = float(settings.get("saturation", 1))
    contrast = float(settings.get("contrast", 1))
    intensity = float(settings.get("intensity", 1))
    gray = _luma(rgb)
    legal = _mix(gray, rgb, saturation)
    legal = _np().clip(((legal - 0.5) * contrast) + 0.5, 16 / 255, 235 / 255)
    return _merge_rgba(_mix(rgb, legal, intensity), alpha)


def _natural_balance(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    warmth = float(settings.get("warmth", 0))
    clarity = float(settings.get("clarity", 0))
    balanced = rgb + _np().array([warmth * 0.06, warmth * 0.02, -warmth * 0.04])
    balanced = _unsharp(balanced, clarity)
    return _merge_rgba(_mix(rgb, balanced, float(settings.get("intensity", 1))), alpha)


def _split_tone(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    hue_shift = float(settings.get("hue_shift", 0)) / 180
    shadow_tint = _style_tint(style)
    highlight_tint = _np().roll(shadow_tint, 1) + hue_shift * 0.08
    luma = _luma(rgb)
    toned = rgb + (1 - luma) * shadow_tint * 0.18 + luma * highlight_tint * 0.14
    toned = ((toned - 0.5) * float(settings.get("contrast", 1))) + 0.5
    return _merge_rgba(_mix(rgb, toned, float(settings.get("intensity", 1))), alpha)


def _analog_decay(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    faded = _mix(rgb, _np().full_like(rgb, 0.5), float(settings.get("fade", 0)) * 0.35)
    faded = _channel_shift(faded, int(2 + 8 * float(settings.get("intensity", 1))))
    faded = _add_grain(faded, float(settings.get("grain", 0)), style)
    return _merge_rgba(faded, alpha)


def _skin_tone_protect(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    warmed = rgb + _np().array([float(settings.get("warmth", 0)) * 0.07, 0.015, -0.025])
    softened = _mix(warmed, _soft_light(warmed, radius=2), float(settings.get("softness", 0)) * 0.45)
    return _merge_rgba(_mix(rgb, softened, float(settings.get("intensity", 1))), alpha)


def _scientific_enhance(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    gray = _luma(rgb)
    edges = _np().abs(_np().roll(gray, 1, 0) - gray) + _np().abs(_np().roll(gray, 1, 1) - gray)
    enhanced = _np().repeat(_np().clip(gray + edges * float(settings.get("detail", 0)) * 4, 0, 1), 3, axis=2)
    mask = (gray > float(settings.get("threshold", 0.5))).astype(float)
    enhanced = _mix(enhanced, rgb, mask * 0.35)
    return _merge_rgba(_mix(rgb, enhanced, float(settings.get("intensity", 1))), alpha)


def _monochrome_grade(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    gray = _np().repeat(_luma(rgb), 3, axis=2)
    gray = ((gray - 0.5) * float(settings.get("contrast", 1))) + 0.5 + _style_tint(style) * 0.08
    gray = _add_grain(gray, float(settings.get("grain", 0)), style)
    return _merge_rgba(_mix(rgb, gray, float(settings.get("intensity", 1))), alpha)


def _motion_compensate(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    shift = round((progress - 0.5) * float(settings.get("smoothness", 0.5)) * 12)
    stabilized = _np().roll(rgb, shift, axis=1)
    return _merge_rgba(_mix(rgb, stabilized, float(settings.get("strength", 0.5))), alpha)


def _camera_shake(image, style: str, settings: dict[str, float | int], progress: float):
    strength = float(settings.get("strength", 0.5)) * (1 - progress * float(settings.get("decay", 0.5)))
    frequency = float(settings.get("frequency", 4))
    offset = round(_np().sin(progress * frequency * _np().pi * 2) * strength * 34)
    zoom = 1 + max(0.05, strength * 0.18)
    return _translate_frame(_zoom_frame(image, zoom), offset, -offset // 2)


def _digital_glitch(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    strength = float(settings.get("strength", 0.5))
    glitched = _channel_shift(rgb, round(18 * float(settings.get("chromatic", 0.2)) * strength))
    frequency = float(settings.get("frequency", 4))
    rows = max(2, round(glitched.shape[0] / (12 + frequency * 2.6)))
    seed = round(progress * 997 + frequency * 31 + strength * 101)
    rng = _np().random.default_rng(seed)
    for row in range(0, glitched.shape[0], rows * 2):
        amount = round(strength * rng.integers(-34, 35))
        glitched[row : row + rows] = _np().roll(glitched[row : row + rows], amount, axis=1)
    return _merge_rgba(glitched, alpha)


def _light_sweep(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    height, width = rgb.shape[:2]
    angle = _np().deg2rad(float(settings.get("angle", 0)))
    yy, xx = _np().mgrid[0:height, 0:width]
    coord = (xx / max(1, width - 1) - 0.5) * _np().cos(angle) + (yy / max(1, height - 1) - 0.5) * _np().sin(angle)
    speed = float(settings.get("speed", 1.8))
    width_setting = max(0.01, float(settings.get("width", 0.08)))
    center = (progress * speed % 1) - 0.5
    shimmer = _np().clip(1 - _np().abs(coord[:, :, None] - center) / width_setting, 0, 1) ** 2
    tint = 0.55 + _style_tint(style)
    screened = 1 - (1 - rgb) * (1 - shimmer * float(settings.get("intensity", 0.65)) * tint)
    return _merge_rgba(_mix(rgb, screened, 0.85), alpha)


def _directional_blur(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    radius = max(1, round(float(settings.get("radius", 5))))
    axis = 0 if 45 < float(settings.get("angle", 0)) % 180 < 135 else 1
    blurred = sum(_np().roll(rgb, offset, axis=axis) for offset in range(-radius, radius + 1)) / (radius * 2 + 1)
    return _merge_rgba(_mix(rgb, blurred, float(settings.get("mix", 0.72))), alpha)


def _mask_composite(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    mask = _radial_mask(rgb.shape[0], rgb.shape[1], float(settings.get("feather", 0.16)))
    matte = _mix(rgb * 0.35, rgb + _style_tint(style) * 0.18, mask)
    return _merge_rgba(_mix(rgb, matte, float(settings.get("opacity", 0.68))), alpha)


def _texture_overlay(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    if style == "film-dust":
        return _film_dust_overlay(rgb, alpha, settings, progress)
    if style in {"vintage-film", "damaged-reel", "vhs-film"}:
        return _film_stock_overlay(rgb, alpha, style, settings, progress)
    texture = _deterministic_noise(rgb.shape[:2], style)
    scaled = _np().repeat(texture[:, :, None], 3, axis=2)
    overlaid = _mix(rgb, _np().clip(rgb + (scaled - 0.5) * float(settings.get("intensity", 0.65)), 0, 1), float(settings.get("opacity", 0.68)))
    return _merge_rgba(overlaid, alpha)


def _film_dust_overlay(rgb, alpha, settings: dict[str, float | int], progress: float):
    np = _np()
    height, width = rgb.shape[:2]
    intensity = float(settings.get("intensity", 0.65))
    opacity = float(settings.get("opacity", 0.68))
    noise = _deterministic_noise((height, width), f"film-dust-{round(progress * 24)}")
    specks = (noise > 1 - intensity * 0.035).astype(float)[:, :, None]
    dark_pits = (noise < intensity * 0.018).astype(float)[:, :, None]
    scratch_seed = _deterministic_noise((1, width), f"film-scratch-{round(progress * 12)}")[0]
    scratches = np.zeros((height, width, 1), dtype=float)
    for x in np.where(scratch_seed > 1 - intensity * 0.018)[0]:
        scratches[:, max(0, x - 1) : min(width, x + 2)] = 1
    damaged = np.clip(rgb + specks * 0.85 - dark_pits * 0.55 + scratches * 0.28, 0, 1)
    return _merge_rgba(_mix(rgb, damaged, opacity), alpha)


def _film_stock_overlay(rgb, alpha, style: str, settings: dict[str, float | int], progress: float):
    np = _np()
    intensity = float(settings.get("intensity", 0.65))
    opacity = float(settings.get("opacity", 0.68))
    grain = _deterministic_noise(rgb.shape[:2], f"{style}-grain-{round(progress * 24)}")[:, :, None] - 0.5
    if style == "vhs-film":
        scan = 1 - 0.18 * (np.sin(np.arange(rgb.shape[0])[:, None] * 1.7 + progress * 18) * 0.5 + 0.5)
        treated = _channel_shift(rgb, max(2, round(intensity * 9)))
        treated = treated * scan[:, :, None] + grain * intensity * 0.24
        treated += np.array([0.02, -0.01, 0.05])
        return _merge_rgba(_mix(rgb, np.clip(treated, 0, 1), opacity), alpha)
    if style == "damaged-reel":
        flicker = 0.88 + 0.18 * np.sin(progress * np.pi * 18)
        treated = rgb * flicker + grain * intensity * 0.34
        scratches = _deterministic_noise(rgb.shape[:2], f"{style}-scratches-{round(progress * 12)}")
        treated = np.where(scratches[:, :, None] > 1 - intensity * 0.018, 1.0, treated)
        return _merge_rgba(_mix(rgb, np.clip(treated, 0, 1), opacity), alpha)
    warm = rgb + np.array([0.12, 0.06, -0.04]) * intensity
    faded = _mix(warm, np.full_like(rgb, 0.48), intensity * 0.18)
    treated = faded + grain * intensity * 0.18
    return _merge_rgba(_mix(rgb, np.clip(treated, 0, 1), opacity), alpha)


def _temporal_sample(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    trail = round(float(settings.get("trail", 6)))
    decay = float(settings.get("decay", 0.55))
    strength = float(settings.get("strength", 0.5))
    direction = -1 if progress < 0.5 else 1
    result = rgb * (1 - strength * 0.16)
    gap = max(3, round(3 + strength * 12))
    for offset in range(1, min(trail, 7) + 1):
        weight = strength * (decay ** (offset - 1)) * 0.34
        ghost = _translate_rgb(rgb, direction * offset * gap, round(offset * 0.45))
        tint = _np().array([0.08, 0.02, 0.16]) * (1 - offset / max(trail, 1))
        result = _np().maximum(result, ghost * weight + tint)
    return _merge_rgba(_mix(rgb, result, min(1, strength * 1.15)), alpha)


def _warp(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    strength = round(float(settings.get("strength", 0.5)) * 12)
    warped = _np().copy(rgb)
    for row in range(rgb.shape[0]):
        warped[row] = _np().roll(rgb[row], round(_np().sin(row / 18 + progress * 6) * strength), axis=0)
    if style == "prism-warp":
        warped = _channel_shift(warped, max(1, round(strength * 0.9)))
    return _merge_rgba(_mix(rgb, warped, min(1, float(settings.get("scale", 1)) / 2)), alpha)


def _text_composite(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    height, width = rgb.shape[:2]
    bar_height = max(2, round(height * 0.08 * float(settings.get("scale", 1))))
    y = min(height - bar_height, max(0, round(progress * (height - bar_height))))
    composited = _np().copy(rgb)
    composited[y : y + bar_height] = _mix(composited[y : y + bar_height], 1 - composited[y : y + bar_height], float(settings.get("intensity", 0.65)))
    return _merge_rgba(composited, alpha)


def _slam_bar(image, style: str, settings: dict[str, float | int], progress: float):
    rgb, alpha = _split_rgba(image)
    height, width = rgb.shape[:2]
    yy, xx = _np().mgrid[0:height, 0:width]
    angle = _np().deg2rad(float(settings.get("angle", 0)))
    coord = (xx / max(1, width - 1) - 0.5) * _np().cos(angle) + (yy / max(1, height - 1) - 0.5) * _np().sin(angle)
    width_setting = max(0.006, float(settings.get("width", 0.08)))
    speed = float(settings.get("speed", 1.6))
    bars = max(1, round(float(settings.get("bands", 1))))
    mask = _np().zeros((height, width, 1), dtype=float)
    for index in range(bars):
        center = ((progress * speed + index / bars) % 1) - 0.5
        mask = _np().maximum(mask, (_np().abs(coord[:, :, None] - center) < width_setting).astype(float))
    intensity = float(settings.get("intensity", 0.65))
    blend = round(float(settings.get("blend", 2)))
    if blend == 0:
        treated = _np().clip(rgb + intensity * 0.65, 0, 1)
    elif blend == 1:
        treated = 1 - (1 - rgb) * (1 - intensity)
    elif blend == 2:
        treated = _np().abs(rgb - intensity)
    else:
        treated = 1 - rgb
    return _merge_rgba(_mix(rgb, treated, mask * intensity), alpha)


def _freecut_effect(image, style: str, settings: dict[str, float | int], progress: float):
    params = {key: value for key, value in settings.items() if key != "mix"}
    rendered = apply_freecut_effect(image, style, params=params, progress=progress)
    return _finish(_mix(image, rendered, float(settings.get("mix", 1))))


def _freecut_preset(image, style: str, settings: dict[str, float | int], progress: float):
    rendered = apply_freecut_preset(image, style, progress=progress)
    return _finish(_mix(image, rendered, float(settings.get("mix", 1))))


def _composite_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _transition_by_style(left, right, style, settings, progress)


def _motion_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "motion_transition",
        style,
        settings,
        progress,
    )


def _mask_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "mask_transition",
        style,
        settings,
        progress,
    )


def _light_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "light_transition",
        style,
        settings,
        progress,
    )


def _film_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "film_transition",
        style,
        settings,
        progress,
    )


def _digital_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "digital_transition",
        style,
        settings,
        progress,
    )


def _camera_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "camera_transition",
        style,
        settings,
        progress,
    )


def _shape_wipe(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "shape_wipe",
        style,
        settings,
        progress,
    )


def _texture_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "texture_transition",
        style,
        settings,
        progress,
    )


def _beat_transition(left, right, style: str, settings: dict[str, float | int], progress: float):
    return _apply_transition_family(
        _transition_by_style(left, right, style, settings, progress),
        "beat_transition",
        style,
        settings,
        progress,
    )


def _transition_by_style(left, right, style: str, settings: dict[str, float | int], progress: float):
    if style == "dip-to-black":
        dip = _np().zeros_like(left)
        return _mix(_mix(left, dip, min(1, progress * 2)), _mix(dip, right, max(0, progress * 2 - 1)), progress)
    if style == "dip-to-white":
        dip = _np().full_like(left, 255)
        return _mix(_mix(left, dip, min(1, progress * 2)), _mix(dip, right, max(0, progress * 2 - 1)), progress)
    if style == "push-left":
        return _push_transition(left, right, progress, -1, 0)
    if style == "push-right":
        return _push_transition(left, right, progress, 1, 0)
    if style == "push-up":
        return _push_transition(left, right, progress, 0, -1)
    if style == "push-down":
        return _push_transition(left, right, progress, 0, 1)
    if style == "whip-pan":
        return _whip_transition(left, right, settings, progress)
    if style == "zoom-through":
        peak = _np().sin(progress * _np().pi)
        return _mix(_zoom_frame(left, 1 + peak * 0.42), _zoom_frame(right, 1.24 - peak * 0.24), _ease(progress, 0.78))
    if style == "spin-match":
        return _spin_match_transition(left, right, progress)
    if style == "luma-wipe":
        return _luma_transition(left, right, settings, progress)
    if style == "ink-spread":
        return _organic_reveal(left, right, settings, progress)
    if style == "radial-iris":
        return _radial_reveal(left, right, settings, progress)
    if style == "venetian":
        return _venetian_reveal(left, right, progress)
    if style == "pixel-sort":
        return _pixel_sort_reveal(left, right, progress)
    if style == "block-glitch":
        return _block_glitch_reveal(left, right, settings, progress)
    if style == "film-burn":
        return _film_burn_transition(left, right, settings, progress)
    if style == "gate-jump":
        return _gate_jump_transition(left, right, settings, progress)
    if style == "paper-tear":
        return _paper_tear_transition(left, right, settings, progress)
    if style == "light-sweep":
        return _light_sweep_transition(left, right, settings, progress)
    if style == "beat-freeze":
        return _beat_freeze_transition(left, right, settings, progress)
    if style == "match-flash":
        return _match_flash_transition(left, right, settings, progress)
    return _mix(left, right, _ease(progress, float(settings.get("ease", 0.65))))


def _apply_transition_family(base, operation: str, style: str, settings: dict[str, float | int], progress: float):
    peak = _np().sin(progress * _np().pi)
    if operation == "motion_transition":
        return _directional_blur(base, style, {"radius": 2 + float(settings.get("blur", 0.35)) * 5, "mix": peak * 0.35}, progress)
    if operation == "mask_transition":
        return _mix(base, _radial_reveal(base, base, settings, progress), 0.18 * peak)
    if operation == "light_transition":
        return _finish(_as_float(base) + peak * float(settings.get("intensity", 0.65)) * 0.28)
    if operation == "film_transition":
        jitter = round(float(settings.get("jitter", 0.22)) * 10 * _np().sin(progress * _np().pi * 4))
        return _texture_overlay(_np().roll(base, jitter, axis=0), style, {"intensity": settings.get("grain", 0.18), "opacity": 0.36}, progress)
    if operation == "digital_transition":
        return _digital_glitch(base, style, {"strength": settings.get("glitch", 0.38), "frequency": 8, "chromatic": 0.35}, progress)
    if operation == "camera_transition":
        return _zoom_frame(base, 1 + peak * max(0, float(settings.get("zoom", 1.16)) - 1))
    if operation == "shape_wipe":
        rgb, alpha = _split_rgba(base)
        return _mix(base, _merge_rgba(_unsharp(rgb, 0.4), alpha), 0.12 * peak)
    if operation == "texture_transition":
        return _texture_overlay(base, style, {"intensity": 0.42, "opacity": settings.get("opacity", 0.68)}, progress)
    if operation == "beat_transition":
        return _finish(_as_float(base) + peak * float(settings.get("impact", 0.7)) * 0.16)
    return base


def _push_transition(left, right, progress: float, direction_x: int, direction_y: int):
    height, width = left.shape[:2]
    offset_x = round(width * progress) * direction_x
    offset_y = round(height * progress) * direction_y
    return _overlay_translated(left, offset_x, offset_y, right, offset_x - (width * direction_x), offset_y - (height * direction_y))


def _whip_transition(left, right, settings: dict[str, float | int], progress: float):
    direction = 1 if int(settings.get("direction", 0)) % 2 == 0 else -1
    peak = _np().sin(progress * _np().pi)
    shifted_left = _translate_frame(left, round(-direction * progress * left.shape[1] * 0.65), 0)
    shifted_right = _translate_frame(right, round(direction * (1 - progress) * right.shape[1] * 0.65), 0)
    return _directional_blur(_mix(shifted_left, shifted_right, _ease(progress, 0.8)), "whip-pan", {"radius": 4 + peak * 10, "mix": 0.82}, progress)


def _spin_match_transition(left, right, progress: float):
    peak = _np().sin(progress * _np().pi)
    left_spun = _np().roll(_np().roll(_zoom_frame(left, 1 + peak * 0.2), round(progress * left.shape[0] * 0.18), axis=0), round(progress * left.shape[1] * 0.18), axis=1)
    right_spun = _np().roll(_np().roll(_zoom_frame(right, 1 + (1 - peak) * 0.1), round((progress - 1) * right.shape[0] * 0.18), axis=0), round((progress - 1) * right.shape[1] * 0.18), axis=1)
    return _mix(left_spun, right_spun, _ease(progress, 0.72))


def _luma_transition(left, right, settings: dict[str, float | int], progress: float):
    luma = _luma(_as_float(right[:, :, :3]))
    feather = max(0.01, float(settings.get("feather", 0.16)))
    threshold = float(settings.get("threshold", 0.48))
    mask = _np().clip((luma - (threshold + (1 - progress) - 0.5) + feather) / (feather * 2), 0, 1)
    return _mix(left, right, mask)


def _organic_reveal(left, right, settings: dict[str, float | int], progress: float):
    noise = _deterministic_noise(left.shape[:2], "ink-spread")[:, :, None]
    radial = _radial_mask(left.shape[0], left.shape[1], max(0.12, float(settings.get("feather", 0.16)) * 3))
    mask = _np().clip((progress * 1.35 + radial * 0.45 - noise) * 2.2, 0, 1)
    return _mix(left, right, mask)


def _radial_reveal(left, right, settings: dict[str, float | int], progress: float):
    feather = max(0.02, float(settings.get("feather", 0.16)))
    mask = _np().clip((_radial_mask(left.shape[0], left.shape[1], feather * 2.5) - (1 - progress)) / feather, 0, 1)
    return _mix(left, right, mask)


def _venetian_reveal(left, right, progress: float):
    x = _np().indices(left.shape[:2])[1]
    stripe = ((x % 28) / 28)[:, :, None]
    return _mix(left, right, (stripe < progress).astype(float))


def _pixel_sort_reveal(left, right, progress: float):
    luma = _luma(_as_float(right[:, :, :3]))
    order = _np().argsort(luma[:, :, 0], axis=1)
    rank = _np().argsort(order, axis=1) / max(1, right.shape[1] - 1)
    mask = (rank[:, :, None] < progress).astype(float)
    shifted = _channel_shift(_as_float(right[:, :, :3]), round(18 * _np().sin(progress * _np().pi)))
    return _mix(left, _merge_rgba(shifted, _as_float(right[:, :, 3:4])), mask)


def _block_glitch_reveal(left, right, settings: dict[str, float | int], progress: float):
    blocks = max(2, round(float(settings.get("blocks", 12))))
    mask = _block_mask(left.shape[0], left.shape[1], blocks, progress, "block-glitch")
    mixed = _mix(left, right, mask)
    return _digital_glitch(mixed, "block-glitch", {"strength": settings.get("glitch", 0.38), "frequency": 12, "chromatic": 0.45}, progress)


def _film_burn_transition(left, right, settings: dict[str, float | int], progress: float):
    base = _mix(left, right, _ease(progress, 0.65))
    height, width = left.shape[:2]
    yy, xx = _np().mgrid[0:height, 0:width]
    burn = _np().clip(1 - _np().abs((xx / max(1, width - 1)) - progress) * 4, 0, 1)[:, :, None]
    rgb, alpha = _split_rgba(base)
    treated = _np().clip(rgb + burn * _np().array([0.95, 0.38, 0.05]) + _np().sin(progress * _np().pi) * 0.18, 0, 1)
    return _merge_rgba(_mix(rgb, treated, 0.72), alpha)


def _gate_jump_transition(left, right, settings: dict[str, float | int], progress: float):
    jitter = round(float(settings.get("jitter", 0.22)) * 24 * _np().sin(progress * _np().pi * 5))
    return _mix(_np().roll(left, jitter, axis=0), _np().roll(right, -jitter, axis=0), 1 if progress > 0.48 else progress * 0.35)


def _paper_tear_transition(left, right, settings: dict[str, float | int], progress: float):
    height, width = left.shape[:2]
    noise = _deterministic_noise((height, 1), "paper-tear")[:, :, None]
    edge = (progress * width + (noise - 0.5) * width * 0.22).astype(float)
    x = _np().indices((height, width))[1][:, :, None]
    feather = max(2, float(settings.get("feather", 0.16)) * width * 0.18)
    mask = _np().clip((edge - x + feather) / (feather * 2), 0, 1)
    torn = _mix(left, right, mask)
    rgb, alpha = _split_rgba(torn)
    edge_line = _np().clip(1 - _np().abs(edge - x) / max(1, feather), 0, 1)
    return _merge_rgba(_np().clip(rgb + edge_line * 0.22, 0, 1), alpha)


def _light_sweep_transition(left, right, settings: dict[str, float | int], progress: float):
    base = _mix(left, right, _ease(progress, 0.52))
    return _light_sweep(base, "light-sweep", {"angle": settings.get("angle", 0), "width": 0.09, "speed": 1, "intensity": settings.get("intensity", 0.65)}, progress)


def _beat_freeze_transition(left, right, settings: dict[str, float | int], progress: float):
    hold = float(settings.get("hold", 0.08))
    impact = float(settings.get("impact", 0.7))
    base = left if progress < 0.5 + hold else right
    return _finish(_as_float(base) + _np().sin(progress * _np().pi) * impact * 0.34)


def _match_flash_transition(left, right, settings: dict[str, float | int], progress: float):
    flash = _np().clip(1 - abs(progress - 0.5) * 8, 0, 1)
    return _mix(_mix(left, right, 1 if progress >= 0.5 else 0), _np().full_like(left, 255), flash * float(settings.get("impact", 0.82)))


def _overlay_translated(left, left_x: int, left_y: int, right, right_x: int, right_y: int):
    canvas = _np().zeros_like(left)
    _paste_translated(canvas, left, left_x, left_y)
    _paste_translated(canvas, right, right_x, right_y)
    return canvas


def _paste_translated(canvas, image, offset_x: int, offset_y: int):
    height, width = canvas.shape[:2]
    dest_x0 = max(0, offset_x)
    dest_y0 = max(0, offset_y)
    dest_x1 = min(width, offset_x + width)
    dest_y1 = min(height, offset_y + height)
    if dest_x0 >= dest_x1 or dest_y0 >= dest_y1:
        return
    source_x0 = dest_x0 - offset_x
    source_y0 = dest_y0 - offset_y
    canvas[dest_y0:dest_y1, dest_x0:dest_x1] = image[source_y0 : source_y0 + dest_y1 - dest_y0, source_x0 : source_x0 + dest_x1 - dest_x0]


def _split_rgba(image):
    if isinstance(image, str) or hasattr(image, "__fspath__") or (hasattr(image, "convert") and hasattr(image, "save")):
        array = to_numpy_image(image, "RGBA")
    else:
        array = _np().asarray(image)
        if array.ndim == 3 and array.shape[-1] == 3:
            alpha = _np().full((*array.shape[:2], 1), 1 if array.dtype.kind == "f" else 255, dtype=array.dtype)
            array = _np().concatenate([array, alpha], axis=2)
    return _as_float(array[:, :, :3]), _as_float(array[:, :, 3:4])


def _merge_rgba(rgb, alpha):
    return _finish(_np().concatenate([_np().clip(rgb, 0, 1), _np().clip(alpha, 0, 1)], axis=2))


def _match_shape(image, target):
    if image.shape == target.shape:
        return image
    np = _np()
    height, width, channels = target.shape
    source_y = np.linspace(0, image.shape[0] - 1, height).round().astype(int)
    source_x = np.linspace(0, image.shape[1] - 1, width).round().astype(int)
    resized = image[source_y[:, None], source_x[None, :]]
    if resized.shape[2] == channels:
        return resized
    if resized.shape[2] > channels:
        return resized[:, :, :channels]
    alpha = np.full((height, width, channels - resized.shape[2]), 255, dtype=resized.dtype)
    return np.concatenate([resized, alpha], axis=2)


def _style_tint(style: str):
    if style in STYLE_TINTS:
        return _np().array(STYLE_TINTS[style])
    seed = sum(ord(char) for char in style)
    return _np().array([((seed * 17) % 101 - 50) / 255, ((seed * 31) % 101 - 50) / 255, ((seed * 47) % 101 - 50) / 255])


def _deterministic_noise(shape: tuple[int, int], style: str):
    seed = sum((index + 1) * ord(char) for index, char in enumerate(style)) % (2**32)
    return _np().random.default_rng(seed).random(shape)


def _block_mask(height: int, width: int, blocks: int, progress: float, style: str):
    cell_h = max(1, height // blocks)
    cell_w = max(1, width // blocks)
    low = _deterministic_noise((height // cell_h + 1, width // cell_w + 1), style)
    mask = _np().repeat(_np().repeat(low < progress, cell_h, axis=0), cell_w, axis=1)[:height, :width]
    return mask[:, :, None].astype(float)


def _radial_mask(height: int, width: int, feather: float):
    yy, xx = _np().mgrid[0:height, 0:width]
    distance = _np().sqrt(((xx - width / 2) / max(1, width / 2)) ** 2 + ((yy - height / 2) / max(1, height / 2)) ** 2)
    return _np().clip((1 - distance) / max(0.01, feather), 0, 1)[:, :, None]


def _channel_shift(rgb, offset: int):
    return _np().stack([
        _np().roll(rgb[:, :, 0], offset, axis=1),
        rgb[:, :, 1],
        _np().roll(rgb[:, :, 2], -offset, axis=1),
    ], axis=2)


def _add_grain(rgb, amount: float, style: str):
    noise = _deterministic_noise(rgb.shape[:2], style)[:, :, None] - 0.5
    return _np().clip(rgb + noise * amount, 0, 1)


def _soft_light(rgb, radius: int):
    return sum(_np().roll(_np().roll(rgb, y, axis=0), x, axis=1) for y in range(-radius, radius + 1) for x in range(-radius, radius + 1)) / ((radius * 2 + 1) ** 2)


def _unsharp(rgb, amount: float):
    return _np().clip(rgb + (rgb - _soft_light(rgb, radius=2)) * amount, 0, 1)


def _zoom_frame(image, scale: float):
    np = _np()
    height, width = image.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    source_x = np.clip(((xx - width / 2) / scale + width / 2).round().astype(int), 0, width - 1)
    source_y = np.clip(((yy - height / 2) / scale + height / 2).round().astype(int), 0, height - 1)
    return image[source_y, source_x]


def _translate_frame(image, offset_x: int, offset_y: int):
    np = _np()
    height, width = image.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    source_x = np.clip(xx - offset_x, 0, width - 1)
    source_y = np.clip(yy - offset_y, 0, height - 1)
    return image[source_y, source_x]


def _translate_rgb(rgb, offset_x: int, offset_y: int):
    np = _np()
    height, width = rgb.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    source_x = np.clip(xx - offset_x, 0, width - 1)
    source_y = np.clip(yy - offset_y, 0, height - 1)
    return rgb[source_y, source_x]


def _luma(rgb):
    return (rgb[:, :, 0:1] * 0.2126) + (rgb[:, :, 1:2] * 0.7152) + (rgb[:, :, 2:3] * 0.0722)


def _mix(left, right, amount):
    return _as_float(left) * (1 - amount) + _as_float(right) * amount


def _ease(progress: float, ease: float):
    smooth = progress * progress * (3 - 2 * progress)
    return progress * (1 - ease) + smooth * ease


def _as_float(array):
    if array.dtype.kind == "f" and array.max(initial=0) <= 1:
        return array.astype(float)
    return array.astype(float) / 255


def _finish(array):
    return (_np().clip(array, 0, 1) * 255).round().astype("uint8")


def _clamp(value: float):
    return max(0, min(1, value))


def _np():
    return require_numpy()
