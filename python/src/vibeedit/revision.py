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
    container_audio_remix = revision_kind == "container" and _container_audio_remix_required(previous, revised)
    if container_audio_remix:
        dirty_audio_ranges = [{"startFrame": 0, "endFrame": revised["durationFrames"]}]
    tail_truncation = revision_kind == "scene-removal" and _tail_truncation_eligible(previous, revised, previous_items, revised_items)
    tail_audio_remix = tail_truncation and any(item["kind"] in {"audio", "sound_effect"} for item in revised_items.values())
    if tail_truncation:
        dirty_ranges = []
    if tail_audio_remix:
        dirty_audio_ranges = [{"startFrame": 0, "endFrame": revised["durationFrames"]}]
    remixes_audio = revision_kind == "audio" or container_audio_remix or tail_audio_remix
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
        "reusableArtifacts": _reusable_artifacts(previous, revised, revision_kind, changed_artifacts, remixes_audio=remixes_audio),
        "requiredRerenderJobs": _rerender_jobs(revision_kind, changed_items, changed_artifacts, dirty_ranges, dirty_audio_ranges, previous_items, revised_items),
        "stitchPlan": _stitch_plan(revision_kind, dirty_ranges, dirty_audio_ranges, tail_truncation=tail_truncation, tail_audio_remix=tail_audio_remix),
        "expectedReuse": {
            "totalFrames": total_frames,
            "dirtyFrames": dirty_frames,
            "reusedFrames": max(0, total_frames - dirty_frames),
            "ratio": round(max(0, total_frames - dirty_frames) / max(1, total_frames), 6),
        },
        "decodeWorkAvoided": _decode_work_avoided(previous, revised, revision_kind, remixes_audio=remixes_audio),
        "dependencyGraph": graph,
        "revisionKind": revision_kind,
        "incrementalEligible": revision_kind not in {"full", "none"},
        "executionStatus": "verified-frame-cache" if revision_kind == "motion" else "verified-stream-copy-video-audio-remix" if container_audio_remix else "verified-stream-copy-remux" if revision_kind == "container" else "verified-audio-remix" if revision_kind == "audio" else "verified-stream-copy-tail-audio-remix" if tail_audio_remix else "verified-stream-copy-tail" if tail_truncation else "planned-not-yet-executed" if revision_kind not in {"full", "none"} else "full-render-required" if revision_kind == "full" else "no-work",
    }


