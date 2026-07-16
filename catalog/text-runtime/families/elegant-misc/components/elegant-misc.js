const W = 640;
const H = 360;
const FPS = 30;

const FONT_FILES = {
  "AbrilFatface-Regular": "AbrilFatface-Regular.ttf",
  "AVANTERegular": "AVANTE.otf",
  "AVANTE": "AVANTE.otf",
  "Bebas-Regular": "Bebas-Regular.otf",
  "Mytupi-Bold": "mytupiBOLD.ttf",
  "Poppins-Black": "Poppins-Black.ttf"
};

const maskCache = new Map();

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function easeOutCubic(value) {
  const t = clamp01(value);
  return 1 - Math.pow(1 - t, 3);
}

function easeOutBack(value) {
  const t = clamp01(value);
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}

function makeCanvas(width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width));
  canvas.height = Math.max(1, Math.round(height));
  return canvas;
}

function fontSpec(name, size) {
  return `${Math.round(size)}px "${name}"`;
}

function textLines(text) {
  const lines = String(text || "").replace(/\r/g, "\n").split("\n");
  return lines.length ? lines : [""];
}

async function loadFonts(root) {
  const faces = Object.entries(FONT_FILES).map(async ([family, file]) => {
    const face = new FontFace(family, `url("${root}${file}")`);
    await face.load();
    document.fonts.add(face);
  });
  await Promise.all(faces);
  await document.fonts.ready;
}

function drawMeasuredText(ctx, metrics, x, y, tracking) {
  for (const line of metrics.lines) {
    const lineX = x + (metrics.width - line.width) / 2;
    const baseline = y + line.y + line.ascent;
    if (tracking) {
      let cx = lineX;
      line.chars.forEach((ch, index) => {
        ctx.fillText(ch, cx, baseline);
        cx += line.widths[index] + tracking;
      });
    } else {
      ctx.fillText(line.text, lineX, baseline);
    }
  }
}

function measureText(text, font, size, tracking = 0, lineGap = 0) {
  const probe = makeCanvas(16, 16);
  const ctx = probe.getContext("2d", { willReadFrequently: true });
  ctx.font = fontSpec(font, size);
  ctx.textBaseline = "alphabetic";
  const lines = textLines(text).map((line) => {
    const measured = ctx.measureText(line);
    const chars = [...line];
    const widths = chars.map((ch) => ctx.measureText(ch).width);
    const width = tracking
      ? widths.reduce((sum, value) => sum + value, 0) + tracking * Math.max(0, chars.length - 1)
      : measured.width;
    const ascent = measured.actualBoundingBoxAscent || size * 0.78;
    const descent = measured.actualBoundingBoxDescent || size * 0.22;
    return { text: line, chars, widths, width, ascent, descent, height: ascent + descent, y: 0 };
  });
  let y = 0;
  for (const line of lines) {
    line.y = y;
    y += line.height + lineGap;
  }
  return {
    width: Math.max(1, ...lines.map((line) => line.width)),
    height: Math.max(1, y - lineGap),
    lines
  };
}

function cropAlpha(source, threshold = 1) {
  const ctx = source.getContext("2d", { willReadFrequently: true });
  const image = ctx.getImageData(0, 0, source.width, source.height);
  let minX = source.width;
  let minY = source.height;
  let maxX = -1;
  let maxY = -1;
  for (let y = 0; y < source.height; y += 1) {
    for (let x = 0; x < source.width; x += 1) {
      if (image.data[(y * source.width + x) * 4 + 3] >= threshold) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    }
  }
  if (maxX < minX || maxY < minY) return makeCanvas(1, 1);
  const out = makeCanvas(maxX - minX + 1, maxY - minY + 1);
  out.getContext("2d", { willReadFrequently: true }).drawImage(source, minX, minY, out.width, out.height, 0, 0, out.width, out.height);
  return out;
}

