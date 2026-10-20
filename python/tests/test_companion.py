"""Real filesystem/SQLite/process boundaries; provider protocol fixtures never bill."""
import concurrent.futures
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

import pytest

from vibeedit.goals import Store, canonical, validate_goal
from vibeedit.worker import RpcClient, confined, execute_tool, validate_task, verify_artifacts


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project with spaces ü"
    root.mkdir()
    (root / "project.vibeedit.json").write_text('{"schemaVersion":"vibeedit.project.v1","id":"proof"}')
    return root


def task(**updates):
    return {"task": "Create a source-linked review", "funding": "byok", "profile": "economical-v1", "tools": ["artifact_write", "project_read"], "references": [], "outputSchema": {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "integer"}}, "additionalProperties": False}, "artifacts": [], "maxModelCalls": 3, "maxToolCalls": 5, "maxOutputTokens": 1024, "maxRetailMicrousd": 200_000, "maxSeconds": 60, "delegationLimit": 0, **updates}


def test_exact_admission_survives_connection_restart_and_conflict(project):
    store = Store(project)
    first = store.create("worker", "stable", task())
    store.close()
    other = Store(project)
    assert other.create("worker", "stable", task())["digest"] == first["digest"]
    assert len(other.events("stable")) == 1
    with pytest.raises(ValueError, match="conflicting reuse"):
        other.create("worker", "stable", task(task="Different scope"))
    other.close()


def test_lease_fence_prevents_old_owner_mutations(project):
    store = Store(project)
    store.create("goal", "goal", {})
    fence = store.claim("goal", "first")
    assert store.claim("goal", "second") is None
    store.db.execute("UPDATE records SET lease_until=0 WHERE id='goal'")
    next_fence = store.claim("goal", "second")
    assert next_fence > fence
    with pytest.raises(RuntimeError, match="lease lost"):
        store.intent("goal", "old-send", "inference", {}, owner="first", fence=fence)
    with pytest.raises(RuntimeError, match="lease lost"):
        store.update("goal", "complete", {}, owner="first", fence=fence)
    store.close()


def test_concurrent_reservations_share_one_cap(project):
    store = Store(project)
    store.create("goal", "goal", {})
    store.close()
    def reserve(index):
        local = Store(project)
        try:
            return local.intent("goal", f"reserve-{index}", "child", {}, reserve=600_000, cap=1_000_000)
        except ValueError:
            return False
        finally:
            local.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, range(2))) == [False, True]
    store = Store(project)
    assert len(store.operations("goal")) == 1
    store.close()


def test_killed_sender_retains_intent_and_reservation(project, tmp_path):
    script = tmp_path / "sender.py"
    script.write_text("from vibeedit.goals import Store\nimport sys,time\ns=Store(sys.argv[1])\ns.create('worker','crash',{})\ns.intent('crash','original-call','inference',{'nativeRequestId':'original'},reserve=500,cap=500)\nprint('durable',flush=True)\ntime.sleep(60)\n")
    child = subprocess.Popen([sys.executable, str(script), str(project)], stdout=subprocess.PIPE)
    assert child.stdout.readline().strip() == b"durable"
    child.kill()
    child.wait(timeout=5)
    store = Store(project)
    assert store.operations("crash")[0]["state"] == "intent"
    assert store.intent("crash", "original-call", "inference", {"nativeRequestId": "original"}, reserve=500, cap=500) is False
    with pytest.raises(ValueError, match="ceiling"):
        store.intent("crash", "replacement", "inference", {}, reserve=1, cap=500)
    store.close()


def test_settlement_exact_retry_keeps_money_history(project):
    store = Store(project)
    store.create("worker", "w", {})
    store.intent("w", "call", "inference", {}, reserve=100)
    store.settle("call", "unknown", {"nativeGenerationId": "gen-original"})
    assert store.operations("w")[0]["settled_microusd"] is None
    store.settle("call", "settled", {"nativeGenerationId": "gen-original", "cost": 30}, 30)
    store.settle("call", "settled", {"nativeGenerationId": "gen-original", "cost": 30}, 30)
    with pytest.raises(ValueError, match="conflicting settlement"):
        store.settle("call", "settled", {"nativeGenerationId": "replacement"}, 1)
    assert store.operations("w")[0]["settled_microusd"] == 30
    store.close()


