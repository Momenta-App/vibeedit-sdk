import { Canvas, Composition, Effect, FrameRate, HTML_CSS_MOTION_COMPONENT_ID, MotionComponent, Placement, Timeline, Track, searchCatalog } from "vibeedit";

const timeline = new Timeline();
const track = timeline.addTrack(new Track({ id: "M1", kind: "motion", order: 10 }));
track.add(new MotionComponent({ id: "title", placement: new Placement(0, 30), componentId: "vibeedit://text/negative", props: { text: "MOVE" } }));
track.add(new MotionComponent({ id: "raw-css", placement: new Placement(0, 30), componentId: HTML_CSS_MOTION_COMPONENT_ID, props: { html: "<h1>MOVE</h1>", css: "h1{animation:fade 1s}" } }));
const composition = new Composition({ id: "types", canvas: new Canvas({ width: 640, height: 360, frameRate: new FrameRate(30) }), durationFrames: 30, timeline });
composition.validate();
new Effect({ id: "fx", effectId: "vibeedit://effect/random-frame-stutter", params: { seed: 1 } });
searchCatalog("motion");
