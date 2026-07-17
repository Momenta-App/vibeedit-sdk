import json

from vibeedit.catalog import compact_catalog_result, search_catalog


def test_search_catalog_supports_deterministic_top_k_filters():
    first = search_catalog("impact", category="sfx", capability="audio", platform="linux", limit=1)
    second = search_catalog("impact", category="sfx", capability="audio", platform="linux", limit=1)
    assert [item["id"] for item in first] == ["vibeedit://sfx/impact-procedural"]
    assert first == second


def test_compact_top_five_stays_within_agent_context_budget():
    results = [compact_catalog_result(item, "captions that highlight each active word") for item in search_catalog("captions that highlight each active word", limit=5)]
    payload = json.dumps(results, separators=(",", ":")).encode()
    assert len(results) == 5
    assert len(payload) < 6_000
    assert all("prompts" not in item and "examples" not in item and "validation" not in item for item in results)


def test_catalog_search_rejects_invalid_limit():
    try:
        search_catalog("caption", limit=0)
    except ValueError as error:
        assert str(error) == "catalog search limit must be at least 1"
        return
    raise AssertionError("expected invalid limit to fail")
