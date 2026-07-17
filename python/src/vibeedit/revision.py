from __future__ import annotations

import hashlib
import json

from vibeedit.spec import JSONObject
from vibeedit.validation import canonical_json, validate_composition


def plan_revision(previous: JSONObject, revised: JSONObject) -> JSONObject:
    validate_composition(previous)
    validate_composition(revised)
    changed_fields = _changed_fields(previous, revised)
    previous_items = _items_by_id(previous)
    revised_items = _items_by_id(revised)
    changed_items = sorted(identifier for identifier in previous_items.keys() | revised_items.keys() if previous_items.get(identifier) != revised_items.get(identifier))
    changed_artifacts = _changed_artifacts(previous, revised)
    revision_kind = _revision_kind(changed_fields, changed_items, changed_artifacts, previous_items, revised_items)
    if revision_kind == "container" and not _container_compatible(revised["render"]["output"]):
        revision_kind = "full"
    dirty_ranges, dirty_audio_ranges = _dirty_ranges(revision_kind, changed_items, changed_artifacts, previous, revised, previous_items, revised_items)
    dirty_frames = sum(item["endFrame"] - item["startFrame"] for item in dirty_ranges)
    total_frames = revised["durationFrames"]
    dirty_layers = [
        {
            "id": identifier,
            "kind": (revised_items.get(identifier) or previous_items[identifier])["kind"],
            "reason": _layer_reason(revision_kind),
        }
        for identifier in changed_items
    ]
    dirty_layers.extend(_artifact_dependents(changed_artifacts, revised_items))
    graph = build_render_graph(revised)
    return {
        "schemaVersion": "1.0.0",
        "previousCompositionHash": _hash(previous),
        "revisedCompositionHash": _hash(revised),
        "changedFields": changed_fields,
        "dirtyLayers": dirty_layers,
        "dirtyFrameRanges": dirty_ranges,
        "dirtyAudioRanges": dirty_audio_ranges,
        "changedArtifacts": changed_artifacts,
        "reusableArtifacts": _reusable_artifacts(previous, revised, revision_kind),
        "requiredRerenderJobs": _rerender_jobs(revision_kind, changed_items, changed_artifacts, dirty_ranges, dirty_audio_ranges, previous_items, revised_items),
        "stitchPlan": _stitch_plan(revision_kind, dirty_ranges, dirty_audio_ranges),
        "expectedReuse": {
            "totalFrames": total_frames,
            "dirtyFrames": dirty_frames,
            "reusedFrames": max(0, total_frames - dirty_frames),
            "ratio": round(max(0, total_frames - dirty_frames) / max(1, total_frames), 6),
        },
        "decodeWorkAvoided": [source["id"] for source in revised["sources"] if source in previous["sources"]] if revision_kind != "full" else [],
        "dependencyGraph": graph,
        "revisionKind": revision_kind,
        "incrementalEligible": revision_kind not in {"full", "none"},
        "executionStatus": "verified-frame-cache" if revision_kind == "motion" else "verified-stream-copy-remux" if revision_kind == "container" else "verified-audio-remix" if revision_kind == "audio" else "planned-not-yet-executed" if revision_kind not in {"full", "none"} else "full-render-required" if revision_kind == "full" else "no-work",
    }


