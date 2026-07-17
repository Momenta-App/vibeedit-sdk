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


def test_catalog_search_distinguishes_workflows_templates_and_mask_intent():
    expected = {
        "show several transitions in one edit": "vibeedit://template/multiple-transitions",
        "add typography to my fan edit": "vibeedit://skill/fanedit-text",
        "route the complete fan edit workflow": "vibeedit://skill/vibeedit-fan-edit",
        "mix Python media and HTML text": "vibeedit://template/mixed-source-html",
        "choose and place transitions for me": "vibeedit://skill/vibeedit-transition-editor",
        "plan sound design for the whole edit": "vibeedit://skill/vibeedit-sound-design",
        "apply an effect only inside the segmentation": "vibeedit://template/mask-subject-effect",
    }
    assert {query: search_catalog(query, limit=1)[0]["id"] for query in expected} == expected
