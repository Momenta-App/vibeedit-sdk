// Shared by accelerated and screenshot paths. Creative code stays ordinary JS.
const vePresentedVideos = new WeakMap();
const veAnimationOrigins = new WeakMap();
const veGsapOrigins = new WeakMap();
const veDecodedImages = new WeakMap();
globalThis.__veRenderFrame = async (context) => {
  const began = performance.now();
  context.media = [];
  await document.fonts.ready;
  const failed = [...document.fonts].filter(font => font.status === "error");
  if (failed.length) throw new Error(`Font load failed: ${failed.map(font => font.family)}`);
  await Promise.all([...document.images].map(image => image.decode()));
  for (const image of document.images) veDecodedImages.set(image, image.currentSrc || image.src);
  const assetsReady = performance.now();
  const automaticAnimations = globalThis.__vibeeditManualAnimationTiming !== true;
  for (const animation of automaticAnimations ? document.getAnimations({subtree: true}) : []) {
    if (!veAnimationOrigins.has(animation)) veAnimationOrigins.set(animation, context.frame === 0 ? 0 : context.time);
    animation.pause();
    animation.currentTime = (context.time - veAnimationOrigins.get(animation)) * 1000;
  }
  if (automaticAnimations && globalThis.gsap?.globalTimeline) {
    const timeline = globalThis.gsap.globalTimeline;
    if (!veGsapOrigins.has(timeline)) {
      const origins = timeline.getChildren(false, true, true).map(animation => animation.startTime() - animation.delay());
      veGsapOrigins.set(timeline, origins.length ? origins.reduce((minimum, origin) => Math.min(minimum, origin), Infinity) : timeline.time());
    }
    timeline.time(context.time + veGsapOrigins.get(timeline), false).pause();
  }
  if (globalThis.anime?.running?.length &&
      typeof globalThis.renderFrame !== "function" &&
      typeof globalThis.vibeedit?.seek !== "function" &&
      typeof globalThis.__vibeeditSeek !== "function")
    throw new Error("Anime.js requires a custom timing adapter; automatic instance ownership is not qualified");
  const automaticReady = performance.now();
  await Promise.all([...document.querySelectorAll("video")].map(async (video, index) => {
    video.pause();
    if (video.error) throw new Error(`Media decode failed: ${video.currentSrc}: ${video.error.message}`);
    if (video.dataset.vibeeditTiming === "manual") return;
    if (video.readyState < 2) await new Promise((resolve, reject) => {
      video.addEventListener("loadeddata", resolve, {once: true});
      video.addEventListener("error", () => reject(new Error(`Media load failed: ${video.currentSrc}`)), {once: true});
      if (video.error) reject(new Error(`Media load failed: ${video.currentSrc}`));
    });
    if (!Number.isFinite(video.duration) || video.duration <= 0) throw new Error(`Live/unknown-duration media needs manual timing: ${video.currentSrc}`);
    const source = Number(video.dataset.sourceOffset || 0) + context.time * Number(video.dataset.sourceRate || 1);
    if (!Number.isFinite(source)) throw new Error(`Invalid source offset/rate: ${video.currentSrc}`);
    const requested = video.loop ? ((source % video.duration) + video.duration) % video.duration : source;
    const target = Math.max(0, Math.min(requested, Math.max(0, video.duration - 0.000001)));
    const timeline = globalThis.__veMediaTimeline?.[video.currentSrc];
    if (!timeline) throw new Error(`No decoded-frame timeline for ${video.currentSrc}; prepare local media or use manual timing`);
    const decodedIndex = time => {
      let low = 0, high = timeline.length;
      while (low < high) {
        const middle = (low + high) >> 1;
        if (timeline[middle] <= time + 0.0000001) low = middle + 1;
        else high = middle;
      }
      return Math.max(0, low - 1);
    };
    const selected = decodedIndex(target);
    context.media[index] = {id: video.id, src: video.currentSrc, requestedTime: source, mappedTime: target, frame: selected, presentationTime: timeline[selected]};
    if (vePresentedVideos.get(video) === selected && !video.seeking) return;
    const presentation = timeline[selected];
    const epsilon = Math.min(0.000001, ((timeline[selected + 1] ?? video.duration) - presentation) / 2);
    // Seek exact source PTS, not a rounded output time near a source boundary.
    // A queued rVFC for the previous seek is not proof of the selected frame.
    await new Promise((resolve, reject) => {
      let callback;
      const cleanup = () => video.removeEventListener("error", error);
      const error = () => {
        if (callback !== undefined) video.cancelVideoFrameCallback(callback);
        cleanup();
        reject(new Error(`Media seek failed: ${video.currentSrc}`));
      };
      const presented = (_, metadata) => {
        if (Math.abs(metadata.mediaTime - presentation) > 0.000002) {
          callback = video.requestVideoFrameCallback(presented);
          return;
        }
        cleanup();
        resolve();
      };
      callback = video.requestVideoFrameCallback(presented);
      video.addEventListener("error", error, {once: true});
      video.currentTime = Math.max(0, Math.min(presentation + Math.max(0, epsilon), video.duration - 0.000001));
    });
    vePresentedVideos.set(video, selected);
  }));
  const mediaReady = performance.now();
  if (typeof globalThis.renderFrame === "function") await globalThis.renderFrame(context.frame, context.time, context);
  else if (typeof globalThis.vibeedit?.seek === "function") await globalThis.vibeedit.seek(context.time, context);
  else if (typeof globalThis.__vibeeditSeek === "function") await globalThis.__vibeeditSeek(context.frame, context);
  dispatchEvent(new CustomEvent("vibeedit:frame", {detail: context}));
  for (const animation of automaticAnimations ? document.getAnimations({subtree: true}) : []) {
    if (veAnimationOrigins.has(animation)) continue;
    veAnimationOrigins.set(animation, context.time);
    animation.pause();
    animation.currentTime = 0;
  }
  const scriptReady = performance.now();
  void document.body?.offsetHeight;
  const introducedImages = [...document.images].filter(image => !image.complete || veDecodedImages.get(image) !== (image.currentSrc || image.src));
  if (document.fonts.status === "loading") await document.fonts.ready;
  if ([...document.fonts].some(font => font.status === "error")) throw new Error("Font load failed after renderFrame");
  if (introducedImages.length) await Promise.all(introducedImages.map(async image => {
    await image.decode();
    veDecodedImages.set(image, image.currentSrc || image.src);
  }));
  const layoutReady = performance.now();
  // Give Blink/compositor the submitted DOM/Canvas/video state. The host
  // separately invalidates and waits for a surface; this isn't a capture ack.
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  return {frame: context.frame, time: context.time, fonts: [...document.fonts].map(font => ({family: font.family, status: font.status})),
    metrics: {assetReadinessSeconds:(assetsReady-began)/1000, automaticAnimationSeconds:(automaticReady-assetsReady)/1000,
      mediaSeekSeconds:(mediaReady-automaticReady)/1000, customScriptSeconds:(scriptReady-mediaReady)/1000,
      forcedLayoutSeconds:(layoutReady-scriptReady)/1000, browserSubmissionSeconds:(performance.now()-layoutReady)/1000}};
};