def build_render_graph(spec: JSONObject) -> JSONObject:
    validate_composition(spec)
    source_hashes = {source["id"]: _hash(source) for source in spec["sources"]}
    source_nodes = [
        {"id": f"source:{source['id']}", "kind": "source", "hash": source_hashes[source["id"]]}
        for source in spec["sources"]
    ]
    artifacts = [
        (kind, item)
        for kind in ("tracking", "masks", "analysis")
        for item in spec.get("artifacts", {}).get(kind, [])
    ]
    artifact_hashes: dict[str, str] = {}
    for _, item in artifacts:
        artifact_hashes[item["id"]] = _hash({
            "artifact": item,
            "dependencies": [artifact_hashes[item["trackingArtifactId"]]] if item.get("trackingArtifactId") in artifact_hashes else [],
            "sources": [source_hashes[identifier] for identifier in item.get("sourceIds", []) if identifier in source_hashes],
        })
    items = [item for track in spec["timeline"]["tracks"] for item in track["items"]]
    layer_hashes = {
        item["id"]: _hash({
            "layer": item,
            "source": source_hashes.get(item.get("source", {}).get("sourceId")),
            "artifacts": [artifact_hashes[identifier] for identifier in _item_artifact_ids(item) if identifier in artifact_hashes],
        })
        for item in items
    }
    layer_nodes = [
        {"id": f"layer:{item['id']}", "kind": item["kind"], "hash": layer_hashes[item["id"]], "frameRange": _item_range(item)}
        for item in items
    ]
    artifact_nodes = [
        {"id": f"artifact:{item['id']}", "kind": kind, "hash": artifact_hashes[item["id"]]}
        for kind, item in artifacts
    ]
    edges = [
        {"from": f"source:{item['source']['sourceId']}", "to": f"layer:{item['id']}", "reason": "layer decodes source media"}
        for item in items
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
        {"from": f"source:{source_id}", "to": f"artifact:{item['id']}", "reason": "analysis artifact depends on source media"}
        for _, item in artifacts
        for source_id in item.get("sourceIds", [])
        if source_id in source_hashes
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
    composite_hash = _hash({"canvas": spec["canvas"], "durationFrames": spec["durationFrames"], "layers": [layer_hashes[item["id"]] for item in items if item["kind"] not in {"audio", "sound_effect"}]})
    audio_mix_hash = _hash({"audio": spec.get("audio", {}), "layers": [layer_hashes[item["id"]] for item in items if item["kind"] in {"audio", "sound_effect"}]})
    output_hash = _hash({"settings": {key: value for key, value in spec["render"]["output"].items() if key != "uri"}, "video": composite_hash, "audio": audio_mix_hash})
    return {
        "nodes": [*source_nodes, *artifact_nodes, *layer_nodes, {"id": "composite:video", "kind": "composite", "hash": composite_hash}, {"id": "mix:audio", "kind": "audio-mix", "hash": audio_mix_hash}, {"id": "output:final", "kind": "output", "hash": output_hash}],
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


def _decode_work_avoided(previous: JSONObject, revised: JSONObject, revision_kind: str, *, remixes_audio: bool = False) -> list[str]:
    if revision_kind == "full":
        return []
    if revision_kind == "transition":
        return []
    decoded_sources = {
        item["source"]["sourceId"]
        for track in revised["timeline"]["tracks"]
        for item in track["items"]
        if remixes_audio and item["kind"] in {"audio", "sound_effect"} and isinstance(item.get("source"), dict)
    }
    return [source["id"] for source in revised["sources"] if source in previous["sources"] and source["id"] not in decoded_sources]


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
    semantic_fields = [path for path in changed_fields if path != "/render/output/uri"]
    if not semantic_fields:
        return "none"
    if set(semantic_fields) == {"/render/output/container"}:
        return "container"
    if changed_artifacts and all(path.startswith("/artifacts") for path in semantic_fields):
        return "artifact"
    kinds = {(revised_items.get(identifier) or previous_items[identifier])["kind"] for identifier in changed_items}
    if kinds and kinds <= {"motion"} and all(not path.startswith(("/canvas", "/durationFrames", "/sources", "/render", "/audio", "/artifacts")) for path in semantic_fields):
        return "motion"
    if kinds and kinds <= {"transition"}:
        return "transition"
    if kinds and kinds <= {"audio", "sound_effect"}:
        return "audio"
    if "video" in kinds and any(identifier not in revised_items for identifier in changed_items):
        return "scene-removal"
    return "full"


def _tail_truncation_eligible(previous: JSONObject, revised: JSONObject, previous_items: dict[str, JSONObject], revised_items: dict[str, JSONObject]) -> bool:
    removed = previous_items.keys() - revised_items.keys()
    removed_visual = {identifier for identifier in removed if previous_items[identifier]["kind"] not in {"audio", "sound_effect"}}
    if revised["durationFrames"] >= previous["durationFrames"] or not removed_visual:
        return False
    if any(identifier not in previous_items or not _retained_visual_prefix_compatible(previous_items[identifier], item, revised["durationFrames"]) for identifier, item in revised_items.items() if item["kind"] not in {"audio", "sound_effect"}):
        return False
    if any(_item_range(item)["endFrame"] > revised["durationFrames"] for item in revised_items.values() if item["kind"] in {"audio", "sound_effect"}):
        return False
    if any(_item_range(previous_items[identifier])["startFrame"] < revised["durationFrames"] for identifier in removed_visual):
        return False
    if any(previous.get(key) != revised.get(key) for key in ("canvas", "sources", "artifacts")):
        return False
    if previous["render"]["backend"] != revised["render"]["backend"]:
        return False
    if {key: value for key, value in previous["render"]["output"].items() if key != "uri"} != {key: value for key, value in revised["render"]["output"].items() if key != "uri"}:
        return False
    previous_tracks = [{key: value for key, value in track.items() if key != "items"} for track in previous["timeline"]["tracks"]]
    revised_tracks = [{key: value for key, value in track.items() if key != "items"} for track in revised["timeline"]["tracks"]]
    return previous_tracks == revised_tracks


def _retained_visual_prefix_compatible(previous: JSONObject, revised: JSONObject, duration_frames: int) -> bool:
    if previous == revised:
        return True
    if previous["kind"] != "video" or revised["kind"] != "video":
        return False
    if {key: value for key, value in previous.items() if key not in {"placement", "source"}} != {key: value for key, value in revised.items() if key not in {"placement", "source"}}:
        return False
    if previous["placement"]["startFrame"] != revised["placement"]["startFrame"] or revised["placement"]["startFrame"] + revised["placement"]["durationFrames"] != duration_frames:
        return False
    if previous["placement"]["startFrame"] + previous["placement"]["durationFrames"] < duration_frames:
        return False
    if {key: value for key, value in previous["source"].items() if key != "durationFrames"} != {key: value for key, value in revised["source"].items() if key != "durationFrames"}:
        return False
    return previous["source"]["durationFrames"] - revised["source"]["durationFrames"] == previous["placement"]["durationFrames"] - revised["placement"]["durationFrames"]


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
    invalidated = {item["id"] for item in result}
    previous_sources = {item["id"]: item for item in previous["sources"]}
    revised_sources = {item["id"]: item for item in revised["sources"]}
    changed_sources = {identifier for identifier in previous_sources.keys() | revised_sources.keys() if previous_sources.get(identifier) != revised_sources.get(identifier)}
    for item in revised.get("artifacts", {}).get("analysis", []):
        if not changed_sources & set(item.get("sourceIds", [])) or item["id"] in invalidated:
            continue
        result.append({"id": item["id"], "kind": "analysis", "change": "dependency-invalidated", "frameRange": None, "reason": "analysis depends on changed source media"})
        invalidated.add(item["id"])
    for item in revised.get("artifacts", {}).get("masks", []):
        if item.get("trackingArtifactId") not in invalidated or item["id"] in invalidated:
            continue
        frame_range = {"startFrame": item["startFrame"], "endFrame": item["startFrame"] + item["durationFrames"]} if isinstance(item.get("startFrame"), int) and isinstance(item.get("durationFrames"), int) else None
        result.append({"id": item["id"], "kind": "masks", "change": "dependency-invalidated", "frameRange": frame_range, "reason": f"mask depends on invalidated tracking artifact {item['trackingArtifactId']}"})
        invalidated.add(item["id"])
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


def _reusable_artifacts(previous: JSONObject, revised: JSONObject, revision_kind: str, changed_artifacts: list[JSONObject], *, remixes_audio: bool = False) -> list[JSONObject]:
    if revision_kind == "full":
        return []
    reusable_source_ids = set(_decode_work_avoided(previous, revised, revision_kind, remixes_audio=remixes_audio))
    invalidated_artifacts = {item["id"] for item in changed_artifacts}
    reusable = [
        {"kind": "source-decoding", "id": source["id"], "reason": "source identity is unchanged"}
        for source in revised["sources"]
        if source["id"] in reusable_source_ids
    ]
    for kind in ("tracking", "masks", "analysis"):
        before = {item["id"]: item for item in previous.get("artifacts", {}).get(kind, [])}
        reusable.extend(
            {"kind": kind, "id": item["id"], "reason": "artifact inputs, parameters, model, runtime, and cache identity are unchanged"}
            for item in revised.get("artifacts", {}).get(kind, [])
            if before.get(item["id"]) == item and item["id"] not in invalidated_artifacts
        )
    if not remixes_audio and previous.get("audio") == revised.get("audio"):
        reusable.append({"kind": "audio-mix", "id": "final", "reason": "audio contract is unchanged"})
    previous_items = _items_by_id(previous)
    reusable.extend(
        {"kind": "layer", "id": item["id"], "reason": "layer content and placement are unchanged"}
        for item in _items_by_id(revised).values()
        if previous_items.get(item["id"]) == item and not set(_item_artifact_ids(item)) & invalidated_artifacts
    )
    return reusable


def _rerender_jobs(revision_kind: str, changed_items: list[str], changed_artifacts: list[JSONObject], dirty_ranges: list[JSONObject], dirty_audio_ranges: list[JSONObject], previous_items: dict[str, JSONObject], revised_items: dict[str, JSONObject]) -> list[JSONObject]:
    if revision_kind == "container":
        if dirty_audio_ranges:
            return [{"kind": "audio-mix", "frameRange": item, "reason": "target container cannot preserve the prior audio priming contract safely"} for item in dirty_audio_ranges] + [{"kind": "remux", "reason": "stream-copy video while encoding the rebuilt audio mix directly into the target container"}]
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
        if dirty_audio_ranges and not dirty_ranges:
            return [{"kind": "video-tail-copy", "frameRange": {"startFrame": 0, "endFrame": item["endFrame"]}, "reason": "retained video is an exact prefix of the approved prior artifact"} for item in dirty_audio_ranges] + [{"kind": "audio-mix", "frameRange": item, "reason": "audio is rebuilt to the revised scene boundary"} for item in dirty_audio_ranges] + [{"kind": "remux", "reason": "stream-copy the retained video prefix while encoding revised audio"}]
        return [{"kind": "timeline-composite", "layerIds": changed_items, "frameRange": item, "reason": "timeline positions after the removed scene must be rebuilt"} for item in dirty_ranges]
    if revision_kind == "none":
        return []
    return [{"kind": "full-composition", "frameRange": item, "reason": "change crosses a proven incremental contract"} for item in dirty_ranges]


def _stitch_plan(revision_kind: str, dirty_ranges: list[JSONObject], dirty_audio_ranges: list[JSONObject], *, tail_truncation: bool = False, tail_audio_remix: bool = False) -> JSONObject:
    strategy = {
        "motion": "content-addressed-frame-sequence",
        "transition": "replace-transition-overlap",
        "scene-removal": "stream-copy-video-tail-audio-remix" if tail_audio_remix else "stream-copy-tail-truncation" if tail_truncation else "reuse-prefix-and-rebuild-timeline-tail",
        "audio": "audio-only-remix-and-remux",
        "artifact": "replace-artifact-dependent-ranges",
        "container": "stream-copy-video-audio-remix" if dirty_audio_ranges else "stream-copy-remux",
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


def _container_audio_remix_required(previous: JSONObject, revised: JSONObject) -> bool:
    families = {"mp4": "iso-bmff", "mov": "iso-bmff", "mkv": "matroska", "matroska": "matroska", "webm": "webm"}
    before = families.get(previous["render"]["output"]["container"].casefold())
    after = families.get(revised["render"]["output"]["container"].casefold())
    has_audio = any(item["kind"] in {"audio", "sound_effect"} for track in revised["timeline"]["tracks"] for item in track["items"])
    return has_audio and before != after and str(revised["render"]["output"].get("audioCodec", "")).casefold() == "aac"


def _hash(value) -> str:
    return hashlib.sha256(canonical_json(json.loads(json.dumps(value))).encode()).hexdigest()
