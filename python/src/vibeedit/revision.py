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
    bounded_motion = bool(changed_items) and all(
        (previous_items.get(identifier) or revised_items.get(identifier, {})).get("kind") == "motion"
        for identifier in changed_items
    ) and all(
        not path.startswith(("/canvas", "/durationFrames", "/sources", "/render", "/audio", "/artifacts"))
        for path in changed_fields
    )
    dirty_ranges = _merge_ranges(
        [
            _item_range(item)
            for identifier in changed_items
            for item in (previous_items.get(identifier), revised_items.get(identifier))
            if bounded_motion and item
        ]
    ) if changed_fields else []
    if changed_fields and not bounded_motion:
        dirty_ranges = [{"startFrame": 0, "endFrame": revised["durationFrames"]}]
    dirty_frames = sum(item["endFrame"] - item["startFrame"] for item in dirty_ranges)
    total_frames = revised["durationFrames"]
    dirty_layers = [
        {
            "id": identifier,
            "kind": (revised_items.get(identifier) or previous_items[identifier])["kind"],
            "reason": "component fields changed within its bounded placement" if bounded_motion else "composition dependency changed",
        }
        for identifier in changed_items
    ]
    graph = build_render_graph(revised)
    return {
        "schemaVersion": "1.0.0",
        "previousCompositionHash": _hash(previous),
        "revisedCompositionHash": _hash(revised),
        "changedFields": changed_fields,
        "dirtyLayers": dirty_layers,
        "dirtyFrameRanges": dirty_ranges,
        "reusableArtifacts": _reusable_artifacts(previous, revised, bounded_motion),
        "requiredRerenderJobs": [
            {
                "kind": "motion-layer" if bounded_motion else "full-composition",
                "layerIds": changed_items,
                "frameRange": item,
                "reason": "only active composite frames depend on the changed motion layer" if bounded_motion else "change crosses the bounded motion-revision contract",
            }
            for item in dirty_ranges
        ],
        "stitchPlan": {
            "strategy": "content-addressed-frame-sequence",
            "reuseCleanFrames": bounded_motion,
            "ranges": dirty_ranges,
        },
        "expectedReuse": {
            "totalFrames": total_frames,
            "dirtyFrames": dirty_frames,
            "reusedFrames": max(0, total_frames - dirty_frames),
            "ratio": round(max(0, total_frames - dirty_frames) / max(1, total_frames), 6),
        },
        "dependencyGraph": graph,
        "incrementalEligible": bounded_motion,
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
    edges = [
        {"from": f"source:{item['source']['sourceId']}", "to": f"layer:{item['id']}", "reason": "layer decodes source media"}
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
        if isinstance(item.get("source"), dict) and item["source"].get("sourceId")
    ]
    edges.extend(
        {"from": node["id"], "to": "composite:final", "reason": "active layer contributes pixels or samples"}
        for node in layer_nodes
    )
    return {
        "nodes": [*source_nodes, *layer_nodes, {"id": "composite:final", "kind": "composite", "hash": _hash({"canvas": spec["canvas"], "durationFrames": spec["durationFrames"]})}],
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


def _reusable_artifacts(previous: JSONObject, revised: JSONObject, bounded_motion: bool) -> list[JSONObject]:
    if not bounded_motion:
        return []
    reusable = [
        {"kind": "source-decoding", "id": source["id"], "reason": "source identity is unchanged"}
        for source in revised["sources"]
        if source in previous["sources"]
    ]
    for kind in ("tracking", "masks", "analysis"):
        if previous.get("artifacts", {}).get(kind) == revised.get("artifacts", {}).get(kind):
            reusable.append({"kind": kind, "id": "all", "reason": f"{kind} inputs and parameters are unchanged"})
    if previous.get("audio") == revised.get("audio"):
        reusable.append({"kind": "audio-mix", "id": "final", "reason": "audio contract is unchanged"})
    return reusable


def _hash(value) -> str:
    return hashlib.sha256(canonical_json(json.loads(json.dumps(value))).encode()).hexdigest()
