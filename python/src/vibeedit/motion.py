from __future__ import annotations

import base64
import hashlib
import html
import http.server
import json
import math
import mimetypes
import re
import subprocess
import tempfile
import threading
import urllib.parse
from contextlib import contextmanager
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

from vibeedit.cache import cache_key, restore_cached_artifact, store_cached_artifact
from vibeedit.data import data_path
from vibeedit.ffmpeg import ffmpeg_path, frame_stream_encoder, overlay_frame_stream_encoder, render_media
from vibeedit.spec import JSONObject
from vibeedit.version import VERSION


class MotionRenderError(RuntimeError):
    pass


HTML_CSS_MOTION_COMPONENT_ID = "vibeedit://motion/html-css"


def motion_render_plan(spec: JSONObject) -> JSONObject:
    layers = []
    for track in spec["timeline"]["tracks"]:
        for item in track["items"]:
            if item["kind"] != "motion":
                continue
            component = _portable_by_id().get(item["componentId"])
            props = item.get("props", {})
            source = " ".join(str(props.get(key, "")) for key in ("html", "css", "javascript", "entry")).casefold()
            declared_libraries = [str(value) for value in props.get("libraries", []) if isinstance(value, str)]
            detected = [
                name
                for name, tokens in {
                    "gsap": ("gsap",),
                    "anime.js": ("anime",),
                    "react": ("react",),
                    "vue": ("vue",),
                    "svelte": ("svelte",),
                    "three.js": ("three", "webglrenderer"),
                    "pixijs": ("pixi",),
                    "webgpu": ("navigator.gpu", "wgsl", "gpuadapter"),
                    "canvas": ("<canvas", "getcontext("),
                }.items()
                if any(token in source or any(token in library.casefold() for library in declared_libraries) for token in tokens)
            ]
            custom = _is_web_component(item)
            advanced = bool(set(detected) & {"three.js", "pixijs", "webgpu", "canvas"})
            html_css_only = item["componentId"] == HTML_CSS_MOTION_COMPONENT_ID
            native_candidate = not custom or html_css_only or (not props.get("javascript") and not props.get("entry") and not advanced)
            layers.append(
                {
                    "id": item["id"],
                    "componentId": item["componentId"],
                    "requestedRenderer": item.get("renderer", "html"),
                    "selectedBackend": "chromium-persistent",
                    "reason": "source-preserved catalog component" if component and component.get("canonical") else "raw HTML/CSS reference document" if html_css_only else "arbitrary local web project" if custom else "portable browser component",
                    "libraries": sorted(set(declared_libraries + detected)),
                    "nativeEligibility": "candidate-unverified" if native_candidate else "browser-required",
                    "seekContract": "automatic-css-animations" if html_css_only else "explicit-vibeedit-seek" if advanced else "automatic-css-waapi-library-adapter",
                    "authoringContract": "html-css-only" if html_css_only else "local-web-runtime",
                }
            )
    return {
        "strategy": "browser-reference-with-conformance-gated-native-routing",
        "selectedBackend": "chromium-persistent" if layers else "none",
        "nativeRoutingEnabled": False,
        "nativeRoutingReason": "no layer is routed until its decoded-pixel conformance suite passes",
        "layers": layers,
    }


