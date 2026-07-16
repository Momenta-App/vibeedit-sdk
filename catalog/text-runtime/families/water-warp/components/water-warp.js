(function () {
  const BASE = { width: 640, height: 360, fps: 30 };

  function clamp(value, lo = 0, hi = 1) {
    return Math.max(lo, Math.min(hi, value));
  }

  function easeOutCubic(value) {
    const t = clamp(value);
    return 1 - Math.pow(1 - t, 3);
  }

  function easeOutQuint(value) {
    const t = clamp(value);
    return 1 - Math.pow(1 - t, 5);
  }

  function rgba(color, alpha = 1) {
    return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${clamp(alpha)})`;
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

  function measureLines(ctx, lines, fontSize) {
    const metrics = lines.map((line) => {
      const measured = ctx.measureText(line);
      return {
        width: measured.width,
        ascent: measured.actualBoundingBoxAscent || fontSize * 0.78,
        descent: measured.actualBoundingBoxDescent || fontSize * 0.2,
      };
    });
    return {
      width: Math.max(...metrics.map((item) => item.width), 1),
      height: metrics.reduce((sum, item) => sum + item.ascent + item.descent, 0),
      metrics,
    };
  }

  function drawTextToMask(mask, text, font, fontSize, stroke = 0, pad = 18) {
    const lines = String(text).split(/\n/);
    const ctx = mask.getContext("2d", { willReadFrequently: true });
    ctx.clearRect(0, 0, mask.width, mask.height);
    ctx.font = `${font.italic ? "italic " : ""}900 ${fontSize}px "${font.family}"`;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    const info = measureLines(ctx, lines, fontSize);
    const lineGap = font.lineGap || 0;
    const totalHeight = info.height + Math.max(0, lines.length - 1) * lineGap;
    const width = Math.ceil(info.width + pad * 2 + stroke * 4);
    const height = Math.ceil(totalHeight + pad * 2 + stroke * 4);
    if (mask.width !== width || mask.height !== height) {
      mask.width = width;
      mask.height = height;
    }
    ctx.clearRect(0, 0, mask.width, mask.height);
    ctx.font = `${font.italic ? "italic " : ""}900 ${fontSize}px "${font.family}"`;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillStyle = "#fff";
    ctx.strokeStyle = "#fff";
    ctx.lineJoin = "round";
    ctx.lineWidth = Math.max(0, stroke * 2);
    let y = pad + stroke * 2;
    lines.forEach((line, index) => {
      const metric = info.metrics[index];
      y += metric.ascent;
      const x = pad + stroke * 2;
      if (stroke > 0) ctx.strokeText(line, x, y);
      ctx.fillText(line, x, y);
      y += metric.descent + lineGap;
    });
  }

  function cropAlpha(source) {
    const ctx = source.getContext("2d", { willReadFrequently: true });
    const data = ctx.getImageData(0, 0, source.width, source.height).data;
    let minX = source.width;
    let minY = source.height;
    let maxX = -1;
    let maxY = -1;
    for (let y = 0; y < source.height; y += 1) {
      for (let x = 0; x < source.width; x += 1) {
        if (data[(y * source.width + x) * 4 + 3] > 0) {
          minX = Math.min(minX, x);
          minY = Math.min(minY, y);
          maxX = Math.max(maxX, x);
          maxY = Math.max(maxY, y);
        }
      }
    }
    if (maxX < minX || maxY < minY) return createCanvas(1, 1);
    const out = createCanvas(maxX - minX + 1, maxY - minY + 1);
    out.getContext("2d", { willReadFrequently: true }).drawImage(source, minX, minY, out.width, out.height, 0, 0, out.width, out.height);
    return out;
  }

  function textMask(text, font, fontSize, stroke = 0, pad = 18) {
    const mask = createCanvas(8, 8);
    drawTextToMask(mask, text, font, fontSize, stroke, pad);
    return cropAlpha(mask);
  }

  function solid(mask, color, opacity = 1, blur = 0) {
    const out = createCanvas(mask.width, mask.height);
    const ctx = out.getContext("2d", { willReadFrequently: true });
    ctx.fillStyle = rgba(color, opacity);
    ctx.fillRect(0, 0, out.width, out.height);
    ctx.globalCompositeOperation = "destination-in";
    if (blur > 0) ctx.filter = `blur(${blur}px)`;
    ctx.drawImage(mask, 0, 0);
    ctx.filter = "none";
    ctx.globalCompositeOperation = "source-over";
    return out;
  }

  function gradient(mask, top, bottom, opacity = 1) {
    const out = createCanvas(mask.width, mask.height);
    const ctx = out.getContext("2d", { willReadFrequently: true });
    const grad = ctx.createLinearGradient(0, 0, 0, out.height);
    grad.addColorStop(0, rgba(top, opacity));
    grad.addColorStop(1, rgba(bottom, opacity));
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, out.width, out.height);
    ctx.globalCompositeOperation = "destination-in";
    ctx.drawImage(mask, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    return out;
  }

  function pasteCenter(ctx, layer, centerX, centerY, opacity = 1, rotateDeg = 0) {
    ctx.save();
    ctx.globalAlpha = clamp(opacity);
    ctx.translate(centerX, centerY);
    if (rotateDeg) ctx.rotate((rotateDeg * Math.PI) / 180);
    ctx.drawImage(layer, -layer.width / 2, -layer.height / 2);
    ctx.restore();
  }

  function rowDisplace(source, amp, period, phase, secondAmp = 0) {
    if (Math.abs(amp) < 0.01 && Math.abs(secondAmp) < 0.01) return source;
    const srcCtx = source.getContext("2d", { willReadFrequently: true });
    const input = srcCtx.getImageData(0, 0, source.width, source.height);
    const output = new ImageData(source.width, source.height);
    for (let y = 0; y < source.height; y += 1) {
      let shift = Math.sin(y / Math.max(1, period) + phase) * amp;
      shift += Math.sin(y / Math.max(1, period * 0.43) + phase * 0.71) * secondAmp;
      const rounded = Math.round(shift);
      for (let x = 0; x < source.width; x += 1) {
        const sx = (x - rounded + source.width) % source.width;
        const src = (y * source.width + sx) * 4;
        const dst = (y * source.width + x) * 4;
        output.data[dst] = input.data[src];
        output.data[dst + 1] = input.data[src + 1];
        output.data[dst + 2] = input.data[src + 2];
        output.data[dst + 3] = input.data[src + 3];
      }
    }
    const out = createCanvas(source.width, source.height);
    out.getContext("2d", { willReadFrequently: true }).putImageData(output, 0, 0);
    return out;
  }

  function venetianBreakup(source, frameIndex, opts = {}) {
    if (!opts.enabled) return source;
    const out = createCanvas(source.width, source.height);
    const ctx = out.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(source, 0, 0);
    const every = opts.every || 7;
    const gap = opts.gap || 2;
    const alpha = opts.alpha ?? 0.35;
    ctx.save();
    ctx.globalCompositeOperation = "destination-out";
    ctx.fillStyle = `rgba(0,0,0,${alpha})`;
    for (let y = 0; y < source.height; y += every) {
      const wobble = Math.sin(y * 0.21 + frameIndex * 0.28);
      if (wobble > -0.22) ctx.fillRect(0, y, source.width, gap);
    }
    ctx.restore();
    ctx.save();
    ctx.globalAlpha = opts.echoAlpha ?? 0.22;
    for (let y = 0; y < source.height; y += every * 3) {
      const shift = Math.round(Math.sin(frameIndex * 0.31 + y * 0.13) * (opts.shift || 4));
      ctx.drawImage(source, 0, y, source.width, Math.min(gap + 1, source.height - y), shift, y, source.width, Math.min(gap + 1, source.height - y));
    }
    ctx.restore();
    return out;
  }

  function lightSweep(mask, frameIndex, totalFrames, opacity, width = 0.12) {
    const source = mask.getContext("2d", { willReadFrequently: true }).getImageData(0, 0, mask.width, mask.height);
    const image = new ImageData(mask.width, mask.height);
    const progress = (frameIndex % Math.max(1, totalFrames)) / Math.max(1, totalFrames - 1);
    const center = -0.25 + progress * 1.55;
    for (let y = 0; y < mask.height; y += 1) {
      for (let x = 0; x < mask.width; x += 1) {
        const d = Math.abs(x / Math.max(1, mask.width - 1) - (y / Math.max(1, mask.height - 1)) * 0.42 - center);
        const a = d < width ? (1 - d / width) * 185 * opacity : 0;
        const idx = (y * mask.width + x) * 4;
        image.data[idx] = 255;
        image.data[idx + 1] = 255;
        image.data[idx + 2] = 255;
        image.data[idx + 3] = Math.min(source.data[idx + 3], Math.round(a));
      }
    }
    const out = createCanvas(mask.width, mask.height);
    out.getContext("2d", { willReadFrequently: true }).putImageData(image, 0, 0);
    return out;
  }

  function addShimmer(layer, frameIndex, opacity = 0.08) {
    const ctx = layer.getContext("2d", { willReadFrequently: true });
    const image = ctx.getImageData(0, 0, layer.width, layer.height);
    let seed = 1000 + frameIndex * 101;
    for (let i = 0; i < image.data.length; i += 4) {
      if (image.data[i + 3] === 0) continue;
      seed = (seed * 1664525 + 1013904223) >>> 0;
      const noise = (((seed >>> 16) & 255) - 128) * opacity;
      image.data[i] = clamp(image.data[i] + noise, 0, 255);
      image.data[i + 1] = clamp(image.data[i + 1] + noise, 0, 255);
      image.data[i + 2] = clamp(image.data[i + 2] + noise, 0, 255);
    }
    const out = createCanvas(layer.width, layer.height);
    out.getContext("2d", { willReadFrequently: true }).putImageData(image, 0, 0);
    return out;
  }

  function textEffectLayer(recipe, frameIndex, top, bottom, strokeColor, glowColor, stroke, amp, period, phaseSpeed, shadowOffset) {
    const font = recipe.font;
    const mask = textMask(recipe.text, font, recipe.fontSize, 0);
    const strokeMask = textMask(recipe.text, font, recipe.fontSize, stroke);
    const layer = createCanvas(Math.max(strokeMask.width, mask.width) + 28, Math.max(strokeMask.height, mask.height) + 24);
    const ctx = layer.getContext("2d", { willReadFrequently: true });
    pasteCenter(ctx, solid(strokeMask, glowColor, 0.34, 2), layer.width / 2 + shadowOffset[0], layer.height / 2 + shadowOffset[1]);
    pasteCenter(ctx, solid(strokeMask, strokeColor, 0.95, 0.45), layer.width / 2 + shadowOffset[0], layer.height / 2 + shadowOffset[1]);
    pasteCenter(ctx, gradient(mask, top, bottom), layer.width / 2, layer.height / 2);
    pasteCenter(ctx, lightSweep(mask, frameIndex + 18, 160, 0.45), layer.width / 2, layer.height / 2);
    return rowDisplace(addShimmer(layer, frameIndex), amp, period, frameIndex * phaseSpeed, amp * 0.38);
  }

  function renderWarp(ctx, recipe, frameIndex) {
    const tuning = recipe.browserTuning || {};
    const enter = easeOutQuint(frameIndex / 8);
    let layer = textEffectLayer(
      recipe,
      frameIndex,
      tuning.gradientTop || [255, 255, 255],
      tuning.gradientBottom || [0, 220, 255],
      tuning.strokeColor || [1, 35, 45],
      tuning.glowColor || [0, 224, 255],
      1,
      tuning.amp ?? 4.4,
      tuning.period ?? 9,
      tuning.phaseSpeed ?? 0.27,
      tuning.shadowOffset || [2, 4]
    );
    layer = venetianBreakup(layer, frameIndex, tuning.venetian || {});
    const flicker = (tuning.flickerBase ?? 0.96) + (tuning.flickerRange ?? 0.04) * (frameIndex % 19 < 14 ? 1 : 0);
    const cx = (tuning.centerX ?? 316) + Math.sin(frameIndex * 0.08) * (tuning.floatX ?? 4.2);
    const cy = (tuning.centerY ?? 184) + Math.sin(frameIndex * 0.11 + 1) * (tuning.floatY ?? 2.2);
    pasteCenter(ctx, layer, cx, cy, enter * flicker, -2);
  }

  function renderWaves(ctx, recipe, frameIndex) {
    const enter = easeOutQuint(frameIndex / 7);
    const layer = textEffectLayer(recipe, frameIndex, [180, 238, 255], [0, 204, 255], [2, 55, 72], [0, 204, 255], 1, -1, 44, 0.10, [3, 4]);
    pasteCenter(ctx, layer, 320, 180, enter);
  }

  function roundedWaterPlate(frameIndex, opacity, tuning = {}) {
    const w = tuning.width || 202;
    const h = tuning.height || 132;
    const plate = createCanvas(w, h);
    const ctx = plate.getContext("2d", { willReadFrequently: true });
    ctx.save();
    roundedRect(ctx, 0, 0, w - 1, h - 1, tuning.outerRadius || 14);
    ctx.clip();
    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, rgba(tuning.outerTop || [0, 186, 148], opacity));
    bg.addColorStop(1, rgba(tuning.outerBottom || [0, 42, 158], opacity));
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.filter = "blur(1.1px)";
    const phase = frameIndex * 0.12;
    [[0, 0.28], [8, 0.15], [16, 0.1]].forEach(([offset, alpha]) => {
      ctx.beginPath();
      for (let x = -10; x <= w + 10; x += 4) {
        const y = 15 + offset + Math.sin(x * 0.045 + phase) * 3 + Math.sin(x * 0.10 - phase * 0.5) * 1.3;
        if (x === -10) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = rgba([0, 244, 190], alpha);
      ctx.lineWidth = 3;
      ctx.stroke();
    });
    ctx.restore();

    ctx.save();
    roundedRect(ctx, tuning.innerX || 9, tuning.innerY || 14, w - (tuning.innerX || 9) * 2, h - (tuning.innerBottom || 27), tuning.innerRadius || 54);
    ctx.clip();
    const inner = ctx.createLinearGradient(0, 0, 0, h);
    inner.addColorStop(0, rgba(tuning.innerTop || [0, 124, 106], opacity * 0.9));
    inner.addColorStop(1, rgba(tuning.innerBottomColor || [0, 48, 78], opacity * 0.9));
    ctx.fillStyle = inner;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();

    ctx.save();
    ctx.lineWidth = 5;
    ctx.strokeStyle = rgba([0, 232, 187], (tuning.outerStrokeAlpha ?? 0.48) * opacity);
    roundedRect(ctx, 2.5, 2.5, w - 5, h - 5, tuning.outerRadius || 14);
    ctx.stroke();
    ctx.lineWidth = 7;
    ctx.strokeStyle = rgba([0, 28, 36], (tuning.innerStrokeAlpha ?? 0.42) * opacity);
    roundedRect(ctx, 12, 17, w - 24, h - 34, 54);
    ctx.stroke();
    ctx.restore();
    return rowDisplace(plate, tuning.displaceAmp ?? 1.35, tuning.displacePeriod ?? 28, frameIndex * 0.11, tuning.secondAmp ?? 0.45);
  }

  function renderWaterPlate(ctx, recipe, frameIndex) {
    const tuning = recipe.browserTuning || {};
    const enter = easeOutCubic(frameIndex / 12);
    const offset = (tuning.enterOffset ?? 72) * (1 - easeOutCubic(frameIndex / 30));
    const plate = roundedWaterPlate(frameIndex, enter, tuning.plate || {});
    pasteCenter(ctx, plate, 319 + offset, 180, enter);
    const mask = textMask(recipe.text, recipe.font, recipe.fontSize, 0);
    const strokeMask = textMask(recipe.text, recipe.font, recipe.fontSize, 1);
    const textLayer = createCanvas(tuning.textLayerWidth || 166, tuning.textLayerHeight || 76);
    const tctx = textLayer.getContext("2d", { willReadFrequently: true });
    const tx = textLayer.width / 2;
    const ty = textLayer.height / 2 + (tuning.textYOffset || 0);
    pasteCenter(tctx, solid(strokeMask, tuning.textShadow || [0, 25, 57], 0.82, 0.35), tx, ty + 2);
    pasteCenter(tctx, gradient(mask, tuning.textTop || [130, 255, 255], tuning.textBottom || [0, 186, 255]), tx, ty);
    pasteCenter(tctx, lightSweep(mask, frameIndex + 22, 130, tuning.sweepOpacity ?? 0.44, 0.18), tx, ty);
    pasteCenter(ctx, textLayer, 319 + offset, 179, enter);
  }

  function darkTextPiece(text, recipe, fontSize, top, bottom, frameIndex) {
    const mask = textMask(text, recipe.font, fontSize, 0, 20);
    const strokeMask = textMask(text, recipe.font, fontSize, 1, 20);
    const layer = createCanvas(strokeMask.width + 20, strokeMask.height + 20);
    const ctx = layer.getContext("2d", { willReadFrequently: true });
    pasteCenter(ctx, solid(strokeMask, [0, 20, 18], 0.95, 0.45), layer.width / 2 + 5, layer.height / 2 + 7);
    pasteCenter(ctx, solid(strokeMask, [0, 255, 204], 0.12, 1.6), layer.width / 2, layer.height / 2);
    pasteCenter(ctx, gradient(mask, top, bottom), layer.width / 2, layer.height / 2);
    pasteCenter(ctx, lightSweep(mask, frameIndex + 8, 110, 0.38, 0.16), layer.width / 2, layer.height / 2);
    return rowDisplace(layer, 0.8, 34, frameIndex * 0.09, 0.25);
  }

  function renderDarkWater(ctx, recipe, frameIndex) {
    const enter = easeOutQuint(frameIndex / 10);
    const xOffset = 26 * (1 - easeOutCubic(frameIndex / 24));
    const first = darkTextPiece(recipe.primaryText, recipe, recipe.primaryFontSize, [0, 255, 204], [0, 88, 75], frameIndex);
    const second = darkTextPiece(recipe.secondaryText, recipe, recipe.secondaryFontSize, [0, 178, 143], [0, 57, 51], frameIndex);
    pasteCenter(ctx, first, 285 + xOffset, 165, enter);
    pasteCenter(ctx, second, 389 + xOffset * 0.35, 190, enter);
  }

  function ensureTimelineFallback() {
    if (window.gsap) return;
    window.gsap = {
      timeline() {
        const tweens = [];
        const api = {
          to(target, vars, at = 0) {
            tweens.push({ target, vars, at });
            return api;
          },
          time(value) {
            tweens.forEach((tween) => {
              const duration = tween.vars.duration || 0;
              const local = duration === 0 ? 1 : clamp((value - tween.at) / duration);
              for (const key of Object.keys(tween.vars)) {
                if (key === "duration" || key === "ease" || key === "onUpdate") continue;
                targetNumberAssign(tween.target, key, tween.vars[key] * local);
              }
              if (typeof tween.vars.onUpdate === "function") tween.vars.onUpdate();
            });
            return api;
          },
          seek(value) { return api.time(value); },
          progress(value) { return value == null ? 0 : api.time(value); },
          pause() { return api; },
          duration() { return 0; },
        };
        return api;
      },
    };
  }

  function targetNumberAssign(target, key, value) {
    target[key] = value;
  }

  function normalizeRecipe(raw) {
    const recipe = { ...raw };
    recipe.fps = recipe.fps || BASE.fps;
    recipe.duration = recipe.duration || 7.6;
    recipe.font = recipe.font || {};
    recipe.font.family = recipe.font.family || "Poppins Black";
    recipe.font.italic = Boolean(recipe.font.italic);
    recipe.fontSize = recipe.fontSize || 38;
    return recipe;
  }

  function fitPreviewStage(root) {
    const resize = () => {
      root.style.setProperty("--hm-preview-scale", String(Math.min(window.innerWidth / BASE.width, window.innerHeight / BASE.height)));
    };
    resize();
    window.addEventListener("resize", resize, { passive: true });
  }

  function mount(rawRecipe) {
    ensureTimelineFallback();
    const recipe = normalizeRecipe(rawRecipe);
    fitPreviewStage(document.getElementById("root"));
    const canvas = document.getElementById("water-warp-canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const variables = window.__hyperframes && window.__hyperframes.getVariables ? window.__hyperframes.getVariables() : {};
    const params = new URLSearchParams(window.location.search);
    const renderMode = params.get("render") === "1";
    let alphaMode = Boolean(variables.alphaMode || recipe.alphaMode || params.get("alpha") === "1");
    const state = { time: 0 };

    function draw(alphaOverride = alphaMode) {
      const frameIndex = Math.max(0, Math.min(Math.round(state.time * recipe.fps), Math.round(recipe.duration * recipe.fps) - 1));
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!alphaOverride) {
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }
      if (recipe.style === "warp_text") renderWarp(ctx, recipe, frameIndex);
      else if (recipe.style === "waves_text") renderWaves(ctx, recipe, frameIndex);
      else if (recipe.style === "water_plate") renderWaterPlate(ctx, recipe, frameIndex);
      else if (recipe.style === "dark_water") renderDarkWater(ctx, recipe, frameIndex);
    }

    window.__timelines = window.__timelines || {};
    const tl = window.gsap.timeline({ paused: true });
    tl.to(state, { time: recipe.duration, duration: recipe.duration, ease: "none", onUpdate: draw }, 0);
    window.__timelines[recipe.compositionId] = tl;
    window.__waterWarpRenderFrame = function renderFrame(time, opts = {}) {
      state.time = clamp(time, 0, recipe.duration);
      alphaMode = Boolean(opts.alpha ?? alphaMode);
      draw(alphaMode);
      return true;
    };
    draw();

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => {
        draw();
        window.__waterWarpReady = true;
      });
    } else {
      window.__waterWarpReady = true;
    }

    if (!renderMode) {
      let start = 0;
      function loop(ts) {
        if (!start) start = ts;
        state.time = ((ts - start) / 1000) % recipe.duration;
        draw();
        window.requestAnimationFrame(loop);
      }
      window.requestAnimationFrame(loop);
    }
  }

  window.WaterWarp = { mount };
}());
