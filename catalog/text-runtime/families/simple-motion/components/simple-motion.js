const W = 640;
const H = 360;
const FPS = 30;

const fontFiles = {
  "Mytupi-Bold": "mytupiBOLD.ttf",
  "AVANTE": "AVANTE.otf",
  "Bebas-Regular": "Bebas-Regular.otf",
  "BirdsofParadise-PersonaluseOnly": "Birds-of-Paradise.ttf",
  "Poppins-Black": "Poppins-Black.ttf",
  "Poppins-BlackItalic": "Poppins-BlackItalic.ttf"
};

function clamp(v, lo = 0, hi = 1) {
  return Math.max(lo, Math.min(hi, v));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function easeOutCubic(t) {
  t = clamp(t);
  return 1 - Math.pow(1 - t, 3);
}

function easeOutQuint(t) {
  t = clamp(t);
  return 1 - Math.pow(1 - t, 5);
}

function smoothstep(edge0, edge1, x) {
  if (edge0 === edge1) return x >= edge1 ? 1 : 0;
  const t = clamp((x - edge0) / (edge1 - edge0));
  return t * t * (3 - 2 * t);
}

function color(values, alphaScale = 1) {
  const v = values.slice();
  if (v.length === 3) v.push(255);
  if (Math.max(v[0], v[1], v[2]) <= 1) {
    v[0] *= 255;
    v[1] *= 255;
    v[2] *= 255;
  }
  const alpha = v[3] <= 1 ? v[3] * 255 : v[3];
  return [Math.round(v[0]), Math.round(v[1]), Math.round(v[2]), Math.round(clamp(alpha / 255 * alphaScale) * 255)];
}

function css(c, alphaScale = 1) {
  const v = color(c, alphaScale);
  return `rgba(${v[0]},${v[1]},${v[2]},${v[3] / 255})`;
}

function canvas(w, h) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return c;
}

function clear(ctx) {
  ctx.clearRect(0, 0, W, H);
}

function fontSpec(font, size) {
  return `${Math.round(size)}px "${font}"`;
}

function textLines(text) {
  const lines = String(text || "").replace(/\r/g, "\n").split("\n").filter(Boolean);
  return lines.length ? lines : [""];
}

function makeTextCanvas(text, font, size, opts = {}) {
  const tracking = opts.tracking || 0;
  const lineSpacing = opts.lineSpacing || 0;
  const pad = opts.pad ?? 32;
  const probe = canvas(10, 10);
  const pctx = probe.getContext("2d", { willReadFrequently: true });
  pctx.font = fontSpec(font, size);
  pctx.textBaseline = "alphabetic";
  const lines = textLines(text);
  const metrics = lines.map((line) => {
    const chars = [...line];
    const widths = chars.map((ch) => pctx.measureText(ch).width);
    const measured = pctx.measureText(line);
    const width = tracking ? widths.reduce((a, b) => a + b, 0) + tracking * Math.max(0, chars.length - 1) : measured.width;
    const ascent = measured.actualBoundingBoxAscent || size * 0.78;
    const descent = measured.actualBoundingBoxDescent || size * 0.22;
    return { line, chars, widths, width, ascent, descent, height: ascent + descent };
  });
  const maxWidth = Math.max(1, ...metrics.map((m) => m.width));
  const totalHeight = metrics.reduce((sum, m) => sum + m.height, 0) + lineSpacing * Math.max(0, metrics.length - 1);
  const out = canvas(maxWidth + pad * 2, totalHeight + pad * 2);
  const ctx = out.getContext("2d", { willReadFrequently: true });
  ctx.font = fontSpec(font, size);
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = opts.fill || "#fff";
  let y = pad;
  for (const m of metrics) {
    const x0 = pad + (maxWidth - m.width) / 2;
    const baseline = y + m.ascent;
    if (tracking) {
      let x = x0;
      m.chars.forEach((ch, i) => {
        ctx.fillText(ch, x, baseline);
        x += m.widths[i] + tracking;
      });
    } else {
      ctx.fillText(m.line, x0, baseline);
    }
    y += m.height + lineSpacing;
  }
  return out;
}

function erodeAlpha(source, radius) {
  const r = Math.max(0, Math.round(radius || 0));
  if (!r) return source;
  const out = canvas(source.width, source.height);
  const sctx = source.getContext("2d", { willReadFrequently: true });
  const octx = out.getContext("2d", { willReadFrequently: true });
  const input = sctx.getImageData(0, 0, source.width, source.height);
  const output = octx.createImageData(source.width, source.height);
  const w = source.width;
  const h = source.height;
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const idx = (y * w + x) * 4;
      let minAlpha = 255;
      for (let oy = -r; oy <= r; oy += 1) {
        const yy = y + oy;
        if (yy < 0 || yy >= h) {
          minAlpha = 0;
          break;
        }
        for (let ox = -r; ox <= r; ox += 1) {
          const xx = x + ox;
          if (xx < 0 || xx >= w) {
            minAlpha = 0;
            break;
          }
          minAlpha = Math.min(minAlpha, input.data[(yy * w + xx) * 4 + 3]);
        }
        if (!minAlpha) break;
      }
      output.data[idx] = 255;
      output.data[idx + 1] = 255;
      output.data[idx + 2] = 255;
      output.data[idx + 3] = minAlpha;
    }
  }
  octx.putImageData(output, 0, 0);
  return out;
}

