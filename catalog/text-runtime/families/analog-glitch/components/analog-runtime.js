(function () {
  "use strict";

  const FONT_URLS = {
    "Mytupi-Bold": "../../assets/fonts/mytupiBOLD.ttf",
    "Poppins-Black": "../../assets/fonts/Poppins-Black.ttf",
    "Poppins-Bold": "../../assets/fonts/Poppins-Bold.ttf",
    "AVANTE": "../../assets/fonts/AVANTE.otf"
  };

  const clamp = (value, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, value));
  const rad = (deg) => (deg * Math.PI) / 180;
  const frameIndex = (cfg, time) => Math.max(0, Math.round(time * cfg.fps));

  function easeOutBack(t) {
    const x = clamp(t);
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
  }

  function introOpacity(cfg, frame, time) {
    const introDuration = cfg.introDuration ?? 0.33;
    const intro = introDuration <= 0 ? 1 : easeOutBack(time / introDuration);
    const flicker = 0.86 + 0.14 * (Math.floor(frame / 4) % 2 ? 1 : 0);
    return intro * flicker;
  }

  function roundedRect(ctx, x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.lineTo(x + w - rr, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
    ctx.lineTo(x + w, y + h - rr);
    ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
    ctx.lineTo(x + rr, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
    ctx.lineTo(x, y + rr);
    ctx.quadraticCurveTo(x, y, x + rr, y);
    ctx.closePath();
  }

  function makeCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  function fontString(cfg, scale = 1) {
    return `${Math.round(cfg.fontSize * scale)}px "${cfg.font}", Arial, sans-serif`;
  }

  function textMetrics(ctx, text) {
    const m = ctx.measureText(text);
    const ascent = m.actualBoundingBoxAscent || 36;
    const descent = m.actualBoundingBoxDescent || 10;
    return { width: m.width, ascent, descent, height: ascent + descent };
  }

  function drawCenteredText(ctx, text, x, y, fill, opts = {}) {
    ctx.save();
    ctx.font = opts.font;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineJoin = "round";
    ctx.globalAlpha = opts.alpha ?? 1;
    if (opts.filter) ctx.filter = opts.filter;
    if (opts.shadowColor) {
      ctx.shadowColor = opts.shadowColor;
      ctx.shadowBlur = opts.shadowBlur || 0;
      ctx.shadowOffsetX = opts.shadowOffsetX || 0;
      ctx.shadowOffsetY = opts.shadowOffsetY || 0;
    }
    if (opts.strokeStyle && opts.lineWidth) {
      ctx.strokeStyle = opts.strokeStyle;
      ctx.lineWidth = opts.lineWidth;
      ctx.strokeText(text, x, y);
    }
    if (opts.gradient) {
      ctx.fillStyle = opts.gradient;
    } else {
      ctx.fillStyle = fill;
    }
    ctx.fillText(text, x, y);
    ctx.restore();
  }

  function drawRotatedRoundRect(ctx, cx, cy, w, h, radius, angle, fill, blur = 0, alpha = 1) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(rad(angle));
    ctx.globalAlpha = alpha;
    if (blur) ctx.filter = `blur(${blur}px)`;
    ctx.fillStyle = fill;
    roundedRect(ctx, -w / 2, -h / 2, w, h, radius);
    ctx.fill();
    ctx.restore();
  }

  function drawScanlines(ctx, width, height, alpha = 0.02, every = 3) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    for (let y = 0; y < height; y += every) {
      ctx.beginPath();
      ctx.moveTo(0, y + 0.5);
      ctx.lineTo(width, y + 0.5);
      ctx.stroke();
    }
    ctx.restore();
  }

  function noiseValue(x, y, seed) {
    let n = (x * 374761393 + y * 668265263 + seed * 362437) >>> 0;
    n = (n ^ (n >> 13)) >>> 0;
    return ((n * 1274126177) >>> 0) & 255;
  }

  function drawNoise(ctx, width, height, seed, alpha = 0.012, step = 2) {
    const temp = makeCanvas(width, height);
    const tempCtx = temp.getContext("2d");
    const image = tempCtx.createImageData(width, height);
    for (let y = 0; y < height; y += step) {
      for (let x = 0; x < width; x += step) {
        const v = noiseValue(x, y, seed);
        for (let yy = 0; yy < step; yy += 1) {
          for (let xx = 0; xx < step; xx += 1) {
            const px = x + xx;
            const py = y + yy;
            if (px >= width || py >= height) continue;
            const i = (py * width + px) * 4;
            image.data[i] = v;
            image.data[i + 1] = v;
            image.data[i + 2] = v;
            image.data[i + 3] = Math.round(255 * alpha);
          }
        }
      }
    }
    tempCtx.putImageData(image, 0, 0);
    ctx.drawImage(temp, 0, 0);
  }

  function displaceRows(source, frame, amount) {
    if (!amount) return source;
    const out = makeCanvas(source.width, source.height);
    const ctx = out.getContext("2d");
    for (let y = 0; y < source.height; y += 1) {
      const shift = Math.round(Math.sin(y * 0.17 + frame * 0.31) * amount);
      ctx.drawImage(source, 0, y, source.width, 1, shift, y, source.width, 1);
      if (shift > 0) ctx.drawImage(source, source.width - shift, y, shift, 1, 0, y, shift, 1);
      if (shift < 0) ctx.drawImage(source, 0, y, -shift, 1, source.width + shift, y, -shift, 1);
    }
    return out;
  }

  function opticsBulge(source, strength = 0) {
    if (!strength) return source;
    const out = makeCanvas(source.width, source.height);
    const ctx = out.getContext("2d");
    const mid = source.height / 2;
    for (let y = 0; y < source.height; y += 1) {
      const n = Math.abs((y - mid) / Math.max(1, mid));
      const scale = 1 + strength * (1 - n * n);
      const rowW = Math.max(1, Math.round(source.width * scale));
      ctx.drawImage(source, 0, y, source.width, 1, (source.width - rowW) / 2, y, rowW, 1);
    }
    return out;
  }

  function tearBands(source, frame, opts = {}) {
    const count = opts.count ?? 0;
    if (!count) return source;
    const out = makeCanvas(source.width, source.height);
    const ctx = out.getContext("2d");
    ctx.drawImage(source, 0, 0);
    const seed = opts.seed ?? 71;
    const irregularity = opts.irregularity ?? 3.5;
    for (let i = 0; i < count; i += 1) {
      const n = noiseValue(i * 19, Math.floor(frame / 2), seed) / 255 - 0.5;
      const n2 = noiseValue(i * 31, Math.floor(frame / 3), seed + 17) / 255 - 0.5;
      const y = Math.round((source.height * (i + 1)) / (count + 1) + Math.sin(frame * 0.19 + i * 1.7) * (opts.drift ?? 3) + n * irregularity);
      const h = Math.max(1, Math.round((opts.height ?? 4) + n2 * 2));
      const shift = Math.round(Math.sin(frame * 0.27 + i * 2.3) * (opts.shift ?? 7) + n * (opts.shift ?? 7) * 0.45);
      ctx.clearRect(0, y, source.width, h);
      ctx.globalAlpha = clamp((opts.alpha ?? 0.85) + n2 * 0.22, 0.32, 0.95);
      ctx.drawImage(source, 0, y, source.width, h, shift, y, source.width, h);
      ctx.globalAlpha = 1;
    }
    return out;
  }

  function drawDiagonalSweep(ctx, width, height, frame, opts = {}) {
    const period = opts.period ?? 135;
    const progress = (frame % period) / period;
    const x = -width * 0.45 + progress * width * 1.9;
    const band = opts.width ?? 34;
    const alpha = opts.alpha ?? 0.18;
    const grad = ctx.createLinearGradient(x - band, 0, x + band, height);
    grad.addColorStop(0, "rgba(255,255,255,0)");
    grad.addColorStop(0.46, `rgba(255,255,255,${alpha})`);
    grad.addColorStop(0.58, `rgba(145,245,255,${alpha * 0.55})`);
    grad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.save();
    ctx.globalCompositeOperation = "source-atop";
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);
    ctx.restore();
  }

  function drawWavyBar(ctx, width, height, color, phase, broken = false, opts = {}) {
    const seed = opts.seed ?? 29;
    const n0 = noiseValue(seed, Math.floor(phase * 10), 3) / 255 - 0.5;
    const n1 = noiseValue(seed + 11, Math.floor(phase * 8), 5) / 255 - 0.5;
    const n2 = noiseValue(seed + 23, Math.floor(phase * 7), 7) / 255 - 0.5;
    const segments = broken
      ? [[0, width * (0.49 + n0 * 0.1)], [width * (0.61 + n1 * 0.08), width * (0.78 + n2 * 0.08)], [width * (0.86 + n0 * 0.06), width]]
      : [[Math.max(0, n0 * 5), width - Math.max(0, n1 * 5)]];
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(2, height / 3);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.filter = "blur(0.35px)";
    for (const [start, end] of segments) {
      ctx.beginPath();
      let moved = false;
      for (let x = start; x <= end; x += 3) {
        const grain = noiseValue(Math.floor(x / 5), Math.floor(phase * 12), seed) / 255 - 0.5;
        const y = height / 2 + Math.sin(x * 0.09 + phase) * 2 + Math.sin(x * 0.21 + phase * 0.7) * 0.9 + grain * (opts.noiseAmp ?? 1.1);
        if (!moved) {
          ctx.moveTo(x, y);
          moved = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawWobblyArc(ctx, cx, cy, radius, startAngle, endAngle, phase, opts = {}) {
    const steps = opts.steps ?? 24;
    const amp = opts.amp ?? 1.15;
    const seed = opts.seed ?? 43;
    ctx.beginPath();
    for (let i = 0; i <= steps; i += 1) {
      const t = i / steps;
      const a = startAngle + (endAngle - startAngle) * t;
      const grain = noiseValue(i, Math.floor(phase * 8), seed) / 255 - 0.5;
      const rr = radius + Math.sin(t * Math.PI * 3 + phase) * amp + grain * amp * 0.9;
      const x = cx + Math.cos(a) * rr;
      const y = cy + Math.sin(a) * rr;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  function drawBrokenHorizontal(ctx, y, width, color, phase, opts = {}) {
    const startX = opts.x ?? 58;
    const segment = opts.segment ?? 13;
    const gap = opts.gap ?? 7;
    const amp = opts.amp ?? 1.8;
    const jitter = opts.jitter ?? 0.16;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = opts.lineWidth ?? 3;
    ctx.lineCap = "round";
    ctx.filter = opts.blur ? `blur(${opts.blur}px)` : "none";
    for (let x = 0; x < width; x += segment + gap) {
      const segEnd = Math.min(width, x + segment + Math.sin(x * 0.19 + phase) * 3);
      ctx.beginPath();
      let moved = false;
      for (let px = x; px <= segEnd; px += 3) {
        const yy = y + Math.sin(px * jitter + phase) * amp + Math.sin(px * 0.07 + phase * 1.7) * 0.8;
        if (!moved) {
          ctx.moveTo(startX + px, yy);
          moved = true;
        } else {
          ctx.lineTo(startX + px, yy);
        }
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawErrorText(ctx, cfg, time, alphaOutput) {
    const frame = frameIndex(cfg, time);
    const intro = introOpacity(cfg, frame, time);
    let [cx, cy] = cfg.center;
    if ([0, 1, 2].includes(frame % 29)) {
      cx += cfg.jitter.x;
      cy -= cfg.jitter.y;
    } else if ([10, 11].includes(frame % 43)) {
      cx -= cfg.jitter.x * 0.6;
      cy += cfg.jitter.y * 0.3;
    }

    let block = makeCanvas(210, 92);
    let b = block.getContext("2d");
    b.font = fontString(cfg);
    const scale = 0.78 + 0.22 * intro;

    drawRotatedRoundRect(b, 105, 46, cfg.pillWidth, cfg.pillHeight, cfg.pillRadius, cfg.pillAngle, cfg.pillColor, cfg.pillBlur, 0.82);
    drawCenteredText(b, cfg.text, 105, 46, cfg.textColor, {
      font: fontString(cfg),
      alpha: 0.62,
      filter: `blur(${cfg.glowBlur}px)`
    });
    drawCenteredText(b, cfg.text, 101, 45, cfg.chromaticCyan, {
      font: fontString(cfg),
      alpha: 0.22,
      filter: "blur(1.2px)"
    });
    drawCenteredText(b, cfg.text, 109, 47, cfg.chromaticMagenta, {
      font: fontString(cfg),
      alpha: 0.24,
      filter: "blur(1.2px)"
    });
    drawCenteredText(b, cfg.text, 105, 46, cfg.textColor, {
      font: fontString(cfg),
      alpha: 0.82,
      filter: `blur(${cfg.textBlur}px)`,
      strokeStyle: cfg.textColor,
      lineWidth: 1
    });
    drawDiagonalSweep(b, block.width, block.height, frame, {
      alpha: cfg.sweepAlpha ?? 0.16,
      width: cfg.sweepWidth ?? 28,
      period: cfg.sweepPeriod ?? 120
    });
    drawRotatedRoundRect(b, 105, 46, cfg.slashWidth, cfg.slashHeight + 6, cfg.slashRadius, cfg.slashAngle, "rgba(255,20,26,0.35)", 2.2, 1);
    drawRotatedRoundRect(b, 105, 46, cfg.slashWidth, cfg.slashHeight, cfg.slashRadius, cfg.slashAngle, cfg.slashColor, 0, 0.78);

    block = displaceRows(block, frame, cfg.waveDisplace);
    ctx.save();
    ctx.globalAlpha = clamp(intro);
    ctx.translate(cx, cy);
    ctx.scale(scale, scale);
    ctx.drawImage(block, -block.width / 2, -block.height / 2);
    ctx.restore();
  }

  function drawVhs(ctx, cfg, time, alphaOutput) {
    const frame = frameIndex(cfg, time);
    const intro = introOpacity(cfg, frame, time);
    let [cx, cy] = cfg.center;
    if ([4, 5].includes(frame % 36)) cx += 2;

    let block = makeCanvas(120, 86);
    let b = block.getContext("2d");
    const p = cfg.plate;
    b.save();
    roundedRect(b, p.x + 4, p.y + 4, p.w, p.h, p.radius);
    b.fillStyle = "rgba(0,0,0,0.45)";
    b.fill();
    roundedRect(b, p.x, p.y, p.w, p.h, p.radius);
    b.fillStyle = cfg.plate.color;
    b.globalAlpha = 0.9;
    b.fill();
    b.globalAlpha = 1;
    b.strokeStyle = "rgba(30,36,36,0.2)";
    b.lineWidth = 2;
    b.beginPath();
    b.moveTo(p.x + 3, p.y + p.h - 8);
    b.lineTo(p.x + p.w - 3, p.y + p.h - 8);
    b.stroke();
    b.restore();

    drawCenteredText(b, cfg.text, p.x + p.w * 0.5, p.y + p.h * 0.48, cfg.textColor, {
      font: fontString(cfg),
      alpha: 0.24,
      filter: "blur(1.8px)"
    });
    drawCenteredText(b, cfg.text, p.x + p.w * 0.5, p.y + p.h * 0.48, cfg.textColor, {
      font: fontString(cfg)
    });

    if ([0, 1, 2, 3, 4, 5].includes(frame % 30)) {
      b.strokeStyle = "rgba(198,210,208,0.4)";
      b.lineWidth = 2;
      b.beginPath();
      b.moveTo(p.x - 8, p.y + 8);
      b.lineTo(p.x - 8, p.y + p.h - 6);
      b.stroke();
    }
    if (frame % 23 === 0) {
      b.fillStyle = "rgba(210,255,255,0.13)";
      b.fillRect(p.x + 7, p.y + 7, p.w - 13, 7);
    }
    drawScanlines(b, block.width, block.height, 0.012, 4);
    drawNoise(b, block.width, block.height, frame, 0.012, 2);
    drawDiagonalSweep(b, block.width, block.height, frame, {
      alpha: cfg.sweepAlpha ?? 0.08,
      width: cfg.sweepWidth ?? 22,
      period: cfg.sweepPeriod ?? 95
    });
    block = displaceRows(block, frame, cfg.waveDisplace ?? 1);
    block = opticsBulge(block, cfg.opticsBulge ?? 0);
    ctx.save();
    ctx.globalAlpha = clamp(intro);
    ctx.drawImage(block, cx - block.width / 2, cy - block.height / 2);
    ctx.restore();
  }

  function drawOldTv(ctx, cfg, time, alphaOutput) {
    const frame = frameIndex(cfg, time);
    const intro = introOpacity(cfg, frame, time);
    const phase = frame * 0.18;
    const [cx, cy] = cfg.center;
    let block = makeCanvas(250, 140);
    let b = block.getContext("2d");

    b.save();
    roundedRect(b, 56, 55, 135, 40, 6);
    b.fillStyle = "rgba(7,8,10,0.52)";
    b.fill();
    b.restore();

    b.font = fontString(cfg);
    const grad = b.createLinearGradient(0, 48, 0, 94);
    grad.addColorStop(0, cfg.gradientTop);
    grad.addColorStop(1, cfg.gradientBottom);
    drawCenteredText(b, cfg.text, 124, 72, cfg.glowColor, {
      font: fontString(cfg),
      alpha: cfg.glowAlpha ?? 0.55,
      filter: `blur(${cfg.glowBlur}px)`,
      strokeStyle: cfg.glowColor,
      lineWidth: 3
    });
    drawCenteredText(b, cfg.text, 124, 72, cfg.glowColor, {
      font: fontString(cfg),
      alpha: cfg.outerGlowAlpha ?? 0.18,
      filter: `blur(${(cfg.glowBlur ?? 4.4) * 2.25}px)`,
      strokeStyle: cfg.glowColor,
      lineWidth: 5
    });
    drawCenteredText(b, cfg.text, 124, 72, "#101426", {
      font: fontString(cfg),
      strokeStyle: "#101426",
      lineWidth: 4
    });
    drawCenteredText(b, cfg.text, 124, 72, cfg.gradientTop, {
      font: fontString(cfg),
      gradient: grad
    });

    drawCenteredText(b, cfg.text, 124, 72, "rgba(255,255,255,0.2)", {
      font: fontString(cfg),
      filter: "blur(0.45px)"
    });

    const barColor = cfg.barColorRgba ?? "rgba(54,68,118,0.68)";
    b.save();
    b.translate(58, 11);
    drawWavyBar(b, 134, 14, barColor, phase, false, { seed: 61, noiseAmp: 1.35 });
    b.restore();
    b.save();
    b.translate(57, 22);
    drawWavyBar(b, 137, 11, "rgba(31,40,75,0.54)", phase + 0.9, true, { seed: 73, noiseAmp: 1.2 });
    b.restore();
    b.save();
    b.translate(57, 106);
    drawWavyBar(b, 137, 12, "rgba(108,120,128,0.42)", phase + 2.2, true, { seed: 89, noiseAmp: 1.1 });
    b.restore();
    b.save();
    b.translate(56, 119);
    drawWavyBar(b, 141, 13, "rgba(128,139,141,0.58)", phase + 3.1, true, { seed: 97, noiseAmp: 1.25 });
    b.restore();
    drawBrokenHorizontal(b, 18, 137, "rgba(75,91,145,0.38)", phase + 0.4, { x: 57, lineWidth: 2, blur: 0.35, segment: 17, gap: 5, amp: 1.2 });
    drawBrokenHorizontal(b, 125, 142, "rgba(136,143,142,0.34)", phase + 2.5, { x: 55, lineWidth: 2, blur: 0.3, segment: 14, gap: 6, amp: 1.1 });

    b.strokeStyle = barColor;
    b.lineWidth = 5;
    drawWobblyArc(b, 40, 71, 19, rad(105), rad(255), phase, { seed: 103, amp: 0.75 });
    drawWobblyArc(b, 212, 71, 20, rad(-75), rad(75), phase + 0.6, { seed: 109, amp: 0.75 });
    b.globalAlpha = cfg.bracketEchoAlpha ?? 0.22;
    b.lineWidth = 3;
    drawWobblyArc(b, 35, 71, 22, rad(108), rad(252), phase + 1.4, { seed: 127, amp: 1.05 });
    drawWobblyArc(b, 218, 71, 23, rad(-72), rad(72), phase + 2.1, { seed: 131, amp: 1.05 });
    b.globalAlpha = 1;
    b.fillStyle = "rgba(118,130,136,0.42)";
    roundedRect(b, 151, 112, 17, 7, 3);
    b.fill();
    roundedRect(b, 178, 112, 21, 7, 3);
    b.fill();

    drawScanlines(b, block.width, block.height, cfg.scanlineAlpha ?? 0.016, 3);
    drawNoise(b, block.width, block.height, frame + 900, cfg.noiseAlpha ?? 0.014, 2);
    block = tearBands(block, frame, cfg.tearBands);
    block = displaceRows(block, frame, cfg.waveDisplace);
    ctx.save();
    ctx.globalAlpha = clamp(intro);
    ctx.drawImage(block, cx - block.width / 2, cy - block.height / 2);
    ctx.restore();
  }

  function drawRadialBlur(ctx, cfg, time, alphaOutput) {
    const frame = frameIndex(cfg, time);
    const intro = introOpacity(cfg, frame, time);
    const [cx, cy] = cfg.center;
    let block = makeCanvas(230, 78);
    let b = block.getContext("2d");
    const font = fontString(cfg);
    const scaleY = cfg.textScaleY ?? 1;

    for (let i = cfg.radialCopies; i > 0; i -= 1) {
      const sc = 1 + i * cfg.radialStep;
      b.save();
      b.translate(115 - i * (cfg.radialOffsetX ?? 1.1), 39 + i * (cfg.radialOffsetY ?? 0.25));
      b.scale(sc, sc * scaleY);
      drawCenteredText(b, cfg.text, 0, 0, cfg.blurColor, {
        font,
        alpha: (cfg.radialOpacity / i) * (cfg.radialBoost ?? 1),
        filter: `blur(${i * (cfg.radialBlurStep ?? 0.45)}px)`
      });
      b.restore();
    }

    for (let i = 4; i >= 1; i -= 1) {
      b.save();
      b.translate(112 - i * 2.2, 43 + i * 0.45);
      b.scale(1 + i * 0.012, scaleY);
      drawCenteredText(b, cfg.text, 0, 0, cfg.shadowColor, {
        font,
        alpha: (cfg.magentaStreakAlpha ?? 0.08) / i,
        filter: `blur(${0.6 + i * 0.35}px)`
      });
      b.restore();
    }

    b.save();
    b.translate(112, 42);
    b.scale(1, scaleY);
    drawCenteredText(b, cfg.text, 0, 0, cfg.shadowColor, {
      font,
      alpha: cfg.shadowAlpha ?? 0.85,
      filter: "blur(0.4px)",
      strokeStyle: cfg.shadowColor,
      lineWidth: 1
    });
    b.restore();
    const grad = b.createLinearGradient(0, 20, 0, 60);
    grad.addColorStop(0, cfg.gradientTop);
    grad.addColorStop(1, cfg.gradientBottom);
    b.save();
    b.translate(115, 39);
    b.scale(1, scaleY);
    drawCenteredText(b, cfg.text, 0, 0, cfg.gradientTop, {
      font,
      gradient: grad,
      strokeStyle: cfg.gradientTop,
      lineWidth: 1
    });
    drawCenteredText(b, cfg.text, -1, -1, "rgba(255,255,255,0.28)", {
      font,
      alpha: cfg.highlightAlpha ?? 0.28,
      filter: "blur(0.55px)"
    });
    b.restore();
    drawDiagonalSweep(b, block.width, block.height, frame, {
      alpha: cfg.sweepAlpha ?? 0.12,
      width: cfg.sweepWidth ?? 24,
      period: cfg.sweepPeriod ?? 150
    });
    block = displaceRows(block, frame, [0, 1].includes(frame % 41) ? 1 : 0);
    ctx.save();
    ctx.globalAlpha = clamp(intro);
    ctx.drawImage(block, cx - block.width / 2, cy - block.height / 2);
    ctx.restore();
  }

  const recipes = {
    ERROR_TEXT: drawErrorText,
    OLD_TV: drawOldTv,
    VHS: drawVhs,
    Radial_BLUR: drawRadialBlur
  };

  async function loadFonts() {
    if (!("FontFace" in window)) return;
    const promises = Object.entries(FONT_URLS).map(([family, url]) => {
      const face = new FontFace(family, `url("${url}")`);
      document.fonts.add(face);
      return face.load().catch(() => null);
    });
    await Promise.all(promises);
    await document.fonts.ready;
  }

  function readConfig() {
    const node = document.getElementById("analog-config");
    if (!node) throw new Error("Missing #analog-config JSON island");
    return JSON.parse(node.textContent);
  }

  function boot() {
    const root = document.querySelector("[data-composition-id]");
    const canvas = document.getElementById("analog-canvas");
    const cfg = readConfig();
    const ctx = canvas.getContext("2d", { alpha: true });
    const params = new URLSearchParams(window.location.search);
    const renderMode = params.get("render") === "1";
    const alphaOutput = params.get("alpha") === "1";
    const recipe = recipes[cfg.slug];
    if (!recipe) throw new Error(`No analog recipe for ${cfg.slug}`);

    canvas.width = cfg.width;
    canvas.height = cfg.height;
    root.style.width = `${cfg.width}px`;
    root.style.height = `${cfg.height}px`;
    root.dataset.duration = String(cfg.duration);
    root.dataset.width = String(cfg.width);
    root.dataset.height = String(cfg.height);

    function renderFrame(time, opts = {}) {
      const transparent = opts.alpha ?? alphaOutput;
      ctx.clearRect(0, 0, cfg.width, cfg.height);
      if (!transparent) {
        ctx.fillStyle = "#000000";
        ctx.fillRect(0, 0, cfg.width, cfg.height);
      }
      recipe(ctx, cfg, clamp(time, 0, cfg.duration), transparent);
      return true;
    }

    window.__timelines = window.__timelines || {};
    window.__timelines[cfg.compositionId] = {
      seek: renderFrame,
      time: renderFrame,
      pause() {},
      play() {},
      duration: () => cfg.duration
    };
    window.__analogConfig = cfg;
    window.__analogRenderFrame = renderFrame;

    let startedAt = 0;
    function loop(ts) {
      if (!startedAt) startedAt = ts;
      const t = ((ts - startedAt) / 1000) % cfg.duration;
      renderFrame(t);
      window.requestAnimationFrame(loop);
    }

    loadFonts().then(() => {
      renderFrame(0, { alpha: alphaOutput });
      window.__analogReady = true;
      if (!renderMode) window.requestAnimationFrame(loop);
    });
  }

  window.AnalogGlitch = { boot };
})();