def test_external_pause_fences_live_scheduler_and_checks_revision(project):
    store = Store(project)
    store.create("goal", "g", {})
    fence = store.claim("g", "scheduler")
    paused = store.update("g", "paused", expected_revision=0)
    assert paused["fence"] > fence
    with pytest.raises(RuntimeError):
        store.heartbeat("g", "scheduler", fence)
    with pytest.raises(ValueError, match="stale"):
        store.update("g", "active", expected_revision=0)
    assert store.get("g")["status"] == "paused"
    store.close()


def test_scoped_tools_are_immutable_and_retry_returns_original_receipt(project):
    store = Store(project)
    store.create("worker", "w", validate_task(task()))
    fence = store.claim("w", "owner")
    first = execute_tool(project, "w", "owner", fence, "call1", "artifact_write", {"name": "draft.json", "value": {"source": "synthetic"}})
    assert execute_tool(project, "w", "owner", fence, "call1", "artifact_write", {"name": "draft.json", "value": {"source": "synthetic"}}) == first
    with pytest.raises(ValueError, match="immutable"):
        execute_tool(project, "w", "owner", fence, "call2", "artifact_write", {"name": "draft.json", "value": {"source": "changed"}})
    with pytest.raises(ValueError, match="allowlist"):
        execute_tool(project, "w", "owner", fence, "shell", "bash", {"command": "anything"})
    with pytest.raises(ValueError, match="filename"):
        execute_tool(project, "w", "owner", fence, "escape", "artifact_write", {"name": "../../outside", "value": {}})
    assert (project / first["path"]).read_text() == '{"source":"synthetic"}\n'
    store.close()


def test_source_digest_and_symlinks_fail_closed(project):
    source = project / "reference.json"
    source.write_text("before")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    store = Store(project)
    store.create("worker", "w", validate_task(task(references=["reference.json"], referenceDigests={"reference.json": digest})))
    fence = store.claim("w", "owner")
    source.write_text("after")
    with pytest.raises(ValueError, match="digest changed"):
        execute_tool(project, "w", "owner", fence, "read", "project_read", {"path": "reference.json"})
    (project / "escape").symlink_to(project.parent)
    with pytest.raises(ValueError, match="symlink"):
        confined(project, "escape/outside.json", must_exist=False)
    store.close()


def test_json_result_and_artifact_contracts_are_checked(project):
    store = Store(project)
    store.create("worker", "w", validate_task(task()))
    fence = store.claim("w", "owner")
    from jsonschema.exceptions import ValidationError
    with pytest.raises(ValidationError):
        execute_tool(project, "w", "owner", fence, "bad", "submit_result", {"value": {"answer": "not-an-int"}})
    result = execute_tool(project, "w", "owner", fence, "good", "submit_result", {"value": {"answer": 42}})
    assert verify_artifacts(project, [{"path": result["path"], "kind": "json", "sha256": result["sha256"], "schema": task()["outputSchema"]}])[0]["sha256"] == result["sha256"]
    with pytest.raises(ValueError, match="review artifact"):
        verify_artifacts(project, [{"path": result["path"], "kind": "review"}])
    store.close()


def test_goal_does_not_complete_from_plan_only():
    spec = {"objective": "Make an edit", "acceptance": ["Playable render, editable composition and review"], "steps": [task()], "maxRetailMicrousd": 200000, "deadlineUnix": time.time()+300, "completionArtifacts": [{"path": "plan.json", "kind": "json"}]}
    with pytest.raises(ValueError, match="playable render"):
        validate_goal(spec)
    with pytest.raises(ValueError, match="allowances"):
        validate_goal({**spec, "maxRetailMicrousd": 1})


