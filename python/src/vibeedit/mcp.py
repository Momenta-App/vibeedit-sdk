from __future__ import annotations

import json
import sys
from pathlib import Path

from vibeedit.catalog import inspect_catalog_item, search_catalog
from vibeedit.ffmpeg import probe
from vibeedit.render import render
from vibeedit.spec import JSONObject
from vibeedit.validation import validate_composition
from vibeedit.verify import verify_output
from vibeedit.version import VERSION


TOOLS = [
    {"name": "search_catalog", "description": "Search VibeEdit capabilities", "inputSchema": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}}},
    {"name": "inspect_catalog_item", "description": "Inspect one stable catalog item", "inputSchema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}},
    {"name": "inspect_media", "description": "Probe a local media file", "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}},
    {"name": "create_composition", "description": "Write a supplied CompositionSpec after validation", "inputSchema": {"type": "object", "required": ["spec", "path"], "properties": {"spec": {"type": "object"}, "path": {"type": "string"}}}},
    {"name": "apply_effect", "description": "Apply an effect entry to a clip in a CompositionSpec", "inputSchema": {"type": "object", "required": ["spec", "clipId", "effect"], "properties": {"spec": {"type": "object"}, "clipId": {"type": "string"}, "effect": {"type": "object"}}}},
    {"name": "apply_transition", "description": "Add a transition item to a track", "inputSchema": {"type": "object", "required": ["spec", "trackId", "transition"], "properties": {"spec": {"type": "object"}, "trackId": {"type": "string"}, "transition": {"type": "object"}}}},
    {"name": "add_motion_component", "description": "Add text or motion to a track", "inputSchema": {"type": "object", "required": ["spec", "trackId", "component"], "properties": {"spec": {"type": "object"}, "trackId": {"type": "string"}, "component": {"type": "object"}}}},
    {"name": "select_and_place_sfx", "description": "Search an SFX and place it on an audio track", "inputSchema": {"type": "object", "required": ["spec", "trackId", "item"], "properties": {"spec": {"type": "object"}, "trackId": {"type": "string"}, "item": {"type": "object"}}}},
    {"name": "render", "description": "Render a CompositionSpec", "inputSchema": {"type": "object", "required": ["spec", "output"], "properties": {"spec": {"type": "object"}, "output": {"type": "string"}}}},
    {"name": "verify", "description": "Verify a rendered output", "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}, "expectations": {"type": "object"}}}},
]


def handle_request(request: JSONObject) -> JSONObject | None:
    identifier = request.get("id")
    try:
        if request.get("method") == "initialize":
            return {"jsonrpc": "2.0", "id": identifier, "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "vibeedit", "version": VERSION}}}
        if request.get("method") == "notifications/initialized":
            return None
        if request.get("method") == "ping":
            return {"jsonrpc": "2.0", "id": identifier, "result": {}}
        if request.get("method") == "tools/list":
            return {"jsonrpc": "2.0", "id": identifier, "result": {"tools": TOOLS}}
        if request.get("method") != "tools/call":
            raise ValueError(f"unsupported method: {request.get('method')}")
        params = request.get("params", {})
        result = call_tool(params.get("name"), params.get("arguments", {}))
        return {"jsonrpc": "2.0", "id": identifier, "result": {"content": [{"type": "text", "text": json.dumps(result)}], "structuredContent": result}}
    except (OSError, ValueError, RuntimeError, NotImplementedError) as error:
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": -32000, "message": str(error)}}


def call_tool(name: str, arguments: JSONObject) -> JSONObject | list[JSONObject]:
    if name == "search_catalog":
        return search_catalog(str(arguments["query"]))
    if name == "inspect_catalog_item":
        return inspect_catalog_item(str(arguments["id"]))
    if name == "inspect_media":
        return probe(str(arguments["path"]))
    if name == "create_composition":
        validate_composition(arguments["spec"])
        path = Path(str(arguments["path"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(arguments["spec"], indent=2) + "\n", encoding="utf-8")
        return {"path": str(path)}
    if name in {"apply_effect", "apply_transition", "add_motion_component", "select_and_place_sfx"}:
        return _edit(name, arguments)
    if name == "render":
        output = render(arguments["spec"], str(arguments["output"]))
        return {"output": str(output), "bytes": output.stat().st_size}
    if name == "verify":
        return verify_output(str(arguments["path"]), arguments.get("expectations")).to_spec()
    raise ValueError(f"unknown tool: {name}")


def _edit(name: str, arguments: JSONObject) -> JSONObject:
    spec = json.loads(json.dumps(arguments["spec"]))
    track = next((track for track in spec["timeline"]["tracks"] if track["id"] == arguments["trackId"]), None)
    if not track:
        raise ValueError(f"unknown track: {arguments['trackId']}")
    if name == "apply_effect":
        clip = next((item for candidate in spec["timeline"]["tracks"] for item in candidate["items"] if item["id"] == arguments["clipId"]), None)
        if not clip:
            raise ValueError(f"unknown clip: {arguments['clipId']}")
        clip.setdefault("effects", []).append(arguments["effect"])
    if name == "apply_transition":
        track["items"].append(arguments["transition"])
    if name == "add_motion_component":
        track["items"].append(arguments["component"])
    if name == "select_and_place_sfx":
        track["items"].append(arguments["item"])
    validate_composition(spec)
    return spec


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle_request(json.loads(line))
        if response is not None:
            print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
