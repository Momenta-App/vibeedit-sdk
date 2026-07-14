from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import TypeAlias

from vibeedit.version import VERSION


JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


def _without_none(value: JSONObject) -> JSONObject:
    return {key: item for key, item in value.items() if item is not None}


@dataclass(frozen=True)
class FrameRate:
    numerator: int
    denominator: int = 1

    def __post_init__(self):
        if self.numerator < 1 or self.denominator < 1:
            raise ValueError("frame-rate numerator and denominator must be positive")
        reduced = Fraction(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", reduced.numerator)
        object.__setattr__(self, "denominator", reduced.denominator)

    def to_spec(self) -> JSONObject:
        return {"numerator": self.numerator, "denominator": self.denominator}

    @property
    def ffmpeg(self) -> str:
        return f"{self.numerator}/{self.denominator}"


@dataclass(frozen=True)
class Canvas:
    width: int
    height: int
    frame_rate: FrameRate
    audio_sample_rate: int = 48_000
    background_color: str = "#000000"
    pixel_format: str = "yuv420p"
    color_space: str = "bt709"

    def __post_init__(self):
        if self.width < 1 or self.height < 1:
            raise ValueError("canvas dimensions must be positive")

    def to_spec(self) -> JSONObject:
        return {
            "width": self.width,
            "height": self.height,
            "frameRate": self.frame_rate.to_spec(),
            "audioSampleRate": self.audio_sample_rate,
            "backgroundColor": self.background_color,
            "pixelFormat": self.pixel_format,
            "colorSpace": self.color_space,
        }


@dataclass(frozen=True)
class Placement:
    start_frame: int
    duration_frames: int
    enabled: bool = True

    def __post_init__(self):
        if self.start_frame < 0 or self.duration_frames < 1:
            raise ValueError("placement requires a non-negative start and positive duration")

    def to_spec(self) -> JSONObject:
        return {"startFrame": self.start_frame, "durationFrames": self.duration_frames, "enabled": self.enabled}


@dataclass(frozen=True)
class SourceRange:
    source_id: str
    in_frame: int
    duration_frames: int

    def to_spec(self) -> JSONObject:
        return {"sourceId": self.source_id, "inFrame": self.in_frame, "durationFrames": self.duration_frames}


@dataclass(frozen=True)
class SourceMedia:
    id: str
    kind: str
    uri: str
    identity: str
    identity_algorithm: str = "sha256"
    media_type: str | None = None
    duration_frames: int | None = None
    metadata: JSONObject = field(default_factory=dict)

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": self.kind,
                "uri": self.uri,
                "identity": {"algorithm": self.identity_algorithm, "value": self.identity},
                "mediaType": self.media_type,
                "durationFrames": self.duration_frames,
                "metadata": self.metadata or None,
            }
        )


@dataclass(frozen=True)
class Transform:
    x: float = 0
    y: float = 0
    scale_x: float = 1
    scale_y: float = 1
    rotation_degrees: float = 0
    opacity: float = 1
    fit: str = "cover"

    def to_spec(self) -> JSONObject:
        return {
            "x": self.x,
            "y": self.y,
            "scaleX": self.scale_x,
            "scaleY": self.scale_y,
            "rotationDegrees": self.rotation_degrees,
            "opacity": self.opacity,
            "fit": self.fit,
        }


@dataclass(frozen=True)
class Effect:
    id: str
    effect_id: str
    params: JSONObject = field(default_factory=dict)
    enabled: bool = True
    mask_id: str | None = None
    tracking_artifact_id: str | None = None
    implementation_version: str = VERSION

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "effectId": self.effect_id,
                "enabled": self.enabled,
                "params": self.params,
                "maskId": self.mask_id,
                "trackingArtifactId": self.tracking_artifact_id,
                "implementationVersion": self.implementation_version,
            }
        )


@dataclass(frozen=True)
class VideoClip:
    id: str
    placement: Placement
    source: SourceRange
    effects: tuple[Effect, ...] = ()
    transform: Transform | None = None
    mask_ids: tuple[str, ...] = ()
    tracking_artifact_ids: tuple[str, ...] = ()

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": "video",
                "placement": self.placement.to_spec(),
                "source": self.source.to_spec(),
                "transform": self.transform.to_spec() if self.transform else None,
                "effects": [effect.to_spec() for effect in self.effects],
                "maskIds": list(self.mask_ids) or None,
                "trackingArtifactIds": list(self.tracking_artifact_ids) or None,
            }
        )