def test_rpc_ids_lf_unicode_and_settled_lifecycle(tmp_path):
    program = tmp_path / "rpc-fixture.py"
    program.write_text("""import sys,json
commands=[json.loads(sys.stdin.buffer.readline()) for _ in range(2)]
for c in reversed(commands):
 print(json.dumps({'type':'response','id':c['id'],'command':c['type'],'success':True,'data':{'text':'a\\u2028b\\u2029c'}},ensure_ascii=False),flush=True)
print(json.dumps({'type':'agent_end','willRetry':True}),flush=True)
print(json.dumps({'type':'agent_settled','aborted':False}),flush=True)
sys.stdin.buffer.read()
""")
    client = RpcClient([sys.executable, str(program)], tmp_path, os.environ.copy())
    try:
        first = client.send({"type": "get_state"}, "first")
        second = client.send({"type": "get_commands"}, "second")
        assert client.response(first)["id"] == "first"
        assert client.response(second)["data"]["text"] == "a\u2028b\u2029c"
        events = [client.records.get(timeout=2) for _ in range(4)]
        assert events[-2]["type"] == "agent_end" and events[-1]["type"] == "agent_settled"
    finally:
        client.close()


def test_rpc_observation_timeout_does_not_resend(tmp_path):
    program = tmp_path / "slow.py"
    marker = tmp_path / "native-handles.json"
    program.write_text("import sys,json,time,pathlib\nc=json.loads(sys.stdin.buffer.readline())\npathlib.Path(sys.argv[1]).write_text(json.dumps(c))\ntime.sleep(60)\n")
    client = RpcClient([sys.executable, str(program), str(marker)], tmp_path, os.environ.copy())
    try:
        handle = client.send({"type": "prompt", "message": "bounded"}, "original")
        with pytest.raises(TimeoutError, match="original command"):
            client.response(handle, .2)
        assert json.loads(marker.read_text())["id"] == "original"
        with pytest.raises(ValueError, match="duplicate"):
            client.send({"type": "prompt", "message": "bounded"}, "original")
    finally:
        client.close()


def test_local_inference_proxy_settles_and_never_replaces_unknown_call(project):
    import http.server
    import threading
    import urllib.request
    import urllib.error
    from vibeedit.worker import FundingProxy
    received = []
    mode = {"partial": False}
    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append(body)
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            event = {"id": "gen-original-"+str(len(received)), "choices": []}
            if not mode['partial']:
                event['usage'] = {"cost": 0.00001, "prompt_tokens": 5, "completion_tokens": 2}
            self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode())
            if not mode['partial']:
                self.wfile.write(b'data: [DONE]\n\n')
    provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    thread = threading.Thread(target=provider.serve_forever, daemon=True)
    thread.start()
    store = Store(project)
    spec = task(maxRetailMicrousd=1000)
    store.create('worker', 'proxy', spec)
    fence = store.claim('proxy', 'owner')
    profile = {"model": "fixture-model", "providerRoute": "fixture", "contextWindow": 100, "inputUsdPerToken": "0.000001", "outputUsdPerToken": "0.0000001", "expiresAtUnix": time.time()+60}
    proxy = FundingProxy(project, 'proxy', spec, profile, 'test-key-only', 'owner', fence, upstream=f'http://127.0.0.1:{provider.server_port}/v1')
    def request():
        return urllib.request.Request(f'http://127.0.0.1:{proxy.server.server_port}/v1/chat/completions', data=json.dumps({"model": "fixture-model", "stream": True, "max_tokens": 999999, "provider": {"only": ["unapproved"]}}).encode(), headers={"Authorization": 'Bearer '+proxy.token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request(), timeout=5) as response:
            assert b'[DONE]' in response.read()
        with proxy.lock:
            first = store.operations('proxy')[0]
        assert first['state'] == 'settled' and first['settled_microusd'] == 10
        assert first['receipt']['nativeGenerationId'] == 'gen-original-1'
        assert received[0]['max_tokens'] == spec['maxOutputTokens']
        assert received[0]['provider']['only'] == ['fixture']
        mode['partial'] = True
        with urllib.request.urlopen(request(), timeout=5) as response:
            response.read()
        with proxy.lock:
            unknown = store.operations('proxy')[1]
        assert unknown['state'] == 'unknown' and unknown['settled_microusd'] is None
        assert unknown['receipt']['nativeGenerationId'] == 'gen-original-2'
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request(), timeout=5)
        assert error.value.code == 409
        assert len(received) == 2
        assert len(store.operations('proxy')) == 2
    finally:
        proxy.close()
        provider.shutdown()
        provider.server_close()
        store.close()