function textMask(text, font, size, tracking = 0, lineGap = 0) {
  const pad = 30;
  const metrics = measureText(text, font, size, tracking, lineGap);
  const out = makeCanvas(metrics.width + pad * 2, metrics.height + pad * 2);
  const ctx = out.getContext("2d", { willReadFrequently: true });
  ctx.font = fontSpec(font, size);
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = "#fff";
  drawMeasuredText(ctx, metrics, pad, pad, tracking);
  return cropAlpha(out, 2);
}

function fitMask(layer, scale = 1) {
  const targetW = Math.max(1, Math.round(layer.box[0] * scale));
  const targetH = Math.max(1, Math.round(layer.box[1] * scale));
  const key = JSON.stringify([
    layer.text,
    layer.font,
    layer.box,
    layer.tracking || 0,
    layer.line_gap || 0,
    layer.alpha_gain ?? 1.85,
    layer.alpha_threshold ?? 8,
    targetW,
    targetH
  ]);
  if (maskCache.has(key)) return maskCache.get(key);

  let lo = 4;
  let hi = 220;
  let best = null;
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    const mask = textMask(layer.text, layer.font, mid, layer.tracking || 0, layer.line_gap || 0);
    if (mask.width <= targetW && mask.height <= targetH) {
      best = mask;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  if (!best) best = textMask(layer.text, layer.font, Math.max(4, hi), layer.tracking || 0, layer.line_gap || 0);

  const fitted = makeCanvas(targetW, targetH);
  fitted.getContext("2d", { willReadFrequently: true }).drawImage(best, 0, 0, targetW, targetH);
  gainAlpha(fitted, layer.alpha_gain ?? 1.85, layer.alpha_threshold ?? 8);
  maskCache.set(key, fitted);
  return fitted;
}

function gainAlpha(canvas, gain, threshold = 0) {
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  for (let i = 3; i < image.data.length; i += 4) {
    const value = image.data[i];
    image.data[i] = value < threshold ? 0 : Math.min(255, Math.round(value * gain));
  }
  ctx.putImageData(image, 0, 0);
}

function dilateAlpha(source, radius) {
  const r = Math.max(0, Math.round(radius || 0));
  if (!r) return source;
  const ctx = source.getContext("2d", { willReadFrequently: true });
  const input = ctx.getImageData(0, 0, source.width, source.height);
  const out = makeCanvas(source.width, source.height);
  const octx = out.getContext("2d", { willReadFrequently: true });
  const output = octx.createImageData(source.width, source.height);
  for (let y = 0; y < source.height; y += 1) {
    for (let x = 0; x < source.width; x += 1) {
      let alpha = 0;
      for (let oy = -r; oy <= r; oy += 1) {
        const yy = y + oy;
        if (yy < 0 || yy >= source.height) continue;
        for (let ox = -r; ox <= r; ox += 1) {
          const xx = x + ox;
          if (xx < 0 || xx >= source.width) continue;
          alpha = Math.max(alpha, input.data[(yy * source.width + xx) * 4 + 3]);
        }
      }
      const index = (y * source.width + x) * 4;
      output.data[index] = 255;
      output.data[index + 1] = 255;
      output.data[index + 2] = 255;
      output.data[index + 3] = alpha;
    }
  }
  octx.putImageData(output, 0, 0);
  return out;
}

function seededNoise(x, y, seed) {
  const n = Math.sin(x * 12.9898 + y * 78.233 + seed * 37.719) * 43758.5453;
  return n - Math.floor(n);
}

function smoothNoise(x, y, seed) {
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const tx = x - x0;
  const ty = y - y0;
  const sx = tx * tx * (3 - 2 * tx);
  const sy = ty * ty * (3 - 2 * ty);
  const a = seededNoise(x0, y0, seed);
  const b = seededNoise(x0 + 1, y0, seed);
  const c = seededNoise(x0, y0 + 1, seed);
  const d = seededNoise(x0 + 1, y0 + 1, seed);
  return (a * (1 - sx) + b * sx) * (1 - sy) + (c * (1 - sx) + d * sx) * sy;
}

function displaceMask(source, amount, frameIndex, posterStep = 1, size = 28, seed = 0) {
  if (!amount) return source;
  const phaseFrame = Math.floor(frameIndex / posterStep) * posterStep;
  const scale = Math.max(8, size || 28);
  const ctx = source.getContext("2d", { willReadFrequently: true });
  const input = ctx.getImageData(0, 0, source.width, source.height);
  const out = makeCanvas(source.width, source.height);
  const octx = out.getContext("2d", { willReadFrequently: true });
  const output = octx.createImageData(source.width, source.height);
  for (let y = 0; y < source.height; y += 1) {
    const slow = Math.sin(y / scale + phaseFrame * 0.19 + seed * 0.31);
    const turbulent = smoothNoise(y / scale, phaseFrame / Math.max(1, posterStep), seed) * 2 - 1;
    const dx = Math.round((slow * 0.65 + turbulent * 0.35) * amount);
    for (let x = 0; x < source.width; x += 1) {
      const sx = ((x - dx) % source.width + source.width) % source.width;
      const si = (y * source.width + sx) * 4;
      const di = (y * source.width + x) * 4;
      output.data[di] = 255;
      output.data[di + 1] = 255;
      output.data[di + 2] = 255;
      output.data[di + 3] = input.data[si + 3];
    }
  }
  if (amount > 1) {
    const staged = output.data.slice();
    for (let x = 0; x < source.width; x += 1) {
      const slow = Math.sin(x / (scale * 1.18) + phaseFrame * 0.13 + seed * 0.17);
      const turbulent = smoothNoise(x / scale, phaseFrame / Math.max(1, posterStep) + 8.5, seed + 17) * 2 - 1;
      const dy = Math.round((slow * 0.7 + turbulent * 0.3) * amount * 0.45);
      for (let y = 0; y < source.height; y += 1) {
        const sy = ((y - dy) % source.height + source.height) % source.height;
        output.data[(y * source.width + x) * 4 + 3] = staged[(sy * source.width + x) * 4 + 3];
      }
    }
  }
  octx.putImageData(output, 0, 0);
  return out;
}

function rgba(values, alphaScale = 1) {
  const alpha = values.length > 3 ? values[3] : 1;
  return `rgba(${values[0]},${values[1]},${values[2]},${clamp01(alpha * alphaScale)})`;
}

function colorLayer(mask, layer, opacity) {
  const out = makeCanvas(mask.width, mask.height);
  const ctx = out.getContext("2d", { willReadFrequently: true });
  if (layer.radial) {
    const gradient = ctx.createRadialGradient(mask.width / 2, mask.height / 2, 0, mask.width / 2, mask.height / 2, Math.max(mask.width, mask.height) / 2);
    gradient.addColorStop(0, rgba(layer.gradient[0], opacity));
    gradient.addColorStop(1, rgba(layer.gradient[1], opacity));
    ctx.fillStyle = gradient;
  } else {
    const gradient = ctx.createLinearGradient(0, 0, 0, mask.height);
    gradient.addColorStop(0, rgba(layer.gradient[0], opacity));
    gradient.addColorStop(1, rgba(layer.gradient[1], opacity));
    ctx.fillStyle = gradient;
  }
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.globalCompositeOperation = "destination-in";
  ctx.drawImage(mask, 0, 0);
  return out;
}

function solidLayer(mask, color, opacity, blur = 0) {
  const out = makeCanvas(mask.width, mask.height);
  const ctx = out.getContext("2d", { willReadFrequently: true });
  ctx.save();
  if (blur) ctx.filter = `blur(${blur}px)`;
  ctx.drawImage(mask, 0, 0);
  ctx.globalCompositeOperation = "source-in";
  ctx.fillStyle = rgba(color, opacity);
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.restore();
  return out;
}

function lightSweep(mask, frameIndex, totalFrames, opacity, widthFactor = 0.07) {
  const w = mask.width;
  const h = mask.height;
  const mctx = mask.getContext("2d", { willReadFrequently: true });
  const input = mctx.getImageData(0, 0, w, h);
  const out = makeCanvas(w, h);
  const ctx = out.getContext("2d", { willReadFrequently: true });
  const image = ctx.createImageData(w, h);
  const t = frameIndex / Math.max(1, totalFrames - 1);
  const center = (t * 1.9 - 0.42) * w;
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const dist = Math.abs(x + y * 0.58 - center);
      const sweep = Math.pow(clamp01(1 - dist / Math.max(8, w * widthFactor)), 1.8);
      const index = (y * w + x) * 4;
      image.data[index] = 255;
      image.data[index + 1] = 255;
      image.data[index + 2] = 255;
      image.data[index + 3] = Math.round(sweep * input.data[index + 3] * clamp01(opacity));
    }
  }
  ctx.putImageData(image, 0, 0);
  return out;
}

