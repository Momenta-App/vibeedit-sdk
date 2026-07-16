import { portableMotionComponents } from "./components.generated.js";

const registry = new Map();

export function registerComponent(id, component) {
  if (!id.startsWith("vibeedit://")) throw new TypeError("motion component IDs must be stable vibeedit:// identifiers");
  registry.set(id, component);
}

export function renderComponent(id, props, frame, context) {
  const component = registry.get(id);
  if (!component) throw new Error(`unknown motion component: ${id}`);
  if (!Number.isInteger(frame)) throw new TypeError("motion frame must be an integer");
  return component(Object.freeze({ ...props }), frame, Object.freeze({ ...context }));
}

export function documentForFrame(spec, frame, options = {}) {
  const layers = spec.timeline.tracks
    .flatMap((track) => track.items.map((item) => ({ ...item, trackOrder: track.order })))
    .filter((item) => item.kind === "motion" && frame >= item.placement.startFrame && frame < item.placement.startFrame + item.placement.durationFrames)
    .sort((left, right) => left.trackOrder - right.trackOrder)
    .map((item) => renderComponent(item.componentId, item.props, frame - item.placement.startFrame, {
      assetBaseUrl: options.assetBaseUrl,
      durationFrames: item.placement.durationFrames,
      fps: spec.canvas.frameRate ? spec.canvas.frameRate.numerator / spec.canvas.frameRate.denominator : 30,
      width: spec.canvas.width,
      height: spec.canvas.height,
    }))
    .join("\n");
  return `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}*{box-sizing:border-box}</style></head><body>${layers}</body></html>`;
}

export function trackingPointAt(points, frame, fallback = { x: 0.5, y: 0.5 }) {
  const valid = Array.isArray(points)
    ? points.filter((point) => Number.isInteger(point?.frame) && Number.isFinite(point?.x) && Number.isFinite(point?.y)).sort((left, right) => left.frame - right.frame)
    : [];
  if (!valid.length) return Object.freeze({ ...fallback });
  if (frame <= valid[0].frame) return Object.freeze({ x: clamp(valid[0].x), y: clamp(valid[0].y) });
  if (frame >= valid.at(-1).frame) return Object.freeze({ x: clamp(valid.at(-1).x), y: clamp(valid.at(-1).y) });
  const rightIndex = valid.findIndex((point) => point.frame >= frame);
  const left = valid[rightIndex - 1];
  const right = valid[rightIndex];
  const progress = (frame - left.frame) / Math.max(1, right.frame - left.frame);
  return Object.freeze({ x: clamp(left.x + (right.x - left.x) * progress), y: clamp(left.y + (right.y - left.y) * progress) });
}

registerComponent("vibeedit://text/negative", (props, frame, context) => {
  const words = String(props.text ?? "").trim().split(/\s+/).filter(Boolean);
  const progress = Math.max(0, Math.min(1, (frame + 1) / Math.max(1, context.durationFrames)));
  const revealed = Math.max(1, Math.ceil(progress * words.length));
  const scale = 1.14 - 0.14 * (1 - Math.pow(1 - progress, 3));
  return `<section data-vibeedit-component="negative" data-frame="${frame}" style="position:absolute;inset:0;display:grid;place-items:center;padding:6%;overflow:hidden;background:${cssColor(props.background, "transparent")};color:${cssColor(props.foreground, "#fff")}"><div style="font-family:'Arial Black','Avenir Next Condensed',sans-serif;font-weight:950;font-size:clamp(56px,13vw,220px);line-height:.78;letter-spacing:-.07em;text-align:center;text-transform:uppercase;transform:scale(${scale.toFixed(6)});transform-origin:center">${words.map((word, index) => `<span style="display:${index < revealed ? "inline" : "none"}">${escapeHtml(word)}</span>`).join(" ")}</div></section>`;
});