def test_paused_parent_blocks_new_child_mutations_and_calls(project):
    from vibeedit.worker import require_parent_admission
    store = Store(project)
    store.create('goal', 'parent', {})
    spec = task(parentGoalId='parent')
    store.create('worker', 'child', spec)
    fence = store.claim('child', 'owner')
    with pytest.raises(ValueError, match='not durably admitted'):
        require_parent_admission(store, 'child', spec)
    store.intent('parent', 'parent:child', 'child_allowance', {'workerId': 'child'}, reserve=spec['maxRetailMicrousd'], cap=spec['maxRetailMicrousd'])
    execute_tool(project, 'child', 'owner', fence, 'before', 'artifact_write', {'name': 'before.json', 'value': {'step': 1}})
    store.update('parent', 'paused', expected_revision=0)
    with pytest.raises(ValueError, match='parent goal stopped'):
        execute_tool(project, 'child', 'owner', fence, 'after', 'artifact_write', {'name': 'after.json', 'value': {'step': 2}})
    assert not (project/'workers/child/artifacts/after.json').exists()
    store.close()


def test_image_receipts_do_not_duplicate_private_image_bytes_in_state(project):
    import base64
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jTFkAAAAASUVORK5CYII=')
    (project/'frame.png').write_bytes(png)
    spec = task(tools=['project_image'], references=['frame.png'], referenceDigests={'frame.png': hashlib.sha256(png).hexdigest()})
    store = Store(project)
    store.create('worker', 'image', spec)
    fence = store.claim('image', 'owner')
    first = execute_tool(project, 'image', 'owner', fence, 'frame', 'project_image', {'path': 'frame.png'})
    assert base64.b64decode(first['imageData']) == png
    assert execute_tool(project, 'image', 'owner', fence, 'frame', 'project_image', {'path': 'frame.png'}) == first
    assert 'imageData' not in store.operations('image')[0]['receipt']
    store.close()


def test_managed_mode_cannot_fall_back_to_internal_or_provider_keys():
    from vibeedit.worker import _funding
    with pytest.raises(ValueError, match='managed inference unavailable'):
        _funding(task(funding='managed'))


def test_bundle_recovery_keeps_native_operations_holds_and_pauses(project, tmp_path):
    from vibeedit.goals import export_recovery, import_recovery
    store = Store(project)
    store.create('worker', 'restored-worker', task())
    fence = store.claim('restored-worker', 'old-supervisor')
    store.intent('restored-worker', 'original-send', 'inference', {'requestSha256': 'a'*64}, reserve=40000, cap=50000, owner='old-supervisor', fence=fence)
    store.settle('original-send', 'unknown', {'nativeGenerationId': 'generation-original'})
    store.event('restored-worker', 'pi', {'message': 'Pi chat must not be bundled'})
    store.event('restored-worker', 'checkpoint', {'summary': 'composition exists'})
    store.close()
    snapshot = export_recovery(project)
    assert 'Pi chat must not be bundled' not in canonical(snapshot)
    assert 'old-supervisor' not in canonical(snapshot)
    restored = tmp_path / 'restored'; restored.mkdir()
    (restored/'project.vibeedit.json').write_text((project/'project.vibeedit.json').read_text())
    result = import_recovery(restored, snapshot)
    assert result['resumeRequired']
    state = Store(restored)
    row = state.get('restored-worker')
    assert row['status'] == 'paused' and row['owner'] is None and row['fence'] > fence
    operation = state.operations('restored-worker')[0]
    assert operation['id'] == 'original-send' and operation['reserved_microusd'] == 40000
    assert operation['state'] == 'unknown' and operation['receipt']['nativeGenerationId'] == 'generation-original'
    assert state.claim('restored-worker', 'unexpected') is None
    state.close()
    with pytest.raises(ValueError, match='empty project'):
        import_recovery(restored, snapshot)


