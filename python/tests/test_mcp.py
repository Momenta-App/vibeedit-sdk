import json

from vibeedit.data import data_path
from vibeedit.mcp import TOOLS, handle_request
from test_project import project


def test_mcp_lists_documented_tools():
    response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert names == {tool["name"] for tool in TOOLS}
    assert {"search_catalog", "inspect_media", "create_composition", "apply_effect", "apply_transition", "add_motion_component", "select_and_place_sfx", "render", "verify"} <= names


def test_mcp_catalog_and_composition_adapters():
    search = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "search_catalog", "arguments": {"query": "procedural"}}})
    assert search["result"]["structuredContent"][0]["id"] == "vibeedit://sfx/impact-procedural"
    assert len(search["result"]["structuredContent"]) <= 5
    assert "prompts" not in search["result"]["structuredContent"][0]
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text(encoding="utf-8"))
    component = {"id": "second-title", "kind": "motion", "placement": {"startFrame": 10, "durationFrames": 20}, "componentId": "vibeedit://text/negative", "props": {"text": "PROOF"}, "renderer": "html", "transparent": True}
    response = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "add_motion_component", "arguments": {"spec": spec, "trackId": "M1", "component": component}}})
    track = next(track for track in response["result"]["structuredContent"]["timeline"]["tracks"] if track["id"] == "M1")
    assert track["items"][-1]["id"] == "second-title"


def test_mcp_catalog_search_applies_progressive_disclosure_filters():
    response = handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_catalog", "arguments": {"query": "impact", "category": "sfx", "capability": "audio", "platform": "linux", "limit": 1}}})
    payload = response["result"]["structuredContent"]
    assert [item["id"] for item in payload] == ["vibeedit://sfx/impact-procedural"]
    assert payload[0]["setupRequirements"] == []


def test_mcp_revision_plan_reports_execution_truth():
    previous = json.loads(data_path("schema", "fixtures", "minimal.json").read_text(encoding="utf-8"))
    revised = json.loads(json.dumps(previous))
    revised["render"]["output"].update({"container": "mkv", "uri": "output.mkv"})
    response = handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "plan_revision", "arguments": {"previous": previous, "revised": revised}}})
    payload = response["result"]["structuredContent"]
    assert payload["revisionKind"] == "container"
    assert payload["executionStatus"] == "verified-stream-copy-remux"


def test_mcp_shared_project_contract_and_foreground_boundary(project):
    response = handle_request({"id": 5, "method": "tools/call", "params": {"name": "agent_command", "arguments": {"argv": ["project", "inspect", str(project.root)]}}})
    payload = response["result"]["structuredContent"]
    assert payload["ok"] is True
    assert payload["results"][0]["result"]["id"] == project.read()["id"]
    rejected = handle_request({"id": 6, "method": "tools/call", "params": {"name": "agent_command", "arguments": {"argv": ["mcp"]}}})
    assert "error" in rejected
    rejected = handle_request({"id": 7, "method": "tools/call", "params": {"name": "agent_command", "arguments": {"argv": ["worker", "run", "--no-detach"]}}})
    assert "error" in rejected


def test_mcp_clip_effect_does_not_require_unrelated_track_id():
    spec = json.loads(data_path("schema", "fixtures", "mixed.json").read_text(encoding="utf-8"))
    clip = next(item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "motion")
    response = handle_request({"id": 8, "method": "tools/call", "params": {"name": "apply_effect", "arguments": {"spec": spec, "clipId": clip["id"], "effect": {"id":"brighten", "effectId":"vibeedit://effect/brightness", "params":{"value":0.1}}}}})
    assert "error" not in response
    assert spec == json.loads(data_path("schema", "fixtures", "mixed.json").read_text(encoding="utf-8"))


def test_mcp_command_preserves_pretty_json_and_help():
    response = handle_request({"id": 9, "method": "tools/call", "params": {"name": "agent_command", "arguments": {"argv": ["doctor", "--json"]}}})
    assert "error" not in response
    assert response["result"]["structuredContent"]["results"]
    help_response = handle_request({"id": 10, "method": "tools/call", "params": {"name": "agent_command", "arguments": {"argv": ["project", "--help"]}}})
    assert "error" not in help_response