registerComponent("vibeedit://text/caption-rail", (props, frame, context) => {
  const words = String(props.text ?? "").trim().split(/\s+/).filter(Boolean);
  const progress = Math.max(0, Math.min(0.999999, (frame + 1) / Math.max(1, context.durationFrames)));
  const active = Math.min(words.length - 1, Math.floor(progress * words.length));
  return `<section data-vibeedit-component="caption-rail" data-frame="${frame}" style="position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center;padding:0 8% 8%;pointer-events:none"><div style="max-width:88%;padding:.42em .68em .5em;border-radius:.28em;background:${cssColor(props.background, "rgba(8,10,14,.82)")};color:${cssColor(props.foreground, "#fff")};font-family:Inter,Arial,sans-serif;font-weight:800;font-size:clamp(28px,4.8vw,72px);line-height:1.06;letter-spacing:-.035em;text-align:center;box-shadow:0 .12em .55em rgba(0,0,0,.34)">${words.map((word, index) => `<span style="color:${index === active ? cssColor(props.accent, "#ecff4d") : "inherit"};transform:${index === active ? "scale(1.04)" : "none"};display:inline-block">${escapeHtml(word)}</span>`).join(" ")}</div></section>`;
});

for (const component of portableMotionComponents) {
  registerComponent(component.id, (props, frame, context) => renderPortableComponent(component, props, frame, context));
}

function renderPortableComponent(component, props, frame, context) {
  if (component.canonical && context.assetBaseUrl) return renderCanonicalComponent(component, props, frame, context);
  const progress = Math.max(0, Math.min(1, (frame + 1) / Math.max(1, context.durationFrames)));
  const eased = 1 - Math.pow(1 - progress, 3);
  const foreground = cssColor(props.foreground, component.palette.foreground);
  const accent = cssColor(props.accent, component.palette.accent);
  const background = cssColor(props.background, "transparent");
  const raw = String(props.text ?? component.defaultText).trim();
  const words = raw.split(/\s+/).filter(Boolean);
  const visible = component.motion === "scramble" ? scramble(raw, progress, frame) : raw;
  const phase = frame % 4;
  const family = familyStyle(component.family, foreground, accent, progress, phase);
  const motion = motionStyle(component.motion, progress, eased, phase, accent, props, frame);
  const content = component.motion === "editorial"
    ? words.map((word, index) => `<span style="font-family:${index % 2 ? "Georgia,serif" : "Arial,sans-serif"};font-size:${index % 2 ? "1.18em" : ".76em"};font-style:${index % 2 ? "italic" : "normal"}">${escapeHtml(word)}</span>`).join(" ")
    : escapeHtml(visible);
  const particles = component.motion === "burst"
    ? Array.from({ length: 8 }, (_, index) => `<i style="position:absolute;left:50%;top:50%;width:.12em;height:.12em;border-radius:50%;background:${index % 2 ? accent : foreground};transform:rotate(${index * 45}deg) translate(${(eased * 4.2).toFixed(3)}em);opacity:${(1 - progress).toFixed(4)}"></i>`).join("")
    : "";
  return `<section data-vibeedit-component="${escapeAttribute(component.id.split("/").at(-1))}" data-family="${escapeAttribute(component.family)}" data-frame="${frame}" style="position:absolute;inset:0;display:flex;align-items:${component.kind === "caption" ? "flex-end" : "center"};justify-content:center;padding:${component.kind === "caption" ? "0 7% 8%" : "7%"};overflow:hidden;pointer-events:none;background:${background}"><div style="position:relative;max-width:94%;color:${foreground};font-family:'Arial Black','Avenir Next',Arial,sans-serif;font-weight:900;font-size:clamp(32px,${component.kind === "caption" ? "6vw" : "10vw"},180px);line-height:.94;letter-spacing:-.045em;text-align:center;text-transform:${component.kind === "caption" ? "none" : "uppercase"};${family}${motion}">${content}${particles}</div></section>`;
}