function drawText(ctx, text, font, size, center, opts = {}) {
  const pad = Math.ceil(Math.max(opts.blur || 0, opts.glowBlur || 0) * 3 + 34);
  const drawAlpha = opts.alpha ?? 1;
  const layerAlpha = opts.singleAlpha ? 1 : drawAlpha;
  let base = makeTextCanvas(text, font, size, { tracking: opts.tracking || 0, lineSpacing: opts.lineSpacing || 0, pad, fill: "#fff" });
  base = erodeAlpha(base, opts.erode || 0);
  const preClipStart = opts.preClipStart !== undefined ? clamp(opts.preClipStart) : 0;
  const preClipEnd = opts.preClipEnd !== undefined
    ? clamp(opts.preClipEnd)
    : (opts.preClipProgress !== undefined ? clamp(opts.preClipProgress) : 1);
  if (preClipStart > 0 || preClipEnd < 1) {
    const clipped = canvas(base.width, base.height);
    const cctx = clipped.getContext("2d", { willReadFrequently: true });
    const sx = Math.round(base.width * preClipStart);
    const sw = Math.max(1, Math.round(base.width * Math.max(0, preClipEnd - preClipStart)));
    cctx.drawImage(base, sx, 0, sw, base.height, sx, 0, sw, base.height);
    base = clipped;
  }
  const layer = canvas(base.width, base.height);
  const lctx = layer.getContext("2d", { willReadFrequently: true });
  if (opts.glow && opts.glowBlur) {
    lctx.save();
    lctx.filter = `blur(${opts.glowBlur}px)`;
    lctx.drawImage(base, 0, 0);
    lctx.globalCompositeOperation = "source-in";
    lctx.fillStyle = css(opts.glow, layerAlpha);
    lctx.fillRect(0, 0, layer.width, layer.height);
    lctx.restore();
  }
  lctx.save();
  if (opts.blur) lctx.filter = `blur(${opts.blur}px)`;
  lctx.drawImage(base, 0, 0);
  lctx.globalCompositeOperation = "source-in";
  if (opts.gradient) {
    const g = opts.gradient.horizontal
      ? lctx.createLinearGradient(0, 0, layer.width, 0)
      : lctx.createLinearGradient(0, 0, 0, layer.height);
    g.addColorStop(0, css(opts.gradient.top, layerAlpha));
    g.addColorStop(1, css(opts.gradient.bottom, layerAlpha));
    lctx.fillStyle = g;
  } else {
    lctx.fillStyle = css(opts.fill || [255, 255, 255, 1], layerAlpha);
  }
  lctx.fillRect(0, 0, layer.width, layer.height);
  lctx.restore();
  if (opts.innerHighlightAlpha) {
    const highlight = canvas(layer.width, layer.height);
    const hctx = highlight.getContext("2d", { willReadFrequently: true });
    hctx.drawImage(base, 0, 0);
    hctx.globalCompositeOperation = "source-in";
    const y0 = layer.height * (opts.innerHighlightStart ?? 0.08);
    const y1 = layer.height * (opts.innerHighlightEnd ?? 0.58);
    const g = hctx.createLinearGradient(0, y0, 0, y1);
    g.addColorStop(0, `rgba(255,255,255,${clamp(opts.innerHighlightAlpha)})`);
    g.addColorStop(0.55, `rgba(235,252,255,${clamp(opts.innerHighlightAlpha * 0.36)})`);
    g.addColorStop(1, "rgba(255,255,255,0)");
    hctx.fillStyle = g;
    hctx.fillRect(0, 0, layer.width, layer.height);
    lctx.save();
    lctx.globalCompositeOperation = "screen";
    lctx.drawImage(highlight, 0, 0);
    lctx.restore();
  }
  if (opts.materialNoiseAlpha) {
    const texture = canvas(layer.width, layer.height);
    const tctx = texture.getContext("2d", { willReadFrequently: true });
    const image = tctx.createImageData(layer.width, layer.height);
    const cell = Math.max(1, Math.round(opts.materialNoiseCell || 2));
    const alphaMax = Math.round(clamp(opts.materialNoiseAlpha) * 255);
    const seed = opts.materialNoiseSeed || 1;
    for (let yy = 0; yy < layer.height; yy += 1) {
      for (let xx = 0; xx < layer.width; xx += 1) {
        const v = noiseValue(Math.floor(xx / cell), Math.floor(yy / cell), seed);
        const idx = (yy * layer.width + xx) * 4;
        const shade = 180 + Math.round(v * 75);
        image.data[idx] = shade;
        image.data[idx + 1] = 245;
        image.data[idx + 2] = 255;
        image.data[idx + 3] = Math.round(alphaMax * Math.abs(v - 0.5) * 2);
      }
    }
    tctx.putImageData(image, 0, 0);
    tctx.globalCompositeOperation = "destination-in";
    tctx.drawImage(base, 0, 0);
    lctx.save();
    lctx.globalCompositeOperation = opts.materialNoiseMode || "screen";
    lctx.drawImage(texture, 0, 0);
    lctx.restore();
  }
  if (opts.sweepAlpha) {
    const sweepLayer = canvas(layer.width, layer.height);
    const sctx = sweepLayer.getContext("2d", { willReadFrequently: true });
    sctx.drawImage(base, 0, 0);
    sctx.globalCompositeOperation = "source-in";
    const sweepCenter = layer.width * clamp(opts.sweepProgress ?? 0.5);
    const sweepWidth = Math.max(1, layer.width * (opts.sweepWidth ?? 0.18));
    const g = sctx.createLinearGradient(sweepCenter - sweepWidth, 0, sweepCenter + sweepWidth, layer.height);
    g.addColorStop(0, "rgba(255,255,255,0)");
    g.addColorStop(0.46, `rgba(255,255,255,${clamp(opts.sweepAlpha * 0.32)})`);
    g.addColorStop(0.54, `rgba(255,255,255,${clamp(opts.sweepAlpha)})`);
    g.addColorStop(1, "rgba(255,255,255,0)");
    sctx.fillStyle = g;
    sctx.fillRect(0, 0, layer.width, layer.height);
    lctx.save();
    lctx.globalCompositeOperation = "screen";
    lctx.drawImage(sweepLayer, 0, 0);
    lctx.restore();
  }
  ctx.save();
  const scaleX = opts.scaleX ?? 1;
  const scaleY = opts.scaleY ?? 1;
  ctx.globalAlpha = drawAlpha;
  ctx.translate(center[0], center[1]);
  ctx.scale(scaleX, scaleY);
  const dx = Math.round(-layer.width / 2);
  const dy = Math.round(-layer.height / 2);
  const clipStart = opts.clipStart !== undefined ? clamp(opts.clipStart) : 0;
  const clipEnd = opts.clipEnd !== undefined
    ? clamp(opts.clipEnd)
    : (opts.clipProgress !== undefined ? clamp(opts.clipProgress) : 1);
  if (clipStart > 0 || clipEnd < 1) {
    const sx = Math.round(layer.width * clipStart);
    const sw = Math.max(1, Math.round(layer.width * Math.max(0, clipEnd - clipStart)));
    ctx.drawImage(layer, sx, 0, sw, layer.height, dx + sx, dy, sw, layer.height);
  } else {
    ctx.drawImage(layer, dx, dy);
  }
  ctx.restore();
}

