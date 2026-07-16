(function () {
  const BASE = { width: 640, height: 360, fps: 30 };

  function clamp01(value) {
    return Math.max(0, Math.min(1, value));
  }

  function easeOutCubic(value) {
    const t = clamp01(value);
    return 1 - Math.pow(1 - t, 3);
  }

  function hsv(hue, sat = 0.86, val = 1) {
    const h = ((hue % 1) + 1) % 1;
    const i = Math.floor(h * 6);
    const f = h * 6 - i;
    const p = val * (1 - sat);
    const q = val * (1 - f * sat);
    const t = val * (1 - (1 - f) * sat);
    const m = i % 6;
    const rgb = m === 0 ? [val, t, p]
      : m === 1 ? [q, val, p]
      : m === 2 ? [p, val, t]
      : m === 3 ? [p, q, val]
      : m === 4 ? [t, p, val]
      : [val, p, q];
    return rgb.map((v) => Math.round(v * 255));
  }

  function rgba(color, alpha = 1) {
    return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${clamp01(alpha)})`;
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

  function createCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  function roundedRect(ctx, x, y, w, h, r) {
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

  function scaleRect(rect, sx, sy) {
    return { x: rect[0] * sx, y: rect[1] * sy, w: rect[2] * sx, h: rect[3] * sy };
  }

  function drawTextMask(maskCanvas, recipe, text, fontSize, centerY, lineGap) {
    const ctx = maskCanvas.getContext("2d", { willReadFrequently: true });
    const sx = maskCanvas.width / BASE.width;
    const scale = Math.min(sx, maskCanvas.height / BASE.height);
    const fontFace = recipe.fontFace || "Mytupi";
    ctx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    ctx.fillStyle = "#fff";
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.font = `${Math.round(fontSize * scale)}px "${fontFace}"`;

    const lines = String(text).split(/\n/);
    const metrics = lines.map((line) => {
      const measured = ctx.measureText(line);
      return {
        ascent: measured.actualBoundingBoxAscent || fontSize * scale * 0.74,
        descent: measured.actualBoundingBoxDescent || fontSize * scale * 0.18,
      };
    });
    const gap = lineGap * scale;
    const total = metrics.reduce((sum, item) => sum + item.ascent + item.descent, 0) + gap * Math.max(0, lines.length - 1);
    let y = maskCanvas.height * centerY - total / 2;
    lines.forEach((line, index) => {
      y += metrics[index].ascent;
      ctx.fillText(line, maskCanvas.width / 2, y);
      y += metrics[index].descent + gap;
    });
  }

  function gradientLayer(mask, phase, options = {}) {
    const layer = createCanvas(mask.width, mask.height);
    const ctx = layer.getContext("2d", { willReadFrequently: true });
    const stops = options.stops || [0.47, 0.6, 0.75, 0.9];
    const gradient = options.vertical
      ? ctx.createLinearGradient(0, 0, 0, mask.height)
      : ctx.createLinearGradient(0, 0, mask.width, 0);
    stops.forEach((stop, index) => {
      gradient.addColorStop(index / (stops.length - 1), rgba(hsv(phase + stop, options.sat || 0.86, options.val || 1), options.opacity ?? 1));
    });
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, mask.width, mask.height);
    ctx.globalCompositeOperation = "destination-in";
    ctx.drawImage(mask, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    return layer;
  }

  function linearGradientLayer(mask, start, end, opacity = 1) {
    const layer = createCanvas(mask.width, mask.height);
    const ctx = layer.getContext("2d", { willReadFrequently: true });
    const gradient = ctx.createLinearGradient(0, 0, mask.width, 0);
    gradient.addColorStop(0, rgba(start, opacity));
    gradient.addColorStop(1, rgba(end, opacity));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, mask.width, mask.height);
    ctx.globalCompositeOperation = "destination-in";
    ctx.drawImage(mask, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    return layer;
  }

  function solidFromMask(mask, color, opacity, blur = 0) {
    const layer = createCanvas(mask.width, mask.height);
    const ctx = layer.getContext("2d", { willReadFrequently: true });
    ctx.fillStyle = rgba(color, opacity);
    ctx.fillRect(0, 0, mask.width, mask.height);
    ctx.globalCompositeOperation = "destination-in";
    if (blur > 0) ctx.filter = `blur(${blur}px)`;
    ctx.drawImage(mask, 0, 0);
    ctx.filter = "none";
    ctx.globalCompositeOperation = "source-over";
    return layer;
  }

  function displaced(source, amp, period, phase) {
    if (amp <= 0) return source;
    const w = source.width;
    const h = source.height;
    const input = source.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, w, h);
    const output = new ImageData(w, h);
    for (let y = 0; y < h; y += 1) {
      const shift = Math.round(Math.sin(y / period + phase) * amp);
      for (let x = 0; x < w; x += 1) {
        const sx = (x - shift + w) % w;
        const src = (y * w + sx) * 4;
        const dst = (y * w + x) * 4;
        output.data[dst] = input.data[src];
        output.data[dst + 1] = input.data[src + 1];
        output.data[dst + 2] = input.data[src + 2];
        output.data[dst + 3] = input.data[src + 3];
      }
    }
    const canvas = createCanvas(w, h);
    canvas.getContext("2d", { willReadFrequently: true }).putImageData(output, 0, 0);
    return canvas;
  }

  function turbulentDisplaced(source, amp, size, phase, seed = 0) {
    if (amp <= 0) return source;
    const w = source.width;
    const h = source.height;
    const period = Math.max(6, size);
    const input = source.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, w, h);
    const output = new ImageData(w, h);
    const rowShifts = new Int16Array(h);
    const colShifts = new Int16Array(w);
    for (let y = 0; y < h; y += 1) {
      const sin = Math.sin(y / period + phase + seed * 0.13);
      const noise = smoothNoise(y / period, phase * 0.35, seed) * 2 - 1;
      rowShifts[y] = Math.round((sin * 0.58 + noise * 0.42) * amp);
    }
    for (let x = 0; x < w; x += 1) {
      const sin = Math.sin(x / (period * 1.25) + phase * 0.73 + seed * 0.07);
      const noise = smoothNoise(x / period, phase * 0.28 + 9, seed + 19) * 2 - 1;
      colShifts[x] = Math.round((sin * 0.7 + noise * 0.3) * amp * 0.32);
    }
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const sx = (x - rowShifts[y] + w) % w;
        const sy = (y - colShifts[x] + h) % h;
        const src = (sy * w + sx) * 4;
        const dst = (y * w + x) * 4;
        output.data[dst] = input.data[src];
        output.data[dst + 1] = input.data[src + 1];
        output.data[dst + 2] = input.data[src + 2];
        output.data[dst + 3] = input.data[src + 3];
      }
    }
    const canvas = createCanvas(w, h);
    canvas.getContext("2d", { willReadFrequently: true }).putImageData(output, 0, 0);
    return canvas;
  }

  function venetianAlpha(mask, frameIndex, openness = 0.58, bandSize = 10, seed = 0) {
    const w = mask.width;
    const h = mask.height;
    const input = mask.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, w, h);
    const output = new ImageData(w, h);
    const phase = Math.floor(frameIndex / 5) * 1.7 + seed;
    for (let y = 0; y < h; y += 1) {
      const band = (y + phase + Math.sin(y * 0.21 + phase) * 2.2) % bandSize;
      const amount = band < bandSize * openness ? 1 : 0.28;
      for (let x = 0; x < w; x += 1) {
        const idx = (y * w + x) * 4;
        output.data[idx] = 255;
        output.data[idx + 1] = 255;
        output.data[idx + 2] = 255;
        output.data[idx + 3] = Math.round(input.data[idx + 3] * amount);
      }
    }
    const canvas = createCanvas(w, h);
    canvas.getContext("2d", { willReadFrequently: true }).putImageData(output, 0, 0);
    return canvas;
  }

  function burnFilm(mask, frameIndex, opacity, phase, seed = 0) {
    const w = mask.width;
    const h = mask.height;
    const input = mask.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, w, h);
    const output = new ImageData(w, h);
    const step = Math.floor(frameIndex / 3);
    for (let y = 0; y < h; y += 1) {
      const verticalBias = clamp01(1 - Math.abs(y / h - 0.48) * 1.9);
      for (let x = 0; x < w; x += 1) {
        const idx = (y * w + x) * 4;
        const alpha = input.data[idx + 3] / 255;
        if (alpha <= 0) continue;
        const grain = smoothNoise(x / 18, y / 11 + step * 0.13, seed) * 0.72 + smoothNoise(x / 48, y / 22, seed + 9) * 0.28;
        const burn = clamp01((grain - 0.38) * 2.2 + verticalBias * 0.35);
        const hot = hsv(phase + 0.02 + burn * 0.11, 0.92, 1);
        output.data[idx] = Math.round(hot[0] * (0.55 + burn * 0.45));
        output.data[idx + 1] = Math.round(hot[1] * (0.42 + burn * 0.36));
        output.data[idx + 2] = Math.round(hot[2] * (0.28 + burn * 0.28));
        output.data[idx + 3] = Math.round(alpha * 255 * opacity * burn);
      }
    }
    const canvas = createCanvas(w, h);
    canvas.getContext("2d", { willReadFrequently: true }).putImageData(output, 0, 0);
    return canvas;
  }

  function chromaOffsets(mask, opacity, strength) {
    const out = createCanvas(mask.width, mask.height);
    const ctx = out.getContext("2d", { willReadFrequently: true });
    [
      [[255, 0, 180], -strength, 0, 0.18],
      [[0, 220, 255], strength, 0, 0.18],
      [[255, 240, 0], 0, strength, 0.08],
    ].forEach(([color, dx, dy, amount]) => {
      ctx.drawImage(solidFromMask(mask, color, opacity * amount), dx, dy);
    });
    return out;
  }

  function lightSweep(mask, frameIndex, totalFrames, opacity) {
    const w = mask.width;
    const h = mask.height;
    const source = mask.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, w, h);
    const image = new ImageData(w, h);
    const t = frameIndex / Math.max(1, totalFrames - 1);
    const center = (t * 1.7 - 0.35) * w;
    const width = Math.max(18, w * 0.06);
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const idx = (y * w + x) * 4;
        const dist = Math.abs((x + y * 0.62) - center);
        const sweep = Math.pow(clamp01(1 - dist / width), 2);
        image.data[idx] = 255;
        image.data[idx + 1] = 255;
        image.data[idx + 2] = 255;
        image.data[idx + 3] = Math.round(sweep * source.data[idx + 3] * 0.42 * opacity);
      }
    }
    const canvas = createCanvas(w, h);
    canvas.getContext("2d", { willReadFrequently: true }).putImageData(image, 0, 0);
    return canvas;
  }

  function dashLayer(size, rects, phase, opacity, trippy = false) {
    const sx = size.width / BASE.width;
    const sy = size.height / BASE.height;
    const out = createCanvas(size.width, size.height);
    const mask = createCanvas(size.width, size.height);
    const outCtx = out.getContext("2d", { willReadFrequently: true });
    const maskCtx = mask.getContext("2d", { willReadFrequently: true });
    rects.forEach(([x, y, w, h, hue]) => {
      const r = scaleRect([x, y, w, h], sx, sy);
      const single = createCanvas(size.width, size.height);
      const sctx = single.getContext("2d", { willReadFrequently: true });
      roundedRect(sctx, r.x, r.y, r.w, r.h, Math.max(1, r.h / 2));
      sctx.fillStyle = `rgba(255,255,255,${trippy ? 0.68 : 0.58})`;
      sctx.fill();
      roundedRect(maskCtx, r.x, r.y, r.w, r.h, Math.max(1, r.h / 2));
      maskCtx.fillStyle = "rgba(255,255,255,.65)";
      maskCtx.fill();
      outCtx.drawImage(solidFromMask(single, hsv(phase + hue, 0.95, trippy ? 0.72 : 0.82), opacity, Math.max(0.8, r.h * 0.16)), 0, 0);
    });
    outCtx.globalCompositeOperation = "destination-over";
    outCtx.drawImage(solidFromMask(mask, hsv(phase + 0.7, 0.9, trippy ? 0.55 : 0.7), trippy ? 0.12 * opacity : 0.1 * opacity, 5 * sx), 0, 0);
    outCtx.globalCompositeOperation = "source-over";
    return out;
  }

  function trippyPhase(frameIndex) {
    const phases = [0, 0.75, 5 / 12, 1 / 12, 0.25, 3 / 8, 0.5, 2 / 3, 7 / 24, 0, 1 / 8, 7 / 24];
    return phases[Math.max(0, Math.min(phases.length - 1, Math.floor(frameIndex / 18)))];
  }

  function cleanPhase(frameIndex, totalFrames) {
    const progress = frameIndex / Math.max(1, totalFrames - 1);
    return 0.46 + progress * 0.12;
  }

  function trippyPlate(size, rect, phase, opacity, radius) {
    const mask = createCanvas(size.width, size.height);
    const ctx = mask.getContext("2d", { willReadFrequently: true });
    roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, radius);
    ctx.fillStyle = `rgba(255,255,255,${0.62 * opacity})`;
    ctx.fill();
    roundedRect(ctx, rect.x + rect.w * 0.07, rect.y + rect.h * 0.12, rect.w * 0.51, rect.h * 0.79, radius);
    ctx.fillStyle = `rgba(255,255,255,${0.41 * opacity})`;
    ctx.fill();
    roundedRect(ctx, rect.x + rect.w * 0.43, rect.y + rect.h * 0.02, rect.w * 0.56, rect.h * 0.96, radius);
    ctx.fillStyle = `rgba(255,255,255,${0.56 * opacity})`;
    ctx.fill();

    const out = createCanvas(size.width, size.height);
    const outCtx = out.getContext("2d", { willReadFrequently: true });
    outCtx.drawImage(solidFromMask(mask, hsv(phase + 0.55, 0.9, 0.65), 0.16 * opacity, radius * 0.55), 0, 0);
    outCtx.drawImage(solidFromMask(mask, [0, 0, 0], 0.22 * opacity, radius * 0.55), 0, 0);
    outCtx.drawImage(gradientLayer(mask, phase, { stops: [0.44, 0.56, 0.69, 0.83], val: 0.54 }), 0, 0);
    return out;
  }

  function cleanWaveEcho(recipe, size, fontScale, phase, opacity, frameIndex) {
    const out = createCanvas(size.width, size.height);
    const ctx = out.getContext("2d", { willReadFrequently: true });
    [
      ["rainbow", 0.38, 0.46, 1.2],
      ["clean", 0.5, 0.15, 1.5],
      ["text", 0.62, 0.12, 1.4],
    ].forEach(([word, y, amount, blur]) => {
      const mask = createCanvas(size.width, size.height);
      drawTextMask(mask, recipe, word, recipe.fontSize * fontScale, y, 0);
      ctx.globalAlpha = amount;
      ctx.filter = `blur(${blur}px)`;
      const warped = turbulentDisplaced(
        venetianAlpha(mask, frameIndex, 0.52, 8, y * 41),
        4.2,
        12,
        frameIndex * 0.16 + y * 7,
        y * 113
      );
      ctx.drawImage(gradientLayer(warped, phase + 0.03, { opacity: opacity * 0.66, stops: [0.48, 0.57, 0.68, 0.82] }), 0, 0);
      ctx.globalAlpha = amount * 0.35;
      ctx.drawImage(burnFilm(warped, frameIndex, opacity * 0.58, phase, y * 97), 0, 0);
      ctx.filter = "none";
      ctx.globalAlpha = 1;
    });
    return out;
  }

  function renderClean(ctx, recipe, time) {
    const size = { width: ctx.canvas.width, height: ctx.canvas.height };
    const frameIndex = Math.round(time * recipe.fps);
    const totalFrames = Math.round(recipe.duration * recipe.fps);
    const enter = easeOutCubic(frameIndex / 16);
    const phase = cleanPhase(frameIndex, totalFrames);
    const mask = createCanvas(size.width, size.height);
    drawTextMask(mask, recipe, recipe.text, recipe.fontSize, 0.5, 3);
    const textMask = turbulentDisplaced(mask, 2.05, 24, frameIndex * 0.11, 23);
    ctx.drawImage(turbulentDisplaced(dashLayer(size, recipe.dashes, phase, enter * 0.86, false), 2.6, 15, frameIndex * 0.12, 71), 0, 0);
    ctx.drawImage(cleanWaveEcho(recipe, size, 1, phase, enter, frameIndex), 0, 0);
    ctx.drawImage(solidFromMask(textMask, hsv(phase + 0.56, 0.9, 0.78), 0.5 * enter, 11), 0, 0);
    ctx.drawImage(chromaOffsets(textMask, enter * 0.82, 1.3), 0, 0);
    ctx.drawImage(burnFilm(textMask, frameIndex, enter * 0.46, phase, 31), 0, 0);
    ctx.drawImage(gradientLayer(textMask, phase, { opacity: enter * 1.04, vertical: true, stops: [0.5, 0.56, 0.64, 0.77] }), 0, 0);
    ctx.drawImage(lightSweep(venetianAlpha(textMask, frameIndex, 0.72, 11, 3), frameIndex + 8, totalFrames, enter * 0.68), 0, 0);
  }

  function renderTrippy(ctx, recipe, time) {
    const size = { width: ctx.canvas.width, height: ctx.canvas.height };
    const frameIndex = Math.round(time * recipe.fps);
    const totalFrames = Math.round(recipe.duration * recipe.fps);
    const enter = easeOutCubic(frameIndex / 30);
    const phase = trippyPhase(frameIndex);
    const plateW = 246 * enter + 34 * (1 - enter);
    const plateH = 74 * enter + 8 * (1 - enter);
    const plateRect = scaleRect([320 - plateW / 2, 139, plateW, plateH], size.width / BASE.width, size.height / BASE.height);
    ctx.drawImage(turbulentDisplaced(dashLayer(size, recipe.dashes, phase, enter, true), 2.9, 14, frameIndex * 0.11, 89), 0, 0);
    ctx.filter = "blur(0.35px)";
    ctx.drawImage(turbulentDisplaced(trippyPlate(size, plateRect, phase, enter * 0.9, 14), 5.2, 18, frameIndex * 0.19, 107), 0, 0);
    ctx.filter = "none";
    const mask = createCanvas(size.width, size.height);
    drawTextMask(mask, recipe, recipe.text, recipe.fontSize, 0.49, 0);
    const warpedMask = turbulentDisplaced(mask, 1.15, 29, frameIndex * 0.09, 113);
    ctx.drawImage(solidFromMask(warpedMask, hsv(phase + 0.58, 0.95, 0.85), 0.38 * enter, 5.5), 0, 0);
    ctx.drawImage(chromaOffsets(warpedMask, enter, 1.45), 0, 0);
    ctx.drawImage(burnFilm(warpedMask, frameIndex, enter * 0.22, phase, 119), 0, 0);
    ctx.drawImage(gradientLayer(warpedMask, phase + 0.02, { opacity: enter * 1.08, stops: [0.5, 0.58, 0.72, 0.88] }), 0, 0);
    ctx.drawImage(lightSweep(warpedMask, frameIndex + 12, totalFrames, enter * 0.62), 0, 0);
  }

  function renderFuturist(ctx, recipe, time) {
    const size = { width: ctx.canvas.width, height: ctx.canvas.height };
    const frameIndex = Math.round(time * recipe.fps);
    const totalFrames = Math.round(recipe.duration * recipe.fps);
    const enter = easeOutCubic(frameIndex / 12);
    const mask = createCanvas(size.width, size.height);
    drawTextMask(mask, recipe, recipe.text, recipe.fontSize, 0.49, 0);
    const textMask = displaced(mask, 0.8, 31, frameIndex * 0.11);
    ctx.drawImage(solidFromMask(textMask, recipe.gradientStart, 0.18 * enter, 3), 0, 0);
    ctx.drawImage(chromaOffsets(textMask, enter, 1), 0, 0);
    ctx.drawImage(linearGradientLayer(textMask, recipe.gradientStart, recipe.gradientEnd, enter), 0, 0);
    ctx.drawImage(lightSweep(textMask, frameIndex + 25, totalFrames, enter * 0.65), 0, 0);
  }

  function build(config, handles) {
    const canvas = handles.canvas;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const recipe = {
      fps: 30,
      width: 640,
      height: 360,
      gradientStart: [255, 0, 216],
      gradientEnd: [0, 204, 255],
      dashes: [],
      ...config,
    };
    let raf = 0;
    let startedAt = 0;

    function draw(time) {
      const duration = recipe.duration || 7.6;
      const wrapped = Math.max(0, Math.min(duration, time));
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!recipe.alpha) {
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }
      if (recipe.style === "clean_stack") renderClean(ctx, recipe, wrapped);
      else if (recipe.style === "trippy_plate") renderTrippy(ctx, recipe, wrapped);
      else renderFuturist(ctx, recipe, wrapped);
    }

    const api = {
      seek(time) {
        draw(Number(time) || 0);
      },
      play() {
        cancelAnimationFrame(raf);
        startedAt = performance.now();
        const tick = (now) => {
          const duration = recipe.duration || 7.6;
          draw(((now - startedAt) / 1000) % duration);
          raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      },
      stop() {
        cancelAnimationFrame(raf);
      },
    };

    draw(0);
    return api;
  }

  window.RainbowTrippy = { build };
}());