def build_render_graph(spec: JSONObject) -> JSONObject:
    validate_composition(spec)
    source_nodes = [
        {"id": f"source:{source['id']}", "kind": "source", "hash": _hash(source)}
        for source in spec["sources"]
    ]
    layer_nodes = [
        {"id": f"layer:{item['id']}", "kind": item["kind"], "hash": _hash(item), "frameRange": _item_range(item)}
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
    ]
    artifact_nodes = [
        {"id": f"artifact:{item['id']}", "kind": kind, "hash": _hash(item)}
        for kind in ("masks", "tracking", "analysis")
        for item in spec.get("artifacts", {}).get(kind, [])
    ]
    edges = [
        {"from": f"source:{item['source']['sourceId']}", "to": f"layer:{item['id']}", "reason": "layer decodes source media"}
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
        if isinstance(item.get("source"), dict) and item["source"].get("sourceId")
    ]
    edges.extend(
        {"from": node["id"], "to": "mix:audio" if node["kind"] in {"audio", "sound_effect"} else "composite:video", "reason": "active layer contributes samples" if node["kind"] in {"audio", "sound_effect"} else "active layer contributes pixels"}
        for node in layer_nodes
    )
    edges.extend(
        {"from": f"artifact:{artifact_id}", "to": f"layer:{item['id']}", "reason": "layer references cached artifact"}
        for item in _items_by_id(spec).values()
        for artifact_id in _item_artifact_ids(item)
    )
    edges.extend(
        {"from": f"artifact:{item['trackingArtifactId']}", "to": f"artifact:{item['id']}", "reason": "mask depends on tracking"}
        for item in spec.get("artifacts", {}).get("masks", [])
        if item.get("trackingArtifactId")
    )
    edges.extend([
        {"from": "composite:video", "to": "output:final", "reason": "video enters final assembly"},
        {"from": "mix:audio", "to": "output:final", "reason": "audio enters final assembly"},
    ])
    return {
        "nodes": [*source_nodes, *artifact_nodes, *layer_nodes, {"id": "composite:video", "kind": "composite", "hash": _hash({"canvas": spec["canvas"], "durationFrames": spec["durationFrames"]})}, {"id": "mix:audio", "kind": "audio-mix", "hash": _hash(spec.get("audio", {}))}, {"id": "output:final", "kind": "output", "hash": _hash(spec["render"]["output"])}],
        "edges": edges,
    }


def _changed_fields(previous, revised, path: str = "") -> list[str]:
    if type(previous) is not type(revised):
        return [path or "/"]
    if isinstance(previous, dict):
        return [
            changed
            for key in sorted(previous.keys() | revised.keys())
            for changed in _changed_fields(previous.get(key), revised.get(key), f"{path}/{key}")
            if key in previous and key in revised
        ] + [f"{path}/{key}" for key in sorted(previous.keys() ^ revised.keys())]
    if isinstance(previous, list):
        if len(previous) != len(revised):
            return [path or "/"]
        return [changed for index, values in enumerate(zip(previous, revised)) for changed in _changed_fields(values[0], values[1], f"{path}/{index}")]
    return [] if previous == revised else [path or "/"]


def _items_by_id(spec: JSONObject) -> dict[str, JSONObject]:
    return {
        item["id"]: item
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
    }


def _item_range(item: JSONObject) -> JSONObject:
    placement = item["placement"]
    return {"startFrame": placement["startFrame"], "endFrame": placement["startFrame"] + placement["durationFrames"]}


def _merge_ranges(ranges: list[JSONObject]) -> list[JSONObject]:
    result: list[JSONObject] = []
    for item in sorted(ranges, key=lambda value: (value["startFrame"], value["endFrame"])):
        if result and item["startFrame"] <= result[-1]["endFrame"]:
            result[-1]["endFrame"] = max(result[-1]["endFrame"], item["endFrame"])
            continue
        result.append(dict(item))
    return result


def _revision_kind(changed_fields: list[str], changed_items: list[str], changed_artifacts: list[JSONObject], previous_items: dict[str, JSONObject], revised_items: dict[str, JSONObject]) -> str:
    if not changed_fields:
        return "none"
    if set(changed_fields) <= {"/render/output/container", "/render/output/uri"}:
        return "container"
    if changed_artifacts and all(path.startswith("/artifacts") for path in changed_fields):
        return "artifact"
    kinds = {(revised_items.get(identifier) or previous_items[identifier])["kind"] for identifier in changed_items}
    if kinds and kinds <= {"motion"} and all(not path.startswith(("/canvas", "/durationFrames", "/sources", "/render", "/audio", "/artifacts")) for path in changed_fields):
        return "motion"
    if kinds and kinds <= {"transition"}:
        return "transition"
    if kinds and kinds <= {"audio", "sound_effect"}:
        return "audio"
    if "video" in kinds and any(identifier not in revised_items for identifier in changed_items):
        return "scene-removal"
    return "full"


