(function () {
  const clamp = (value, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, value));
  const smoothstep = (edge0, edge1, value) => {
    const t = clamp((value - edge0) / Math.max(1e-6, edge1 - edge0));
    return t * t * (3 - 2 * t);
  };
  const easeOutBack = (value) => {
    const t = clamp(value);
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  };

  function rgba(values, alphaScale = 1) {
    const [r, g, b] = values;
    const alpha = values.length > 3 ? values[3] : 1;
    return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${clamp(alpha * alphaScale)})`;
  }

  function fontFamily(font = "") {
    if (font.includes("Bucklane")) return "BucklaneLocal";
    if (font.includes("Poppins")) return "PoppinsRegularLocal";
    return "MytupiLocal";
  }

  function create(tag, className, parent) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (parent) parent.appendChild(node);
    return node;
  }

  function applyBounds(node, bounds) {
    node.style.left = `${bounds[0]}px`;
    node.style.top = `${bounds[1]}px`;
    node.style.width = `${bounds[2]}px`;
    node.style.height = `${bounds[3]}px`;
  }

  function applyVars(node, vars = {}) {
    for (const [key, value] of Object.entries(vars)) {
      if (value !== undefined && value !== null) {
        node.style.setProperty(key.startsWith("--") ? key : `--${key}`, String(value));
      }
    }
  }

  function cssColor(value, fallback) {
    return typeof value === "string" && CSS.supports("color", value) ? value : fallback;
  }

  function gradientStops(colors) {
    return colors.map((color, index) => `${rgba(color)} ${(index / Math.max(1, colors.length - 1)) * 100}%`).join(", ");
  }

  function textSize(bounds, text, scale = 1, factor = 1.15) {
    const lineCount = Math.max(1, String(text).split(/\n/).length);
    return `${Math.round((bounds[3] / lineCount) * factor * scale)}px`;
  }

  function fitText(text, bounds, options = {}) {
    const minSize = options.minFontSize || 8;
    const padX = options.fitPadX || 0;
    const padY = options.fitPadY || 0;
    let size = parseFloat(getComputedStyle(text).fontSize);
    if (!Number.isFinite(size)) return;
    const maxWidth = Math.max(1, bounds[2] - padX);
    const maxHeight = Math.max(1, bounds[3] - padY);
    for (let guard = 0; guard < 80; guard += 1) {
      const widthFits = text.scrollWidth <= maxWidth + 1;
      const heightFits = text.scrollHeight <= maxHeight + 1;
      if (widthFits && heightFits) break;
      size -= 1;
      if (size <= minSize) {
        size = minSize;
        break;
      }
      text.style.setProperty("--font-size", `${Math.round(size)}px`);
    }
  }

  function addText(parent, spec, bounds, options = {}) {
    const holder = create("div", options.className || "ac-item", parent);
    applyBounds(holder, bounds);
    const text = create("div", "ac-text", holder);
    text.textContent = spec.text;
    text.dataset.text = spec.text;
    text.style.setProperty("--font-family", `"${fontFamily(spec.font)}"`);
    text.style.setProperty("--font-size", options.fontSize || (spec.fontSize ? `${spec.fontSize}px` : textSize(bounds, spec.text, spec.sizeScale || 1, options.lineFactor || 1.15)));
    text.style.setProperty("--line-height", options.lineHeight || String(spec.lineHeight || .82));
    if (spec.color) text.style.setProperty("--text-color", rgba(spec.color));
    if (options.shadow) text.style.setProperty("--text-shadow", options.shadow);
    if (spec.textOpacity != null) text.style.opacity = String(spec.textOpacity);
    if (options.glyphSweepAlpha != null) {
      text.style.setProperty("--glyph-sweep-opacity", String(options.glyphSweepAlpha));
      text.style.setProperty("--glyph-sweep-width", options.glyphSweepWidth || "8%");
      text.style.setProperty("--glyph-sweep-alpha", String(options.glyphSweepPeak ?? .85));
    }
    if (options.fit !== false) fitText(text, bounds, options);
    return { holder, text };
  }

  function motionState(recipe, t, fps, duration) {
    const frame = t * fps;
    const introSec = (recipe.introFrames || 24) / fps;
    const q = clamp(t / Math.max(1e-6, introSec));
    const state = {
      opacity: smoothstep(0, .28, q),
      x: 0,
      y: 0,
      scale: 1,
      scaleY: 1,
      reveal: 1,
      distort: 0,
      sweep: (t / Math.max(.001, duration)) * (recipe.sweepRate ?? 1.7) + (recipe.sweepOffset ?? .06),
    };

    if (recipe.motion === "smooth_bob") {
      state.y = Math.exp(-frame / 11) * Math.sin(frame * .72) * 12;
    } else if (recipe.motion === "right_slide") {
      const eased = easeOutBack(q);
      state.x = (recipe.startOffset?.[0] || 50) * (1 - eased);
      state.y = (recipe.startOffset?.[1] || 0) * (1 - eased);
    } else if (recipe.motion === "zoom_settle") {
      state.scale = 1.18 - .18 * easeOutBack(q);
    } else if (recipe.motion === "ladder") {
      state.y = Math.exp(-frame / 7) * Math.sin(frame * 1.1) * 10;
      state.scaleY = frame < 8 ? 1 + (8 - frame) * .035 : 1;
    } else if (recipe.motion === "center_reveal" || recipe.motion === "left_reveal") {
      state.reveal = smoothstep(0, 1, q);
      state.distort = (1 - state.reveal) * (recipe.revealDistort ?? 0);
    }
    return state;
  }

  function applyMotion(stage, recipe, time, fps, duration) {
    const state = motionState(recipe, time, fps, duration);
    stage.style.opacity = state.opacity.toFixed(4);
    stage.style.setProperty("--reveal", state.reveal.toFixed(4));
    stage.style.setProperty("--reveal-distort", state.distort.toFixed(4));
    stage.style.setProperty("--sweep-progress", (state.sweep % 1).toFixed(4));
    stage.style.transform = `translate(${state.x.toFixed(2)}px, ${state.y.toFixed(2)}px) scale(${state.scale.toFixed(4)}, ${(state.scale * state.scaleY).toFixed(4)})`;
    if (recipe.type === "clean_style") {
      const cleanProgress = easeOutBack(clamp(time / .52));
      const styleProgress = easeOutBack(clamp((time - .14) / .56));
      const clean = stage.querySelector(".clean-word");
      const style = stage.querySelector(".style-word");
      clean.style.opacity = clamp(time / .28).toFixed(4);
      clean.style.setProperty("--enter-x", `${((1 - cleanProgress) * -52).toFixed(2)}px`);
      clean.style.setProperty("--entrance-blur", `${((1 - clamp(time / .38)) * .45).toFixed(2)}px`);
      style.style.opacity = clamp((time - .14) / .28).toFixed(4);
      style.style.setProperty("--enter-x", `${((1 - styleProgress) * 58).toFixed(2)}px`);
      style.style.setProperty("--entrance-blur", `${((1 - clamp((time - .14) / .4)) * .45).toFixed(2)}px`);
    }
  }

  function buildPlain(root, recipe) {
    const stage = create(
      "div",
      `ac-stage plain-mask ${recipe.motion === "center_reveal" ? "reveal-center" : ""} ${recipe.motion === "left_reveal" ? "reveal-left" : ""} ${recipe.revealDistort ? "distorted-reveal" : ""}`,
      root
    );
    applyBounds(stage, recipe.bounds);
    applyVars(stage, {
      "sweep-width": recipe.sweepWidth || "9%",
      "reveal-skew": recipe.revealSkew || "-8deg",
      "reveal-pull": recipe.revealPull || "-7px",
    });
    const glow = recipe.glows?.[0];
    const shadow = glow
      ? `0 0 ${Math.max(2, glow.radius * 3)}px ${rgba(glow.color, glow.alpha)}`
      : "0 0 4px rgba(255,255,255,.16)";
    addText(stage, recipe, [0, 0, recipe.bounds[2], recipe.bounds[3]], {
      shadow,
      lineFactor: 1.12,
      glyphSweepAlpha: recipe.sweep === false ? 0 : recipe.sweepStrength ?? .14,
      glyphSweepWidth: recipe.sweepWidth || "8%",
    });
    return stage;
  }

  function buildGradient(root, recipe) {
    const stage = create("div", "ac-stage gradient-text", root);
    applyBounds(stage, recipe.bounds);
    applyVars(stage, {
      "gradient": gradientStops(recipe.gradient),
      "gradient-size": recipe.gradientSize || "112%",
      "gradient-travel": recipe.gradientTravel || "8%",
      "gradient-offset": recipe.gradientOffset || "-2%",
      "sweep-width": recipe.sweepWidth || "8%",
    });
    addText(stage, { ...recipe, color: [255, 255, 255, 1] }, [0, 0, recipe.bounds[2], recipe.bounds[3]], {
      shadow: "0 0 6px rgba(255,70,210,.22)",
      lineFactor: 1.12,
      glyphSweepAlpha: recipe.sweepStrength ?? .14,
      glyphSweepWidth: recipe.sweepWidth || "8%",
    });
    return stage;
  }

  function buildAppleStyle(root, recipe) {
    const stage = create("div", "ac-stage apple-style-mask", root);
    applyBounds(stage, recipe.bounds);
    applyVars(stage, {
      "apple-stroke-alpha": recipe.strokeAlpha ?? 0,
      "apple-stroke-width": recipe.strokeAlpha ? "1px" : "0",
      "apple-halo-opacity": recipe.haloOpacity ?? .18,
      "apple-halo-blur": `${recipe.haloBlur ?? 2.5}px`,
      "apple-sweep-opacity": recipe.sweepStrength ?? .18,
      "apple-sweep-width": recipe.sweepWidth || "8%",
      "apple-drop-alpha": recipe.dropAlpha ?? .16,
      "apple-drop-radius": `${recipe.dropRadius ?? 4}px`,
      "apple-depth-alpha": recipe.depthAlpha ?? .08,
    });
    addText(stage, recipe, [0, 0, recipe.bounds[2], recipe.bounds[3]], {
      lineHeight: String(recipe.lineHeight ?? 1.02),
      lineFactor: recipe.lineFactor ?? 1.12,
      shadow: `0 0 ${recipe.glowRadius ?? 3}px rgba(255,255,255,${recipe.glowAlpha ?? .06}), 0 4px 4px rgba(0,0,0,${recipe.shadowAlpha ?? .05})`,
      fit: recipe.fitText !== false,
    });
    return stage;
  }

  function buildCleanAesthetic(root, recipe) {
    const stage = create("div", "ac-stage clean-aesthetic reveal-left", root);
    applyBounds(stage, recipe.bounds);
    applyVars(stage, {
      "text-pad-y": `${recipe.textPadY ?? 7}px`,
      "pill-alpha": recipe.pill?.alpha ?? .64,
      "pill-border-alpha": recipe.pill?.borderAlpha ?? .58,
      "pill-radius": `${recipe.pill?.radius ?? 7}px`,
      "pill-inset-x": `${recipe.pill?.insetX ?? 4}px`,
      "pill-inset-y": `${recipe.pill?.insetY ?? 6}px`,
      "pill-shadow-alpha": recipe.pill?.shadowAlpha ?? .38,
      "text-glow-alpha": recipe.textGlowAlpha ?? .46,
      "text-glow-radius": `${recipe.textGlowRadius ?? 6}px`,
      "text-wide-glow-alpha": recipe.textWideGlowAlpha ?? .13,
      "text-wide-glow-radius": `${recipe.textWideGlowRadius ?? 11}px`,
      "text-halo-opacity": recipe.textHaloOpacity ?? .42,
      "text-halo-blur": `${recipe.textHaloBlur ?? 4}px`,
      "text-sweep-opacity": recipe.textSweepOpacity ?? .13,
      "text-shadow-alpha": recipe.textShadowAlpha ?? .28,
    });
    create("div", "ac-pill", stage);
    addText(stage, recipe, [0, 0, recipe.bounds[2], recipe.bounds[3]], {
      fontSize: `${Math.round(recipe.bounds[3] * (recipe.fontBoundsScale ?? .4))}px`,
      lineHeight: "1",
    });
    return stage;
  }

  function addLine(stage, className, line, bounds, fontSize) {
    const holder = create("div", `ac-item ${className}`, stage);
    applyBounds(holder, bounds);
    applyVars(holder, line.vars || {});
    const text = create("div", "ac-text", holder);
    text.textContent = line.text;
    text.dataset.text = line.text;
    text.style.setProperty("--font-family", `"${fontFamily(line.font)}"`);
    text.style.setProperty("--font-size", `${fontSize}px`);
    text.style.setProperty("--line-height", ".8");
  }

  function buildCleanBlue(root, recipe) {
    const stage = create("div", "ac-stage clean-blue", root);
    applyBounds(stage, recipe.bounds);
    applyVars(stage, {
      "top-glow-alpha": recipe.topGlowAlpha ?? .34,
      "bottom-glow-alpha": recipe.bottomGlowAlpha ?? .52,
      "teal-shadow-alpha": recipe.tealShadowAlpha ?? .42,
      "top-blue-glow-alpha": recipe.topBlueGlowAlpha ?? .13,
      "bottom-depth-alpha": recipe.bottomDepthAlpha ?? .22,
    });
    addLine(stage, "top-word", recipe.lines[0], recipe.topBounds || [-1, -1, 163, 59], recipe.topFontSize || 51);
    addLine(stage, "bottom-word", recipe.lines[1], recipe.bottomBounds || [0, 31, 161, 73], recipe.bottomFontSize || 52);
    return stage;
  }

  function buildCleanStyle(root, recipe) {
    const stage = create("div", "ac-stage clean-style clean-style-dom", root);
    applyBounds(stage, recipe.bounds);
    applyVars(stage, {
      "clean-color": cssColor(recipe.cleanColor, "#ffffff"),
      "style-color": cssColor(recipe.styleColor, "#4169e1"),
      "clean-glow-alpha": recipe.cleanGlowAlpha ?? .44,
      "style-glow-alpha": recipe.styleGlowAlpha ?? .48,
      "style-shadow-alpha": recipe.styleShadowAlpha ?? .38,
      "clean-red-glow-alpha": recipe.cleanRedGlowAlpha ?? .2,
      "clean-wide-glow-alpha": recipe.cleanWideGlowAlpha ?? .18,
      "style-wide-glow-alpha": recipe.styleWideGlowAlpha ?? .18,
    });
    const clean = create("span", "clean-word", stage);
    clean.textContent = recipe.lines[0].text;
    clean.style.fontSize = `${recipe.cleanFontSize || 58}px`;
    const style = create("span", "style-word", stage);
    style.textContent = recipe.lines[1].text;
    style.style.fontSize = `${recipe.styleFontSize || 72}px`;
    requestAnimationFrame(() => {
      if (clean.scrollWidth > 270) clean.style.fontSize = `${Math.max(16, (recipe.cleanFontSize || 58) * (270 / clean.scrollWidth))}px`;
      if (style.scrollWidth > 260) style.style.fontSize = `${Math.max(18, (recipe.styleFontSize || 72) * (260 / style.scrollWidth))}px`;
      const cleanCharacters = Math.max(1, recipe.lines[0].text.replace(/\s/g, "").length);
      const horizontalOffset = Math.min(clean.offsetWidth * .22, (clean.offsetWidth / cleanCharacters) * 1.1);
      const uppercaseSecondary = /^[A-Z]/.test(recipe.lines[1].text.trim());
      const verticalOverlap = uppercaseSecondary
        ? Math.min(56, clean.offsetHeight * .62)
        : Math.min(60, clean.offsetHeight * .6);
      const left = (recipe.bounds[2] - Math.max(clean.offsetWidth, horizontalOffset + style.offsetWidth)) / 2;
      clean.style.left = `${left}px`;
      clean.style.top = "24px";
      style.style.left = `${left + horizontalOffset}px`;
      style.style.top = `${24 + clean.offsetHeight - verticalOverlap}px`;
    });
    return stage;
  }

  function build(root, config) {
    const recipe = config.recipe;
    if (recipe.type === "plain") return buildPlain(root, recipe);
    if (recipe.type === "gradient_text") return buildGradient(root, recipe);
    if (recipe.type === "apple_style") return buildAppleStyle(root, recipe);
    if (recipe.type === "clean_aesthetic") return buildCleanAesthetic(root, recipe);
    if (recipe.type === "clean_blue") return buildCleanBlue(root, recipe);
    if (recipe.type === "clean_style") return buildCleanStyle(root, recipe);
    throw new Error(`Unknown apple-clean recipe type: ${recipe.type}`);
  }

  async function loadConfig(root) {
    const embedded = document.getElementById("template-config");
    if (embedded) return JSON.parse(embedded.textContent);
    const slug = new URLSearchParams(location.search).get("slug") || root.dataset.slug || "apple_LADDER";
    const response = await fetch(`../../configs/${encodeURIComponent(slug)}.json`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Unable to load apple-clean config for ${slug}`);
    return response.json();
  }

  function fitPreviewStage(root) {
    const resize = () => {
      root.style.setProperty("--hm-preview-scale", String(Math.min(window.innerWidth / 640, window.innerHeight / 360)));
    };
    resize();
    window.addEventListener("resize", resize, { passive: true });
  }

  async function start() {
    const root = document.getElementById("composition-root") || document.querySelector(".ac-root");
    if (!root) throw new Error("Missing apple-clean composition root");
    fitPreviewStage(root);
    const config = await loadConfig(root);
    const params = new URLSearchParams(location.search);
    if (config.recipe?.type === "clean_style") {
      config.recipe.lines[0].text = params.get("text1") || params.get("word1") || config.recipe.lines[0].text;
      config.recipe.lines[1].text = params.get("text2") || params.get("word2") || config.recipe.lines[1].text;
      config.recipe.cleanColor = params.get("topColor") || params.get("cleanColor") || config.recipe.cleanColor || "#ffffff";
      config.recipe.styleColor = params.get("bottomColor") || params.get("styleColor") || config.recipe.styleColor || "#4169e1";
    }
    const isAlpha = new URLSearchParams(location.search).get("alpha") === "1" || root.dataset.alpha === "1";
    root.classList.toggle("is-alpha", isAlpha);
    root.dataset.slug = config.slug;

    if (document.fonts && document.fonts.ready && config.recipe?.skipFontReady !== true) await document.fonts.ready;

    const stage = build(root, config);
    const duration = config.canvas?.duration || 7.6;
    const fps = config.canvas?.fps || 30;
    const timeline = {
      duration: () => duration,
      time(value) {
        applyMotion(stage, config.recipe, clamp(Number(value) || 0, 0, duration), fps, duration);
        return this;
      },
      seek(value) {
        return this.time(value);
      },
      progress(value) {
        return this.time((Number(value) || 0) * duration);
      },
      pause() {
        return this;
      },
    };
    timeline.time(Number(new URLSearchParams(location.search).get("time") || 0));
    window.__timelines = window.__timelines || {};
    window.__timelines[root.dataset.compositionId] = timeline;
    window.__appleCleanConfig = config;
    window.__appleCleanTimeline = timeline;
  }

  window.__readyPromise = start().catch((error) => {
    document.body.dataset.error = error && error.message ? error.message : String(error);
    throw error;
  });
})();
