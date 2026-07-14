export type JSONValue = null | boolean | number | string | JSONValue[] | { [key: string]: JSONValue };
export type JSONObject = { [key: string]: JSONValue };
export declare const portableMotionComponents: readonly JSONObject[];
export type CatalogCategory = "effect" | "transition" | "text" | "motion" | "template" | "sfx" | "skill";

export declare class FrameRate {
  constructor(numerator: number, denominator?: number);
  numerator: number;
  denominator: number;
  toJSON(): { numerator: number; denominator: number };
}

export declare class Canvas {
  constructor(options: { width: number; height: number; frameRate: FrameRate | { numerator: number; denominator: number }; audioSampleRate?: number; backgroundColor?: string; pixelFormat?: string; colorSpace?: string });
  width: number;
  height: number;
  frameRate: FrameRate;
  audioSampleRate: number;
  backgroundColor: string;
  pixelFormat: string;
  colorSpace: string;
  toJSON(): JSONObject;
}

export declare class Placement {
  constructor(startFrame: number, durationFrames: number, enabled?: boolean);
  startFrame: number;
  durationFrames: number;
  enabled: boolean;
  toJSON(): JSONObject;
}

export declare class SourceRange {
  constructor(sourceId: string, inFrame: number, durationFrames: number);
  sourceId: string;
  inFrame: number;
  durationFrames: number;
  toJSON(): JSONObject;
}

export declare class SourceMedia {
  constructor(options: { id: string; kind: "video" | "audio" | "image" | "font" | "data"; uri: string; identity: string; identityAlgorithm?: string; mediaType?: string; durationFrames?: number; metadata?: JSONObject });
  id: string;
  kind: string;
  uri: string;
  identity: string;
  toJSON(): JSONObject;
}

export declare class Effect {
  constructor(options: { id: string; effectId: string; params?: JSONObject; enabled?: boolean; maskId?: string; trackingArtifactId?: string; implementationVersion?: string });
  id: string;
  effectId: string;
  params: JSONObject;
  toJSON(): JSONObject;
}

export interface TimelineItemOptions { id: string; placement: Placement | JSONObject; effects?: Effect[]; [key: string]: unknown }
export declare class VideoClip { constructor(options: TimelineItemOptions & { source: SourceRange | JSONObject }); id: string; kind: "video"; toJSON(): JSONObject }
export declare class AudioClip { constructor(options: TimelineItemOptions & { source: SourceRange | JSONObject; role?: string; gainDb?: number; pan?: number }); id: string; kind: "audio"; toJSON(): JSONObject }
export declare class ImageClip { constructor(options: TimelineItemOptions & { sourceId: string }); id: string; kind: "image"; toJSON(): JSONObject }
export declare class MotionComponent { constructor(options: TimelineItemOptions & { componentId: string; props?: JSONObject; renderer?: string; transparent?: boolean }); id: string; kind: "motion"; toJSON(): JSONObject }
export { MotionComponent as Text };
export declare class Transition { constructor(options: TimelineItemOptions & { transitionId: string; fromItemId: string; toItemId: string; params?: JSONObject }); id: string; kind: "transition"; toJSON(): JSONObject }
export declare class SoundEffect { constructor(options: TimelineItemOptions & { soundEffectId: string; params?: JSONObject; gainDb?: number; variationSeed?: number; avoidImmediateRepeat?: boolean }); id: string; kind: "sound_effect"; toJSON(): JSONObject }
export type TimelineItem = VideoClip | AudioClip | ImageClip | MotionComponent | Transition | SoundEffect;

export declare class Track {
  constructor(options: { id: string; kind: "video" | "audio" | "image" | "motion" | "data"; order: number; role?: string; enabled?: boolean; muted?: boolean; items?: TimelineItem[] });
  id: string;
  kind: string;
  order: number;
  items: TimelineItem[];
  add<T extends TimelineItem>(item: T): T;
  toJSON(): JSONObject;
}