function drawLayer(ctx, layer, frameIndex, totalFrames, scale, opacity, center) {
  const posterFps = layer.posterize_fps || 6;
  const step = layer.posterized ? Math.max(1, Math.round(FPS / posterFps)) : 1;
  let mask = fitMask(layer, scale);
  if (layer.turbulent) {
    mask = displaceMask(
      mask,
      layer.turbulent * scale,
      frameIndex,
      step,
      (layer.turbulent_size || 28) * scale,
      layer.turbulent_seed || 0
    );
  }

  const strokeMask = layer.stroke && layer.stroke_width > 0 ? dilateAlpha(mask, layer.stroke_width) : mask;
  const x = Math.round(center[0] - strokeMask.width / 2);
  const y = Math.round(center[1] - strokeMask.height / 2);

  if (layer.shadow && layer.shadow_opacity > 0) {
    const shadow = solidLayer(strokeMask, layer.shadow, layer.shadow_opacity * opacity, layer.shadow_radius * scale);
    ctx.drawImage(shadow, x + Math.round(layer.shadow_offset[0] * scale), y + Math.round(layer.shadow_offset[1] * scale));
  }

  if (layer.glow && layer.glow_opacity > 0) {
    const glow = solidLayer(strokeMask, layer.glow, layer.glow_opacity * opacity, layer.glow_radius * scale);
    ctx.drawImage(glow, x, y);
  }

  const fill = colorLayer(strokeMask, layer, opacity);
  ctx.drawImage(fill, x, y);

  if (layer.stroke && layer.stroke_width > 0) {
    const core = fitMask(layer, scale);
    const stroke = solidLayer(strokeMask, layer.stroke, layer.stroke_opacity * opacity);
    const sx = Math.round(center[0] - core.width / 2);
    const sy = Math.round(center[1] - core.height / 2);
    const cut = stroke.getContext("2d", { willReadFrequently: true });
    cut.globalCompositeOperation = "destination-out";
    cut.drawImage(core, sx - x, sy - y);
    ctx.drawImage(stroke, x, y);
  }

  const sweep = lightSweep(strokeMask, frameIndex + 8, totalFrames, 0.18 * opacity);
  ctx.drawImage(sweep, x, y);
}