def _dirty_ranges(revision_kind: str, changed_items: list[str], changed_artifacts: list[JSONObject], previous: JSONObject, revised: JSONObject, previous_items: dict[str, JSONObject], revised_items: dict[str, JSONObject]) -> tuple[list[JSONObject], list[JSONObject]]:
    item_ranges = [
        _item_range(item)
        for identifier in changed_items
        for item in (previous_items.get(identifier), revised_items.get(identifier))
        if item
    ]
    if revision_kind in {"motion", "transition"}:
        return _merge_ranges(item_ranges), []
    if revision_kind == "audio":
        return [], _merge_ranges(item_ranges)
    if revision_kind == "artifact":
        artifact_ranges = [item["frameRange"] for item in changed_artifacts if item.get("frameRange")]
        dependent_ranges = [
            _item_range(item)
            for item in revised_items.values()
            if set(_item_artifact_ids(item)) & {artifact["id"] for artifact in changed_artifacts}
        ]
        return _merge_ranges([*artifact_ranges, *dependent_ranges]), []
    if revision_kind == "scene-removal":
        start = min(item["startFrame"] for item in item_ranges)
        return ([{"startFrame": min(start, revised["durationFrames"]), "endFrame": revised["durationFrames"]}] if start < revised["durationFrames"] else []), []
    if revision_kind in {"container", "none"}:
        return [], []
    return [{"startFrame": 0, "endFrame": revised["durationFrames"]}], []


def _changed_artifacts(previous: JSONObject, revised: JSONObject) -> list[JSONObject]:
    result = []
    for kind in ("masks", "tracking", "analysis"):
        before = {item["id"]: item for item in previous.get("artifacts", {}).get(kind, [])}
        after = {item["id"]: item for item in revised.get("artifacts", {}).get(kind, [])}
        for identifier in sorted(before.keys() | after.keys()):
            if before.get(identifier) == after.get(identifier):
                continue
            item = after.get(identifier) or before[identifier]
            frame_range = None
            if isinstance(item.get("startFrame"), int) and isinstance(item.get("durationFrames"), int):
                frame_range = {"startFrame": item["startFrame"], "endFrame": item["startFrame"] + item["durationFrames"]}
            result.append({"id": identifier, "kind": kind, "change": "added" if identifier not in before else "removed" if identifier not in after else "modified", "frameRange": frame_range, "reason": "artifact content, parameters, model, runtime, or provenance changed"})
    return result


def _artifact_dependents(changed_artifacts: list[JSONObject], items: dict[str, JSONObject]) -> list[JSONObject]:
    identifiers = {item["id"] for item in changed_artifacts}
    return [
        {"id": item["id"], "kind": item["kind"], "reason": "layer references an invalidated artifact"}
        for item in items.values()
        if set(_item_artifact_ids(item)) & identifiers
    ]


def _item_artifact_ids(item: JSONObject) -> list[str]:
    return list(dict.fromkeys([
        *item.get("maskIds", []),
        *item.get("trackingArtifactIds", []),
        *[effect["maskId"] for effect in item.get("effects", []) if effect.get("maskId")],
        *[effect["trackingArtifactId"] for effect in item.get("effects", []) if effect.get("trackingArtifactId")],
    ]))


def _reusable_artifacts(previous: JSONObject, revised: JSONObject, revision_kind: str) -> list[JSONObject]:
    if revision_kind == "full":
        return []
    reusable = [
        {"kind": "source-decoding", "id": source["id"], "reason": "source identity is unchanged"}
        for source in revised["sources"]
        if source in previous["sources"]
    ]
    for kind in ("tracking", "masks", "analysis"):
        before = {item["id"]: item for item in previous.get("artifacts", {}).get(kind, [])}
        reusable.extend(
            {"kind": kind, "id": item["id"], "reason": "artifact inputs, parameters, model, runtime, and cache identity are unchanged"}
            for item in revised.get("artifacts", {}).get(kind, [])
            if before.get(item["id"]) == item
        )
    if revision_kind != "audio" and previous.get("audio") == revised.get("audio"):
        reusable.append({"kind": "audio-mix", "id": "final", "reason": "audio contract is unchanged"})
    previous_items = _items_by_id(previous)
    reusable.extend(
        {"kind": "layer", "id": item["id"], "reason": "layer content and placement are unchanged"}
        for item in _items_by_id(revised).values()
        if previous_items.get(item["id"]) == item
    )
    return reusable


