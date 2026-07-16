# HTML Motion Runtime

VibeEdit lets an agent use HTML, CSS, and JavaScript as the primary language for
text, text effects, motion graphics, SVG, Canvas, WebGL, and WebGPU. The agent
does not select a low-level renderer. VibeEdit keeps the browser compatibility
path available and may move a layer to a conformance-proven native path later.

## Custom project component

Use `vibeedit://motion/html` for an inline fragment or
`vibeedit://motion/web-project` for a bundled project entry point.

```json
{
  "id": "title",
  "kind": "motion",
  "placement": { "startFrame": 0, "durationFrames": 90 },
  "componentId": "vibeedit://motion/html",
  "renderer": "auto",
  "transparent": true,
  "props": {
    "html": "<h1>BUILT DIFFERENT</h1>",
    "css": "h1 { animation: enter 1s cubic-bezier(.2,.8,.2,1) both }",
    "javascript": "addEventListener('vibeedit:frame', ({detail}) => document.body.dataset.frame = detail.frame)"
  }
}
```

For React, Vue, Svelte, Solid, Three.js, PixiJS, D3, or another framework,
compile the application normally and point `props.entry` at its local HTML
file. Relative scripts, styles, images, video, and fonts resolve from the
composition directory. Network URLs are intentionally blocked.

```json
{
  "componentId": "vibeedit://motion/web-project",
  "renderer": "auto",
  "props": { "entry": "motion-title/dist/index.html" }
}
```

## Deterministic frame contract

The page is loaded once and remains alive for the render. At every output frame
VibeEdit provides:

```js
{
  frame,          // local integer frame
  absoluteFrame,  // composition frame
  durationFrames,
  fps,
  time,           // local seconds
  progress        // normalized 0..1
}
```

CSS animations and Web Animations API animations are paused and sought
automatically. GSAP's global timeline and active Anime.js timelines are also
sought automatically. Every project receives a `vibeedit:frame` event.

For Canvas, Three.js, PixiJS, simulations, custom WebGL/WebGPU, or any runtime
whose state cannot be inferred, expose one explicit seek function:

```js
window.vibeedit = {
  async seek(time, context) {
    renderAt(context.frame, time, context.progress);
  },
};
```

The alternative `window.__vibeeditSeek(frame, context)` contract is supported
for small scripts. Avoid wall-clock timers and unseeded randomness in offline
renders because neither is seekable.

## Libraries

| Library or platform | Status | Timing contract |
| --- | --- | --- |
| Plain HTML/CSS/SVG | Supported | CSS animations are sought automatically |
| Web Animations API / Motion One | Supported | Browser animations are sought automatically |
| GSAP | Supported | Bundle locally; global timeline is sought automatically |
| Anime.js | Supported | Bundle locally; active timelines are sought automatically |
| React, Preact, Vue, Svelte, Solid | Supported | Bundle normally; use CSS/WAAPI or the frame event |
| D3 | Supported | Use the frame event for JavaScript-driven transitions |
| Canvas 2D | Supported | Implement `vibeedit.seek` |
| Three.js, PixiJS, WebGL | Supported | Implement `vibeedit.seek` |
| WebGPU/WGSL | Capability-gated | Implement `vibeedit.seek`; adapter availability is device-dependent |
| Remote CDN scripts | Not supported | Vendor or bundle them locally |

“Supported” means the bundled browser project can execute. It does not imply
that the layer is eligible for native Rust/WGPU compilation. Native routing is
allowed only after feature coverage and image-conformance tests pass.

Run `vibeedit inspect composition.json --json` to see the selected backend,
detected libraries, seek contract, and native-candidate status for every motion
layer. A candidate remains on the browser reference path until its decoded-pixel
conformance suite passes; the router never silently trades correctness for
speed.

When a composition declares `renderer: "webgpu"` or contains WebGPU/WGSL API
usage, VibeEdit enables Chromium's headless WebGPU feature for that isolated
local render. `navigator.gpu` still may return no adapter on unsupported devices
or CI hosts; WebGPU projects should surface an actionable capability error or
provide a Canvas/WebGL fallback.

## Fonts

Any font that pinned Chromium can decode can be used through ordinary CSS
`@font-face`. Bundle WOFF2 when available, or WOFF, TTF, OTF, and variable-font
files when licensing permits. VibeEdit waits for `document.fonts.ready` before
capturing a frame.

System font-family names also work when installed, but they are not portable or
reproducible across operating systems. Production compositions should bundle
the exact font files and record their licenses and hashes. Google Fonts, Adobe
Fonts, and other hosted font URLs do not load during an offline render; include
licensed local copies instead.

## Current acceleration boundary

The persistent renderer removes per-frame page, framework, iframe, and font
initialization. Chromium's `optimizeForSpeed` lossless PNG capture is used for
the current master path. Browser-only compositions stream those PNG frames
directly into FFmpeg with `image2pipe`, avoiding intermediate frame files. PNG
extraction is still an encoded CPU readback; raw or shared-texture extraction
requires a deeper Chromium/Skia integration and is the next acceleration
boundary.