export declare class Timeline {
  constructor(tracks?: Track[]);
  tracks: Track[];
  addTrack(track: Track): Track;
  toJSON(): JSONObject;
}

export declare class Mask { constructor(options: JSONObject); toJSON(): JSONObject }
export declare class TrackingArtifact { constructor(options: JSONObject); toJSON(): JSONObject }
export declare class AnalysisArtifact { constructor(options: JSONObject); toJSON(): JSONObject }
export declare class RenderJob { constructor(options: { compositionId: string; output: string; backend?: string; deterministic?: boolean }); compositionId: string; output: string; backend: string; deterministic: boolean }
export declare class VerificationReport { constructor(options: { passed: boolean; output: string; checks?: JSONObject[]; errors?: string[]; warnings?: string[] }); passed: boolean; output: string; checks: JSONObject[]; errors: string[]; warnings: string[] }
export declare class CatalogItem { constructor(options: JSONObject); id: string; name: string; category: CatalogCategory; version: string }
export declare class SkillPackage { constructor(options: JSONObject); id: string; name: string; version: string; path: string; harnesses: string[]; checksum: string }

export interface CompositionOptions {
  id: string;
  canvas: Canvas | JSONObject;
  durationFrames: number;
  title?: string;
  sources?: SourceMedia[];
  timeline?: Timeline;
  artifacts?: { masks: Mask[]; tracking: TrackingArtifact[]; analysis: AnalysisArtifact[] };
  render?: JSONObject;
  verification?: JSONObject;
  metadata?: JSONObject;
  provenance?: JSONObject;
}

export declare class Composition {
  constructor(options: CompositionOptions);
  id: string;
  canvas: Canvas | JSONObject;
  durationFrames: number;
  timeline: Timeline;
  toJSON(): JSONObject;
  validate(): JSONObject;
}
export { Composition as CompositionSpec, Composition as ProjectSpec };

export declare class CompositionValidationError extends TypeError { errors: JSONObject[] }
export declare function validateComposition(spec: JSONObject): JSONObject;
export declare function canonicalJson(value: JSONValue): string;

export interface CatalogManifestItem extends JSONObject { id: string; name: string; description: string; category: CatalogCategory; version: string }
export declare function catalog(): { schemaVersion: string; catalogVersion: string; items: CatalogManifestItem[] };
export declare function listCatalog(category?: CatalogCategory): CatalogManifestItem[];
export declare function searchCatalog(query: string): CatalogManifestItem[];
export declare function inspectCatalogItem(id: string): CatalogManifestItem;
export declare function createExample(id: string, destination?: string): string;

export interface SkillInstallOptions { harness: "agents" | "codex" | "claude" | "opencode"; scope?: "project" | "user"; cwd?: string }
export declare function listSkills(): JSONObject[];
export declare function installSkill(id: string, options: SkillInstallOptions): JSONObject;
export declare function checkSkill(id: string, options: SkillInstallOptions): JSONObject;
export declare function updateSkill(id: string, options: SkillInstallOptions): JSONObject;
export declare function removeSkill(id: string, options: SkillInstallOptions): JSONObject;
export declare function treeChecksum(root: string, excluded?: Set<string>): string;

export declare function registerComponent(id: string, component: (props: JSONObject, frame: number, context: JSONObject) => string): void;
export declare function renderComponent(id: string, props: JSONObject, frame: number, context: JSONObject): string;
export declare function documentForFrame(spec: JSONObject, frame: number): string;
export declare function trackingPointAt(points: JSONObject[], frame: number, fallback?: { x: number; y: number }): Readonly<{ x: number; y: number }>;
export declare function renderMotionFrame(spec: JSONObject, frame: number, output: string, options?: { transparent?: boolean }): Promise<string>;

export declare const vibeedit: Readonly<{ name: "VibeEdit"; version: "0.1.0"; website: "https://vibeedit.com"; npm: "https://www.npmjs.com/package/vibeedit"; schemaVersion: "1.0.0"; catalogVersion: "0.1.0" }>;
export default vibeedit;