function renderCanonicalComponent(component, props, frame, context) {
  const source = new URL(component.canonical.entry, context.assetBaseUrl);
  source.searchParams.set("alpha", "1");
  source.searchParams.set("render", "1");
  source.searchParams.set("transparent", "1");
  const text = String(props.text ?? component.defaultText).trim();
  if (text && normalizeText(text) !== normalizeText(component.defaultText)) source.searchParams.set("text", text);
  const time = frame / Math.max(1, context.fps ?? component.canonical.fps ?? 30);
  return `<section data-vibeedit-component="${escapeAttribute(component.id.split("/").at(-1))}" data-family="${escapeAttribute(component.family)}" data-frame="${frame}" style="position:absolute;inset:0;overflow:hidden;pointer-events:none;background:${cssColor(props.background, "transparent")}"><span style="position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)">${escapeHtml(text)}</span><iframe data-vibeedit-canonical="true" data-vibeedit-time="${time.toFixed(6)}" title="${escapeAttribute(component.name)}" src="${escapeHtml(source.href)}" style="position:absolute;inset:0;width:100%;height:100%;border:0;background:transparent;pointer-events:none" tabindex="-1"></iframe></section>`;
}

function familyStyle(family, foreground, accent, progress, phase) {
  if (family === "aesthetic-glow") return `background:linear-gradient(180deg,${foreground},${accent});color:transparent;background-clip:text;-webkit-background-clip:text;filter:drop-shadow(0 0 ${(0.08 + progress * 0.18).toFixed(3)}em ${accent});`;
  if (family === "dimensional-metal") return `background:linear-gradient(180deg,#fff 0%,${foreground} 42%,${accent} 100%);color:transparent;background-clip:text;-webkit-background-clip:text;text-shadow:.035em .055em 0 ${accent},.07em .1em 0 #111;transform-style:preserve-3d;`;
  if (family === "analog-glitch") return `text-shadow:${phase % 2 ? ".035em" : "-.035em"} 0 ${accent},${phase % 2 ? "-.025em" : ".025em"} .02em #27e8ff;filter:contrast(1.18);`;
  if (family === "rainbow-trippy") return `background:linear-gradient(90deg,#ff3155,#ffd23f,#2ee6a6,#4b7bff,#d44bff);color:transparent;background-clip:text;-webkit-background-clip:text;filter:hue-rotate(${(progress * 180).toFixed(2)}deg);`;
  if (family === "water-warp") return `color:${foreground};filter:blur(${((1 - progress) * 0.08).toFixed(4)}em) drop-shadow(0 .08em .12em ${accent});`;
  if (family === "elegant-misc") return `font-family:Georgia,'Times New Roman',serif;font-weight:700;letter-spacing:.01em;color:${foreground};text-shadow:0 .04em .16em ${accent};`;
  if (family === "apple-clean") return `font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;font-weight:750;letter-spacing:-.055em;color:${foreground};text-shadow:0 .06em .18em rgba(0,0,0,.22);`;
  return `color:${foreground};`;
}

