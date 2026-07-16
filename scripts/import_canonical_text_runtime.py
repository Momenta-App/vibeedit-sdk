from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PREFIX = "packages/app/public/text-effect-catalog/components/html-motion-mogrt"
DESTINATION = PACKAGE_ROOT / "catalog" / "text-runtime"
REFINED_EFFECTS = [
    "3D_TEXT",
    "AESTHETIC_PURPLE",
    "AESTHETIC_STRINKING",
    "BLUR_IN",
    "BOTTOM_IN",
    "CLEAN_BLUE",
    "ELEGANT",
    "ESMERALD",
    "GOLD_TEXT",
    "LEFT_IN",
    "OPACITY_IN",
    "RIGHT_IN",
    "SMOOTH_OPACITY",
    "dark_water",
    "fluorscent",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone the tracked VibeEdit HTML motion-title runtime without redesigning it")
    parser.add_argument("--source-root", type=Path, required=True, help="path to a VibeEdit source checkout")
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    root = args.source_root.resolve()
    revision = _git(root, "rev-parse", args.revision).decode().strip()
    paths = [
        path
        for path in _git(root, "ls-tree", "-r", "--name-only", revision, SOURCE_PREFIX).decode().splitlines()
        if path.startswith(f"{SOURCE_PREFIX}/")
    ]
    if not paths:
        raise RuntimeError("tracked canonical text runtime is empty")

    shutil.rmtree(DESTINATION, ignore_errors=True)
    records = []
    for path in paths:
        relative = Path(path).relative_to(SOURCE_PREFIX)
        payload = _git(root, "show", f"{revision}:{path}")
        payload = _refine(relative, payload)
        if relative.suffix == ".html":
            payload = _inject_adapter(payload.decode()).encode()
        destination = DESTINATION / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        records.append({"path": relative.as_posix(), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})

    adapter = _adapter().encode()
    (DESTINATION / "vibeedit-adapter.js").write_bytes(adapter)
    records.append({"path": "vibeedit-adapter.js", "bytes": len(adapter), "sha256": hashlib.sha256(adapter).hexdigest()})
    manifest = {
        "schemaVersion": "vibeedit.canonical-text-runtime.v1",
        "source": SOURCE_PREFIX,
        "revision": revision,
        "refinementPolicy": "Approved beta catalogue refinements preserve each source effect family while correcting requested motion, clarity, color, shimmer, and 3D behavior.",
        "refinedEffects": REFINED_EFFECTS,
        "files": sorted(records, key=lambda item: item["path"]),
    }
    (DESTINATION / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "revision": revision, "files": len(records)}))
    return 0