def test_bundle_recovery_refuses_credentials_and_forged_schema(project, tmp_path):
    from vibeedit.goals import export_recovery, import_recovery
    store = Store(project)
    store.create('worker', 'secret', task(apiKey='never-export'))
    store.close()
    with pytest.raises(ValueError, match='credential objects'):
        export_recovery(project)
    with pytest.raises(ValueError, match='digest mismatch'):
        import_recovery(project, {'schemaVersion': 'vibeedit.companion.v1.snapshot.1', 'tables': {}, 'sha256': '0'*64})


def test_project_concurrency_and_no_progress_are_durable(project):
    from vibeedit.worker import require_progress_budget
    store = Store(project)
    for identity in ['one', 'two', 'three']:
        store.create('worker', identity, task(maxNoProgressCalls=2))
    assert store.claim('one', 'owner-one')
    assert store.claim('two', 'owner-two')
    assert store.claim('three', 'owner-three') is None
    assert store.get('three')['status'] == 'blocked'
    for index in range(2):
        store.intent('one', 'inference-' + str(index), 'inference', {})
        store.settle('inference-' + str(index), 'settled', {'cost': 0}, 0)
    with pytest.raises(ValueError, match='no-progress'):
        require_progress_budget(store, 'one', task(maxNoProgressCalls=2))
    store.intent('one', 'read', 'tool', {'name': 'project_read'})
    store.settle('read', 'settled', {'ok': True}, 0)
    with pytest.raises(ValueError, match='no-progress'):
        require_progress_budget(store, 'one', task(maxNoProgressCalls=2))
    store.intent('one', 'evidence', 'tool', {'name': 'artifact_write'})
    store.settle('evidence', 'settled', {'path': 'artifact.json', 'sha256': 'a'*64}, 0)
    require_progress_budget(store, 'one', task(maxNoProgressCalls=2))
    for index in range(2,4):
        store.intent('one', 'inference-' + str(index), 'inference', {})
        store.settle('inference-' + str(index), 'settled', {'cost': 0}, 0)
    store.intent('one', 'same-evidence', 'tool', {'name': 'artifact_write'})
    store.settle('same-evidence', 'settled', {'path': 'other-name.json', 'sha256': 'a'*64}, 0)
    with pytest.raises(ValueError, match='no-progress'):
        require_progress_budget(store, 'one', task(maxNoProgressCalls=2))
    store.close()


def test_artifact_recovery_fences_unknown_rpc_without_provider_replay(project):
    from vibeedit.worker import recover_artifacts
    store = Store(project)
    store.create('worker', 'recovery', task())
    fence = store.claim('recovery', 'old-owner')
    store.intent('recovery', 'original-prompt', 'rpc_prompt', {'promptSha256': 'a'*64})
    execute_tool(project, 'recovery', 'old-owner', fence, 'original-submit', 'submit_result', {'value': {'answer': 42}})
    store.db.execute("UPDATE records SET lease_until=0 WHERE id='recovery'")
    recovered = recover_artifacts(store, 'recovery')
    assert recovered['status'] == 'complete' and recovered['fence'] > fence
    assert recovered['result']['result'] == {'answer': 42}
    assert len(store.operations('recovery')) == 2
    assert store.operations('recovery')[0]['id'] == 'original-prompt'
    assert store.operations('recovery')[0]['receipt']['transport'] == 'original RPC disposition unknown'
    assert recover_artifacts(store, 'recovery')['status'] == 'complete'
    store.close()


def test_artifact_recovery_cannot_release_unknown_provider_hold(project):
    from vibeedit.worker import recover_artifacts
    store = Store(project)
    store.create('worker', 'held', task())
    store.intent('held', 'provider-send', 'inference', {'requestSha256': 'b'*64}, reserve=10, cap=10)
    store.settle('provider-send', 'unknown', {'nativeGenerationId': 'original'})
    with pytest.raises(ValueError, match='provider/tool acknowledgement remains unknown'):
        recover_artifacts(store, 'held')
    assert store.operations('held')[0]['reserved_microusd'] == 10
    store.close()