@dataclass(frozen=True)
class AudioClip:
    id: str
    placement: Placement
    source: SourceRange
    role: str = "other"
    gain_db: float = 0
    pan: float = 0
    fade_in_frames: int = 0
    fade_out_frames: int = 0
    effects: tuple[Effect, ...] = ()

    def to_spec(self) -> JSONObject:
        return {
            "id": self.id,
            "kind": "audio",
            "placement": self.placement.to_spec(),
            "source": self.source.to_spec(),
            "role": self.role,
            "gainDb": self.gain_db,
            "pan": self.pan,
            "fadeInFrames": self.fade_in_frames,
            "fadeOutFrames": self.fade_out_frames,
            "effects": [effect.to_spec() for effect in self.effects],
        }


@dataclass(frozen=True)
class ImageClip:
    id: str
    placement: Placement
    source_id: str
    effects: tuple[Effect, ...] = ()
    transform: Transform | None = None
    mask_ids: tuple[str, ...] = ()

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": "image",
                "placement": self.placement.to_spec(),
                "sourceId": self.source_id,
                "transform": self.transform.to_spec() if self.transform else None,
                "effects": [effect.to_spec() for effect in self.effects],
                "maskIds": list(self.mask_ids) or None,
            }
        )


@dataclass(frozen=True)
class MotionComponent:
    id: str
    placement: Placement
    component_id: str
    props: JSONObject = field(default_factory=dict)
    renderer: str = "html"
    transparent: bool = True
    effects: tuple[Effect, ...] = ()
    transform: Transform | None = None

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": "motion",
                "placement": self.placement.to_spec(),
                "componentId": self.component_id,
                "props": self.props,
                "renderer": self.renderer,
                "transparent": self.transparent,
                "effects": [effect.to_spec() for effect in self.effects],
                "transform": self.transform.to_spec() if self.transform else None,
            }
        )


Text = MotionComponent


@dataclass(frozen=True)
class Transition:
    id: str
    placement: Placement
    transition_id: str
    from_item_id: str
    to_item_id: str
    params: JSONObject = field(default_factory=dict)
    audio_transition_id: str | None = None
    implementation_version: str = VERSION

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": "transition",
                "placement": self.placement.to_spec(),
                "transitionId": self.transition_id,
                "fromItemId": self.from_item_id,
                "toItemId": self.to_item_id,
                "params": self.params,
                "audioTransitionId": self.audio_transition_id,
                "implementationVersion": self.implementation_version,
            }
        )


@dataclass(frozen=True)
class SoundEffect:
    id: str
    placement: Placement
    sound_effect_id: str
    params: JSONObject = field(default_factory=dict)
    gain_db: float = 0
    variation_seed: int = 0
    avoid_immediate_repeat: bool = True

    def to_spec(self) -> JSONObject:
        return {
            "id": self.id,
            "kind": "sound_effect",
            "placement": self.placement.to_spec(),
            "soundEffectId": self.sound_effect_id,
            "params": self.params,
            "gainDb": self.gain_db,
            "variationSeed": self.variation_seed,
            "avoidImmediateRepeat": self.avoid_immediate_repeat,
        }


TimelineItem: TypeAlias = VideoClip | AudioClip | ImageClip | MotionComponent | Transition | SoundEffect


@dataclass
class Track:
    id: str
    kind: str
    order: int
    items: list[TimelineItem] = field(default_factory=list)
    role: str | None = None
    enabled: bool = True
    muted: bool = False

    def add(self, item: TimelineItem) -> TimelineItem:
        self.items.append(item)
        return item

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": self.kind,
                "order": self.order,
                "role": self.role,
                "enabled": self.enabled,
                "muted": self.muted,
                "items": [item.to_spec() for item in self.items],
            }
        )


@dataclass
class Timeline:
    tracks: list[Track] = field(default_factory=list)
    markers: list[JSONObject] = field(default_factory=list)

    def add_track(self, track: Track) -> Track:
        if any(existing.id == track.id for existing in self.tracks):
            raise ValueError(f"duplicate track id: {track.id}")
        self.tracks.append(track)
        return track

    def to_spec(self) -> JSONObject:
        return _without_none({"tracks": [track.to_spec() for track in self.tracks], "markers": self.markers or None})


@dataclass(frozen=True)
class Mask:
    id: str
    kind: str
    start_frame: int
    duration_frames: int
    artifact_uri: str
    format: str
    provenance: JSONObject
    inverted: bool = False
    tracking_artifact_id: str | None = None

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": self.kind,
                "startFrame": self.start_frame,
                "durationFrames": self.duration_frames,
                "artifactUri": self.artifact_uri,
                "format": self.format,
                "inverted": self.inverted,
                "trackingArtifactId": self.tracking_artifact_id,
                "provenance": self.provenance,
            }
        )


