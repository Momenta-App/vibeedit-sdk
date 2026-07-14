import json

from vibeedit.data import data_path
from vibeedit.mcp import TOOLS, handle_request


def test_mcp_lists_documented_tools():
    response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert names == {tool["name"] for tool in TOOLS}
    assert {"search_catalog", "inspect_media", "create_composition", "apply_effect", "apply_transition", "add_motion_component", "select_and_place_sfx", "render", "verify"} <= names


def test_mcp_catalog_and_composition_adapters():
    search = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "search_catalog", "arguments": {"query": "procedural"}}})
    assert search["result"]["structuredContent"][0]["id"] == "vibeedit://sfx/impact-procedural"
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text())
    component = {"id": "second-title", "kind": "motion", "placement": {"startFrame": 10, "durationFrames": 20}, "componentId": "vibeedit://text/negative", "props": {"text": "PROOF"}, "renderer": "html", "transparent": True}
    response = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "add_motion_component", "arguments": {"spec": spec, "trackId": "M1", "component": component}}})
    track = next(track for track in response["result"]["structuredContent"]["timeline"]["tracks"] if track["id"] == "M1")
    assert track["items"][-1]["id"] == "second-title"
