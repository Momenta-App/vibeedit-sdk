"""Real pinned Pi process and scoped tools against a nonbilling loopback provider.

This qualifies local protocol integration, never an OpenRouter/managed customer journey.
"""
import hashlib
import http.server
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time

import pytest

from vibeedit.goals import Store
from vibeedit.spec import Composition, Canvas, FrameRate
from vibeedit.worker import companion_path


def test_real_pi_executes_validated_artifact_and_render(tmp_path):
    runtime = companion_path()
    if not (runtime / "node_modules/@earendil-works/pi-coding-agent/package.json").is_file() or not shutil.which("ffmpeg"):
        pytest.skip("install pinned companion npm dependencies and FFmpeg for actual RPC boundary qualification")
    project = tmp_path / "real Pi project ü"
    project.mkdir()
    (project / "project.vibeedit.json").write_text('{"schemaVersion":"vibeedit.project.v1","id":"pi-proof"}', encoding="utf-8")
    composition = Composition("pi-proof", Canvas(320, 180, FrameRate(30)), 30, created_at="2026-10-20T00:00:00Z").to_spec()
    requests = []
    steps = [
        ("artifact_write", {"name": "composition.json", "value": composition}),
        ("render_ffmpeg", {"compositionPath": "workers/pi-proof/artifacts/composition.json", "outputName": "proof.mp4"}),
        ("submit_result", {"value": {"answer": 42}}),
    ]
    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            index = len(requests)
            requests.append(value)
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            delta = {"role": "assistant", "content": ""}
            if index < len(steps):
                name, arguments = steps[index]
                delta['tool_calls'] = [{"index": 0, "id": f"tool-{index}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]
            else:
                delta['content'] = 'Finished generated render and structured result.'
            events = [
                {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if index < len(steps) else "stop"}]},
                {"choices": [], "usage": {"prompt_tokens": 20, "completion_tokens": 20, "total_tokens": 40, "cost": 0}},
            ]
            for event in events:
                self.wfile.write(('data: '+json.dumps({"id": f"gen-fixture-{index}", "object": "chat.completion.chunk", "created": int(time.time()), "model": "fixture-model", **event})+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    script = tmp_path / "qualify.py"
    script.write_text('''import sys,pathlib,json,time
from vibeedit.worker import run_worker,configure_byok
from vibeedit.goals import Store
project=pathlib.Path(sys.argv[1]);runtime=pathlib.Path(sys.argv[2]);upstream=sys.argv[3]
configure_byok('nonbilling-fixture-key')
spec={"task":"Produce a generated editable composition, playable render and answer42","funding":"byok","profile":"economical-v1","tools":["artifact_write","render_ffmpeg"],"references":[],"outputSchema":{"type":"object","required":["answer"],"properties":{"answer":{"const":42}},"additionalProperties":False},"artifacts":[{"path":"workers/pi-proof/artifacts/composition.json","kind":"composition"},{"path":"workers/pi-proof/artifacts/proof.mp4","kind":"render"}],"maxModelCalls":6,"maxToolCalls":5,"maxOutputTokens":1024,"maxRetailMicrousd":1000,"maxSeconds":30,"delegationLimit":0}
s=Store(project);s.create('worker','pi-proof',spec);s.close()
profile={"model":"fixture-model","providerRoute":"fixture","contextWindow":4096,"input":["text"],"inputUsdPerToken":"0","outputUsdPerToken":"0","expiresAtUnix":time.time()+60}
run_worker(project,'pi-proof',runtime=runtime,profile=profile,upstream=upstream)
s=Store(project);print(json.dumps(s.get('pi-proof')));s.close()
''', encoding="utf-8")
    try:
        env = {**os.environ, "VIBEEDIT_CONFIG_HOME": str(tmp_path / "private-config")}
        result = subprocess.run([sys.executable, str(script), str(project), str(runtime), f'http://127.0.0.1:{server.server_port}/v1'], env=env, capture_output=True, text=True, timeout=50)
        assert result.returncode == 0, result.stderr
        record = json.loads(result.stdout)
        assert record['status'] == 'complete', record
        assert record['result']['result'] == {"answer": 42}
        assert len(requests) == 4
        if os.environ.get("VIBEEDIT_COMPANION_EVIDENCE_DIR"):
            evidence = pathlib.Path(os.environ["VIBEEDIT_COMPANION_EVIDENCE_DIR"])
            evidence.mkdir(parents=True, exist_ok=True)
            for name in ('composition.json', 'proof.mp4'):
                shutil.copyfile(project/'workers/pi-proof/artifacts'/name, evidence/name)
            (evidence/'receipt.json').write_text(json.dumps({"scope":"local nonbilling protocol fixture using actual Pi and SDK renderer; no real model or editorial quality claim","piVersion":"1.3.0","modelTurns":len(requests),"worker":record},indent=2)+'\n', encoding="utf-8")
        for request in requests:
            assert set(t['function']['name'] for t in request['tools']) == {'artifact_write', 'render_ffmpeg', 'submit_result'}
            assert request['provider']['allow_fallbacks'] is False
        with Store(project).db as db:
            states = db.execute("SELECT state FROM operations WHERE kind='inference'").fetchall()
            assert len(states) == 4 and all(row[0] == 'settled' for row in states)
    finally:
        server.shutdown()
        server.server_close()
