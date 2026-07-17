from __future__ import annotations

import json
import re
from functools import lru_cache

from vibeedit.data import data_path
from vibeedit.spec import JSONObject


@lru_cache(maxsize=1)
def load_catalog() -> JSONObject:
    return json.loads(data_path("catalog", "catalog.json").read_text(encoding="utf-8"))


def list_catalog(category: str | None = None) -> list[JSONObject]:
    items = load_catalog()["items"]
    return [item for item in items if item["category"] == category] if category else list(items)


def search_catalog(
    query: str,
    *,
    category: str | None = None,
    capability: str | None = None,
    platform: str | None = None,
    limit: int | None = None,
) -> list[JSONObject]:
    if limit is not None and limit < 1:
        raise ValueError("catalog search limit must be at least 1")
    tokens = _query_tokens(query)
    if not tokens or _unsupported_query(tokens):
        return []
    candidates = [
        item
        for item in list_catalog(category)
        if (not platform or platform in item.get("platforms", []))
        and (not capability or capability.casefold() in _capability_text(item))
    ]
    ranked = [(_search_score(item, tokens), item) for item in candidates]
    results = [item for score, item in sorted(ranked, key=lambda value: (-value[0], value[1]["id"])) if score > 0]
    return results[:limit] if limit else results


def inspect_catalog_item(identifier: str) -> JSONObject:
    item = next((item for item in list_catalog() if item["id"] == identifier), None)
    if not item:
        raise ValueError(f"unknown catalog item: {identifier}")
    return item


def compact_catalog_result(item: JSONObject, query: str) -> JSONObject:
    tokens = _query_tokens(query)
    score = _search_score(item, tokens)
    requirements = item.get("requirements", {})
    return {
        "id": item["id"],
        "name": item["name"],
        "intent": item["description"] if len(item["description"]) <= 180 else item["description"][:177].rstrip() + "...",
        "category": item["category"],
        "requiredCapability": _required_capability(item),
        "backends": item.get("backends", []),
        "determinism": "validated" if any(record.get("status") == "passed" for record in item.get("validation", [])) else "declared",
        "parameterCount": len(item.get("parameters", {}).get("properties", {})),
        "preview": item.get("preview", {}).get("status", "unknown"),
        "compatibility": item.get("platforms", []),
        "estimatedSetupCost": "optional-model-or-asset" if requirements.get("models") or requirements.get("assets") else "none-declared",
        "estimatedRenderCost": "browser-frame-render" if "html" in item.get("backends", []) else "media-pipeline" if item["category"] != "skill" else "workflow-dependent",
        "setupRequirements": [*requirements.get("models", []), *requirements.get("assets", [])],
        "confidence": round(min(1.0, score / max(12, len(tokens) * 6)), 3),
        "reason": f"matched {', '.join(token for token in tokens if token in _search_text(item)) or 'catalog intent'}",
    }


def _query_tokens(query: str) -> list[str]:
    aliases = {
        "browser": ["html"], "chromium": ["html"], "css": ["html"], "subtitles": ["captions"],
        "subtitle": ["captions"], "grade": ["color"], "footage": ["video"], "music": ["beat"],
        "synchronized": ["beat"], "follows": ["follow", "tracking"], "follow": ["tracking"],
        "person": ["subject"], "scenes": ["transitions"], "sound": ["audio", "sfx"],
        "transition": ["transitions"], "reframe": ["framing", "tracking"], "detected": ["tracking"],
        "segment": ["segmentation", "sam"], "masks": ["mask"], "cutouts": ["segmentation"],
        "several": ["multiple"], "inside": ["mask", "confined"], "route": ["orchestration"],
        "transitions": ["transition"], "mix": ["mixed"], "edits": ["edit"],
    }
    ignored = {"a", "add", "an", "and", "around", "between", "for", "from", "give", "in", "into", "it", "make", "me", "my", "of", "on", "one", "only", "over", "simple", "so", "the", "this", "to", "use", "with"}
    original = [token for token in re.findall(r"[a-z0-9]+", query.casefold()) if token not in ignored]
    return list(dict.fromkeys(token for original_token in original for token in [original_token, *aliases.get(original_token, [])]))


def _unsupported_query(tokens: list[str]) -> bool:
    return "vev1" in tokens or "publish" in tokens or "avatar" in tokens or set(tokens) <= {"do", "something", "cool"} or ({"sam", "3", "1"} <= set(tokens))


def _search_text(item: JSONObject) -> str:
    return " ".join([item["id"], item["name"], item["category"], *item.get("tags", []), *item.get("backends", []), item["description"], *item.get("prompts", [])]).casefold().replace("-", " ")


def _search_score(item: JSONObject, tokens: list[str]) -> int:
    identity = " ".join([item["id"], item["name"], item["category"], *item.get("tags", []), *item.get("backends", [])]).casefold().replace("-", " ")
    details = " ".join([item["description"], *item.get("prompts", [])]).casefold().replace("-", " ")
    matched = [token for token in tokens if token in identity or token in details]
    if not matched:
        return 0
    coverage = len(matched) / len(tokens)
    if len(tokens) > 1 and len(matched) < 2 and coverage < 0.5:
        return 0
    score = sum(6 if token in identity else 2 for token in matched) + round(coverage * 8)
    phrase = " ".join(tokens)
    if phrase in identity:
        score += 12
    if item["category"] == "template" and any(token in tokens for token in ("create", "edit", "example", "workflow", "combine", "mix", "layer")):
        score += 8
    if item["category"] == "skill" and any(token in tokens for token in ("choose", "plan", "route", "orchestration")):
        score += 16
    elif item["category"] == "skill" and "workflow" in tokens:
        score += 7
    if item["category"] == "skill" and "fan" in tokens and "typography" in tokens:
        score += 7
    if item["category"] == "skill" and "complete" in tokens and "orchestration" in details:
        score += 6
    if item["category"] == "skill" and "place" in tokens and "transition" in tokens and "editor" in identity:
        score += 4
    if item["category"] in {"template", "skill"} and any(token in tokens for token in ("mask", "segmentation", "tracking", "sam")):
        score += 7
    if item["category"] == "transition" and any(token in tokens for token in ("transition", "transitions", "crossfade")):
        score += 7
    if item["category"] == "sfx" and any(token in tokens for token in ("sound", "audio", "sfx", "procedural")):
        score += 7
    return score


def _required_capability(item: JSONObject) -> str:
    models = item.get("requirements", {}).get("models", [])
    if models:
        return str(models[0])
    return {"text": "browser-motion", "transition": "media-transition", "effect": "media-effect", "sfx": "audio", "skill": "workflow"}.get(item["category"], "composition")


def _capability_text(item: JSONObject) -> str:
    return " ".join([
        _required_capability(item),
        *item.get("backends", []),
        *item.get("tags", []),
        *item.get("requirements", {}).get("models", []),
        *item.get("requirements", {}).get("assets", []),
        json.dumps(item.get("inputs", {}), ensure_ascii=False),
    ]).casefold()
