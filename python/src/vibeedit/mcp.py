from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from vibeedit.catalog import compact_catalog_result, inspect_catalog_item, search_catalog
from vibeedit.ffmpeg import probe
from vibeedit.render import render
from vibeedit.revision import plan_revision
from vibeedit.spec import JSONObject
from vibeedit.validation import validate_composition
from vibeedit.verify import verify_output
from vibeedit.version import VERSION


TOOLS = [
    {"name": "agent_command", "description": "Run the shared VibeEdit CLI contract without a shell: project/review/acquisition, durable worker/goal handles and customer jobs. Requires explicit caps for paid admission just like CLI. Foreground execution and credential entry are excluded from stdio MCP; detached starts return original durable handles. Model inference/setup use the parent agent's local CLI.", "inputSchema": {"type": "object", "required": ["argv"], "properties": {"argv": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"type": "string", "maxLength": 4096}}}, "additionalProperties": False}},
    {"name": "search_catalog", "description": "Return up to five compact ranked VibeEdit capabilities; inspect one stable ID for full details", "inputSchema": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}, "category": {"type": "string"}, "capability": {"type": "string"}, "platform": {"enum": ["macos", "windows", "linux"]}}}},
    {"name": "inspect_catalog_item", "description": "Inspect one stable catalog item", "inputSchema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}},
    {"name": "plan_revision", "description": "Compare previous and revised CompositionSpecs and explain dirty ranges, reusable artifacts, jobs, and execution support", "inputSchema": {"type": "object", "required": ["previous", "revised"], "properties": {"previous": {"type": "object"}, "revised": {"type": "object"}}}},
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
    except (OSError, ValueError, RuntimeError, NotImplementedError, KeyError, TypeError) as error:
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": -32000, "message": str(error)}}


def call_tool(name: str, arguments: JSONObject) -> JSONObject | list[JSONObject]:
    if name == "agent_command":
        argv = arguments.get("argv")
        if not isinstance(argv, list) or not 1 <= len(argv) <= 64 or any(not isinstance(v, str) or not v or len(v) > 4096 or "\x00" in v for v in argv):
            raise ValueError("Expected 1–64 bounded command arguments")
        if argv[0] not in {"project", "review", "acquire", "worker", "goal", "myriograph", "analyze", "jobs", "doctor"} or any(v in {"--foreground", "--no-detach"} for v in argv) or argv[:2] in (["worker", "configure"], ["worker", "setup"]):
            raise ValueError("Use parent-agent local CLI for this foreground/setup/credential command")
        try:
            result = subprocess.run([sys.executable, "-m", "vibeedit.cli", *argv, *([] if "--json" in argv else ["--json"])], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=75)
        except subprocess.TimeoutExpired:
            return {"ok": False, "status": "observation-timeout", "action": "Inspect the original project operation/job/worker/goal handle. A timeout does not authorize repeating a paid admission or replacing its handle."}
        if len(result.stdout.encode()) > 8 * 1024**2:
            raise ValueError("Command output exceeds MCP context limit; use paginated local CLI")
        if "--help" in argv:
            return {"ok": result.returncode == 0, "exitCode": result.returncode, "help": result.stdout}
        values = []
        remaining = result.stdout.lstrip()
        decoder = json.JSONDecoder()
        while remaining:
            value, end = decoder.raw_decode(remaining)
            values.append(value)
            if len(values) > 64:
                raise ValueError("Command emits too many JSON records for one MCP call")
            remaining = remaining[end:].lstrip()
        return {"ok": result.returncode == 0, "exitCode": result.returncode, "results": values, **({"action": "Use local CLI help to inspect the rejected command; remote stderr is not exposed"} if result.returncode and not values else {})}
    if name == "search_catalog":
        limit = int(arguments.get("limit", 5))
        if limit > 20:
            raise ValueError("search_catalog limit cannot exceed 20")
        query = str(arguments["query"])
        return [
            compact_catalog_result(item, query)
            for item in search_catalog(
                query,
                category=str(arguments["category"]) if arguments.get("category") else None,
                capability=str(arguments["capability"]) if arguments.get("capability") else None,
                platform=str(arguments["platform"]) if arguments.get("platform") else None,
                limit=limit,
            )
        ]
    if name == "inspect_catalog_item":
        return inspect_catalog_item(str(arguments["id"]))
    if name == "plan_revision":
        return plan_revision(arguments["previous"], arguments["revised"])
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
    track = next((track for track in spec["timeline"]["tracks"] if track["id"] == arguments.get("trackId")), None)
    if name != "apply_effect" and not track:
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
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Expected a JSON-RPC object")
            response = handle_request(request)
        except (ValueError, TypeError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON-RPC input"}}
        if response is not None:
            print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