def _rerender_jobs(revision_kind: str, changed_items: list[str], changed_artifacts: list[JSONObject], dirty_ranges: list[JSONObject], dirty_audio_ranges: list[JSONObject], previous_items: dict[str, JSONObject], revised_items: dict[str, JSONObject]) -> list[JSONObject]:
    if revision_kind == "container":
        return [{"kind": "remux", "reason": "container changed while encoded streams remain compatible"}]
    if revision_kind == "audio":
        return [{"kind": "audio-mix", "layerIds": changed_items, "frameRange": item, "reason": "audio parameters changed without changing video pixels"} for item in dirty_audio_ranges] + [{"kind": "remux", "reason": "replace the audio stream while reusing encoded video"}]
    if revision_kind == "artifact":
        return [{"kind": "artifact", "artifactIds": [item["id"] for item in changed_artifacts], "frameRange": item, "reason": "artifact parameters or provenance changed"} for item in dirty_ranges] + [{"kind": "composite", "frameRange": item, "reason": "downstream pixels reference the invalidated artifact"} for item in dirty_ranges]
    if revision_kind == "transition":
        return [
            {"kind": "transition", "layerIds": changed_items, "frameRange": item, "sourceHandles": sorted({value for identifier in changed_items for value in ((revised_items.get(identifier) or previous_items[identifier]).get("fromItemId"), (revised_items.get(identifier) or previous_items[identifier]).get("toItemId")) if value}), "reason": "transition implementation or parameters changed only within its overlap"}
            for item in dirty_ranges
        ]
    if revision_kind == "motion":
        return [{"kind": "motion-layer", "layerIds": changed_items, "frameRange": item, "reason": "only active composite frames depend on the changed motion layer"} for item in dirty_ranges]
    if revision_kind == "scene-removal":
        return [{"kind": "timeline-composite", "layerIds": changed_items, "frameRange": item, "reason": "timeline positions after the removed scene must be rebuilt"} for item in dirty_ranges]
    if revision_kind == "none":
        return []
    return [{"kind": "full-composition", "frameRange": item, "reason": "change crosses a proven incremental contract"} for item in dirty_ranges]


def _stitch_plan(revision_kind: str, dirty_ranges: list[JSONObject], dirty_audio_ranges: list[JSONObject]) -> JSONObject:
    strategy = {
        "motion": "content-addressed-frame-sequence",
        "transition": "replace-transition-overlap",
        "scene-removal": "reuse-prefix-and-rebuild-timeline-tail",
        "audio": "audio-only-remix-and-remux",
        "artifact": "replace-artifact-dependent-ranges",
        "container": "stream-copy-remux",
        "none": "no-op",
    }.get(revision_kind, "full-render")
    return {"strategy": strategy, "reuseCleanFrames": revision_kind not in {"full", "none"}, "ranges": dirty_ranges, "audioRanges": dirty_audio_ranges}


def _layer_reason(revision_kind: str) -> str:
    return {
        "motion": "component fields changed within its bounded placement",
        "transition": "transition fields changed within its overlap",
        "audio": "audio layer parameters changed",
        "scene-removal": "timeline layer was removed",
    }.get(revision_kind, "composition dependency changed")


def _container_compatible(output: JSONObject) -> bool:
    container = output["container"].casefold()
    video_codec = output["videoCodec"].casefold()
    audio_codec = str(output.get("audioCodec", "")).casefold()
    if container in {"mkv", "matroska"}:
        return True
    if container in {"mp4", "mov"}:
        return video_codec in {"h264", "hevc", "av1"} and (not audio_codec or audio_codec in {"aac", "alac"})
    if container == "webm":
        return video_codec in {"vp9", "av1"} and (not audio_codec or audio_codec in {"opus", "vorbis"})
    return False


def _hash(value) -> str:
    return hashlib.sha256(canonical_json(json.loads(json.dumps(value))).encode()).hexdigest()