function introOpacity(frameIndex, frames = 11) {
  return easeOutCubic(frameIndex / frames);
}

function renderBubble(ctx, recipe, frameIndex, totalFrames) {
  let scale;
  if (frameIndex <= 11) scale = 0.02 + (0.66 - 0.02) * easeOutCubic(frameIndex / 11);
  else if (frameIndex <= 23) scale = 0.66 + (0.9 - 0.66) * easeOutCubic((frameIndex - 11) / 12);
  else scale = 0.9 + (1 - 0.9) * easeOutCubic((frameIndex - 23) / 19);
  drawLayer(ctx, recipe.layers[0], frameIndex, totalFrames, scale, introOpacity(frameIndex, 10), recipe.layers[0].center);
}

function renderElegant(ctx, recipe, frameIndex, totalFrames) {
  const p = easeOutCubic(frameIndex / 18);
  const layer = recipe.layers[0];
  drawLayer(ctx, layer, frameIndex, totalFrames, 0.92 + 0.08 * p, introOpacity(frameIndex, 8), layer.center);
  if (frameIndex < 17) {
    const t = frameIndex / 17;
    ctx.save();
    ctx.filter = `blur(${5.5 * (1 - t) + 1}px)`;
    ctx.fillStyle = `rgba(226,197,125,${(170 * (1 - t)) / 255})`;
    ctx.beginPath();
    ctx.ellipse(380.5, 189.5, 23.5, 17.5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `rgba(250,238,196,${(170 * (1 - t) * 0.38) / 255})`;
    ctx.fillRect(337, 173, 47, 26);
    ctx.restore();
  }
}

function renderPosterized(ctx, recipe, frameIndex, totalFrames) {
  const layer = recipe.layers[0];
  const step = Math.max(1, Math.round(FPS / 6));
  const snap = Math.floor(frameIndex / step);
  drawLayer(
    ctx,
    layer,
    frameIndex,
    totalFrames,
    1,
    1,
    [layer.center[0] + Math.sin(snap * 1.7) * layer.jitter, layer.center[1] + Math.cos(snap * 1.3) * layer.jitter * 0.6]
  );
}

function renderRebound(ctx, recipe, frameIndex, totalFrames, big) {
  const layer = recipe.layers[0];
  const p = easeOutBack(frameIndex / 20);
  const tail = Math.max(0, 1 - frameIndex / 18);
  const scale = 0.82 + 0.18 * p;
  const y = layer.center[1] + 8 * tail * Math.cos(frameIndex * 0.42);
  drawLayer(ctx, layer, frameIndex, totalFrames, scale, introOpacity(frameIndex, 9), [layer.center[0] + 4.5 * tail, y]);
  if (tail > 0) {
    const bx = layer.center[0] + (big ? 63 : 45) * scale;
    const by = layer.center[1] + (big ? 12 : 10);
    const r = (big ? 14 : 10) * (0.7 + 0.5 * tail);
    ctx.save();
    ctx.filter = "blur(1.2px)";
    ctx.fillStyle = `rgba(116,120,120,${155 * tail / 255})`;
    ctx.beginPath();
    ctx.ellipse(bx, by, r, r, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `rgba(232,238,237,${90 * tail / 255})`;
    ctx.beginPath();
    ctx.ellipse(bx - r * 0.1, by - r * 0.25, r * 0.25, r * 0.2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

function renderTriple(ctx, recipe, frameIndex, totalFrames) {
  const p = easeOutCubic(frameIndex / 13);
  const opacity = introOpacity(frameIndex, 7);
  const dx = (1 - p) * -8;
  recipe.layers.forEach((layer, index) => {
    const localDx = dx * (index === 1 ? 1 : 1.5);
    drawLayer(ctx, layer, frameIndex, totalFrames, 1, opacity, [layer.center[0] + localDx, layer.center[1]]);
  });
}

function renderFrame(ctx, recipe, frameIndex) {
  const totalFrames = Math.round(recipe.duration * FPS);
  ctx.clearRect(0, 0, W, H);
  if (recipe.style === "bubble") renderBubble(ctx, recipe, frameIndex, totalFrames);
  else if (recipe.style === "elegant") renderElegant(ctx, recipe, frameIndex, totalFrames);
  else if (recipe.style === "posterized") renderPosterized(ctx, recipe, frameIndex, totalFrames);
  else if (recipe.style === "rebote") renderRebound(ctx, recipe, frameIndex, totalFrames, false);
  else if (recipe.style === "rebound") renderRebound(ctx, recipe, frameIndex, totalFrames, true);
  else if (recipe.style === "triple") renderTriple(ctx, recipe, frameIndex, totalFrames);
  else throw new Error(`Unknown elegant-misc style: ${recipe.style}`);
}

async function loadConfig() {
  const path = window.ELEGANT_MISC_CONFIG_PATH || `../../configs/${window.ELEGANT_MISC_SLUG}.json`;
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Could not load ${path}`);
  return response.json();
}

function installTimeline(config, ctx) {
  const compositionId = `elegant-misc-${config.slug}`;
  window.__timelines = window.__timelines || {};
  const state = { timeValue: 0 };
  const timeline = {
    paused: true,
    duration: () => config.duration,
    time(value) {
      if (value === undefined) return state.timeValue;
      state.timeValue = Math.max(0, Math.min(config.duration, value));
      renderFrame(ctx, config.recipe, Math.min(Math.round(config.duration * FPS) - 1, Math.round(state.timeValue * FPS)));
      return this;
    },
    seek(value) {
      return this.time(value);
    },
    pause() {
      return this;
    },
    progress(value) {
      if (value === undefined) return state.timeValue / config.duration;
      return this.time(value * config.duration);
    }
  };
  window.__timelines[compositionId] = timeline;
  timeline.time(0);
}

function installHtmlTimeline(config, root) {
  const stage = document.createElement("div");
  stage.className = `elegant-html-stage elegant-html-${config.recipe.style}`;
  const text = document.createElement("span");
  text.className = "elegant-html-text";
  text.textContent = config.recipe.layers[0].text;
  text.dataset.text = config.recipe.layers[0].text;
  stage.append(text);
  root.querySelector(".clip").replaceChildren(stage);
  const state = { timeValue: 0 };
  const timeline = {
    paused: true,
    duration: () => config.duration,
    time(value) {
      if (value === undefined) return state.timeValue;
      state.timeValue = Math.max(0, Math.min(config.duration, Number(value) || 0));
      const progress = easeOutCubic(Math.min(1, state.timeValue / .58));
      const bounce = config.recipe.style === "rebote" ? Math.sin(progress * Math.PI) * (1 - progress) * -8 : 0;
      text.style.opacity = Math.min(1, state.timeValue / .24).toFixed(4);
      text.style.transform = `translateY(${((1 - progress) * 16 + bounce).toFixed(2)}px) scale(${(.96 + progress * .04).toFixed(4)})`;
      text.style.setProperty("--shimmer-position", `${-140 + Math.min(1, state.timeValue / 1.15) * 280}%`);
      return this;
    },
    seek(value) {
      return this.time(value);
    },
    pause() {
      return this;
    },
    progress(value) {
      if (value === undefined) return state.timeValue / config.duration;
      return this.time(value * config.duration);
    }
  };
  window.__timelines = window.__timelines || {};
  window.__timelines[`elegant-misc-${config.slug}`] = timeline;
  timeline.time(0);
}

function fitPreviewStage(root) {
  const resize = () => {
    root.style.setProperty("--hm-preview-scale", String(Math.min(window.innerWidth / 640, window.innerHeight / 360)));
  };
  resize();
  window.addEventListener("resize", resize, { passive: true });
}

async function main() {
  await loadFonts(window.ELEGANT_MISC_FONT_ROOT || "../../assets/fonts/");
  const config = await loadConfig();
  const replacement = new URLSearchParams(location.search).get("text");
  if (replacement && config.recipe?.layers?.[0]) config.recipe.layers[0].text = replacement;
  window.__elegantMiscConfig = config;
  const root = document.getElementById("root");
  fitPreviewStage(root);
  if (config.recipe.style === "elegant" || config.recipe.style === "rebote") {
    installHtmlTimeline(config, root);
    return;
  }
  const canvas = document.getElementById("elegant-misc-canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  installTimeline(config, ctx);
}

main().catch((error) => {
  console.error(error);
  document.body.dataset.error = error.message;
});