@dataclass(frozen=True)
class TrackingArtifact:
    id: str
    kind: str
    artifact_uri: str
    start_frame: int
    duration_frames: int
    coordinate_space: str
    provenance: JSONObject
    format: str | None = None

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": self.kind,
                "artifactUri": self.artifact_uri,
                "startFrame": self.start_frame,
                "durationFrames": self.duration_frames,
                "coordinateSpace": self.coordinate_space,
                "format": self.format,
                "provenance": self.provenance,
            }
        )


@dataclass(frozen=True)
class AnalysisArtifact:
    id: str
    kind: str
    artifact_uri: str
    provenance: JSONObject
    format: str | None = None
    source_ids: tuple[str, ...] = ()
    metadata: JSONObject = field(default_factory=dict)

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "id": self.id,
                "kind": self.kind,
                "artifactUri": self.artifact_uri,
                "format": self.format,
                "sourceIds": list(self.source_ids) or None,
                "provenance": self.provenance,
                "metadata": self.metadata or None,
            }
        )


@dataclass(frozen=True)
class RenderJob:
    composition_id: str
    output: Path
    backend: str = "auto"
    deterministic: bool = True


@dataclass(frozen=True)
class VerificationReport:
    passed: bool
    output: str
    checks: tuple[JSONObject, ...]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_spec(self) -> JSONObject:
        return {
            "passed": self.passed,
            "output": self.output,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    category: str
    version: str
    description: str
    manifest: JSONObject = field(default_factory=dict)


@dataclass(frozen=True)
class SkillPackage:
    id: str
    name: str
    version: str
    path: str
    harnesses: tuple[str, ...]
    checksum: str


@dataclass
class Composition:
    id: str
    canvas: Canvas
    duration_frames: int
    title: str = ""
    sources: list[SourceMedia] = field(default_factory=list)
    timeline: Timeline = field(default_factory=Timeline)
    masks: list[Mask] = field(default_factory=list)
    tracking_artifacts: list[TrackingArtifact] = field(default_factory=list)
    analysis_artifacts: list[AnalysisArtifact] = field(default_factory=list)
    render_backend: str = "auto"
    output_uri: str = "output.mp4"
    output_container: str = "mp4"
    video_codec: str = "h264"
    audio_codec: str = "aac"
    transparent: bool = False
    verification: JSONObject = field(default_factory=dict)
    metadata: JSONObject = field(default_factory=dict)
    generator: str = "vibeedit-python"
    generator_version: str = VERSION
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def to_spec(self) -> JSONObject:
        return _without_none(
            {
                "schemaVersion": "1.0.0",
                "kind": "vibeedit.composition",
                "id": self.id,
                "title": self.title or None,
                "canvas": self.canvas.to_spec(),
                "durationFrames": self.duration_frames,
                "sources": [source.to_spec() for source in self.sources],
                "timeline": self.timeline.to_spec(),
                "artifacts": {
                    "masks": [mask.to_spec() for mask in self.masks],
                    "tracking": [artifact.to_spec() for artifact in self.tracking_artifacts],
                    "analysis": [artifact.to_spec() for artifact in self.analysis_artifacts],
                },
                "render": {
                    "backend": self.render_backend,
                    "output": {
                        "uri": self.output_uri,
                        "container": self.output_container,
                        "videoCodec": self.video_codec,
                        "audioCodec": self.audio_codec,
                        "pixelFormat": self.canvas.pixel_format,
                        "transparent": self.transparent,
                    },
                    "deterministic": True,
                },
                "verification": self.verification or None,
                "provenance": {
                    "generator": self.generator,
                    "generatorVersion": self.generator_version,
                    "createdAt": self.created_at,
                    "schemaSource": "schema/composition.schema.json",
                },
                "metadata": self.metadata or None,
            }
        )

    def validate(self) -> None:
        from vibeedit.validation import validate_composition

        validate_composition(self.to_spec())

    def write(self, path: str | Path) -> Path:
        self.validate()
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_spec(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return output

    @classmethod
    def read(cls, path: str | Path) -> JSONObject:
        from vibeedit.validation import validate_composition

        spec = json.loads(Path(path).read_text(encoding="utf-8"))
        validate_composition(spec)
        return spec


ProjectSpec = Composition
CompositionSpec = Composition
