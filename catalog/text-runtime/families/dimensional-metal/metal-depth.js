/* global gsap */
(function () {
  const STAGE_SCALE = 1 / 3;

  function rgba(color, opacity = 1) {
    const alpha = color.length > 3 ? color[3] : 255;
    return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${(alpha / 255) * opacity})`;
  }

  function stage(value) {
    return value * STAGE_SCALE;
  }

  function relativeBox(node, centerOffset, size) {
    node.style.left = `${stage(centerOffset[0] - size[0] / 2)}px`;
    node.style.top = `${stage(centerOffset[1] - size[1] / 2)}px`;
    node.style.width = `${stage(size[0])}px`;
    node.style.height = `${stage(size[1])}px`;
  }

  function fontFamily(fontPath) {
    if ((fontPath || "").includes("Birds")) return "BirdsParadise";
    if ((fontPath || "").includes("AVANTE")) return "AvanteHF";
    return "MytupiHF";
  }

  function makeTextSpan(text, className) {
    const span = document.createElement("span");
    span.className = className;
    span.textContent = text;
    span.setAttribute("aria-hidden", "true");
    return span;
  }

  function makeArtGroup(scene, id, center) {
    const group = document.createElement("div");
    group.id = `${id}-art`;
    group.className = "title-art";
    group.style.left = `${stage(center[0])}px`;
    group.style.top = `${stage(center[1])}px`;
    scene.appendChild(group);
    return group;
  }

  function build3dText(scene, config) {
    const group = makeArtGroup(scene, config.slug, config.center);
    group.classList.add("text3d");
    group.style.fontFamily = fontFamily(config.font);
    group.style.fontSize = `${stage(config.font_size)}px`;

    const stack = document.createElement("div");
    stack.className = "text-stack";
    group.appendChild(stack);

    const depth = Math.max(12, Math.round(config.extrusion / 4));
    for (let i = depth; i >= 1; i -= 1) {
      const layer = makeTextSpan(config.text, "depth-layer");
      const t = i / depth;
      const shade = 0.48 + t * 0.34;
      layer.style.color = rgba([
        Math.round(config.back_color[0] * shade),
        Math.round(config.back_color[1] * shade),
        Math.round(config.back_color[2] * shade),
        255,
      ]);
      layer.style.opacity = String(0.54 + (1 - t) * 0.28);
      layer.style.transform = `translate(${-i * 0.34}px, ${i * 0.18}px)`;
      layer.style.zIndex = String(depth - i);
      stack.appendChild(layer);
    }

    const front = makeTextSpan(config.text, "front-layer metal-front red-front");
    front.style.color = rgba(config.front_color);
    front.style.webkitTextStroke = `${Math.max(0.35, stage(config.stroke_width))}px rgba(255,255,255,.78)`;
    stack.appendChild(front);

    const rim = makeTextSpan(config.text, "front-layer red-rim");
    rim.style.webkitTextStroke = `${Math.max(0.5, stage(config.stroke_width) * 1.2)}px rgba(255,255,255,.55)`;
    stack.appendChild(rim);

    const shine = makeTextSpan(config.text, "front-layer shine-layer");
    shine.style.webkitTextStroke = front.style.webkitTextStroke;
    stack.appendChild(shine);
    return { group, shine };
  }

  function buildGoldText(scene, config) {
    const group = makeArtGroup(scene, config.slug, config.center);
    group.classList.add("gold-title");
    group.style.fontFamily = fontFamily(config.font);
    group.style.fontSize = `${stage(config.font_size)}px`;

    const stroke = Math.max(0.55, stage(config.stroke_width) * 0.32);
    const depth = 5;
    for (let i = depth; i >= 1; i -= 1) {
      const layer = makeTextSpan(config.text, "gold-depth");
      layer.style.color = rgba(config.shadow_color, 0.72);
      layer.style.webkitTextStroke = `${stroke}px rgba(0,0,0,.86)`;
      layer.style.opacity = String(0.3 + (i / depth) * 0.13);
      layer.style.transform = `translate(${i * 0.42}px, ${i * 0.7}px)`;
      group.appendChild(layer);
    }

    const front = makeTextSpan(config.text, "front-layer metal-front gold-front");
    front.style.webkitTextStroke = `${stroke}px rgba(0,0,0,.9)`;
    front.style.setProperty("--top", rgba(config.top_color));
    front.style.setProperty("--bottom", rgba(config.bottom_color));
    group.appendChild(front);

    const bevel = makeTextSpan(config.text, "front-layer bevel-layer");
    bevel.style.webkitTextStroke = `${Math.max(0.85, stage(config.bevel) * 1.08)}px rgba(255,255,235,.42)`;
    group.appendChild(bevel);

    const fill = makeTextSpan(config.text, "front-layer gold-fill");
    fill.style.webkitTextStroke = `${Math.max(0.38, stroke * 0.2)}px rgba(255,255,220,.94)`;
    fill.style.setProperty("--top", rgba(config.top_color));
    fill.style.setProperty("--bottom", rgba(config.bottom_color));
    group.appendChild(fill);

    const bevelHot = makeTextSpan(config.text, "front-layer gold-hot-edge");
    bevelHot.style.webkitTextStroke = `${Math.max(0.44, stroke * 0.38)}px rgba(255,255,238,.78)`;
    bevelHot.style.setProperty("--top", rgba(config.top_color));
    bevelHot.style.setProperty("--bottom", rgba(config.bottom_color));
    group.appendChild(bevelHot);

    const shine = makeTextSpan(config.text, "front-layer shine-layer");
    shine.style.webkitTextStroke = `${stroke}px rgba(0,0,0,.12)`;
    group.appendChild(shine);
    return { group, shine };
  }

  function buildOldMoney(scene, config) {
    const plateConfig = config.plate;
    const group = makeArtGroup(scene, config.slug, plateConfig.center);
    group.classList.add("old-money-title");

    const oldLine = config.text_lines[0];
    const old = makeTextSpan(oldLine.text, "old-line old-word");
    old.style.fontFamily = fontFamily(oldLine.font);
    old.style.fontSize = `${stage(oldLine.font_size)}px`;
    old.style.left = `${stage(oldLine.center[0] - plateConfig.center[0])}px`;
    old.style.top = `${stage(oldLine.center[1] - plateConfig.center[1])}px`;
    old.style.setProperty("--top", rgba(oldLine.top_color));
    old.style.setProperty("--bottom", rgba(oldLine.bottom_color));
    group.appendChild(old);

    const moneyLine = config.text_lines[1];
    const money = makeTextSpan(moneyLine.text, "old-line money-word");
    money.style.fontFamily = fontFamily(moneyLine.font);
    money.style.fontSize = `${stage(moneyLine.font_size)}px`;
    money.style.left = `${stage(moneyLine.center[0] - plateConfig.center[0])}px`;
    money.style.top = `${stage(moneyLine.center[1] - plateConfig.center[1])}px`;
    money.style.setProperty("--top", rgba(moneyLine.top_color));
    money.style.setProperty("--bottom", rgba(moneyLine.bottom_color));
    group.appendChild(money);
    const highlights = [[oldLine, "old-word"], [moneyLine, "money-word"]].map(([line, className]) => {
      const highlight = makeTextSpan(line.text, `old-line ${className} old-money-shine-line`);
      highlight.style.fontFamily = fontFamily(line.font);
      highlight.style.fontSize = `${stage(line.font_size)}px`;
      highlight.style.left = `${stage(line.center[0] - plateConfig.center[0])}px`;
      highlight.style.top = `${stage(line.center[1] - plateConfig.center[1])}px`;
      highlight.style.zIndex = "20";
      group.appendChild(highlight);
      return highlight;
    });
    requestAnimationFrame(() => {
      if (old.scrollWidth > 430) old.style.fontSize = `${Math.max(30, stage(oldLine.font_size) * (430 / old.scrollWidth))}px`;
      if (money.scrollWidth > 450) money.style.fontSize = `${Math.max(30, stage(moneyLine.font_size) * (450 / money.scrollWidth))}px`;
      highlights[0].style.fontSize = old.style.fontSize;
      highlights[1].style.fontSize = money.style.fontSize;
    });
    return { group, shine: highlights };
  }

  function buildTimeline(config, handles) {
    const tl = gsap.timeline({ paused: true });
    gsap.set(handles.group, { transformOrigin: "50% 50%", opacity: 1 });

    if (config.slug === "3D_TEXT") {
      tl.fromTo(
        handles.group,
        { opacity: 0, scale: 0.92, x: -2, y: -1, rotationY: 87, rotation: -92 },
        { opacity: 1, scale: 1, x: 0, y: 0, rotationY: 10, rotation: -4, duration: 1.55, ease: "back.out(1.08)" },
        0
      );
      tl.to(handles.group, { rotationY: 0, rotation: 0, duration: 0.35, ease: "power2.out" }, 1.1);
      tl.fromTo(handles.shine, { opacity: 0, x: -40 }, { opacity: 0.72, x: 44, duration: 0.72, ease: "power1.inOut" }, 0.22);
      tl.to(handles.shine, { opacity: 0, duration: 0.28, ease: "power1.out" }, 0.92);
      return tl;
    }

    if (config.slug === "OLD_MONEY") {
      tl.fromTo(
        handles.group,
        { opacity: 0, scale: 0.83, y: 16 },
        { opacity: 1, scale: 1, y: 0, duration: 0.55, ease: "back.out(1.2)" },
        0
      );
      tl.set(handles.shine, { visibility: "visible" }, 0.28);
      tl.fromTo(handles.shine, { opacity: 0 }, { opacity: 0.78, duration: 0.2, ease: "power1.out" }, 0.28);
      tl.fromTo(handles.shine, { backgroundPosition: "-120% 50%" }, { backgroundPosition: "120% 50%", duration: 0.9, ease: "power1.inOut" }, 0.28);
      tl.to(handles.shine, { opacity: 0, duration: 0.12, ease: "power1.out" }, 0.96);
      tl.set(handles.shine, { visibility: "hidden" }, 1.08);
      return tl;
    }

    tl.fromTo(
      handles.group,
      { opacity: 0, scale: 0.82, y: 20 },
      { opacity: 1, scale: 1, y: 0, duration: 0.45, ease: "back.out(1.25)" },
      0
    );
    tl.fromTo(handles.shine, { opacity: 0, x: -60 }, { opacity: 0.88, x: 66, duration: 0.7, ease: "power1.inOut" }, 0.12);
    tl.to(handles.shine, { opacity: 0, duration: 0.26, ease: "power1.out" }, 0.82);
    return tl;
  }

  function build(config, options = {}) {
    const root = options.root || document.getElementById("root");
    const scene = options.scene || document.getElementById("scene");
    scene.replaceChildren();

    let handles;
    if (config.slug === "3D_TEXT") {
      handles = build3dText(scene, config);
    } else if (config.slug === "OLD_MONEY") {
      handles = buildOldMoney(scene, config);
    } else {
      handles = buildGoldText(scene, config);
    }

    root.dataset.slug = config.slug;
    const timeline = buildTimeline(config, handles);
    const duration = Number(config.duration || 7);
    timeline.seek(0, false);

    return {
      config,
      duration,
      root,
      scene,
      timeline,
      seek(seconds) {
        timeline.seek(Math.max(0, Math.min(duration, Number(seconds) || 0)), false);
      },
      play() {
        timeline.play(0);
      },
    };
  }

  window.DimensionalMetal = { build };
})();