def test_explicit_goal_resume_adopts_committed_child_after_rpc_crash(project):
    from vibeedit.goals import recover_goal_children
    store = Store(project)
    store.create('goal', 'parent-recover', {'maxRetailMicrousd':1000000})
    spec = task(parentGoalId='parent-recover')
    store.create('worker', 'child-recover', spec)
    store.intent('parent-recover', 'allowance', 'child_allowance', {'workerId':'child-recover'}, reserve=spec['maxRetailMicrousd'], cap=1000000)
    fence = store.claim('child-recover', 'dead-owner')
    store.intent('child-recover', 'crashed-rpc', 'rpc_prompt', {'promptSha256':'b'*64})
    execute_tool(project, 'child-recover', 'dead-owner', fence, 'committed-submission', 'submit_result', {'value':{'answer':42}})
    store.db.execute("UPDATE records SET lease_until=0 WHERE id='child-recover'")
    recover_goal_children(store, 'parent-recover')
    assert store.get('child-recover')['status']=='complete'
    assert len(store.operations('child-recover'))==2
    assert store.operations('child-recover')[0]['id']=='crashed-rpc'
    store.close()


def test_cancellation_admission_order_preserves_exact_existing_operations(project):
    store = Store(project);store.create('worker','ordered',task())
    assert store.intent('ordered','before','inference',{},reserve=1,cap=10)
    store.control('ordered','cancel',{},'cancel-original')
    assert store.intent('ordered','before','inference',{},reserve=1,cap=10) is False
    with pytest.raises(ValueError,match='cancellation/stop'):
        store.intent('ordered','after','inference',{},reserve=1,cap=10)
    assert len(store.operations('ordered'))==1
    store.close()


def test_later_goal_step_pins_earlier_verified_artifact_and_rejects_mutation(project):
    from vibeedit.goals import bind_step_references, step_worker_id
    path='workers/context-step-1/artifacts/lesson.json'
    first=task(artifacts=[{'path':path,'kind':'json'}])
    second=task(derivedReferences=[{'step':0,'path':path}])
    spec={'objective':'Create then revise from verified evidence','acceptance':['editable production'],'steps':[first,second],'maxRetailMicrousd':400000,'deadlineUnix':time.time()+60,'completionArtifacts':[{'path':'composition.json','kind':'composition'},{'path':'render.mp4','kind':'render'},{'path':'review.json','kind':'review'}]}
    validate_goal(spec)
    store=Store(project);store.create('goal','context',spec)
    store.create('worker','context-step-1',{**first,'parentGoalId':'context'})
    store.intent('context','context:child:1','child_allowance',{'workerId':'context-step-1'},reserve=200000,cap=400000)
    fence=store.claim('context-step-1','owner')
    receipt=execute_tool(project,'context-step-1','owner',fence,'artifact','artifact_write',{'name':'lesson.json','value':{'finding':'retain the readable hold'}})
    store.update('context-step-1','complete',{'artifacts':[{**receipt,'kind':'json'}]},expected_revision=0)
    bound=bind_step_references(store,'context',1)
    assert bound['references']==[path] and bound['referenceDigests'][path]==receipt['sha256']
    assert bind_step_references(store,'context',1)==bound
    assert store.get('context')['spec']['steps'][1]==second
    (project/path).write_text('{"changed":true}')
    with pytest.raises(ValueError,match='changed before child admission'):
        bind_step_references(store,'context',1)
    assert len(step_worker_id('x'*120,99))<=120
    store.close()


def test_explicit_platform_allocation_is_inside_original_retail_ceiling():
    from vibeedit.worker import validate_task
    for value in [-1,True,100001]:
        with pytest.raises(ValueError,match='platformBudgetMicros'):
            validate_task(task(platformBudgetMicros=value))
    validate_task(task(platformBudgetMicros=100000))
    first=task(platformBudgetMicros=100000)
    spec={'objective':'Bound real provider and infrastructure costs','acceptance':['source-bound outputs'],'steps':[first],'maxRetailMicrousd':200000,'deadlineUnix':time.time()+60,'completionArtifacts':[{'path':'composition.json','kind':'composition'},{'path':'render.mp4','kind':'render'},{'path':'review.json','kind':'review'}]}
    with pytest.raises(ValueError,match='child platform'):
        validate_goal(spec)
    validate_goal({**spec,'platformBudgetMicros':100000})
