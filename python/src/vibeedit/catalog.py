from __future__ import annotations

import json
from functools import lru_cache

from vibeedit.data import data_path
from vibeedit.spec import JSONObject


@lru_cache(maxsize=1)
def load_catalog() -> JSONObject:
    return json.loads(data_path("catalog", "catalog.json").read_text(encoding="utf-8"))


def list_catalog(category: str | None = None) -> list[JSONObject]:
    items = load_catalog()["items"]
    return [item for item in items if item["category"] == category] if category else list(items)


def search_catalog(query: str) -> list[JSONObject]:
    needle = query.casefold()
    return [item for item in list_catalog() if needle in json.dumps(item, ensure_ascii=False).casefold()]


def inspect_catalog_item(identifier: str) -> JSONObject:
    item = next((item for item in list_catalog() if item["id"] == identifier), None)
    if not item:
        raise ValueError(f"unknown catalog item: {identifier}")
    return item

