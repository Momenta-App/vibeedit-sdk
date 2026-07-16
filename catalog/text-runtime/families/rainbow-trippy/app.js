(function () {
  const params = new URLSearchParams(window.location.search);
  const slug = params.get("slug") || "RAINBOW_CLEAN_TEXT";
  const isAlpha = params.get("alpha") === "1" || params.get("alpha") === "true";
  const startTime = Number(params.get("time") || 0);

  function fitPreviewStage(root) {
    const resize = () => {
      root.style.setProperty("--hm-preview-scale", String(Math.min(window.innerWidth / 640, window.innerHeight / 360)));
    };
    resize();
    window.addEventListener("resize", resize, { passive: true });
  }

  async function start() {
    const root = document.getElementById("root");
    fitPreviewStage(root);
    root.classList.toggle("is-alpha", isAlpha);

    const response = await fetch(`../../configs/${encodeURIComponent(slug)}.json`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Unable to load config for ${slug}`);

    const config = await response.json();
    config.alpha = isAlpha;

    if (document.fonts && document.fonts.ready) await document.fonts.ready;

    const app = window.RainbowTrippy.build(config, {
      root,
      canvas: document.getElementById("scene"),
    });
    app.seek(startTime);
    if (params.get("play") === "1") app.play();
    window.__timelines = window.__timelines || {};
    window.__timelines[config.compositionId || `rainbow-trippy-${slug}`] = {
      duration: () => config.duration || 7.6,
      time(value) {
        if (value === undefined) return 0;
        app.seek(value);
        return this;
      },
      seek(value) {
        return this.time(value);
      },
      pause() {
        app.stop();
        return this;
      },
      play() {
        app.play();
        return this;
      },
      progress(value) {
        if (value === undefined) return 0;
        return this.time((Number(value) || 0) * (config.duration || 7.6));
      },
    };
    window.__rainbowTrippyApp = app;
  }

  window.__readyPromise = start().catch((error) => {
    document.body.dataset.error = String(error && error.message ? error.message : error);
    throw error;
  });
}());