def render_mixed(spec: JSONObject, output: str | Path | None = None, base: str | Path = ".", *, metrics: JSONObject | None = None) -> Path:
    unsupported = [
        item
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
        if item["kind"] == "image"
    ]
    if unsupported:
        kinds = ", ".join(sorted({item["kind"] for item in unsupported}))
        raise MotionRenderError(f"mixed dispatcher cannot compose {kinds} inputs yet")
    video = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "video"]
    if len(video) > 2:
        raise MotionRenderError("mixed dispatcher supports at most two source-video clips")
    audio = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "audio"]
    transitions = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "transition"]
    if audio and not video:
        raise MotionRenderError("mixed audio clips currently require a source-video layer")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise MotionRenderError('mixed rendering requires: pip install "vibeedit[browser]"; then run vibeedit setup --browser') from error

    destination = Path(output or spec["render"]["output"]["uri"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vibeedit-motion-") as temporary:
        overlay_spec = spec
        if len(video) > 1 or audio or transitions:
            intermediate = Path(temporary) / "python-media-base.mkv"
            media_spec = json.loads(json.dumps(spec))
            media_spec["timeline"]["tracks"] = [
                {**track, "items": [item for item in track["items"] if item["kind"] != "motion"]}
                for track in media_spec["timeline"]["tracks"]
                if any(item["kind"] != "motion" for item in track["items"])
            ]
            media_spec["render"]["output"].update({"container": "mkv", "videoCodec": "ffv1", "audioCodec": "flac", "pixelFormat": "yuv420p"})
            media_spec["render"]["output"]["uri"] = "<internal-media-base>"
            media_key = cache_key(
                "motion.media_base",
                media_spec,
                implementation_version=VERSION,
                runtime_versions={"ffmpeg": _ffmpeg_version()},
            )
            media_cache_hit = spec.get("cache", {}).get("enabled", False) and restore_cached_artifact("motion.media_base", media_key, intermediate)
            if not media_cache_hit:
                render_media(media_spec, intermediate, base)
                if spec.get("cache", {}).get("enabled", False):
                    store_cached_artifact("motion.media_base", media_key, intermediate)
            if metrics is not None:
                metrics.update({"mediaBaseCacheHit": media_cache_hit, "mediaBaseFramesRendered": 0 if media_cache_hit else spec["durationFrames"]})
            overlay_spec = _single_video_overlay_spec(spec, intermediate)
        encoder_context = overlay_frame_stream_encoder(overlay_spec, destination, base) if video else frame_stream_encoder(spec, destination)
        with encoder_context as encoder, sync_playwright() as playwright, _motion_asset_server(base) as asset_urls:
            browser = playwright.chromium.launch(headless=True, args=["--enable-unsafe-webgpu"] if _requires_webgpu(spec) else [])
            context = browser.new_context(viewport={"width": spec["canvas"]["width"], "height": spec["canvas"]["height"]}, device_scale_factor=1)
            context.route("**/*", lambda route: route.continue_() if _is_local_browser_url(route.request.url, asset_urls["origin"]) else route.abort("blockedbyclient"))
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("requestfailed", lambda request: errors.append(f"asset request failed: {request.url} ({request.failure or 'unknown error'})"))
            page.on("response", lambda response: errors.append(f"asset request returned HTTP {response.status}: {response.url}") if response.status >= 400 else None)
            _load_persistent_page(page, spec, asset_urls, transparent=bool(video))
            session = context.new_cdp_session(page)
            if video:
                session.send("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
            rendered_frames = 0
            reused_frames = 0
            for frame in range(spec["durationFrames"]):
                frame_file = Path(temporary) / f"motion-frame-{frame:08d}.png"
                key = cache_key(
                    "motion.composite_frame",
                    _motion_frame_inputs(spec, frame, transparent=bool(video)),
                    implementation_version=VERSION,
                    runtime_versions={"playwright": _package_version("playwright"), "chromium": browser.version},
                )
                if spec.get("cache", {}).get("enabled", False) and restore_cached_artifact("motion.composite_frame", key, frame_file):
                    encoder.write(frame_file.read_bytes())
                    reused_frames += 1
                    continue
                _apply_persistent_frame(page, spec, frame, asset_urls["catalog"])
                _settle_canonical_frames(page)
                _settle_web_frames(page, spec, frame)
                if errors:
                    raise MotionRenderError(f"browser motion component failed: {errors[0]}")
                payload = _capture_fast_png(session)
                encoder.write(payload)
                rendered_frames += 1
                if spec.get("cache", {}).get("enabled", False):
                    frame_file.write_bytes(payload)
                    store_cached_artifact("motion.composite_frame", key, frame_file)
            context.close()
            browser.close()
            if metrics is not None:
                metrics.update(
                    {
                        "framesRendered": rendered_frames,
                        "framesReused": reused_frames,
                        "motionFramesCaptured": rendered_frames,
                        "motionFramesReused": reused_frames,
                        "videoFramesEncoded": spec["durationFrames"],
                        "reuseKind": "content-addressed-motion-overlay-frames" if video and reused_frames else "content-addressed-composite-frames" if reused_frames else "none",
                    }
                )
        return destination


def _motion_frame_inputs(spec: JSONObject, frame: int, *, transparent: bool) -> JSONObject:
    active = [
        {"trackOrder": track["order"], "item": item}
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
        if item["kind"] == "motion"
        and item["placement"]["startFrame"] <= frame < item["placement"]["startFrame"] + item["placement"]["durationFrames"]
    ]
    return {
        "contractVersion": 1,
        "namespace": spec.get("cache", {}).get("namespace", "default"),
        "canvas": spec["canvas"],
        "frame": frame,
        "transparent": transparent,
        "activeMotionLayers": active,
    }


def _package_version(name: str) -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(name)
    except PackageNotFoundError:
        return "unavailable"


@lru_cache(maxsize=1)
def _ffmpeg_version() -> str:
    result = subprocess.run([ffmpeg_path(), "-version"], capture_output=True, text=True, check=False)
    return (result.stdout or result.stderr).splitlines()[0] if result.returncode == 0 else "unavailable"


def _single_video_overlay_spec(spec: JSONObject, source: Path) -> JSONObject:
    result = json.loads(json.dumps(spec))
    result["sources"] = [{"id": "vibeedit-python-media-base", "kind": "video", "uri": str(source), "identity": {"algorithm": "generated", "value": "python-media-base"}}]
    result["timeline"]["tracks"] = [
        {
            "id": "VIBEEDIT_MEDIA_BASE",
            "kind": "video",
            "order": 0,
            "items": [
                {
                    "id": "vibeedit-python-media-base",
                    "kind": "video",
                    "placement": {"startFrame": 0, "durationFrames": spec["durationFrames"]},
                    "source": {"sourceId": "vibeedit-python-media-base", "inFrame": 0, "durationFrames": spec["durationFrames"]},
                    "effects": [],
                }
            ],
        }
    ]
    return result


def _persistent_document(spec: JSONObject, catalog_url: str, project_url: str, *, atoms_url: str | None = None, inline_url: str | None = None, inline_documents: dict[str, bytes] | None = None, transparent: bool = False) -> str:
    layers = []
    for order, item in sorted(
        (
            (track["order"], item)
            for track in spec["timeline"]["tracks"]
            for item in track["items"]
            if item["kind"] == "motion"
        ),
        key=lambda value: value[0],
    ):
        token = _item_token(item)
        kind = "dynamic"
        content = ""
        component = _portable_by_id().get(item["componentId"])
        if component and component.get("canonical"):
            kind = "canonical"
            frame_rate = spec["canvas"].get("frameRate", {"numerator": 30, "denominator": 1})
            content = _portable_component(component, item["props"], 0, item["placement"]["durationFrames"], catalog_url, frame_rate["numerator"] / frame_rate["denominator"])
        if _is_web_component(item):
            kind = "web"
            content = _web_component(item, project_url, atoms_url, inline_url, inline_documents)
        layers.append(
            f'<div data-vibeedit-item="{token}" data-vibeedit-kind="{kind}" data-vibeedit-order="{order}" style="position:absolute;inset:0;visibility:hidden;pointer-events:none">{content}</div>'
        )
    background = "transparent" if transparent else _css_color(spec["canvas"].get("backgroundColor"), "transparent")
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        f'html,body,#vibeedit-root{{margin:0;width:100%;height:100%;overflow:hidden;background:{background}}}'
        '*{box-sizing:border-box}</style></head><body><main id="vibeedit-root">'
        + "\n".join(layers)
        + "</main></body></html>"
    )


def _load_persistent_page(page, spec: JSONObject, asset_urls: dict, *, transparent: bool = False) -> None:
    name = "vibeedit-render-shell.html"
    asset_urls["inlineDocuments"][name] = _persistent_document(
        spec,
        asset_urls["catalog"],
        asset_urls["project"],
        atoms_url=asset_urls["atoms"],
        inline_url=asset_urls["inline"],
        inline_documents=asset_urls["inlineDocuments"],
        transparent=transparent,
    ).encode()
    page.goto(urllib.parse.urljoin(asset_urls["inline"], name), wait_until="load")


def _apply_persistent_frame(page, spec: JSONObject, frame: int, catalog_url: str) -> None:
    payload = []
    frame_rate = spec["canvas"].get("frameRate", {"numerator": 30, "denominator": 1})
    fps = frame_rate["numerator"] / frame_rate["denominator"]
    for track in spec["timeline"]["tracks"]:
        for item in track["items"]:
            if item["kind"] != "motion":
                continue
            start = item["placement"]["startFrame"]
            duration = item["placement"]["durationFrames"]
            active = start <= frame < start + duration
            local_frame = frame - start
            component = _portable_by_id().get(item["componentId"])
            kind = "web" if _is_web_component(item) else "canonical" if component and component.get("canonical") else "dynamic"
            layer = ""
            if active and kind == "dynamic":
                layer = _layer_for_item(item, local_frame, catalog_url, fps)
            payload.append({"token": _item_token(item), "kind": kind, "active": active, "frame": local_frame, "durationFrames": duration, "time": local_frame / max(1, fps), "html": layer})
    page.evaluate(
        """(items) => {
          for (const item of items) {
            const layer = document.querySelector(`[data-vibeedit-item="${item.token}"]`);
            if (!layer) throw new Error(`missing VibeEdit motion layer ${item.token}`);
            layer.style.visibility = item.active ? "visible" : "hidden";
            layer.dataset.vibeeditActive = item.active ? "true" : "false";
            layer.dataset.vibeeditFrame = String(item.frame);
            layer.dataset.vibeeditDurationFrames = String(item.durationFrames);
            if (item.kind === "dynamic" && item.active) layer.innerHTML = item.html;
            if (item.kind === "canonical") {
              const frame = layer.querySelector("iframe[data-vibeedit-canonical]");
              if (frame) frame.dataset.vibeeditTime = String(item.time);
            }
          }
        }""",
        payload,
    )


def _layer_for_item(item: JSONObject, local_frame: int, asset_base_url: str | None, fps: float) -> str:
    if item["componentId"] == "vibeedit://text/negative":
        return _negative(item["props"], local_frame, item["placement"]["durationFrames"])
    if item["componentId"] == "vibeedit://text/caption-rail":
        return _caption_rail(item["props"], local_frame, item["placement"]["durationFrames"])
    component = _portable_by_id().get(item["componentId"])
    if component:
        return _portable_component(component, item["props"], local_frame, item["placement"]["durationFrames"], asset_base_url, fps)
    if _is_web_component(item):
        raise MotionRenderError("custom HTML motion components require the persistent browser renderer")
    raise MotionRenderError(f"unknown motion component: {item['componentId']}")


def _is_web_component(item: JSONObject) -> bool:
    return item.get("componentId") in {HTML_CSS_MOTION_COMPONENT_ID, "vibeedit://motion/html", "vibeedit://motion/web-project"}


def _requires_webgpu(spec: JSONObject) -> bool:
    return any(
        item.get("renderer") == "webgpu"
        or any(token in " ".join(str(item.get("props", {}).get(key, "")) for key in ("html", "css", "javascript", "entry")).casefold() for token in ("navigator.gpu", "gpuadapter", "@compute", "@vertex", "@fragment", "wgsl"))
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
        if item["kind"] == "motion"
    )


def _item_token(item: JSONObject) -> str:
    return hashlib.sha256(str(item["id"]).encode()).hexdigest()[:20]


def _web_component(item: JSONObject, project_url: str, atoms_url: str | None, inline_url: str | None, inline_documents: dict[str, bytes] | None) -> str:
    props = item["props"]
    if item["componentId"] == HTML_CSS_MOTION_COMPONENT_ID:
        source = _html_css_document(props, project_url, atoms_url)
        if inline_url and inline_documents is not None:
            name = f"{_item_token(item)}.html"
            inline_documents[name] = source.encode()
            source_url = urllib.parse.urljoin(inline_url, name)
            return f'<iframe data-vibeedit-web="true" data-vibeedit-html-css="true" src="{html.escape(source_url, quote=True)}" style="position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent"></iframe>'
        return f'<iframe data-vibeedit-web="true" data-vibeedit-html-css="true" srcdoc="{html.escape(source, quote=True)}" style="position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent"></iframe>'
    if props.get("entry"):
        source = urllib.parse.urljoin(project_url, urllib.parse.quote(str(props["entry"])))
        return f'<iframe data-vibeedit-web="true" src="{html.escape(source, quote=True)}" style="position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent" allow="webgpu"></iframe>'
    markup = str(props.get("html", ""))
    css = str(props.get("css", ""))
    javascript = str(props.get("javascript", ""))
    stylesheets = "".join(f'<link rel="stylesheet" href="{html.escape(str(source), quote=True)}">' for source in props.get("stylesheets", []) if isinstance(source, str))
    libraries = "".join(f'<script src="{html.escape(str(source), quote=True)}"></script>' for source in props.get("libraries", []) if isinstance(source, str))
    script_type = "module" if props.get("scriptType") == "module" else "text/javascript"
    javascript = javascript.replace("</script", "<\\/script")
    source = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<base href="{html.escape(project_url, quote=True)}">'
        '<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}*{box-sizing:border-box}</style>'
        f"{stylesheets}<style>{css}</style></head><body>{markup}{libraries}<script type=\"{script_type}\">{javascript}</script></body></html>"
    )
    if inline_url and inline_documents is not None:
        name = f"{_item_token(item)}.html"
        inline_documents[name] = source.encode()
        source_url = urllib.parse.urljoin(inline_url, name)
        return f'<iframe data-vibeedit-web="true" src="{html.escape(source_url, quote=True)}" style="position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent" allow="webgpu"></iframe>'
    return f'<iframe data-vibeedit-web="true" srcdoc="{html.escape(source, quote=True)}" style="position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent" allow="webgpu"></iframe>'


def _html_css_document(props: JSONObject, project_url: str, atoms_url: str | None) -> str:
    forbidden = [key for key in ("javascript", "libraries", "entry", "scriptType") if props.get(key)]
    if forbidden:
        raise MotionRenderError(f"{HTML_CSS_MOTION_COMPONENT_ID} does not allow {', '.join(forbidden)}; use raw HTML, CSS, and local stylesheets only")
    markup = str(props.get("html", ""))
    css = str(props.get("css", ""))
    validator = _HTMLCSSValidator()
    validator.feed(markup)
    validator.close()
    if validator.error:
        raise MotionRenderError(f"{HTML_CSS_MOTION_COMPONENT_ID} rejected markup: {validator.error}")
    stylesheets = "".join(
        f'<link rel="stylesheet" href="{html.escape(str(source), quote=True)}">'
        for source in props.get("stylesheets", [])
        if isinstance(source, str)
    )
    atoms = f'<link rel="stylesheet" href="{html.escape(atoms_url, quote=True)}">' if atoms_url and props.get("atoms", True) is not False else ""
    head = (
        '<meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'self\' data: blob:; script-src \'none\'; connect-src \'none\'; frame-src \'none\'; object-src \'none\'; base-uri \'self\'; style-src \'self\' \'unsafe-inline\' data: blob:; font-src \'self\' data: blob:; img-src \'self\' data: blob:; media-src \'self\' data: blob:">'
        f'<base href="{html.escape(project_url, quote=True)}">'
        '<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}*{box-sizing:border-box}</style>'
        f'{atoms}{stylesheets}<style>{css}</style>'
    )
    if re.search(r"<head\b", markup, flags=re.IGNORECASE):
        return re.sub(r"(<head\b[^>]*>)", lambda match: match.group(1) + head, markup, count=1, flags=re.IGNORECASE)
    if re.search(r"<html\b", markup, flags=re.IGNORECASE):
        return re.sub(r"(<html\b[^>]*>)", lambda match: match.group(1) + f"<head>{head}</head>", markup, count=1, flags=re.IGNORECASE)
    return f"<!doctype html><html><head>{head}</head><body>{markup}</body></html>"


class _HTMLCSSValidator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.error: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._validate(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._validate(tag, attrs)

    def _validate(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.error:
            return
        if tag.casefold() in {"script", "iframe", "object", "embed"}:
            self.error = f"<{tag}> is outside the HTML/CSS-only contract"
            return
        normalized = {name.casefold(): (value or "") for name, value in attrs}
        if any(name.startswith("on") or name == "srcdoc" for name in normalized):
            self.error = f"event handlers and srcdoc are outside the HTML/CSS-only contract on <{tag}>"
            return
        if any(value.lstrip().casefold().startswith("javascript:") for value in normalized.values()):
            self.error = f"javascript: URLs are outside the HTML/CSS-only contract on <{tag}>"
            return
        if tag.casefold() == "meta" and normalized.get("http-equiv", "").casefold() == "refresh":
            self.error = "meta refresh is outside the HTML/CSS-only contract"


def _settle_web_frames(page, spec: JSONObject, frame_number: int) -> None:
    frame_rate = spec["canvas"].get("frameRate", {"numerator": 30, "denominator": 1})
    fps = frame_rate["numerator"] / frame_rate["denominator"]
    layers = page.locator('[data-vibeedit-kind="web"][data-vibeedit-active="true"]')
    for index in range(layers.count()):
        layer = layers.nth(index)
        element = layer.locator("iframe[data-vibeedit-web]").element_handle()
        child = element.content_frame() if element else None
        if child is None:
            raise MotionRenderError(f"custom HTML frame {index} did not attach")
        local_frame = int(layer.get_attribute("data-vibeedit-frame") or frame_number)
        duration = int(layer.get_attribute("data-vibeedit-duration-frames") or spec["durationFrames"])
        child.evaluate(
            """async (context) => {
              if (document.fonts && document.fonts.ready) await document.fonts.ready;
              const failedFonts = document.fonts ? [...document.fonts].filter((font) => font.status === "error").map((font) => font.family) : [];
              if (failedFonts.length) throw new Error(`font loading failed: ${failedFonts.join(", ")}`);
              const api = globalThis.vibeedit;
              if (api && typeof api.seek === "function") await api.seek(context.time, context);
              else if (typeof globalThis.__vibeeditSeek === "function") await globalThis.__vibeeditSeek(context.frame, context);
              if (globalThis.gsap && globalThis.gsap.globalTimeline) {
                globalThis.gsap.globalTimeline.time(context.time, false).pause();
              }
              if (globalThis.anime && Array.isArray(globalThis.anime.running)) {
                for (const animation of globalThis.anime.running) {
                  if (typeof animation.seek === "function") animation.seek(context.time * 1000);
                  if (typeof animation.pause === "function") animation.pause();
                }
              }
              for (const animation of document.getAnimations({subtree: true})) {
                animation.pause();
                const timing = animation.effect && animation.effect.getComputedTiming ? animation.effect.getComputedTiming() : null;
                const end = timing && Number.isFinite(timing.endTime) ? timing.endTime : context.time * 1000;
                animation.currentTime = Math.min(context.time * 1000, end);
              }
              globalThis.dispatchEvent(new CustomEvent("vibeedit:frame", {detail: context}));
              void document.body.offsetHeight;
            }""",
            {"frame": local_frame, "absoluteFrame": frame_number, "durationFrames": duration, "fps": fps, "time": local_frame / max(1, fps), "progress": max(0.0, min(1.0, local_frame / max(1, duration - 1)))},
        )


def _capture_fast_png(session) -> bytes:
    result = session.send("Page.captureScreenshot", {"format": "png", "fromSurface": True, "captureBeyondViewport": False, "optimizeForSpeed": True})
    return base64.b64decode(result["data"])


def _is_local_browser_url(url: str, origin: str) -> bool:
    if url.startswith((origin, "about:", "data:", "blob:")):
        return True
    return False


def document_for_frame(spec: JSONObject, frame: int, asset_base_url: str | None = None) -> str:
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
        frame_rate = spec["canvas"].get("frameRate", {"numerator": 30, "denominator": 1})
        layers.append(_layer_for_item(item, local_frame, asset_base_url, frame_rate["numerator"] / frame_rate["denominator"]))
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
def list_motion_atoms() -> JSONObject:
    return json.loads(data_path("catalog", "motion-atoms", "manifest.json").read_text(encoding="utf-8"))


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


def _portable_component(component: JSONObject, props: JSONObject, frame: int, duration_frames: int, asset_base_url: str | None = None, fps: float = 30) -> str:
    if component.get("canonical") and asset_base_url:
        return _canonical_component(component, props, frame, asset_base_url, fps)
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


def _canonical_component(component: JSONObject, props: JSONObject, frame: int, asset_base_url: str, fps: float) -> str:
    source = urllib.parse.urljoin(asset_base_url, component["canonical"]["entry"])
    parsed = urllib.parse.urlparse(source)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    query.update({"alpha": "1", "render": "1", "transparent": "1"})
    text = str(props.get("text", component["defaultText"])).strip()
    if text and _normalize_text(text) != _normalize_text(component["defaultText"]):
        query["text"] = text
    source = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
    background = _css_color(props.get("background"), "transparent")
    slug = html.escape(component["id"].rsplit("/", 1)[-1], quote=True).replace(";", "")
    family = html.escape(component["family"], quote=True).replace(";", "")
    name = html.escape(component["name"], quote=True).replace(";", "")
    return f'<section data-vibeedit-component="{slug}" data-family="{family}" data-frame="{frame}" style="position:absolute;inset:0;overflow:hidden;pointer-events:none;background:{background}"><span style="position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)">{html.escape(text)}</span><iframe data-vibeedit-canonical="true" data-vibeedit-time="{frame / max(1, fps):.6f}" title="{name}" src="{html.escape(source, quote=True)}" style="position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent;pointer-events:none" tabindex="-1"></iframe></section>'


def _settle_canonical_frames(page) -> None:
    frames = page.locator("iframe[data-vibeedit-canonical]")
    for index in range(frames.count()):
        element = frames.nth(index)
        if not element.is_visible():
            continue
        handle = element.element_handle()
        frame = handle.content_frame() if handle else None
        if frame is None:
            raise MotionRenderError(f"canonical text frame {index} did not attach")
        frame.wait_for_function("Object.keys(globalThis.__timelines || {}).length > 0 || Boolean(document.body.dataset.error)", timeout=15_000)
        error = frame.locator("body").get_attribute("data-error")
        if error:
            raise MotionRenderError(f"canonical text frame {index}: {error}")
        frame.evaluate("""async (time) => {
          if (document.fonts && document.fonts.ready) await document.fonts.ready;
          const timeline = Object.values(globalThis.__timelines || {})[0];
          timeline.time(0);
          timeline.time(time);
          if (typeof timeline.pause === "function") timeline.pause();
          await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }""", float(element.get_attribute("data-vibeedit-time")))


@contextmanager
def _motion_asset_server(project_root: str | Path = "."):
    roots = {
        "catalog": data_path("catalog", "text-runtime").resolve(),
        "atoms": data_path("catalog", "motion-atoms").resolve(),
        "project": Path(project_root).resolve(),
    }
    inline_documents: dict[str, bytes] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            parts = [part for part in urllib.parse.unquote(parsed.path).split("/") if part]
            if not parts:
                self.send_error(404)
                return
            if parts[0] == "inline":
                payload = inline_documents.get("/".join(parts[1:]))
                if payload is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)
                return
            namespace = parts[0] if parts[0] in roots else "catalog"
            relative = parts[1:] if parts[0] in roots else parts
            root = roots[namespace]
            target = root.joinpath(*relative).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                self.send_error(404)
                return
            payload = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        origin = f"http://127.0.0.1:{server.server_port}/"
        yield {"origin": origin, "catalog": f"{origin}catalog/", "atoms": f"{origin}atoms/v1.css", "project": f"{origin}project/", "inline": f"{origin}inline/", "inlineDocuments": inline_documents}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


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
        return f"background:repeating-linear-gradient(135deg,{accent} 0 .12em,#fff .12em .2em,{accent} .2em .34em);background-size:220% 220%;background-position:{progress * 100:.3f}% {100 - progress * 100:.3f}%;color:transparent;background-clip:text;-webkit-background-clip:text;filter:contrast(1.15);"
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