def _refine(relative: Path, payload: bytes) -> bytes:
    if relative.parent == Path("configs") and relative.suffix == ".json":
        config = json.loads(payload)
        _refine_config(config)
        return (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode()

    if relative.suffix == ".html":
        text = payload.decode()
        pattern = r'(<script[^>]+id="template-config"[^>]*>\s*)(\{.*?\})(\s*</script>)'
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            return payload
        config = json.loads(match.group(2))
        _refine_config(config)
        return (text[:match.start(2)] + json.dumps(config, indent=2, ensure_ascii=False) + text[match.end(2):]).encode()

    text = payload.decode() if relative.suffix in {".js", ".css"} else None
    if text is None:
        return payload
    path = relative.as_posix()
    if path == "families/simple-motion/components/simple-motion.js":
        text = _replace(text, """    glow: [255, 255, 255, 55],
    glowBlur: 0.9
""", """    glow: cfg.glow || [255, 255, 255, 0],
    glowBlur: cfg.glow_blur ?? 0
""")
    if path == "families/aesthetic-glow/components/glow-composition.js":
        text = _replace(text, """        word.style.filter = `blur(${((1 - progress) * 0.6).toFixed(2)}px)`;
""", """        const blur = (1 - progress) * (config.recipe.crossing_texts[index].start_blur ?? 4);
        word.style.filter = `blur(${blur.toFixed(2)}px)`;
""")
    if path == "families/aesthetic-glow/components/glow-composition.css":
        text = _replace(text, """.ag-aesthetic-purple .ag-html-word-2 {
  text-shadow:
    0 0 5px rgba(215, 30, 255, .72),
    0 0 14px rgba(160, 0, 224, .42);
}

.ag-aesthetic-strinking .ag-html-word-2 {
  text-shadow: 0 3px 6px rgba(72, 0, 0, .48);
}
""", """.ag-aesthetic-purple .ag-html-word-2,
.ag-aesthetic-strinking .ag-html-word-2 {
  text-shadow:
    0 2px 3px rgba(12, 16, 24, .22),
    0 0 5px rgba(226, 232, 242, .12);
}
""")
    if path == "families/dimensional-metal/metal-depth.js":
        text = _replace(text, """    const depth = Math.max(12, Math.round(config.extrusion / 4));
""", """    const depth = Math.max(20, Math.round(config.extrusion / 2.5));
""")
        text = _replace(text, """      layer.style.transform = `translate(${-i * 0.34}px, ${i * 0.18}px)`;
""", """      layer.style.transform = `translate3d(${-i * 0.48}px, ${i * 0.24}px, ${-i * 1.8}px)`;
""")
        text = _replace(text, """    stack.appendChild(front);

    const rim = makeTextSpan(config.text, "front-layer red-rim");
""", """    front.style.transform = "translateZ(3px)";
    stack.appendChild(front);

    const rim = makeTextSpan(config.text, "front-layer red-rim");
""")
        text = _replace(text, """    rim.style.webkitTextStroke = `${Math.max(0.5, stage(config.stroke_width) * 1.2)}px rgba(255,255,255,.55)`;
    stack.appendChild(rim);

    const shine = makeTextSpan(config.text, "front-layer shine-layer");
""", """    rim.style.webkitTextStroke = `${Math.max(0.5, stage(config.stroke_width) * 1.2)}px rgba(255,255,255,.55)`;
    rim.style.transform = "translateZ(4px)";
    stack.appendChild(rim);

    const shine = makeTextSpan(config.text, "front-layer shine-layer");
""")
        text = _replace(text, """    shine.style.webkitTextStroke = front.style.webkitTextStroke;
    stack.appendChild(shine);
""", """    shine.style.webkitTextStroke = front.style.webkitTextStroke;
    shine.style.transform = "translateZ(5px)";
    stack.appendChild(shine);
""")
        text = _replace(text, """        { opacity: 0, scale: 0.92, x: -2, y: -1, rotationY: 87, rotation: -92 },
        { opacity: 1, scale: 1, x: 0, y: 0, rotationY: 10, rotation: -4, duration: 1.55, ease: "back.out(1.08)" },
        0
      );
      tl.to(handles.group, { rotationY: 0, rotation: 0, duration: 0.35, ease: "power2.out" }, 1.1);
""", """        { opacity: 0, scale: 0.92, x: -2, y: -1, rotationX: -16, rotationY: -72, rotationZ: -8 },
        { opacity: 1, scale: 1, x: 0, y: 0, rotationX: 8, rotationY: 288, rotationZ: 2, duration: 1.55, ease: "power2.inOut" },
        0
      );
      tl.to(handles.group, { rotationX: 0, rotationY: 360, rotationZ: 0, duration: 0.35, ease: "power2.out" }, 1.55);
""")
    if path == "families/dimensional-metal/dimensional-metal.css":
        text = _replace(text, """    linear-gradient(180deg, var(--top), #fff9a8 33%, #ffe85a 54%, var(--bottom) 78%, #8a6500 100%);
""", """    linear-gradient(180deg, var(--top), #ffe078 30%, #ffc21c 52%, var(--bottom) 78%, #6f3500 100%);
""")
        text = _replace(text, """  filter: brightness(1.52) saturate(1.38) contrast(1.04);
""", """  filter: brightness(1.18) saturate(1.52) contrast(1.08);
""")
    if path == "families/water-warp/components/water-warp.js":
        text = _replace(text, """    pasteCenter(ctx, solid(strokeMask, [0, 20, 18], 0.95, 0.45), layer.width / 2 + 5, layer.height / 2 + 7);
    pasteCenter(ctx, solid(strokeMask, [0, 255, 204], 0.12, 1.6), layer.width / 2, layer.height / 2);
    pasteCenter(ctx, gradient(mask, top, bottom), layer.width / 2, layer.height / 2);
    pasteCenter(ctx, lightSweep(mask, frameIndex + 8, 110, 0.38, 0.16), layer.width / 2, layer.height / 2);
    return rowDisplace(layer, 0.8, 34, frameIndex * 0.09, 0.25);
""", """    pasteCenter(ctx, solid(strokeMask, [0, 20, 18], 0.72, 0.25), layer.width / 2 + 2, layer.height / 2 + 3);
    pasteCenter(ctx, solid(strokeMask, [0, 255, 204], 0.08, 0.7), layer.width / 2, layer.height / 2);
    pasteCenter(ctx, gradient(mask, top, bottom), layer.width / 2, layer.height / 2);
    pasteCenter(ctx, lightSweep(mask, frameIndex + 8, 110, 0.52, 0.11), layer.width / 2, layer.height / 2);
    return layer;
""")
    if path == "families/elegant-misc/components/elegant-misc.css":
        text = _replace(text, """.elegant-html-rebote .elegant-html-text::after {
""", """.elegant-html-elegant .elegant-html-text,
.elegant-html-rebote .elegant-html-text {
  position: relative;
}

.elegant-html-elegant .elegant-html-text::after,
.elegant-html-rebote .elegant-html-text::after {
""")
    return text.encode()


def _refine_config(config: dict) -> None:
    slug = config.get("slug")
    if slug not in REFINED_EFFECTS:
        return
    if slug == "3D_TEXT":
        config.update({"extrusion": 90, "back_color": [0, 82, 210, 255], "glow": 0.32})
    if slug in {"AESTHETIC_PURPLE", "AESTHETIC_STRINKING"}:
        palettes = [([255, 255, 255], [190, 196, 206]), ([246, 248, 252], [145, 153, 166])]
        for text, (top, bottom) in zip(config["recipe"]["crossing_texts"], palettes):
            text.update({"top": top, "bottom": bottom, "start_blur": 4.5, "end_blur": 0})
            text["shadow"].update({"dy": 2, "blur": 2, "opacity": 0.18, "color": [10, 14, 22]})
            text["glow"].update({"color": [224, 230, 240], "start_radius": 4, "end_radius": 0.4, "start_opacity": 0.18, "end_opacity": 0.03})
            text["halos"] = []
            if text.get("reflection"):
                text["reflection"]["opacity"] = 0.08
    if slug in {"BLUR_IN", "BOTTOM_IN", "LEFT_IN", "RIGHT_IN"}:
        offsets = {"BLUR_IN": [0, 18], "BOTTOM_IN": [0, 205], "LEFT_IN": [-390, 0], "RIGHT_IN": [390, 0]}
        config.update({
            "blur_text_in": True,
            "offset": offsets[slug],
            "start_scale": 1.02 if slug == "BLUR_IN" else 1,
            "end_scale": 1,
            "settle_frame": 24,
            "appear_frames": 4,
            "start_text_blur": 18 if slug in {"BLUR_IN", "BOTTOM_IN"} else 14,
            "end_text_blur": 0,
            "start_glow_blur": 4,
            "end_glow_blur": 0,
            "blur_glow": [255, 255, 255, 18],
        })
    if slug == "CLEAN_BLUE":
        recipe = config["recipe"]
        recipe.update({"topGlowAlpha": 0.02, "bottomGlowAlpha": 0.1, "tealShadowAlpha": 0.05, "topBlueGlowAlpha": 0.01, "bottomDepthAlpha": 0.06})
        recipe["lines"][0].update({"color": [255, 255, 255, 1], "vars": {"top-halo-opacity": 0.01, "top-halo-blur": "0.4px", "top-sweep-opacity": 0.1}})
        recipe["lines"][1].update({"color": [30, 150, 255, 1], "vars": {"bottom-halo-opacity": 0.09, "bottom-halo-blur": "1.6px", "bottom-sweep-opacity": 0.14}})
    if slug == "ESMERALD":
        text = config["recipe"]["texts"][0]
        text["shadow"].update({"dy": 3, "blur": 2, "opacity": 0.12})
        text["glows"] = [{"color": [0, 255, 135], "radius": 3, "opacity": 0.14}, {"color": [180, 255, 252], "radius": 1, "opacity": 0.08}]
        text["extrude"].update({"steps": 1, "opacity": 0.14})
        text["sweep"] = {"center": 0.52, "width": 12, "angle": -16, "opacity": 0.2}
    if slug == "fluorscent":
        text = config["recipe"]["texts"][0]
        text["shadow"].update({"dy": 2, "blur": 1, "opacity": 0})
        text["glows"] = [{"color": [176, 255, 40], "radius": 1.5, "opacity": 0.1}]
        text["extrude"].update({"steps": 1, "opacity": 0.08})
        text["reflection"]["opacity"] = 0
        text["turbulence"]["scale"] = 0
        text["blinds"]["opacity"] = 0
    if slug == "GOLD_TEXT":
        config.update({"top_color": [255, 224, 96, 255], "bottom_color": [172, 82, 0, 255], "shadow_color": [48, 22, 0, 255], "bevel": 8, "glow": 0.62})
    if slug == "OPACITY_IN":
        config.update({"fade_frames": 20, "glow": [255, 255, 255, 0], "glow_blur": 0})
    if slug == "SMOOTH_OPACITY":
        config.update({
            "fade_frames": 10,
            "main_glow": [0, 205, 230, 28],
            "main_glow_blur": 1.2,
            "main_material_noise_alpha": 0,
            "main_back_alpha": 0.1,
            "main_back_blur": 2.2,
            "main_back_scale_x": 1.03,
            "main_back_scale_y": 1.05,
            "main_chroma_alpha": 0.04,
            "small_back_alpha": 0.06,
            "small_back_blur": 1.4,
            "small_back_scale_x": 1.02,
            "small_back_scale_y": 1.05,
            "small_highlight_alpha": 0.12,
            "small_highlight_blur": 0.35,
        })


def _replace(text: str, before: str, after: str) -> str:
    if before not in text:
        raise RuntimeError("approved canonical refinement target changed")
    return text.replace(before, after, 1)


def _inject_adapter(document: str) -> str:
    injection = '<script src="/vibeedit-adapter.js"></script><style>html,body,.elegant-misc-root{background:transparent!important}</style>'
    if "</head>" not in document:
        raise RuntimeError("canonical HTML output has no head boundary")
    return document.replace("</head>", f"{injection}</head>", 1)


def _adapter() -> str:
    return r'''(() => {
  const requested = new URLSearchParams(location.search).get("text");
  if (!requested) return;
  const apply = (config) => {
    if (!config || typeof config !== "object" || (!config.slug && !config.family)) return config;
    const words = requested.trim().split(/\s+/).filter(Boolean);
    const distribute = (layers) => {
      if (!Array.isArray(layers) || !layers.length) return;
      const explicit = requested.split(/\s*[|\n]\s*/).filter(Boolean);
      const values = explicit.length === layers.length
        ? explicit
        : layers.map((_, index) => index === layers.length - 1
          ? words.slice(Math.floor(index * words.length / layers.length)).join(" ")
          : words.slice(Math.floor(index * words.length / layers.length), Math.floor((index + 1) * words.length / layers.length)).join(" "));
      layers.forEach((layer, index) => {
        if (layer && typeof layer === "object" && values[index]) layer.text = values[index];
      });
    };
    config.text = requested;
    distribute(config.text_lines);
    const recipes = [config.recipe, config.componentRecipe].filter((value) => value && typeof value === "object");
    recipes.forEach((recipe) => {
      recipe.text = requested;
      distribute(recipe.lines);
      distribute(recipe.layers);
      distribute(recipe.texts);
      distribute(recipe.crossing_texts);
    });
    return config;
  };
  const parse = JSON.parse.bind(JSON);
  JSON.parse = (value, reviver) => apply(parse(value, reviver));
  const fetchRequest = fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await fetchRequest(...args);
    const read = response.json.bind(response);
    response.json = async () => apply(await read());
    return response;
  };
})();
'''


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
