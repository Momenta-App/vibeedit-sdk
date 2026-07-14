import { validateComposition } from "./validation.js";

export class FrameRate {
  constructor(numerator, denominator = 1) {
    if (!Number.isInteger(numerator) || !Number.isInteger(denominator) || numerator < 1 || denominator < 1) throw new RangeError("frame rate must use positive integers");
    const divisor = gcd(numerator, denominator);
    this.numerator = numerator / divisor;
    this.denominator = denominator / divisor;
  }

  toJSON() { return { numerator: this.numerator, denominator: this.denominator }; }
}

export class Canvas {
  constructor({ width, height, frameRate, audioSampleRate = 48000, backgroundColor = "#000000", pixelFormat = "yuv420p", colorSpace = "bt709" }) {
    Object.assign(this, { width, height, frameRate: frameRate instanceof FrameRate ? frameRate : new FrameRate(frameRate.numerator, frameRate.denominator), audioSampleRate, backgroundColor, pixelFormat, colorSpace });
  }

  toJSON() { return { width: this.width, height: this.height, frameRate: this.frameRate.toJSON(), audioSampleRate: this.audioSampleRate, backgroundColor: this.backgroundColor, pixelFormat: this.pixelFormat, colorSpace: this.colorSpace }; }
}

export class Placement {
  constructor(startFrame, durationFrames, enabled = true) { Object.assign(this, { startFrame, durationFrames, enabled }); }
  toJSON() { return { startFrame: this.startFrame, durationFrames: this.durationFrames, enabled: this.enabled }; }
}

export class SourceRange {
  constructor(sourceId, inFrame, durationFrames) { Object.assign(this, { sourceId, inFrame, durationFrames }); }
  toJSON() { return { sourceId: this.sourceId, inFrame: this.inFrame, durationFrames: this.durationFrames }; }
}

export class SourceMedia {
  constructor({ id, kind, uri, identity, identityAlgorithm = "sha256", mediaType, durationFrames, metadata = {} }) { Object.assign(this, { id, kind, uri, identity, identityAlgorithm, mediaType, durationFrames, metadata }); }
  toJSON() { return compact({ id: this.id, kind: this.kind, uri: this.uri, identity: { algorithm: this.identityAlgorithm, value: this.identity }, mediaType: this.mediaType, durationFrames: this.durationFrames, metadata: Object.keys(this.metadata).length ? this.metadata : undefined }); }
}

export class Effect {
  constructor({ id, effectId, params = {}, enabled = true, maskId, trackingArtifactId, implementationVersion = "0.1.0" }) { Object.assign(this, { id, effectId, params, enabled, maskId, trackingArtifactId, implementationVersion }); }
  toJSON() { return compact({ id: this.id, effectId: this.effectId, params: this.params, enabled: this.enabled, maskId: this.maskId, trackingArtifactId: this.trackingArtifactId, implementationVersion: this.implementationVersion }); }
}

class TimelineItem {
  constructor(values) { Object.assign(this, values); }
  toJSON() { return compact({ ...this, placement: this.placement?.toJSON?.() ?? this.placement, source: this.source?.toJSON?.() ?? this.source, effects: this.effects?.map((effect) => effect.toJSON?.() ?? effect) }); }
}

export class VideoClip extends TimelineItem { constructor(values) { super({ kind: "video", effects: [], ...values }); } }
export class AudioClip extends TimelineItem { constructor(values) { super({ kind: "audio", role: "other", gainDb: 0, pan: 0, effects: [], ...values }); } }
export class ImageClip extends TimelineItem { constructor(values) { super({ kind: "image", effects: [], ...values }); } }
export class MotionComponent extends TimelineItem { constructor(values) { super({ kind: "motion", renderer: "html", transparent: true, effects: [], props: {}, ...values }); } }
export const Text = MotionComponent;
export class Transition extends TimelineItem { constructor(values) { super({ kind: "transition", params: {}, implementationVersion: "0.1.0", ...values }); } }
export class SoundEffect extends TimelineItem { constructor(values) { super({ kind: "sound_effect", params: {}, gainDb: 0, variationSeed: 0, avoidImmediateRepeat: true, ...values }); } }

