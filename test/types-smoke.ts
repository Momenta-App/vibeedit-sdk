import { Canvas, Composition, Effect, FrameRate, MotionComponent, Placement, Timeline, Track, searchCatalog } from "vibeedit";

const timeline = new Timeline();
const track = timeline.addTrack(new Track({ id: "M1", kind: "motion", order: 10 }));
track.add(new MotionComponent({ id: "title", placement: new Placement(0, 30), componentId: "vibeedit://text/negative", props: { text: "MOVE" } }));
const composition = new Composition({ id: "types", canvas: new Canvas({ width: 640, height: 360, frameRate: new FrameRate(30) }), durationFrames: 30, timeline });
composition.validate();
new Effect({ id: "fx", effectId: "vibeedit://effect/random-frame-stutter", params: { seed: 1 } });
searchCatalog("motion");
