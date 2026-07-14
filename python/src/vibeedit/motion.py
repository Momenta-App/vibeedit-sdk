from __future__ import annotations

import html
import json
import math
import tempfile
from functools import lru_cache
from pathlib import Path

from vibeedit.data import data_path
from vibeedit.ffmpeg import render_frame_sequence, render_overlay_sequence
from vibeedit.spec import JSONObject


class MotionRenderError(RuntimeError):
    pass


def render_mixed(spec: JSONObject, output: str | Path | None = None, base: str | Path = ".") -> Path:
    unsupported = [
        item
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
        if item["kind"] in {"image", "transition", "audio"}
    ]
    if unsupported:
        kinds = ", ".join(sorted({item["kind"] for item in unsupported}))
        raise MotionRenderError(f"alpha mixed dispatcher cannot compose {kinds} inputs yet")
    video = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "video"]
    if len(video) > 1:
        raise MotionRenderError("alpha mixed dispatcher supports at most one source-video clip")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise MotionRenderError('mixed rendering requires: pip install "vibeedit[browser]"; then run vibeedit setup --browser') from error

    destination = Path(output or spec["render"]["output"]["uri"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vibeedit-motion-") as temporary:
        frames = Path(temporary)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": spec["canvas"]["width"], "height": spec["canvas"]["height"]}, device_scale_factor=1)
            page.emulate_media(reduced_motion="reduce")
            for frame in range(spec["durationFrames"]):
                page.set_content(document_for_frame(spec, frame), wait_until="load")
                page.screenshot(path=str(frames / f"frame-{frame:06d}.png"), omit_background=bool(video), animations="disabled")
            browser.close()
        if video:
            return render_overlay_sequence(spec, frames / "frame-%06d.png", destination, base)
        return render_frame_sequence(spec, frames / "frame-%06d.png", destination)


def document_for_frame(spec: JSONObject, frame: int) -> str:
    layers = []
    items = sorted(
        (
            (track["order"], item)
            for track in spec["timeline"]["tracks"]
            for item in track["items"]
            if item["kind"] == "motion"
            and frame >= item["placement"]["startFrame"]
            and frame < item["placement"]["startFrame"] + item["placement"]["durationFrames"]
        ),
        key=lambda value: value[0],
    )
    for _, item in items:
        local_frame = frame - item["placement"]["startFrame"]
        if item["componentId"] == "vibeedit://text/negative":
            layers.append(_negative(item["props"], local_frame, item["placement"]["durationFrames"]))
            continue
        if item["componentId"] == "vibeedit://text/caption-rail":
            layers.append(_caption_rail(item["props"], local_frame, item["placement"]["durationFrames"]))
            continue
        component = _portable_by_id().get(item["componentId"])
        if component:
            layers.append(_portable_component(component, item["props"], local_frame, item["placement"]["durationFrames"]))
            continue
        raise MotionRenderError(f"unknown motion component: {item['componentId']}")
    return '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}*{box-sizing:border-box}</style></head><body>' + "\n".join(layers) + "</body></html>"


def _negative(props: JSONObject, frame: int, duration_frames: int) -> str:
    words = str(props.get("text", "")).strip().split()
    progress = max(0.0, min(1.0, (frame + 1) / max(1, duration_frames)))
    revealed = max(1, math.ceil(progress * len(words)))
    scale = 1.14 - 0.14 * (1 - (1 - progress) ** 3)
    visible = " ".join(f'<span style="display:{"inline" if index < revealed else "none"}">{html.escape(word)}</span>' for index, word in enumerate(words))
    background = html.escape(str(props.get("background", "transparent"))).replace(";", "")
    foreground = html.escape(str(props.get("foreground", "#fff"))).replace(";", "")
    return f'<section data-vibeedit-component="negative" data-frame="{frame}" style="position:absolute;inset:0;display:grid;place-items:center;padding:6%;overflow:hidden;background:{background};color:{foreground}"><div style="font-family:\'Arial Black\',\'Avenir Next Condensed\',sans-serif;font-weight:950;font-size:clamp(56px,13vw,220px);line-height:.78;letter-spacing:-.07em;text-align:center;text-transform:uppercase;transform:scale({scale:.6f});transform-origin:center">{visible}</div></section>'


def _caption_rail(props: JSONObject, frame: int, duration_frames: int) -> str:
    words = str(props.get("text", "")).strip().split()
    progress = max(0.0, min(0.999999, (frame + 1) / max(1, duration_frames)))
    active = min(len(words) - 1, math.floor(progress * len(words)))
    foreground = html.escape(str(props.get("foreground", "#fff"))).replace(";", "")
    accent = html.escape(str(props.get("accent", "#ecff4d"))).replace(";", "")
    background = html.escape(str(props.get("background", "rgba(8,10,14,.82)"))).replace(";", "")
    visible = " ".join(f'<span style="color:{accent if index == active else "inherit"};transform:{"scale(1.04)" if index == active else "none"};display:inline-block">{html.escape(word)}</span>' for index, word in enumerate(words))
    return f'<section data-vibeedit-component="caption-rail" data-frame="{frame}" style="position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center;padding:0 8% 8%;pointer-events:none"><div style="max-width:88%;padding:.42em .68em .5em;border-radius:.28em;background:{background};color:{foreground};font-family:Inter,Arial,sans-serif;font-weight:800;font-size:clamp(28px,4.8vw,72px);line-height:1.06;letter-spacing:-.035em;text-align:center;box-shadow:0 .12em .55em rgba(0,0,0,.34)">{visible}</div></section>'


@lru_cache(maxsize=1)
def list_motion_components() -> list[JSONObject]:
    return json.loads(data_path("catalog", "motion-components.json").read_text(encoding="utf-8"))["components"]


@lru_cache(maxsize=1)
def _portable_by_id() -> dict[str, JSONObject]:
    return {component["id"]: component for component in list_motion_components()}


def tracking_point_at(points, frame: int, fallback: tuple[float, float] = (0.5, 0.5)) -> tuple[float, float]:
    valid = sorted(
        (point for point in points if isinstance(point, dict) and isinstance(point.get("frame"), int) and isinstance(point.get("x"), (int, float)) and isinstance(point.get("y"), (int, float))),
        key=lambda point: point["frame"],
    ) if isinstance(points, list) else []
    if not valid:
        return fallback
    if frame <= valid[0]["frame"]:
        return max(0.0, min(1.0, valid[0]["x"])), max(0.0, min(1.0, valid[0]["y"]))
    if frame >= valid[-1]["frame"]:
        return max(0.0, min(1.0, valid[-1]["x"])), max(0.0, min(1.0, valid[-1]["y"]))
    right_index = next(index for index, point in enumerate(valid) if point["frame"] >= frame)
    left = valid[right_index - 1]
    right = valid[right_index]
    progress = (frame - left["frame"]) / max(1, right["frame"] - left["frame"])
    return (
        max(0.0, min(1.0, left["x"] + (right["x"] - left["x"]) * progress)),
        max(0.0, min(1.0, left["y"] + (right["y"] - left["y"]) * progress)),
    )


def _portable_component(component: JSONObject, props: JSONObject, frame: int, duration_frames: int) -> str:
    progress = max(0.0, min(1.0, (frame + 1) / max(1, duration_frames)))
    eased = 1 - (1 - progress) ** 3
    foreground = _css_color(props.get("foreground"), component["palette"]["foreground"])
    accent = _css_color(props.get("accent"), component["palette"]["accent"])
    background = _css_color(props.get("background"), "transparent")
    raw = str(props.get("text", component["defaultText"])).strip()
    visible = _scramble(raw, progress, frame) if component["motion"] == "scramble" else raw
    words = raw.split()
    if component["motion"] == "editorial":
        content = " ".join(
            f'<span style="font-family:{"Georgia,serif" if index % 2 else "Arial,sans-serif"};font-size:{"1.18em" if index % 2 else ".76em"};font-style:{"italic" if index % 2 else "normal"}">{html.escape(word)}</span>'
            for index, word in enumerate(words)
        )
    else:
        content = html.escape(visible)
    particles = ""
    if component["motion"] == "burst":
        particles = "".join(
            f'<i style="position:absolute;left:50%;top:50%;width:.12em;height:.12em;border-radius:50%;background:{accent if index % 2 else foreground};transform:rotate({index * 45}deg) translate({eased * 4.2:.3f}em);opacity:{1 - progress:.4f}"></i>'
            for index in range(8)
        )
    slug = html.escape(component["id"].rsplit("/", 1)[-1]).replace(";", "")
    family = html.escape(component["family"]).replace(";", "")
    align = "flex-end" if component["kind"] == "caption" else "center"
    padding = "0 7% 8%" if component["kind"] == "caption" else "7%"
    size = "6vw" if component["kind"] == "caption" else "10vw"
    transform = "none" if component["kind"] == "caption" else "uppercase"
    styles = _family_style(component["family"], foreground, accent, progress, frame % 4) + _motion_style(component["motion"], progress, eased, frame % 4, accent, props, frame)
    return f'<section data-vibeedit-component="{slug}" data-family="{family}" data-frame="{frame}" style="position:absolute;inset:0;display:flex;align-items:{align};justify-content:center;padding:{padding};overflow:hidden;pointer-events:none;background:{background}"><div style="position:relative;max-width:94%;color:{foreground};font-family:\'Arial Black\',\'Avenir Next\',Arial,sans-serif;font-weight:900;font-size:clamp(32px,{size},180px);line-height:.94;letter-spacing:-.045em;text-align:center;text-transform:{transform};{styles}">{content}{particles}</div></section>'


def _family_style(family: str, foreground: str, accent: str, progress: float, phase: int) -> str:
    if family == "aesthetic-glow":
        return f"background:linear-gradient(180deg,{foreground},{accent});color:transparent;background-clip:text;-webkit-background-clip:text;filter:drop-shadow(0 0 {0.08 + progress * 0.18:.3f}em {accent});"
    if family == "dimensional-metal":
        return f"background:linear-gradient(180deg,#fff 0%,{foreground} 42%,{accent} 100%);color:transparent;background-clip:text;-webkit-background-clip:text;text-shadow:.035em .055em 0 {accent},.07em .1em 0 #111;transform-style:preserve-3d;"
    if family == "analog-glitch":
        return f"text-shadow:{'.035em' if phase % 2 else '-.035em'} 0 {accent},{'-.025em' if phase % 2 else '.025em'} .02em #27e8ff;filter:contrast(1.18);"
    if family == "rainbow-trippy":
        return f"background:linear-gradient(90deg,#ff3155,#ffd23f,#2ee6a6,#4b7bff,#d44bff);color:transparent;background-clip:text;-webkit-background-clip:text;filter:hue-rotate({progress * 180:.2f}deg);"
    if family == "water-warp":
        return f"color:{foreground};filter:blur({(1 - progress) * 0.08:.4f}em) drop-shadow(0 .08em .12em {accent});"
    if family == "elegant-misc":
        return f"font-family:Georgia,'Times New Roman',serif;font-weight:700;letter-spacing:.01em;color:{foreground};text-shadow:0 .04em .16em {accent};"
    if family == "apple-clean":
        return f"font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;font-weight:750;letter-spacing:-.055em;color:{foreground};text-shadow:0 .06em .18em rgba(0,0,0,.22);"
    return f"color:{foreground};"


def _motion_style(motion: str, progress: float, eased: float, phase: int, accent: str, props: JSONObject, frame: int) -> str:
    if motion == "wipe":
        return f"clip-path:inset(0 {(1 - eased) * 100:.3f}% 0 0);"
    if motion == "pop":
        return f"transform:scale({0.55 + eased * 0.45:.5f});opacity:{eased:.5f};"
    if motion == "slam":
        return f"transform:translateX({(1 - eased) * (-34 if phase % 2 else 34):.3f}%) scale({1.28 - eased * 0.28:.5f});opacity:{eased:.5f};"
    if motion == "glitch":
        return f"transform:translate({phase - 1.5}px,{1.5 - phase}px);text-shadow:{phase - 2}px 0 #ff285c,{2 - phase}px 0 #25e6ff;"
    if motion == "gradient":
        return f"background:linear-gradient(90deg,{accent},#fff,{accent});background-size:220% 100%;background-position:{100 - progress * 200:.3f}% 0;color:transparent;background-clip:text;-webkit-background-clip:text;transform:scale({0.9 + eased * 0.1:.5f});"
    if motion == "highlight":
        return f"background:{accent};padding:.13em .22em;border-radius:.12em;color:#fff;clip-path:inset(0 {(1 - eased) * 100:.3f}% 0 0);"
    if motion == "glow":
        return f"color:{accent};text-shadow:0 0 .08em {accent},0 0 .32em {accent};opacity:{eased:.5f};"
    if motion == "parallax":
        return f"text-shadow:.035em .045em 0 {accent},.07em .09em 0 rgba(0,0,0,.5);transform:perspective(700px) rotateY({(1 - eased) * -18:.3f}deg);"
    if motion == "pill":
        return f"background:{accent};padding:.24em .52em;border-radius:999px;color:#101217;transform:scaleX({0.72 + eased * 0.28:.5f});"
    if motion in {"texture", "texture-mask"}:
        return f"background:repeating-linear-gradient(135deg,{accent} 0 .12em,#fff .12em .2em,{accent} .2em .34em);color:transparent;background-clip:text;-webkit-background-clip:text;filter:contrast(1.15);"
    if motion == "weight":
        return f"font-weight:{round(300 + eased * 600)};letter-spacing:{(1 - eased) * 0.08 - 0.03:.4f}em;"
    if motion == "difference":
        return "mix-blend-mode:difference;color:#fff;"
    if motion == "face-follow":
        point = tracking_point_at(props.get("trackingFrames"), frame, (0.5 + math.sin(progress * math.pi * 2) * 0.18, 0.5))
        return f"position:absolute;left:{point[0] * 100:.4f}%;top:{point[1] * 100:.4f}%;mix-blend-mode:difference;color:#fff;transform:translate(-50%,-50%);"
    if motion == "morph":
        return f"filter:blur({math.sin(progress * math.pi) * 0.16:.4f}em) contrast(1.4);transform:scale({1 + math.sin(progress * math.pi) * 0.08:.5f});"
    if motion == "shimmer":
        return f"background:linear-gradient(110deg,{accent} 20%,#fff 45%,{accent} 70%);background-size:240% 100%;background-position:{120 - progress * 240:.3f}% 0;color:transparent;background-clip:text;-webkit-background-clip:text;"
    if motion == "creed":
        return f"transform:perspective(800px) rotateY({(1 - eased) * -12:.3f}deg) skewX(-3deg) scale({0.86 + eased * 0.14:.5f});text-shadow:.035em .055em 0 {accent};"
    return f"transform:translateY({(1 - eased) * 0.55:.4f}em) scale({0.82 + eased * 0.18:.5f});opacity:{eased:.5f};"


def _scramble(value: str, progress: float, frame: int) -> str:
    glyphs = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    count = math.floor(len(value) * progress)
    return "".join(character if index < count or character.isspace() else glyphs[(index * 17 + frame * 13) % len(glyphs)] for index, character in enumerate(value))


def _css_color(value, fallback: str) -> str:
    import re

    candidate = str(value if value is not None else fallback).strip()
    if re.fullmatch(r"(#[0-9a-fA-F]{3,8}|rgba?\([\d\s.,%+\-]+\)|hsla?\([\d\s.,%+\-]+\)|transparent|white|black)", candidate):
        return html.escape(candidate).replace(";", "")
    return fallback