export class Mask { constructor(values) { Object.assign(this, values); } toJSON() { return compact({ ...this, startFrame: this.startFrame, durationFrames: this.durationFrames, artifactUri: this.artifactUri, trackingArtifactId: this.trackingArtifactId }); } }
export class TrackingArtifact { constructor(values) { Object.assign(this, values); } toJSON() { return compact({ ...this }); } }
export class AnalysisArtifact { constructor(values) { Object.assign(this, values); } toJSON() { return compact({ ...this }); } }
export class RenderJob { constructor({ compositionId, output, backend = "auto", deterministic = true }) { Object.assign(this, { compositionId, output, backend, deterministic }); } }
export class VerificationReport { constructor({ passed, output, checks = [], errors = [], warnings = [] }) { Object.assign(this, { passed, output, checks, errors, warnings }); } }
export class CatalogItem { constructor(values) { Object.assign(this, values); } }
export class SkillPackage { constructor(values) { Object.assign(this, values); } }

export class Track {
  constructor({ id, kind, order, role, enabled = true, muted = false, items = [] }) { Object.assign(this, { id, kind, order, role, enabled, muted, items }); }
  add(item) { this.items.push(item); return item; }
  toJSON() { return compact({ id: this.id, kind: this.kind, order: this.order, role: this.role, enabled: this.enabled, muted: this.muted, items: this.items.map((item) => item.toJSON?.() ?? item) }); }
}

export class Timeline {
  constructor(tracks = []) { this.tracks = tracks; }
  addTrack(track) { if (this.tracks.some((item) => item.id === track.id)) throw new Error(`duplicate track id: ${track.id}`); this.tracks.push(track); return track; }
  toJSON() { return { tracks: this.tracks.map((track) => track.toJSON?.() ?? track) }; }
}

export class Composition {
  constructor({ id, canvas, durationFrames, title = "", sources = [], timeline = new Timeline(), artifacts = { masks: [], tracking: [], analysis: [] }, render = {}, verification, metadata, provenance = {} }) {
    Object.assign(this, { id, canvas, durationFrames, title, sources, timeline, artifacts, render, verification, metadata, provenance });
  }

  toJSON() {
    return compact({
      schemaVersion: "1.0.0",
      kind: "vibeedit.composition",
      id: this.id,
      title: this.title || undefined,
      canvas: this.canvas.toJSON?.() ?? this.canvas,
      durationFrames: this.durationFrames,
      sources: this.sources.map((source) => source.toJSON?.() ?? source),
      timeline: this.timeline.toJSON?.() ?? this.timeline,
      artifacts: this.artifacts,
      render: {
        backend: this.render.backend ?? "auto",
        output: { uri: this.render.uri ?? "output.mp4", container: this.render.container ?? "mp4", videoCodec: this.render.videoCodec ?? "h264", audioCodec: this.render.audioCodec ?? "aac", pixelFormat: this.render.pixelFormat ?? "yuv420p", transparent: this.render.transparent ?? false },
        deterministic: this.render.deterministic ?? true,
      },
      verification: this.verification,
      provenance: { generator: this.provenance.generator ?? "vibeedit-node", generatorVersion: this.provenance.generatorVersion ?? "0.1.0", createdAt: this.provenance.createdAt ?? new Date().toISOString(), schemaSource: "schema/composition.schema.json" },
      metadata: this.metadata,
    });
  }

  validate() { return validateComposition(this.toJSON()); }
}

export const CompositionSpec = Composition;
export const ProjectSpec = Composition;

function compact(value) { return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined)); }
function gcd(left, right) { return right ? gcd(right, left % right) : left; }