function motionStyle(motion, progress, eased, phase, accent, props, frame) {
  if (motion === "wipe") return `clip-path:inset(0 ${((1 - eased) * 100).toFixed(3)}% 0 0);`;
  if (motion === "pop") return `transform:scale(${(0.55 + eased * 0.45).toFixed(5)});opacity:${eased.toFixed(5)};`;
  if (motion === "slam") return `transform:translateX(${((1 - eased) * (phase % 2 ? -34 : 34)).toFixed(3)}%) scale(${(1.28 - eased * 0.28).toFixed(5)});opacity:${eased.toFixed(5)};`;
  if (motion === "glitch") return `transform:translate(${phase - 1.5}px,${1.5 - phase}px);text-shadow:${phase - 2}px 0 #ff285c,${2 - phase}px 0 #25e6ff;`;
  if (motion === "gradient") return `background:linear-gradient(90deg,${accent},#fff,${accent});background-size:220% 100%;background-position:${(100 - progress * 200).toFixed(3)}% 0;color:transparent;background-clip:text;-webkit-background-clip:text;transform:scale(${(0.9 + eased * 0.1).toFixed(5)});`;
  if (motion === "highlight") return `background:${accent};padding:.13em .22em;border-radius:.12em;color:#fff;clip-path:inset(0 ${((1 - eased) * 100).toFixed(3)}% 0 0);`;
  if (motion === "glow") return `color:${accent};text-shadow:0 0 .08em ${accent},0 0 .32em ${accent};opacity:${eased.toFixed(5)};`;
  if (motion === "parallax") return `text-shadow:.035em .045em 0 ${accent},.07em .09em 0 rgba(0,0,0,.5);transform:perspective(700px) rotateY(${((1 - eased) * -18).toFixed(3)}deg);`;
  if (motion === "pill") return `background:${accent};padding:.24em .52em;border-radius:999px;color:#101217;transform:scaleX(${(0.72 + eased * 0.28).toFixed(5)});`;
  if (motion === "texture" || motion === "texture-mask") return `background:repeating-linear-gradient(135deg,${accent} 0 .12em,#fff .12em .2em,${accent} .2em .34em);background-size:220% 220%;background-position:${(progress * 100).toFixed(3)}% ${(100 - progress * 100).toFixed(3)}%;color:transparent;background-clip:text;-webkit-background-clip:text;filter:contrast(1.15);`;
  if (motion === "weight") return `font-weight:${Math.round(300 + eased * 600)};letter-spacing:${((1 - eased) * 0.08 - 0.03).toFixed(4)}em;`;
  if (motion === "difference") return `mix-blend-mode:difference;color:#fff;`;
  if (motion === "face-follow") {
    const point = trackingPointAt(props.trackingFrames, frame, { x: 0.5 + Math.sin(progress * Math.PI * 2) * 0.18, y: 0.5 });
    return `position:absolute;left:${(point.x * 100).toFixed(4)}%;top:${(point.y * 100).toFixed(4)}%;mix-blend-mode:difference;color:#fff;transform:translate(-50%,-50%);`;
  }
  if (motion === "morph") return `filter:blur(${(Math.sin(progress * Math.PI) * 0.16).toFixed(4)}em) contrast(1.4);transform:scale(${(1 + Math.sin(progress * Math.PI) * 0.08).toFixed(5)});`;
  if (motion === "shimmer") return `background:linear-gradient(110deg,${accent} 20%,#fff 45%,${accent} 70%);background-size:240% 100%;background-position:${(120 - progress * 240).toFixed(3)}% 0;color:transparent;background-clip:text;-webkit-background-clip:text;`;
  if (motion === "creed") return `transform:perspective(800px) rotateY(${((1 - eased) * -12).toFixed(3)}deg) skewX(-3deg) scale(${(0.86 + eased * 0.14).toFixed(5)});text-shadow:.035em .055em 0 ${accent};`;
  return `transform:translateY(${((1 - eased) * 0.55).toFixed(4)}em) scale(${(0.82 + eased * 0.18).toFixed(5)});opacity:${eased.toFixed(5)};`;
}

function scramble(value, progress, frame) {
  const glyphs = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  const count = Math.floor(value.length * progress);
  return [...value].map((character, index) => index < count || /\s/.test(character) ? character : glyphs[(index * 17 + frame * 13) % glyphs.length]).join("");
}

function escapeHtml(value) { return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
function escapeAttribute(value) { return escapeHtml(String(value)).replaceAll(";", ""); }
function cssColor(value, fallback) {
  const candidate = String(value ?? fallback).trim();
  return /^(#[0-9a-f]{3,8}|rgba?\([\d\s.,%+-]+\)|hsla?\([\d\s.,%+-]+\)|transparent|white|black)$/i.test(candidate) ? escapeAttribute(candidate) : fallback;
}
function clamp(value) { return Math.max(0, Math.min(1, value)); }
function normalizeText(value) { return value.normalize("NFKC").replace(/\s+/g, " ").trim().toLocaleLowerCase(); }