function roundRect(ctx, x, y, w, h, r) {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

function drawRounded(ctx, x, y, w, h, r, fill, opts = {}) {
  ctx.save();
  if (opts.blur) ctx.filter = `blur(${opts.blur}px)`;
  ctx.globalAlpha = opts.alpha ?? 1;
  roundRect(ctx, x, y, w, h, r);
  ctx.fillStyle = fill;
  ctx.fill();
  if (opts.stroke) {
    ctx.lineWidth = opts.lineWidth || 1;
    ctx.strokeStyle = opts.stroke;
    ctx.stroke();
  }
  ctx.restore();
}

function drawWarpedRounded(ctx, x, y, w, h, r, fill, opts = {}, cfg = {}, seed = 1) {
  const amp = cfg.card_warp_amp || 0;
  const jitter = cfg.card_warp_jitter || 0;
  if (!amp && !jitter) {
    drawRounded(ctx, x, y, w, h, r, fill, opts);
    return;
  }
  const pad = Math.ceil((opts.blur || 0) * 3 + (opts.lineWidth || 0) + Math.max(amp, jitter) + 5);
  const layer = canvas(w + pad * 2, h + pad * 2);
  const lctx = layer.getContext("2d", { willReadFrequently: true });
  drawRounded(lctx, pad, pad, w, h, r, fill, opts);
  const strip = Math.max(1, Math.round(cfg.card_warp_strip || 2));
  const period = cfg.card_warp_period || 17;
  ctx.save();
  for (let yy = 0; yy < layer.height; yy += strip) {
    const hh = Math.min(strip, layer.height - yy);
    const wave = Math.sin((yy + seed * 11) / period) * amp;
    const rough = (noiseValue(Math.floor(yy / strip), seed, seed + 41) - 0.5) * jitter;
    ctx.drawImage(layer, 0, yy, layer.width, hh, x - pad + wave + rough, y - pad + yy, layer.width, hh);
  }
  ctx.restore();
}

function withLocalSkew(ctx, x, y, skewX = 0, skewY = 0, draw) {
  ctx.save();
  ctx.translate(x, y);
  ctx.transform(1, skewY, skewX, 1, 0, 0);
  draw();
  ctx.restore();
}

function drawOrganicEdgeErosion(ctx, x, y, w, h, r, alpha = 0, cfg = {}, seed = 1) {
  if (!alpha) return;
  const top = cfg.card_edge_cut_top ?? 1;
  const side = cfg.card_edge_cut_side ?? 0.55;
  const bottom = cfg.card_edge_cut_bottom ?? 0.35;
  const count = cfg.card_edge_cut_count || 10;
  ctx.save();
  roundRect(ctx, x - 2, y - 2, w + 4, h + 4, r + 2);
  ctx.clip();
  ctx.globalCompositeOperation = "destination-out";
  ctx.fillStyle = `rgba(0,0,0,${clamp(alpha)})`;
  for (let i = 0; i < count; i += 1) {
    const n = noiseValue(i, seed, seed + 13);
    const xx = x + 6 + n * (w - 18);
    const ww = 8 + noiseValue(i, seed + 3, seed) * 28;
    const hh = 2 + noiseValue(i, seed + 5, seed) * 5;
    if (top) {
      ctx.globalAlpha = top * (0.42 + n * 0.58);
      ctx.beginPath();
      ctx.ellipse(xx, y - 1 + noiseValue(i, seed + 7, seed) * 3, ww / 2, hh, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    if (bottom && i % 3 === 0) {
      ctx.globalAlpha = bottom * (0.35 + n * 0.65);
      ctx.fillRect(xx, y + h - 2 + noiseValue(i, seed + 11, seed) * 2, ww * 0.7, hh);
    }
  }
  for (let i = 0; i < Math.max(4, Math.round(count * 0.55)); i += 1) {
    const n = noiseValue(i, seed + 17, seed);
    const yy = y + 4 + n * (h - 12);
    const hh = 5 + noiseValue(i, seed + 19, seed) * 16;
    ctx.globalAlpha = side * (0.36 + n * 0.64);
    if (i % 2 === 0) {
      ctx.fillRect(x - 1, yy, 2 + noiseValue(i, seed + 23, seed) * 5, hh);
    } else {
      ctx.fillRect(x + w - 4 - noiseValue(i, seed + 29, seed) * 4, yy, 6, hh);
    }
  }
  ctx.restore();
}

function drawRoundedFilmDamage(ctx, x, y, w, h, r, alpha = 0, cfg = {}, seed = 1) {
  if (!alpha) return;
  ctx.save();
  roundRect(ctx, x, y, w, h, r);
  ctx.clip();
  ctx.globalCompositeOperation = "screen";
  const streaks = cfg.card_edge_streaks || 18;
  for (let i = 0; i < streaks; i += 1) {
    const n = noiseValue(i, seed, seed + 3);
    const side = n > 0.48 ? "top" : "left";
    const a = alpha * (0.16 + n * 0.38);
    ctx.fillStyle = `rgba(245,250,255,${a})`;
    if (side === "top") {
      const xx = x + 4 + noiseValue(i, seed + 7, seed) * (w - 12);
      const ww = 4 + noiseValue(i, seed + 13, seed) * 26;
      ctx.fillRect(xx, y + 1 + noiseValue(i, seed + 19, seed) * 5, ww, 1.2);
    } else {
      const yy = y + 5 + noiseValue(i, seed + 23, seed) * (h - 12);
      const hh = 3 + noiseValue(i, seed + 29, seed) * 18;
      ctx.fillRect(x + 1 + noiseValue(i, seed + 31, seed) * 4, yy, 1.4, hh);
    }
  }
  ctx.globalCompositeOperation = "multiply";
  ctx.fillStyle = `rgba(20,12,8,${alpha * 0.22})`;
  for (let i = 0; i < Math.max(6, Math.round(streaks * 0.55)); i += 1) {
    const xx = x + 5 + noiseValue(i, seed + 37, seed) * (w - 16);
    const yy = y + 5 + noiseValue(i, seed + 43, seed) * (h - 12);
    ctx.fillRect(xx, yy, 5 + noiseValue(i, seed + 47, seed) * 16, 1);
  }
  ctx.restore();
}

function noiseValue(x, y, seed = 1) {
  let n = (x * 374761393 + y * 668265263 + seed * 1442695041) | 0;
  n = (n ^ (n >>> 13)) * 1274126177;
  return ((n ^ (n >>> 16)) >>> 0) / 4294967295;
}

function drawRoundedNoise(ctx, x, y, w, h, r, alpha = 0, seed = 1, cell = 2) {
  if (!alpha) return;
  const iw = Math.max(1, Math.round(w));
  const ih = Math.max(1, Math.round(h));
  const layer = canvas(iw, ih);
  const lctx = layer.getContext("2d", { willReadFrequently: true });
  const image = lctx.createImageData(iw, ih);
  const stride = Math.max(1, Math.round(cell));
  for (let yy = 0; yy < ih; yy += 1) {
    for (let xx = 0; xx < iw; xx += 1) {
      const v = noiseValue(Math.floor(xx / stride), Math.floor(yy / stride), seed);
      const idx = (yy * iw + xx) * 4;
      const shade = v > 0.54 ? 255 : 0;
      image.data[idx] = shade;
      image.data[idx + 1] = shade;
      image.data[idx + 2] = shade;
      image.data[idx + 3] = Math.round(alpha * Math.abs(v - 0.5) * 2);
    }
  }
  lctx.putImageData(image, 0, 0);
  ctx.save();
  roundRect(ctx, x, y, w, h, r);
  ctx.clip();
  ctx.globalCompositeOperation = "screen";
  ctx.drawImage(layer, x, y, w, h);
  ctx.restore();
}

function drawRoundedSweep(ctx, x, y, w, h, r, sweepX, sweepW, alpha = 0, skew = 0) {
  if (!alpha || !sweepW) return;
  ctx.save();
  roundRect(ctx, x, y, w, h, r);
  ctx.clip();
  const cx = x + sweepX;
  const half = sweepW / 2;
  const g = ctx.createLinearGradient(cx - half - h * skew, y, cx + half + h * skew, y + h);
  g.addColorStop(0, "rgba(255,255,255,0)");
  g.addColorStop(0.42, `rgba(255,255,255,${clamp(alpha / 510)})`);
  g.addColorStop(0.53, `rgba(255,255,255,${clamp(alpha / 255)})`);
  g.addColorStop(0.64, `rgba(180,248,255,${clamp(alpha / 720)})`);
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(x, y, w, h);
  ctx.restore();
}

function drawRoundedRampGlow(ctx, x, y, w, h, r, alpha = 0, cfg = {}) {
  if (!alpha) return;
  ctx.save();
  roundRect(ctx, x, y, w, h, r);
  ctx.clip();
  ctx.globalCompositeOperation = "screen";
  const glow = ctx.createRadialGradient(
    x + w * (cfg.ramp_glow_x ?? 0.68),
    y + h * (cfg.ramp_glow_y ?? 0.33),
    0,
    x + w * (cfg.ramp_glow_x ?? 0.68),
    y + h * (cfg.ramp_glow_y ?? 0.33),
    w * (cfg.ramp_glow_radius ?? 0.58)
  );
  glow.addColorStop(0, `rgba(36,220,255,${clamp(alpha / 255)})`);
  glow.addColorStop(0.42, `rgba(0,154,188,${clamp(alpha / 510)})`);
  glow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(x, y, w, h);
  ctx.globalCompositeOperation = "multiply";
  const shade = ctx.createLinearGradient(x, y + h * 0.32, x, y + h);
  shade.addColorStop(0, "rgba(255,255,255,0)");
  shade.addColorStop(1, `rgba(0,10,12,${clamp((cfg.ramp_shadow_alpha ?? 42) / 255)})`);
  ctx.fillStyle = shade;
  ctx.fillRect(x, y, w, h);
  ctx.restore();
}

function drawRoundedEdgeDamage(ctx, x, y, w, h, r, alpha = 0, cfg = {}) {
  if (!alpha) return;
  const leftColors = cfg.edge_damage_left || [
    [32, 255, 82, 145],
    [238, 38, 78, 105],
    [54, 128, 255, 80]
  ];
  const rightColors = cfg.edge_damage_right || [
    [16, 55, 255, 110],
    [15, 220, 90, 74],
    [225, 30, 92, 72]
  ];
  const drawSide = (side, colors, seed) => {
    const baseX = side === "left" ? x + 1 : x + w - 4;
    const direction = side === "left" ? 1 : -1;
    const segments = cfg.edge_damage_segments || 18;
    for (let i = 0; i < segments; i += 1) {
      const n = noiseValue(i, seed, seed + 17);
      const yy = y + 3 + i * (h - 7) / segments + (n - 0.5) * 6;
      const hh = 3 + noiseValue(i, seed + 3, seed) * 15;
      const ww = 1.4 + noiseValue(i, seed + 7, seed) * 3.2;
      const inset = noiseValue(i, seed + 11, seed) * 3.5;
      const c = colors[i % colors.length];
      ctx.fillStyle = css(c, alpha * (0.42 + n * 0.58));
      ctx.fillRect(baseX + direction * inset, yy, direction * ww, hh);
    }
  };
  ctx.save();
  roundRect(ctx, x, y, w, h, r);
  ctx.clip();
  ctx.globalCompositeOperation = "screen";
  ctx.filter = `blur(${cfg.edge_damage_blur || 0.35}px)`;
  drawSide("left", leftColors, 231);
  drawSide("right", rightColors, 337);
  const rimAlpha = alpha * (cfg.edge_rim_alpha ?? 0.36);
  if (rimAlpha) {
    ctx.filter = `blur(${cfg.edge_rim_blur ?? 0.6}px)`;
    ctx.lineWidth = cfg.edge_rim_width ?? 1.4;
    for (const [offset, side, c] of [
      [1.5, "left", leftColors[0]],
      [3.2, "left", leftColors[1]],
      [1.4, "right", rightColors[0]],
      [3.4, "right", rightColors[2]]
    ]) {
      ctx.strokeStyle = css(c, rimAlpha);
      ctx.beginPath();
      const xx = side === "left" ? x + offset : x + w - offset;
      ctx.moveTo(xx, y + 4);
      for (let i = 0; i <= 8; i += 1) {
        const yy = y + 4 + i * (h - 8) / 8;
        const wobble = (noiseValue(i, offset * 11, side === "left" ? 701 : 709) - 0.5) * 2.6;
        ctx.lineTo(xx + (side === "left" ? wobble : -wobble), yy);
      }
      ctx.stroke();
    }
  }
  if (cfg.edge_top_scuff_alpha) {
    ctx.filter = `blur(${cfg.edge_top_scuff_blur ?? 0.5}px)`;
    ctx.globalCompositeOperation = "screen";
    for (let i = 0; i < 12; i += 1) {
      const n = noiseValue(i, 61, 811);
      const xx = x + 8 + n * (w - 42);
      const len = 14 + noiseValue(i, 67, 823) * 42;
      const yy = y + 1 + noiseValue(i, 71, 827) * 5;
      ctx.fillStyle = css(i % 2 ? leftColors[0] : rightColors[0], alpha * cfg.edge_top_scuff_alpha * (0.28 + n * 0.72));
      ctx.fillRect(xx, yy, len, 1.1);
    }
  }
  if (cfg.edge_chip_alpha) {
    ctx.filter = "none";
    ctx.globalCompositeOperation = "screen";
    for (let i = 0; i < 14; i += 1) {
      const n = noiseValue(i, 91, 887);
      const side = n > 0.52 ? 1 : -1;
      const c = side < 0 ? leftColors[(i + 1) % leftColors.length] : rightColors[(i + 2) % rightColors.length];
      const xx = side < 0 ? x + 1 + noiseValue(i, 97, 891) * 7 : x + w - 8 - noiseValue(i, 101, 907) * 7;
      const yy = y + 6 + noiseValue(i, 103, 911) * (h - 15);
      const ww = 2 + noiseValue(i, 107, 919) * 8;
      const hh = 1 + noiseValue(i, 109, 929) * 3;
      ctx.fillStyle = css(c, alpha * cfg.edge_chip_alpha * (0.36 + n * 0.64));
      ctx.fillRect(xx, yy, ww, hh);
    }
  }
  ctx.restore();
}

function drawPillGlossDamage(ctx, x, y, w, h, r, alpha = 0, cfg = {}) {
  if (!alpha) return;
  ctx.save();
  roundRect(ctx, x, y, w, h, r);
  ctx.clip();
  ctx.globalAlpha = alpha;
  ctx.globalCompositeOperation = "screen";
  const scratches = cfg.lower_gloss_scratches || [
    [0.18, 0.40, 0.36, 0.06, 90],
    [0.42, 0.28, 0.28, 0.045, 74],
    [0.66, 0.36, 0.22, 0.05, 58]
  ];
  for (const [cx, cy, sw, sh, a] of scratches) {
    const g = ctx.createRadialGradient(x + w * cx, y + h * cy, 0, x + w * cx, y + h * cy, w * sw);
    g.addColorStop(0, `rgba(255,255,255,${clamp(a / 255)})`);
    g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.save();
    ctx.scale(1, sh / Math.max(0.001, sw));
    ctx.fillStyle = g;
    ctx.fillRect(x, (y + h * cy) / (sh / Math.max(0.001, sw)) - h, w, h * 2);
    ctx.restore();
  }
  ctx.globalCompositeOperation = "multiply";
  ctx.fillStyle = "rgba(0,0,0,0.28)";
  for (let i = 0; i < 11; i += 1) {
    const n = noiseValue(i, 19, 503);
    const xx = x + 8 + n * (w - 22);
    const yy = y + h * (0.48 + (noiseValue(i, 23, 509) - 0.5) * 0.22);
    ctx.fillRect(xx, yy, 10 + noiseValue(i, 31, 521) * 22, 1);
  }
  ctx.globalCompositeOperation = "screen";
  ctx.filter = `blur(${cfg.lower_gloss_scratch_blur ?? 0.35}px)`;
  ctx.strokeStyle = `rgba(255,255,255,${clamp((cfg.lower_gloss_scratch_alpha ?? 42) / 255)})`;
  ctx.lineWidth = 1;
  for (let i = 0; i < 9; i += 1) {
    const n = noiseValue(i, 43, 541);
    const yy = y + h * (0.25 + noiseValue(i, 47, 547) * 0.45);
    const xx = x + 14 + n * (w - 58);
    const len = 16 + noiseValue(i, 53, 557) * 36;
    ctx.beginPath();
    ctx.moveTo(xx, yy);
    ctx.quadraticCurveTo(xx + len * 0.45, yy - 2 + n * 4, xx + len, yy + (noiseValue(i, 59, 563) - 0.5) * 3);
    ctx.stroke();
  }
  ctx.restore();
}

function drawCapsule(ctx, center, w, h, alpha, cfg) {
  const x = center[0] - w / 2;
  const y = center[1] - h / 2;
  drawRounded(ctx, x, y, w, h, h / 2, css(cfg.blob_color || [156, 156, 150, 245]), {
    alpha,
    blur: cfg.blob_blur || 0.8,
    stroke: css(cfg.rim_color || [255, 255, 245, 58]),
    lineWidth: 2
  });
  drawRounded(ctx, x + h * 0.12, y + h * 0.15, w - h * 0.24, h * 0.45, h * 0.22, "rgba(255,255,245,0.18)", {
    alpha,
    blur: 2.4
  });
}

function drawBlobMotion(ctx, frame, cfg) {
  const settle = cfg.settle_frame || 40;
  const raw = clamp(frame / Math.max(1, settle));
  const p = easeOutQuint(raw);
  const startScale = cfg.start_scale ?? 2.1;
  const scale = lerp(startScale, cfg.end_scale ?? 1, p);
  const offset = cfg.offset || [0, 0];
  const cx = cfg.center[0] + lerp(offset[0], 0, p);
  const cy = cfg.center[1] + lerp(offset[1], 0, p);
  const alpha = smoothstep(0, cfg.appear_frames ?? 1, frame);
  if (cfg.blur_text_in) {
    drawText(ctx, cfg.text, cfg.font, cfg.font_size * scale, [cx, cy], {
      fill: cfg.blur_color || cfg.color,
      alpha,
      blur: lerp(cfg.start_text_blur || 10, cfg.end_text_blur || 0, p),
      glow: cfg.blur_glow || [255, 255, 255, 65],
      glowBlur: lerp(cfg.start_glow_blur || 12, cfg.end_glow_blur || 0.4, p),
      tracking: cfg.tracking || 0
    });
    return;
  }
  if (raw < 1) {
    const defaultW = cfg.text.length * cfg.font_size * 0.8;
    const startW = cfg.blob_start_width || defaultW * startScale;
    const startH = cfg.blob_start_height || cfg.font_size * 3.2;
    const endW = cfg.blob_end_width || defaultW + 16;
    const endH = cfg.blob_end_height || cfg.font_size + 8;
    const blobAlpha = alpha * (1 - smoothstep(cfg.blob_fade_start || 0.64, 1, raw));
    drawCapsule(ctx, [cx, cy], lerp(startW, endW, p), lerp(startH, endH, p), blobAlpha, cfg);
  }
  drawText(ctx, cfg.text, cfg.font, cfg.font_size, cfg.center, {
    fill: cfg.color,
    alpha: alpha * smoothstep(cfg.crisp_start || 0.42, cfg.crisp_end || 0.9, raw),
    glow: cfg.text_glow || [255, 255, 255, 24],
    glowBlur: cfg.text_glow_blur || 0.6,
    tracking: cfg.tracking || 0
  });
}

function drawOpacity(ctx, frame, cfg) {
  drawText(ctx, cfg.text, cfg.font, cfg.font_size, cfg.center, {
    fill: cfg.color,
    alpha: smoothstep(0, cfg.fade_frames || 3, frame),
    glow: [255, 255, 255, 55],
    glowBlur: 0.9
  });
}

function drawFast(ctx, frame, cfg) {
  const p = easeOutCubic(frame / Math.max(1, cfg.settle_frame || 44));
  const offset = cfg.offset || [-112, 0];
  const center = [cfg.center[0] + lerp(offset[0], 0, p), cfg.center[1] + lerp(offset[1], 0, p)];
  drawText(ctx, cfg.text, cfg.font, cfg.font_size, center, {
    alpha: smoothstep(0, 2, frame),
    gradient: { top: [255, 22, 22, 255], bottom: [80, 0, 0, 255], horizontal: true },
    glow: [0, 0, 0, 180],
    glowBlur: 1.4,
    tracking: -1
  });
}

function drawSmoothBounce(ctx, frame, cfg) {
  const yKeys = cfg.y_keyframes || [
    [0, cfg.center[1] - 112],
    [2, cfg.center[1] - 112],
    [4, cfg.center[1]],
    [7, cfg.center[1]],
    [10, cfg.center[1] - 2],
    [14, cfg.center[1]],
    [Math.round((cfg.duration || 7) * FPS), cfg.center[1]]
  ];
  let y = cfg.center[1];
  for (let i = 0; i < yKeys.length - 1; i += 1) {
    const [f0, y0] = yKeys[i];
    const [f1, y1] = yKeys[i + 1];
    if (frame >= f0 && frame <= f1) {
      y = lerp(y0, y1, easeOutCubic((frame - f0) / Math.max(1, f1 - f0)));
      break;
    }
    if (frame > f1) y = y1;
  }
  const white = smoothstep(cfg.white_start_frame ?? 2, cfg.white_end_frame ?? 12, frame);
  const c = [
    lerp(255, color(cfg.color)[0], white),
    lerp(0, color(cfg.color)[1], white),
    lerp(0, color(cfg.color)[2], white),
    255
  ];
  const finalGlow = cfg.final_glow || [255, 255, 255, 60];
  const redGlow = cfg.red_glow || [255, 0, 0, 90];
  drawText(ctx, cfg.text, cfg.font, cfg.font_size, [cfg.center[0], y], {
    fill: c,
    alpha: smoothstep(0, 2, frame) * (cfg.main_alpha ?? 1),
    lineSpacing: cfg.line_spacing || -8,
    glow: white < 1 ? redGlow : finalGlow,
    glowBlur: white < 1 ? (cfg.red_glow_blur || 1.2) : (cfg.final_glow_blur || 1.2),
    erode: cfg.text_erode || 0
  });
}

function drawSmoothOpacity(ctx, frame, cfg) {
  const p = easeOutCubic(frame / Math.max(1, cfg.settle_frame || 28));
  const y = lerp(cfg.start_y || 100, cfg.center[1], p);
  const alpha = smoothstep(0, cfg.fade_frames || 1, frame);
  const glyphDerivedSupports = Boolean(cfg.glyph_derived_supports);
  const topW = cfg.top_width || 406;
  const topH = cfg.top_height || 74;
  const topX = 319 - topW / 2;
  const topY = y - topH / 2;
  if (!glyphDerivedSupports) {
    withLocalSkew(ctx, topX, topY, cfg.top_skew_x || 0, cfg.top_skew_y || 0, () => {
      drawRounded(ctx, -5, 6, topW + 10, topH + 8, (cfg.top_radius || 10) + 2, "rgba(0,70,74,0.58)", {
        alpha: alpha * (cfg.top_shadow_alpha ?? 1),
        blur: 2.4
      });
      drawRounded(ctx, 0, 0, topW, topH, cfg.top_radius || 10, css(cfg.top_fill || [5, 40, 42, 235]), { alpha });
      drawRoundedRampGlow(ctx, 0, 0, topW, topH, cfg.top_radius || 10, alpha * (cfg.ramp_glow_alpha || 0), cfg);
      drawRounded(ctx, 0, 0, topW, cfg.top_highlight_height || 31, cfg.top_radius || 10, css(cfg.top_highlight || [0, 68, 92, 52]), { alpha, blur: 1.2 });
      drawRoundedSweep(ctx, 0, 0, topW, topH, cfg.top_radius || 10, cfg.top_sweep_x || topW * 0.72, cfg.top_sweep_width || 0, alpha * (cfg.top_sweep_alpha || 0), cfg.top_sweep_skew || 0);
      drawRoundedNoise(ctx, 0, 0, topW, topH, cfg.top_radius || 10, alpha * (cfg.top_noise_alpha || 0), 43, cfg.top_noise_cell || 2);
      drawRoundedEdgeDamage(ctx, 0, 0, topW, topH, cfg.top_radius || 10, alpha * (cfg.edge_damage_alpha || 0), cfg);
      drawRounded(ctx, 1, 1, topW - 3, topH - 3, cfg.top_radius || 10, "transparent", {
        alpha,
        stroke: css(cfg.top_bevel_hi || [210, 245, 255, 18]),
        lineWidth: 2
      });
      if (cfg.top_bevel_low) {
        drawRounded(ctx, 1, topH - (cfg.top_bottom_bevel_height || 14), topW - 3, cfg.top_bottom_bevel_height || 14, cfg.top_radius || 10, "transparent", {
          alpha,
          stroke: css(cfg.top_bevel_low),
          lineWidth: cfg.top_bottom_bevel_width || 2
        });
      }
      ctx.save();
      ctx.globalAlpha = alpha * 0.85;
      ctx.fillStyle = css(cfg.left_accent || [230, 28, 68, 78]);
      ctx.beginPath();
      ctx.moveTo(0, 10);
      ctx.lineTo(10, 3);
      ctx.lineTo(13, topH - 4);
      ctx.lineTo(0, topH - 12);
      ctx.fill();
      ctx.fillStyle = css(cfg.right_accent || [0, 76, 196, 100]);
      ctx.beginPath();
      ctx.moveTo(topW - 18, 1);
      ctx.lineTo(topW - 2, 8);
      ctx.lineTo(topW - 9, topH - 7);
      ctx.lineTo(topW - 24, topH - 1);
      ctx.fill();
      ctx.restore();
    });
  }
  const lowerW = cfg.lower_width || 202;
  const lowerH = cfg.lower_height || 48;
  const lowerFollow = cfg.lower_follow_top ?? 1;
  const lowerTargetY = y + (cfg.lower_offset_y || 51);
  const lowerFixedY = cfg.lower_center_y ?? (cfg.center[1] + (cfg.lower_offset_y || 51));
  const lowerY = lerp(lowerFixedY, lowerTargetY, lowerFollow);
  const lowerX = 320 - lowerW / 2;
  if (!glyphDerivedSupports) {
    drawRounded(ctx, lowerX - 2, lowerY - lowerH / 2 + 3, lowerW + 4, lowerH + 5, cfg.lower_radius || 22, "rgba(22,22,22,0.8)", { alpha, blur: 2 });
    drawRounded(ctx, lowerX, lowerY - lowerH / 2, lowerW, lowerH, cfg.lower_radius || 22, css(cfg.lower_fill || [45, 45, 45, 240]), { alpha });
    drawRounded(ctx, lowerX, lowerY - lowerH / 2, lowerW, cfg.lower_highlight_height || 23, cfg.lower_radius || 22, css(cfg.lower_highlight || [245, 245, 245, 66]), { alpha, blur: 1 });
    drawRoundedSweep(ctx, lowerX, lowerY - lowerH / 2, lowerW, lowerH, cfg.lower_radius || 22, cfg.lower_sweep_x || lowerW * 0.5, cfg.lower_sweep_width || 0, alpha * (cfg.lower_sweep_alpha || 0), cfg.lower_sweep_skew || 0);
    drawRoundedNoise(ctx, lowerX, lowerY - lowerH / 2, lowerW, lowerH, cfg.lower_radius || 22, alpha * (cfg.lower_noise_alpha || 0), 79, cfg.lower_noise_cell || 2);
    drawPillGlossDamage(ctx, lowerX, lowerY - lowerH / 2, lowerW, lowerH, cfg.lower_radius || 22, alpha * (cfg.lower_gloss_damage_alpha || 0), cfg);
    ctx.save();
    ctx.globalAlpha = alpha * ((cfg.lower_center_gloss_alpha || 118) / 255);
    ctx.filter = `blur(${cfg.lower_center_gloss_blur || 9}px)`;
    ctx.fillStyle = "white";
    ctx.beginPath();
    ctx.ellipse(320, lowerY + (cfg.lower_center_gloss_y || -3), (cfg.lower_center_gloss_width || 168) / 2, (cfg.lower_center_gloss_height || 30) / 2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    if (cfg.lower_bottom_rim_alpha) {
      ctx.save();
      roundRect(ctx, lowerX, lowerY - lowerH / 2, lowerW, lowerH, cfg.lower_radius || 22);
      ctx.clip();
      ctx.globalCompositeOperation = "screen";
      const rim = ctx.createLinearGradient(lowerX, lowerY + lowerH * 0.08, lowerX, lowerY + lowerH / 2);
      rim.addColorStop(0, "rgba(255,255,255,0)");
      rim.addColorStop(0.72, `rgba(255,255,255,${clamp(cfg.lower_bottom_rim_alpha * alpha)})`);
      rim.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = rim;
      ctx.fillRect(lowerX, lowerY - lowerH / 2, lowerW, lowerH);
      ctx.restore();
    }
  }
  const mainCenter = [319 + (cfg.main_text_offset_x || 0), y + (cfg.main_text_offset_y || 3)];
  const smallY = cfg.small_text_follow_lower
    ? lowerY + (cfg.small_text_lower_offset_y ?? -4)
    : y + (cfg.small_text_offset_y || 47);
  if (glyphDerivedSupports) {
    drawText(ctx, cfg.text, cfg.font, cfg.main_text_size || 72, [mainCenter[0] - 1, mainCenter[1] + 2], {
      fill: cfg.main_back_fill || [0, 38, 42, 205],
      alpha: alpha * (cfg.main_back_alpha ?? 0.78),
      blur: cfg.main_back_blur ?? 4.6,
      scaleX: cfg.main_back_scale_x ?? 1.05,
      scaleY: cfg.main_back_scale_y ?? 1.1,
      tracking: cfg.tracking || 0
    });
    for (const rim of cfg.main_chroma_rims || [
      [-3, 0, [255, 28, 82, 96]],
      [3, 0, [20, 72, 255, 104]],
      [0, -2, [42, 255, 102, 70]]
    ]) {
      drawText(ctx, cfg.text, cfg.font, cfg.main_text_size || 72, [mainCenter[0] + rim[0], mainCenter[1] + rim[1]], {
        fill: rim[2],
        alpha: alpha * (cfg.main_chroma_alpha ?? 0.78),
        blur: cfg.main_chroma_blur ?? 0.7,
        tracking: cfg.tracking || 0
      });
    }
    drawText(ctx, cfg.text, cfg.font, cfg.small_text_size || 24, [320, smallY + 2], {
      fill: cfg.small_back_fill || [54, 54, 54, 220],
      alpha: alpha * (cfg.small_back_alpha ?? 0.78),
      blur: cfg.small_back_blur ?? 3.2,
      scaleX: cfg.small_back_scale_x ?? 1.08,
      scaleY: cfg.small_back_scale_y ?? 1.3,
      tracking: cfg.small_tracking || 1
    });
    if (cfg.small_highlight_alpha) {
      drawText(ctx, cfg.text, cfg.font, cfg.small_text_size || 24, [320, smallY - 1], {
        fill: cfg.small_highlight_fill || [255, 255, 255, 255],
        alpha: alpha * cfg.small_highlight_alpha,
        blur: cfg.small_highlight_blur ?? 1.1,
        scaleX: cfg.small_highlight_scale_x ?? 1.02,
        scaleY: cfg.small_highlight_scale_y ?? 1,
        tracking: cfg.small_tracking || 1,
        innerHighlightAlpha: cfg.small_inner_highlight_alpha || 0
      });
    }
  }
  drawText(ctx, cfg.text, cfg.font, cfg.main_text_size || 72, mainCenter, {
    alpha: alpha * (cfg.main_text_alpha ?? 1),
    singleAlpha: cfg.text_single_alpha || false,
    gradient: { top: cfg.main_top || [0, 178, 202, 255], bottom: cfg.main_bottom || [160, 232, 255, 255] },
    glow: cfg.main_glow || [0, 205, 230, 64],
    glowBlur: cfg.main_glow_blur || 2.2,
    sweepAlpha: cfg.main_sweep_alpha || 0,
    sweepProgress: cfg.main_sweep_progress || 0.58,
    sweepWidth: cfg.main_sweep_width || 0.18,
    innerHighlightAlpha: cfg.main_inner_highlight_alpha || 0,
    innerHighlightStart: cfg.main_inner_highlight_start,
    innerHighlightEnd: cfg.main_inner_highlight_end,
    materialNoiseAlpha: cfg.main_material_noise_alpha || 0,
    materialNoiseCell: cfg.main_material_noise_cell || 2,
    materialNoiseSeed: cfg.main_material_noise_seed || 1207,
    tracking: cfg.tracking || 0,
    erode: cfg.main_text_erode || 0
  });
  drawText(ctx, cfg.text, cfg.font, cfg.small_text_size || 24, [320, smallY], {
    alpha: alpha * (cfg.small_text_alpha ?? 1),
    singleAlpha: cfg.text_single_alpha || false,
    gradient: { top: cfg.small_top || [255, 255, 255, 255], bottom: cfg.small_bottom || [86, 86, 86, 255] },
    tracking: cfg.small_tracking || 1,
    erode: cfg.small_text_erode || 0
  });
}

function drawSmoothUp(ctx, frame, cfg) {
  const p = easeOutCubic(frame / Math.max(1, cfg.settle_frame || 26));
  const x = lerp(cfg.center[0] + (cfg.start_offset_x || -72), cfg.center[0], p);
  const y = lerp(cfg.center[1] + (cfg.start_offset_y || 16), cfg.center[1], p);
  const blur = lerp(cfg.glow_blur_start || 10, cfg.glow_blur_end || 0.8, p);
  const reveal = smoothstep(cfg.reveal_start_frame ?? 1, cfg.reveal_end_frame ?? 12, frame);
  const trailHold = smoothstep(cfg.trail_start_frame ?? 1, cfg.trail_full_frame ?? 9, frame);
  const trailFade = 1 - (cfg.trail_decay ?? 0.72) * smoothstep(cfg.trail_decay_start ?? 16, cfg.trail_decay_end ?? 34, frame);
  const frontierStart = clamp(reveal - (cfg.frontier_width || 0.16));
  const frontierEnd = clamp(reveal + (cfg.frontier_ahead || 0.11));
  if (cfg.frontier_glow_alpha) {
    drawText(ctx, cfg.text, cfg.font, cfg.font_size, [x + (cfg.frontier_offset_x || 18), y + (cfg.frontier_offset_y || 1)], {
      fill: cfg.frontier_color || cfg.glow_color || [255, 255, 255, 255],
      alpha: trailHold * trailFade * (cfg.frontier_glow_alpha || 0),
      singleAlpha: cfg.text_single_alpha || false,
      blur: cfg.frontier_blur || 11,
      preClipStart: frontierStart,
      preClipEnd: frontierEnd,
      scaleX: cfg.frontier_scale_x || 1.18,
      erode: cfg.text_erode || 0
    });
  }
  drawText(ctx, cfg.text, cfg.font, cfg.font_size, [x - (cfg.trail_offset_x || 9), y + (cfg.trail_offset_y || 1)], {
    fill: cfg.trail_color || [255, 255, 255, 72],
    alpha: trailHold * trailFade * (cfg.trail_alpha || 0.46),
    singleAlpha: cfg.text_single_alpha || false,
    blur: cfg.trail_blur || 5.4,
    preClipProgress: cfg.trail_clip === false ? undefined : reveal,
    scaleX: cfg.trail_scale_x || 1,
    erode: cfg.text_erode || 0
  });
  drawText(ctx, cfg.text, cfg.font, cfg.font_size, [x, y], {
    fill: cfg.color,
    alpha: smoothstep(cfg.main_start_frame ?? 3, cfg.main_full_frame ?? 14, frame) * (cfg.main_alpha ?? 1),
    singleAlpha: cfg.text_single_alpha || false,
    glow: cfg.glow_color || [255, 255, 255, 0.62],
    glowBlur: blur,
    preClipProgress: cfg.main_clip === false ? undefined : reveal,
    sweepAlpha: cfg.main_sweep_alpha || 0,
    sweepProgress: cfg.main_sweep_progress || reveal,
    sweepWidth: cfg.main_sweep_width || 0.14,
    erode: cfg.text_erode || 0
  });
}

function drawZoomWord(ctx, frame, cfg) {
  const p = easeOutCubic(frame / Math.max(1, cfg.settle_frame || 24));
  const scale = lerp((cfg.start_scale || 0.88) * (cfg.final_scale || 1), cfg.final_scale || 1, p);
  const y = lerp(cfg.center[1] + (cfg.start_offset_y || -16), cfg.center[1], p);
  const alpha = smoothstep(0, cfg.fade_frames || 5, frame);
  const lx = cfg.center[0] + (cfg.group_offset_x || 0) - (cfg.layer_size?.[0] || 320) * scale / 2;
  const ly = y - (cfg.layer_size?.[1] || 184) * scale / 2;
  const s = (v) => v * scale;
  const rect = (xy, size, r, fill, opts = {}, warped = true, seed = 1) => {
    const xx = lx + s(xy[0]);
    const yy = ly + s(xy[1]);
    const ww = s(size[0]);
    const hh = s(size[1]);
    const draw = warped ? drawWarpedRounded : drawRounded;
    draw(ctx, xx, yy, ww, hh, s(r), fill, { ...opts, alpha: (opts.alpha ?? 1) * alpha }, cfg, seed);
    if (warped) drawOrganicEdgeErosion(ctx, xx, yy, ww, hh, s(r), alpha * (cfg.card_edge_cut_alpha || 0), cfg, seed + 173);
    drawRoundedFilmDamage(ctx, xx, yy, ww, hh, s(r), alpha * (cfg.card_edge_alpha || 0), cfg, seed + 97);
  };
  const noise = (xy, size, r, noiseAlpha, seed) => drawRoundedNoise(ctx, lx + s(xy[0]), ly + s(xy[1]), s(size[0]), s(size[1]), s(r), alpha * (noiseAlpha || 0), seed, cfg.noise_cell || 2);
  const sweep = (xy, size, r, sweepX, sweepW, sweepAlpha) => drawRoundedSweep(ctx, lx + s(xy[0]), ly + s(xy[1]), s(size[0]), s(size[1]), s(r), s(sweepX || 0), s(sweepW || 0), alpha * (sweepAlpha || 0));
  rect(cfg.back_shadow_xy || [32, 44], cfg.back_shadow_size || [232, 82], cfg.back_shadow_radius || 15, css(cfg.back_shadow || [0, 0, 0, 210]), { blur: s(cfg.back_shadow_blur || 5.6) }, false);
  rect(cfg.upper_xy || [24, 22], cfg.upper_size || [190, 29], cfg.upper_radius || 11, css(cfg.upper_fill || [62, 65, 62, 206]), {}, true, 17);
  rect(cfg.upper_xy || [24, 22], [cfg.upper_size?.[0] || 190, cfg.upper_highlight_height || 10], cfg.upper_radius || 11, css(cfg.upper_highlight || [218, 232, 255, 44]), {}, true, 23);
  sweep(cfg.upper_xy || [24, 22], cfg.upper_size || [190, 29], cfg.upper_radius || 11, cfg.upper_sweep_x || 116, cfg.upper_sweep_width || 36, cfg.upper_sweep_alpha || 0);
  noise(cfg.upper_xy || [24, 22], cfg.upper_size || [190, 29], cfg.upper_radius || 11, cfg.upper_noise_alpha || 0, 101);
  rect(cfg.left_xy || [22, 35], cfg.left_size || [216, 64], cfg.left_radius || 16, css(cfg.left_fill || [37, 37, 32, 232]), {
    stroke: css(cfg.left_rim || [245, 252, 255, 64]),
    lineWidth: s(cfg.left_rim_width || 2)
  }, true, 31);
  rect(cfg.left_xy || [22, 35], [cfg.left_size?.[0] || 216, cfg.left_highlight_height || 24], cfg.left_radius || 16, css(cfg.left_highlight || [102, 104, 100, 78]), { blur: 1 }, true, 37);
  sweep(cfg.left_xy || [22, 35], cfg.left_size || [216, 64], cfg.left_radius || 16, cfg.left_sweep_x || 118, cfg.left_sweep_width || 42, cfg.left_sweep_alpha || 0);
  noise(cfg.left_xy || [22, 35], cfg.left_size || [216, 64], cfg.left_radius || 16, cfg.left_noise_alpha || 0, 131);
  rect(cfg.right_shadow_xy || [117, 64], cfg.right_shadow_size || [174, 84], cfg.right_shadow_radius || 13, css(cfg.right_shadow || [62, 0, 58, 205]), { blur: s(cfg.right_shadow_blur || 8.2) }, false);
  rect(cfg.right_xy || [116, 57], cfg.right_size || [168, 68], cfg.right_radius || 17, css(cfg.right_fill || [96, 0, 92, 236]), {
    stroke: css(cfg.right_rim || [255, 210, 255, 58]),
    lineWidth: s(cfg.right_rim_width || 2)
  }, true, 43);
  rect(cfg.right_xy || [116, 57], [cfg.right_size?.[0] || 168, cfg.right_highlight_height || 25], cfg.right_radius || 17, css(cfg.right_highlight || [238, 0, 202, 110]), { blur: 1 }, true, 47);
  sweep(cfg.right_xy || [116, 57], cfg.right_size || [168, 68], cfg.right_radius || 17, cfg.right_sweep_x || 66, cfg.right_sweep_width || 32, cfg.right_sweep_alpha || 0);
  noise(cfg.right_xy || [116, 57], cfg.right_size || [168, 68], cfg.right_radius || 17, cfg.right_noise_alpha || 0, 181);
  drawText(ctx, "aesthetic", "Poppins-Black", s(cfg.aesthetic_size || 37), [lx + s(cfg.aesthetic_center?.[0] || 118), ly + s(cfg.aesthetic_center?.[1] || 68)], {
    alpha,
    tracking: s(cfg.aesthetic_tracking || -2),
    gradient: { top: cfg.aesthetic_top || [255, 255, 232, 255], bottom: cfg.aesthetic_bottom || [200, 184, 126, 255] }
  });
  drawText(ctx, "purple", "Poppins-Black", s(cfg.purple_size || 38), [lx + s(cfg.purple_center?.[0] || 196), ly + s(cfg.purple_center?.[1] || 94)], {
    alpha,
    tracking: s(cfg.purple_tracking || -2),
    gradient: { top: cfg.purple_top || [248, 32, 226, 255], bottom: cfg.purple_bottom || [124, 0, 150, 255] },
    glow: cfg.purple_glow || [255, 0, 255, 116],
    glowBlur: s(cfg.purple_glow_blur || 3.4)
  });
}

const renderers = {
  blob_motion: drawBlobMotion,
  opacity: drawOpacity,
  fast: drawFast,
  smooth_bounce: drawSmoothBounce,
  smooth_opacity: drawSmoothOpacity,
  smooth_up: drawSmoothUp,
  zoom_word: drawZoomWord
};

async function loadFonts(cfg) {
  const needed = new Set([cfg.font]);
  if (cfg.kind === "zoom_word") needed.add("Poppins-Black");
  const entries = Object.entries(fontFiles).filter(([family]) => !needed.size || needed.has(family));
  const loads = entries.map(async ([family, rel]) => {
    const fontPath = window.SIMPLE_MOTION_FONT_ROOT ? `${window.SIMPLE_MOTION_FONT_ROOT}${rel}` : rel;
    const face = new FontFace(family, `url("${new URL(fontPath, window.location.href).href}")`);
    await face.load();
    document.fonts.add(face);
  });
  await Promise.all(loads);
  await document.fonts.ready;
}

function makeTimeline(duration, draw) {
  let current = 0;
  return {
    paused: true,
    duration: () => duration,
    time(value) {
      if (typeof value === "number") {
        current = clamp(value, 0, duration);
        draw(current);
        return this;
      }
      return current;
    },
    seek(value) {
      return this.time(value);
    },
    pause() {
      this.paused = true;
      return this;
    },
    play() {
      this.paused = false;
      return this;
    },
    progress(value) {
      if (typeof value === "number") return this.time(value * duration);
      return duration ? current / duration : 0;
    }
  };
}

function fitPreviewStage(root) {
  const resize = () => {
    root.style.setProperty("--hm-preview-scale", String(Math.min(window.innerWidth / W, window.innerHeight / H)));
  };
  resize();
  window.addEventListener("resize", resize, { passive: true });
}

async function init() {
  const slug = window.SIMPLE_MOTION_SLUG;
  const configUrl = window.SIMPLE_MOTION_CONFIG_PATH
    ? new URL(window.SIMPLE_MOTION_CONFIG_PATH, window.location.href)
    : new URL(`../configs/${slug}.json`, import.meta.url);
  const cfg = await fetch(configUrl).then((r) => {
    if (!r.ok) throw new Error(`Could not load ${configUrl.href}`);
    return r.json();
  });
  if (new URLSearchParams(window.location.search).has("transparent")) {
    document.body.classList.add("transparent");
  }
  await loadFonts(cfg);
  const root = document.querySelector("[data-composition-id]");
  fitPreviewStage(root);
  const compId = `simple-motion-${cfg.slug}`;
  root.dataset.compositionId = compId;
  root.dataset.duration = String(cfg.duration);
  root.dataset.width = String(W);
  root.dataset.height = String(H);
  const canvasEl = document.getElementById("simple-motion-canvas");
  const ctx = canvasEl.getContext("2d", { willReadFrequently: true });
  function drawAt(time) {
    clear(ctx);
    const frame = Math.max(0, Math.min(Math.round(time * FPS), Math.round(cfg.duration * FPS) - 1));
    renderers[cfg.kind](ctx, frame, cfg);
  }
  window.__timelines = window.__timelines || {};
  window.__timelines[compId] = makeTimeline(cfg.duration, drawAt);
  window.renderAt = drawAt;
  window.__simpleMotionConfig = cfg;
  drawAt(0);
  window.__simpleMotionReady = true;
}

init().catch((error) => {
  console.error(error);
  window.__simpleMotionError = String(error?.stack || error);
});
