(function () {
  const SVG_NS = "http://www.w3.org/2000/svg";

  function clamp(value, min = 0, max = 1) {
    return Math.max(min, Math.min(max, value));
  }

  function easeOutCubic(value) {
    const t = clamp(value);
    return 1 - Math.pow(1 - t, 3);
  }

  function rgb(value) {
    return `rgb(${value[0]}, ${value[1]}, ${value[2]})`;
  }

  function idSafe(value) {
    return String(value).replace(/[^a-zA-Z0-9_-]+/g, "-");
  }

  function svgEl(tag, attrs = {}) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value !== undefined && value !== null) {
        node.setAttribute(key, String(value));
      }
    }
    return node;
  }

  function addGradient(defs, id, top, bottom) {
    const gradient = svgEl("linearGradient", {
      id,
      x1: "0",
      y1: "0",
      x2: "0",
      y2: "1",
    });
    gradient.append(
      svgEl("stop", { offset: "0%", "stop-color": rgb(top) }),
      svgEl("stop", { offset: "100%", "stop-color": rgb(bottom) })
    );
    defs.append(gradient);
    return `url(#${id})`;
  }

  function addGlowFilter(defs, id, radius, color, opacity) {
    const filter = svgEl("filter", {
      id,
      x: "-80%",
      y: "-120%",
      width: "260%",
      height: "340%",
      "color-interpolation-filters": "sRGB",
    });
    filter.append(
      svgEl("feGaussianBlur", { in: "SourceAlpha", stdDeviation: radius, result: "blur" }),
      svgEl("feFlood", { "flood-color": rgb(color), "flood-opacity": opacity, result: "glowColor" }),
      svgEl("feComposite", { in: "glowColor", in2: "blur", operator: "in", result: "glow" }),
      svgEl("feMerge", {})
    );
    filter.lastElementChild.append(svgEl("feMergeNode", { in: "glow" }), svgEl("feMergeNode", { in: "SourceGraphic" }));
    defs.append(filter);
    return `url(#${id})`;
  }

  function addTurbulenceFilter(defs, id, spec = {}) {
    const filter = svgEl("filter", {
      id,
      x: "-16%",
      y: "-30%",
      width: "132%",
      height: "170%",
      "color-interpolation-filters": "sRGB",
    });
    filter.append(
      svgEl("feTurbulence", {
        type: spec.type || "fractalNoise",
        baseFrequency: spec.frequency || "0.018 0.12",
        numOctaves: spec.octaves || 2,
        seed: spec.seed || 7,
        result: "noise",
      }),
      svgEl("feDisplacementMap", {
        in: "SourceGraphic",
        in2: "noise",
        scale: spec.scale || 2.2,
        xChannelSelector: "R",
        yChannelSelector: "G",
        result: "displaced",
      })
    );
    if (spec.blur) {
      filter.append(svgEl("feGaussianBlur", { in: "displaced", stdDeviation: spec.blur, result: "soft" }));
      filter.append(svgEl("feMerge", {}));
      filter.lastElementChild.append(svgEl("feMergeNode", { in: "soft" }));
    }
    defs.append(filter);
    return `url(#${id})`;
  }

  function addRadialGradient(defs, id, color, opacity = 1) {
    const gradient = svgEl("radialGradient", {
      id,
      cx: "50%",
      cy: "50%",
      r: "55%",
      fx: "50%",
      fy: "50%",
    });
    gradient.append(
      svgEl("stop", { offset: "0%", "stop-color": rgb(color), "stop-opacity": opacity }),
      svgEl("stop", { offset: "62%", "stop-color": rgb(color), "stop-opacity": opacity * 0.42 }),
      svgEl("stop", { offset: "100%", "stop-color": rgb(color), "stop-opacity": 0 })
    );
    defs.append(gradient);
    return `url(#${id})`;
  }

  function seeded01(seed, index) {
    const value = Math.sin((seed || 1) * 129.17 + index * 73.91) * 43758.5453;
    return value - Math.floor(value);
  }

  function makeText(spec, fill, className = "ag-text") {
    const text = svgEl("text", {
      class: className,
      x: spec.x || 0,
      y: spec.y || 0,
      "font-family": spec.font,
      "font-size": spec.size,
      "font-style": spec.font && spec.font.includes("Italic") ? "italic" : "normal",
      "font-weight": "900",
      "letter-spacing": spec.tracking || 0,
      fill,
    });
    text.textContent = String(spec.text || "").replace(/\r/g, "");
    return text;
  }

  function transformStyle(layer = {}) {
    const parts = [];
    if (layer.dx || layer.dy) {
      parts.push(`translate(${layer.dx || 0}px, ${layer.dy || 0}px)`);
    }
    if (layer.scale_x || layer.scale_y) {
      parts.push(`scale(${layer.scale_x || 1}, ${layer.scale_y || 1})`);
    }
    if (layer.skew_x) {
      parts.push(`skewX(${layer.skew_x}deg)`);
    }
    return parts.join(" ");
  }

  function drawHaloLayers(svg, spec, halos = [], className = "ag-halo") {
    for (const [index, halo] of halos.entries()) {
      const haloText = makeText(spec, rgb(halo.color || spec.top), `ag-text ${className}`);
      haloText.setAttribute("opacity", halo.opacity ?? 0.2);
      if (halo.blur) {
        haloText.setAttribute("filter", `blur(${halo.blur}px)`);
      }
      const transform = transformStyle(halo);
      if (transform) {
        haloText.style.transform = transform;
      }
      if (halo.stroke_width) {
        haloText.setAttribute("stroke", rgb(halo.stroke_color || halo.color || spec.top));
        haloText.setAttribute("stroke-width", halo.stroke_width);
        haloText.setAttribute("stroke-opacity", halo.stroke_opacity ?? halo.opacity ?? 0.2);
      }
      if (halo.mix_blend_mode) {
        haloText.style.mixBlendMode = halo.mix_blend_mode;
      }
      haloText.dataset.haloIndex = String(index);
      svg.append(haloText);
    }
  }

  function drawReflection(svg, defs, spec, index, fill) {
    if (!spec.reflection || spec.reflection.opacity <= 0) {
      return;
    }
    const ref = spec.reflection;
    const reflectionFill = ref.top || ref.bottom
      ? addGradient(defs, `reflection-gradient-${index}`, ref.top || spec.bottom || spec.top, ref.bottom || [0, 0, 0])
      : fill;
    const group = svgEl("g", {
        opacity: ref.opacity,
      filter: ref.blur ? `blur(${ref.blur}px)` : undefined,
      transform: `translate(${ref.dx || 0} ${ref.dy || spec.size * 0.72}) scale(${ref.scale_x || 1} -${ref.scale_y || 0.55}) translate(0 ${-(spec.y || 0) * 2 - spec.size})`,
    });
    const text = makeText(spec, reflectionFill, "ag-text ag-reflection");
    group.append(text);
    svg.append(group);
  }

  function drawPanel(svg, defs, panel, index) {
    const [x, y, w, h] = panel.rect;
    const glow = panel.glow;
    if (glow) {
      const glowRect = svgEl("rect", {
        x,
        y,
        width: w,
        height: h,
        rx: panel.radius || 8,
        fill: rgb(glow.color),
        opacity: glow.opacity || 0.4,
        filter: `blur(${glow.radius || 10}px)`,
      });
      svg.append(glowRect);
    }
    if (panel.shadow) {
      const s = panel.shadow;
      svg.append(svgEl("rect", {
        x: x + (s.dx || 0),
        y: y + (s.dy || 0),
        width: w,
        height: h,
        rx: panel.radius || 8,
        fill: rgb(s.color || [0, 0, 0]),
        opacity: s.opacity || 0.6,
        filter: `blur(${s.blur || 8}px)`,
      }));
    }
    for (const [depthIndex, depth] of (panel.depth || []).entries()) {
      const depthFill = addGradient(defs, `panel-depth-${index}-${depthIndex}`, depth.top || panel.top, depth.bottom || panel.bottom);
      const dRect = svgEl("rect", {
        x: x + (depth.dx || 0),
        y: y + (depth.dy || 0),
        width: w,
        height: h,
        rx: panel.radius || 8,
        fill: depthFill,
        opacity: depth.opacity || 0.32,
        filter: depth.blur ? `blur(${depth.blur}px)` : undefined,
      });
      svg.append(dRect);
    }
    const fill = addGradient(defs, `panel-gradient-${index}`, panel.top, panel.bottom);
    const rect = svgEl("rect", {
      x,
      y,
      width: w,
      height: h,
      rx: panel.radius || 8,
      fill,
      opacity: panel.opacity !== undefined ? panel.opacity / 255 : undefined,
      filter: panel.turbulence ? addTurbulenceFilter(defs, `panel-turbulence-${index}`, panel.turbulence) : undefined,
    });
    svg.append(rect);
    for (const [burnIndex, burn] of (panel.burns || []).entries()) {
      const burnFill = addRadialGradient(defs, `panel-burn-${index}-${burnIndex}`, burn.color || panel.top, burn.opacity || 0.2);
      svg.append(svgEl("ellipse", {
        cx: x + (burn.cx || w * 0.5),
        cy: y + (burn.cy || h * 0.5),
        rx: burn.rx || w * 0.45,
        ry: burn.ry || h * 0.38,
        fill: burnFill,
        opacity: burn.opacity || 0.2,
        filter: burn.blur ? `blur(${burn.blur}px)` : undefined,
      }));
    }
    svg.append(svgEl("rect", {
      x: x + 2,
      y: y + 2,
      width: Math.max(1, w - 4),
      height: Math.max(1, h * 0.44),
      rx: Math.max(1, (panel.radius || 8) - 2),
      fill: "#fff",
      opacity: 0.13,
    }));
    if (panel.lip) {
      svg.append(svgEl("rect", {
        x: x + (panel.lip.dx || 0),
        y: y + h - (panel.lip.height || 8) + (panel.lip.dy || 0),
        width: w,
        height: panel.lip.height || 8,
        rx: Math.max(1, (panel.radius || 8) - 3),
        fill: rgb(panel.lip.color || panel.bottom),
        opacity: panel.lip.opacity || 0.3,
        filter: panel.lip.blur ? `blur(${panel.lip.blur}px)` : undefined,
      }));
    }
    if (panel.noise) {
      const clipId = `panel-noise-clip-${index}`;
      const clip = svgEl("clipPath", { id: clipId });
      clip.append(svgEl("rect", { x, y, width: w, height: h, rx: panel.radius || 8 }));
      defs.append(clip);
      const noise = svgEl("g", { "clip-path": `url(#${clipId})`, opacity: panel.noise.opacity || 0.14 });
      const seed = panel.noise.seed || 11;
      for (let n = 0; n < (panel.noise.count || 22); n += 1) {
        const nx = x + seeded01(seed, n) * w;
        const ny = y + seeded01(seed + 3, n) * h;
        const nw = (panel.noise.min_width || 18) + seeded01(seed + 9, n) * (panel.noise.max_width || 50);
        noise.append(svgEl("rect", {
          x: nx.toFixed(2),
          y: ny.toFixed(2),
          width: nw.toFixed(2),
          height: panel.noise.height || 1.2,
          fill: rgb(panel.noise.color || [255, 255, 255]),
          opacity: 0.25 + seeded01(seed + 17, n) * 0.55,
          transform: `rotate(${(panel.noise.angle || -4).toFixed(2)} ${nx.toFixed(2)} ${ny.toFixed(2)})`,
        }));
      }
      svg.append(noise);
    }
    if (panel.edge) {
      svg.append(svgEl("rect", {
        x: x + 1,
        y: y + 1,
        width: Math.max(1, w - 2),
        height: Math.max(1, h - 2),
        rx: panel.radius || 8,
        fill: "none",
        stroke: rgb(panel.edge),
        "stroke-opacity": (panel.edge_alpha || 60) / 255,
      }));
    }
  }

  function drawHaze(svg, defs, haze, index) {
    const fill = haze.radial
      ? addRadialGradient(defs, `haze-radial-${index}`, haze.color, haze.opacity || 0.35)
      : rgb(haze.color);
    const attrs = {
      fill,
      opacity: haze.radial ? 1 : haze.opacity || 0.35,
      filter: haze.blur ? `blur(${haze.blur}px)` : undefined,
      transform: haze.rotate ? `rotate(${haze.rotate} ${haze.cx || 320} ${haze.cy || 180})` : undefined,
    };
    if (haze.type === "ellipse") {
      svg.append(svgEl("ellipse", {
        ...attrs,
        cx: haze.cx,
        cy: haze.cy,
        rx: haze.rx,
        ry: haze.ry,
      }));
    } else {
      svg.append(svgEl("rect", {
        ...attrs,
        x: haze.rect[0],
        y: haze.rect[1],
        width: haze.rect[2],
        height: haze.rect[3],
        rx: haze.radius || 10,
      }));
    }
  }

  function drawBackdrops(svg, defs, background = {}) {
    const group = svgEl("g", { class: "ag-backdrop" });
    svg.append(group);
    group.dataset.noBox = "true";
    return group;
  }

  function drawText(svg, defs, spec, index) {
    const fill = addGradient(defs, `text-gradient-${index}`, spec.top, spec.bottom || spec.top);
    drawHaloLayers(svg, spec, spec.halos || []);
    drawReflection(svg, defs, spec, index, fill);
    if (spec.shadow) {
      const s = spec.shadow;
      const shadow = makeText({ ...spec, x: spec.x + (s.dx || 0), y: spec.y + (s.dy || 0) }, rgb(s.color || [0, 0, 0]), "ag-text ag-shadow");
      shadow.setAttribute("opacity", s.opacity ?? 0.55);
      shadow.setAttribute("filter", `blur(${s.blur || 2}px)`);
      svg.append(shadow);
    }
    if (spec.extrude) {
      const e = spec.extrude;
      for (let step = e.steps || 3; step >= 1; step -= 1) {
        const extrude = makeText({ ...spec, x: spec.x + (e.dx || 1) * step, y: spec.y + (e.dy || 1) * step }, rgb(e.color || [20, 20, 20]), "ag-text ag-extrude");
        extrude.setAttribute("opacity", e.opacity ?? 0.55);
        svg.append(extrude);
      }
    }
    for (const [glowIndex, glow] of (spec.glows || []).entries()) {
      const glowText = makeText(spec, rgb(glow.color), "ag-text ag-glow");
      glowText.setAttribute("opacity", glow.opacity ?? 0.4);
      glowText.setAttribute("filter", `blur(${glow.radius || 8}px)`);
      svg.append(glowText);
      if (glowIndex === 0) {
        glowText.setAttribute("data-primary-glow", "true");
      }
    }
    const face = makeText(spec, fill);
    if (spec.stroke) {
      face.setAttribute("stroke", rgb(spec.stroke.color || [0, 0, 0]));
      face.setAttribute("stroke-width", spec.stroke.width || 1);
      face.setAttribute("stroke-opacity", spec.stroke.opacity ?? 0.55);
    }
    if (spec.wave) {
      face.style.transform = `skewX(-${Math.min(4, Math.abs(spec.wave.amp || 1.0) * 2)}deg)`;
    }
    if (spec.turbulence) {
      face.setAttribute("filter", addTurbulenceFilter(defs, `text-turbulence-${index}`, spec.turbulence));
    }
    svg.append(face);
    if (spec.blinds) {
      const maskId = `text-blinds-mask-${index}`;
      const mask = svgEl("mask", { id: maskId, maskUnits: "userSpaceOnUse", x: 0, y: 0, width: 640, height: 360 });
      mask.append(makeText(spec, "#fff"));
      defs.append(mask);
      const stripes = svgEl("g", { mask: `url(#${maskId})`, opacity: spec.blinds.opacity || 0.18 });
      const step = spec.blinds.step || 8;
      const height = spec.blinds.height || 2;
      for (let yy = spec.y - spec.size * 0.12; yy < spec.y + spec.size * 1.15; yy += step) {
        stripes.append(svgEl("rect", {
          x: spec.x - 8,
          y: yy,
          width: spec.size * String(spec.text || "").length * 0.72,
          height,
          fill: rgb(spec.blinds.color || [0, 0, 0]),
        }));
      }
      svg.append(stripes);
    }
    if (spec.sweep) {
      const sw = spec.sweep;
      const sweep = makeText(spec, "#fff", "ag-text ag-sweep");
      sweep.setAttribute("opacity", sw.opacity || 0.15);
      sweep.setAttribute("filter", `blur(${sw.blur || 1}px)`);
      sweep.style.clipPath = `polygon(${Math.max(0, sw.center * 100 - sw.width)}% 0, ${Math.min(100, sw.center * 100 + sw.width)}% 0, ${Math.min(100, sw.center * 100 + sw.width - 12)}% 100%, ${Math.max(0, sw.center * 100 - sw.width - 12)}% 100%)`;
      svg.append(sweep);
    }
  }

  function drawStatic(config, svg, defs) {
    const group = svgEl("g", { id: "static-stage" });
    svg.append(group);
    if (config.recipe.background) {
      drawBackdrops(group, defs, config.recipe.background);
    }
    for (const [index, text] of (config.recipe.texts || []).entries()) {
      drawText(group, defs, text, index);
    }
    return function renderAt(time) {
      const motion = config.recipe.motion || {};
      const intro = motion.intro || 0.7;
      const p = easeOutCubic(time / intro);
      const dx = (motion.from_dx || 0) * (1 - p);
      const dy = (motion.from_dy || 0) * (1 - p);
      const fromScale = motion.from_scale || 1;
      const scale = fromScale + (1 - fromScale) * p;
      group.setAttribute("opacity", p.toFixed(4));
      group.setAttribute("transform", `translate(${dx.toFixed(3)} ${dy.toFixed(3)}) scale(${scale.toFixed(4)})`);
    };
  }

  function drawCrossing(config, svg, defs) {
    const items = [];
    const stage = svgEl("g", { id: "crossing-stage" });
    svg.append(stage);
    const background = config.recipe.background ? drawBackdrops(stage, defs, config.recipe.background) : null;
    const sorted = [...config.recipe.crossing_texts].sort((a, b) => (a.z || 0) - (b.z || 0));
    for (const [index, spec] of sorted.entries()) {
      const fill = addGradient(defs, `cross-gradient-${index}`, spec.top, spec.bottom || spec.top);
      const group = svgEl("g", { id: `cross-${index}` });
      drawHaloLayers(group, { ...spec, x: 0, y: 0 }, spec.halos || [], "ag-cross-halo");
      if (spec.reflection) {
        const ref = spec.reflection;
        const reflectionFill = ref.top || ref.bottom
          ? addGradient(defs, `cross-reflection-gradient-${index}`, ref.top || spec.bottom || spec.top, ref.bottom || [0, 0, 0])
          : fill;
        const reflection = makeText({ ...spec, x: 0, y: 0 }, reflectionFill, "ag-text ag-cross-reflection");
        reflection.setAttribute("opacity", ref.opacity ?? 0.14);
        reflection.setAttribute("filter", ref.blur ? `blur(${ref.blur}px)` : "");
        reflection.setAttribute(
          "transform",
          `translate(${ref.dx || 0} ${(ref.dy || spec.size * 0.72) + spec.size * 1.05}) scale(${ref.scale_x || 1} -${ref.scale_y || 0.5})`
        );
        group.append(reflection);
      }
      if (spec.shadow) {
        const s = spec.shadow;
        const shadow = makeText({ ...spec, x: s.dx || 0, y: s.dy || 0 }, rgb(s.color || [0, 0, 0]), "ag-text ag-cross-shadow");
        shadow.setAttribute("opacity", s.opacity ?? 0.45);
        shadow.setAttribute("filter", `blur(${s.blur || 2}px)`);
        group.append(shadow);
      }
      if (spec.extrude) {
        const e = spec.extrude;
        for (let step = e.steps || 3; step >= 1; step -= 1) {
          const extrude = makeText({ ...spec, x: (e.dx || 1) * step, y: (e.dy || 1) * step }, rgb(e.color || [20, 20, 20]), "ag-text ag-cross-extrude");
          extrude.setAttribute("opacity", e.opacity ?? 0.55);
          group.append(extrude);
        }
      }
      const glow = spec.glow;
      if (glow) {
        const glowText = makeText({ ...spec, x: 0, y: 0 }, rgb(glow.color), "ag-text ag-cross-glow");
        group.append(glowText);
      }
      const face = makeText({ ...spec, x: 0, y: 0 }, fill, "ag-text ag-cross-face");
      if (spec.stroke) {
        face.setAttribute("stroke", rgb(spec.stroke.color || [0, 0, 0]));
        face.setAttribute("stroke-width", spec.stroke.width || 1);
        face.setAttribute("stroke-opacity", spec.stroke.opacity ?? 0.55);
      }
      group.append(face);
      stage.append(group);
      items.push({ spec, group });
    }
    return function renderAt(time) {
      const intro = config.recipe.crossing_intro || 1.1;
      const p = easeOutCubic(time / intro);
      const introOpacity = config.recipe.intro_opacity;
      if (introOpacity) {
        const start = introOpacity.start ?? 1;
        const endTime = Math.max(0.001, introOpacity.end_time || 0.17);
        const opacity = start + (1 - start) * clamp(time / endTime);
        stage.setAttribute("opacity", opacity.toFixed(4));
      }
      if (background) {
        const bg = config.recipe.background || {};
        const fadeStart = bg.fade_start ?? 0.25;
        const fadeEnd = bg.fade_end ?? 1.05;
        background.setAttribute("opacity", clamp((time - fadeStart) / Math.max(0.001, fadeEnd - fadeStart)).toFixed(4));
      }
      for (const item of items) {
        const spec = item.spec;
        const x = spec.start[0] * (1 - p) + spec.end[0] * p;
        const y = spec.start[1] * (1 - p) + spec.end[1] * p;
        const blur = (spec.start_blur || 0) * (1 - p) + (spec.end_blur || 0) * p;
        const glow = spec.glow || {};
        const glowRadius = (glow.start_radius || 0) * (1 - p) + (glow.end_radius || 0) * p;
        const glowOpacity = (glow.start_opacity || 0) * (1 - p) + (glow.end_opacity || 0) * p;
        item.group.setAttribute("transform", `translate(${x.toFixed(3)} ${y.toFixed(3)})`);
        item.group.style.filter = blur > 0.05 ? `blur(${blur.toFixed(3)}px)` : "";
        const glowNode = item.group.querySelector(".ag-cross-glow");
        if (glowNode) {
          glowNode.setAttribute("opacity", glowOpacity.toFixed(4));
          glowNode.setAttribute("filter", glowRadius > 0.05 ? `blur(${glowRadius.toFixed(3)}px)` : "");
        }
        for (const haloNode of item.group.querySelectorAll(".ag-cross-halo")) {
          const haloIndex = Number(haloNode.dataset.haloIndex || 0);
          const halo = (spec.halos || [])[haloIndex] || {};
          const startOpacity = halo.start_opacity ?? halo.opacity ?? 0.2;
          const endOpacity = halo.end_opacity ?? halo.opacity ?? startOpacity;
          const opacity = startOpacity * (1 - p) + endOpacity * p;
          const startBlur = halo.start_blur ?? halo.blur ?? 0;
          const endBlur = halo.end_blur ?? halo.blur ?? startBlur;
          const haloBlur = startBlur * (1 - p) + endBlur * p;
          haloNode.setAttribute("opacity", opacity.toFixed(4));
          haloNode.setAttribute("filter", haloBlur > 0.05 ? `blur(${haloBlur.toFixed(3)}px)` : "");
        }
      }
    };
  }

  function makeTimeline(duration, renderAt) {
    let current = 0;
    const timeline = {
      paused: true,
      duration() {
        return duration;
      },
      time(value) {
        if (value === undefined) {
          return current;
        }
        current = clamp(Number(value) || 0, 0, duration);
        renderAt(current);
        return timeline;
      },
      seek(value) {
        return timeline.time(value);
      },
      progress(value) {
        if (value === undefined) {
          return duration === 0 ? 0 : current / duration;
        }
        return timeline.time((Number(value) || 0) * duration);
      },
      pause() {
        return timeline;
      },
    };
    renderAt(0);
    return timeline;
  }

  function drawCrossingHtml(root, config) {
    const stage = document.createElement("div");
    stage.className = `ag-html-stage ag-${config.slug.toLowerCase().replace(/_/g, "-")}`;
    const words = config.recipe.crossing_texts.map((spec, index) => {
      const word = document.createElement("span");
      word.className = `ag-html-word ag-html-word-${index + 1}`;
      word.textContent = spec.text;
      word.dataset.text = spec.text;
      word.style.fontFamily = `"${spec.font}"`;
      word.style.fontSize = `${spec.size}px`;
      word.style.setProperty("--word-top", rgb(spec.top));
      word.style.setProperty("--word-bottom", rgb(spec.bottom));
      stage.append(word);
      return word;
    });
    root.querySelector(".ag-stage").append(stage);
    const fit = () => words.forEach((word, index) => {
      if (word.scrollWidth <= 500) return;
      word.style.fontSize = `${Math.max(24, config.recipe.crossing_texts[index].size * (500 / word.scrollWidth))}px`;
    });
    requestAnimationFrame(fit);
    return (time) => {
      words.forEach((word, index) => {
        const delay = index * 0.24;
        const progress = easeOutCubic((time - delay) / 0.5);
        word.style.opacity = progress.toFixed(4);
        word.style.setProperty("--enter-y", `${((1 - progress) * 14).toFixed(2)}px`);
        const blur = (1 - progress) * (config.recipe.crossing_texts[index].start_blur ?? 4);
        word.style.filter = `blur(${blur.toFixed(2)}px)`;
      });
    };
  }

  async function loadConfig() {
    const embedded = document.getElementById("template-config");
    if (embedded) {
      return JSON.parse(embedded.textContent);
    }
    const params = new URLSearchParams(window.location.search);
    const slug = params.get("slug") || "AESTHETIC_PURPLE";
    const response = await fetch(`../../configs/${slug}.json`);
    return response.json();
  }

  async function boot() {
    const config = await loadConfig();
    const params = new URLSearchParams(window.location.search);
    if (config.recipe.crossing_texts) {
      config.recipe.crossing_texts[0].text = params.get("text1") || params.get("word1") || config.recipe.crossing_texts[0].text;
      config.recipe.crossing_texts[1].text = params.get("text2") || params.get("word2") || config.recipe.crossing_texts[1].text;
    }
    const root = document.querySelector("[data-composition-id]") || document.getElementById("composition-root");
    const resize = () => {
      root.style.setProperty("--hm-preview-scale", String(Math.min(window.innerWidth / 640, window.innerHeight / 360)));
    };
    resize();
    window.addEventListener("resize", resize, { passive: true });
    const compositionId = root.dataset.compositionId || `aesthetic-glow-${idSafe(config.slug)}`;
    root.dataset.compositionId = compositionId;
    root.dataset.duration = String(config.canvas.duration);

    if (document.fonts?.ready) await document.fonts.ready;

    const svg = config.recipe.crossing_texts ? undefined : svgEl("svg", { viewBox: "0 0 640 360", role: "img", "aria-label": config.slug });
    const defs = config.recipe.crossing_texts ? undefined : svgEl("defs");
    if (svg && defs) {
      svg.append(defs);
      root.querySelector(".ag-stage").append(svg);
    }

    const renderAt = config.recipe.crossing_texts ? drawCrossingHtml(root, config) : drawStatic(config, svg, defs);
    window.__timelines = window.__timelines || {};
    const timeline = makeTimeline(config.canvas.duration, renderAt);
    window.__timelines[compositionId] = timeline;
    const seekParam = new URLSearchParams(window.location.search).get("t");
    if (seekParam !== null) {
      timeline.time(Number(seekParam));
    }
    window.__aestheticGlowConfig = config;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
