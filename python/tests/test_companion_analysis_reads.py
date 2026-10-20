"""Actual HTTPS download -> durable scoped read. No paid service/model calls."""
import json
import subprocess
import sys

import pytest

from test_companion_managed import gateway


@pytest.mark.parametrize("financially_settled", [True, False])
def test_original_native_download_is_readable_after_restart_with_immutable_authority(tmp_path, gateway, financially_settled):
    state, env = gateway
    if not financially_settled:
        state['nativeMode'] = 'missing-settlement'
    project = tmp_path / "native result project"
    project.mkdir()
    (project / "project.vibeedit.json").write_text('{"schemaVersion":"vibeedit.project.v1","id":"read-proof"}')
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=10:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(project / 'source.mp4')], check=True)
    script = '''import hashlib,json,sys
from pathlib import Path
from vibeedit.goals import Store
from vibeedit.worker import execute_tool
root=Path(sys.argv[1]);sha=hashlib.sha256((root/'source.mp4').read_bytes()).hexdigest()
permission={'operationId':'original-native','service':'video','source':'source.mp4','sourceSha256':sha,'maxRetailMicrousd':10000,'options':{}}
spec={'task':'Read only the original paid result','funding':'byok','profile':'economical-v1','tools':['analyze','analysis_status','project_read','artifact_write'],'references':['source.mp4'],'referenceDigests':{'source.mp4':sha},'analysisPermissions':[permission],'outputSchema':{'type':'object'},'artifacts':[],'maxModelCalls':3,'maxToolCalls':40,'maxOutputTokens':64,'maxRetailMicrousd':100000,'maxSeconds':30,'delegationLimit':0,'parentGoalId':'goal'}
s=Store(root);s.create('goal','goal',{'maxRetailMicrousd':200000});s.create('worker','reader',spec);s.intent('goal','child','child_allowance',{'workerId':'reader'},reserve=100000,cap=200000);f=s.claim('reader','owner')
args={k:permission[k] for k in ['operationId','service','source','sourceSha256','maxRetailMicrousd']}
admitted=execute_tool(root,'reader','owner',f,'admit','analyze',args)
status=execute_tool(root,'reader','owner',f,'download','analysis_status',{'operationId':'original-native','download':True})
path=status['artifacts'][0]['path'];expected=status['artifacts'][0]['sha256']
financial=next(x for x in s.operations('reader') if x['kind']=='analysis');assert financial['state']==('settled' if sys.argv[2]=='True' else 'waiting') and financial['settled_microusd']==(2 if sys.argv[2]=='True' else None) and financial['reserved_microusd']==10000
s.close()
'''
    subprocess.run([sys.executable, '-c', script, str(project), str(financially_settled)], env=env, check=True, capture_output=True, text=True, timeout=20)
    read = '''import json,sys
from pathlib import Path
from vibeedit.goals import Store
from vibeedit.worker import execute_tool,analysis_status
root=Path(sys.argv[1]);s=Store(root);row=s.get('reader');f=row['fence'];grant=next(x for x in s.operations('reader') if x['kind']=='analysis_artifacts');artifact=grant['receipt']['artifacts'][0];path=artifact['path'];financial=next(x for x in s.operations('reader') if x['kind']=='analysis')
read=execute_tool(root,'reader','owner',f,'read','project_read',{'path':path})
assert read['sha256']==artifact['sha256'] and read['jobId']==grant['receipt']['jobId'] and read['analysisOperationId']=='original-native'
value=json.loads(read['content']);assert value['sourceSha256']==read['sourceSha256'] and value['findings']==['nonbilling protocol fixture only']
assert execute_tool(root,'reader','owner',f,'read','project_read',{'path':path})==read
assert next(x for x in s.operations('reader') if x['kind']=='analysis')==financial
again=analysis_status(s,'reader','original-native',download=True);assert again['artifacts']==grant['receipt']['artifacts']
current=next(x for x in s.operations('reader') if x['kind']=='analysis');assert all(current[key]==financial[key] for key in ['id','intent','state','reserved_microusd','settled_microusd','receipt'])
print(json.dumps({'nativeJobId':read['jobId'],'artifactSha256':read['sha256'],'readAfterRestart':True,'exactRetry':True,'downloadReplay':True}));s.close()
'''
    result = subprocess.run([sys.executable, '-c', read, str(project)], env=env, check=True, capture_output=True, text=True, timeout=20)
    assert json.loads(result.stdout)['readAfterRestart'] is True
    assert state['nativeCreates'] == 1 and state['creates'] == 1 and state['posts'] == 0


def test_scoped_analysis_read_rejects_changed_foreign_unreceipted_and_symlink_bytes(tmp_path, gateway):
    # Reuse the actual transport qualification, then exercise only local original
    # proof checks. A forged result cannot gain authority merely by living nearby.
    state, env = gateway
    project = tmp_path / 'adversarial'
    project.mkdir()
    (project / 'project.vibeedit.json').write_text('{"schemaVersion":"vibeedit.project.v1","id":"adversarial"}')
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=10:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(project / 'source.mp4')], check=True)
    script = '''import hashlib,json,sys
from pathlib import Path
from vibeedit.goals import Store,canonical
from vibeedit.worker import execute_tool
root=Path(sys.argv[1]);sha=hashlib.sha256((root/'source.mp4').read_bytes()).hexdigest();permission={'operationId':'native','service':'video','source':'source.mp4','sourceSha256':sha,'maxRetailMicrousd':10000,'options':{}}
spec={'task':'Read only authenticated original result','funding':'byok','profile':'economical-v1','tools':['analyze','analysis_status','project_read'],'references':['source.mp4'],'referenceDigests':{'source.mp4':sha},'analysisPermissions':[permission],'outputSchema':{'type':'object'},'artifacts':[],'maxModelCalls':3,'maxToolCalls':40,'maxOutputTokens':64,'maxRetailMicrousd':100000,'maxSeconds':30,'delegationLimit':0,'parentGoalId':'goal'}
s=Store(root);s.create('goal','goal',{'maxRetailMicrousd':200000});s.create('worker','reader',spec);s.intent('goal','child','child_allowance',{'workerId':'reader'},reserve=100000,cap=200000);f=s.claim('reader','owner')
execute_tool(root,'reader','owner',f,'admit','analyze',{k:permission[k] for k in ['operationId','service','source','sourceSha256','maxRetailMicrousd']})
result=execute_tool(root,'reader','owner',f,'download','analysis_status',{'operationId':'native','download':True});relative=result['artifacts'][0]['path'];path=root/relative;original=path.read_bytes()
def denied(call,relative=relative):
 try:execute_tool(root,'reader','owner',f,call,'project_read',{'path':relative})
 except (ValueError,UnicodeDecodeError):return
 raise AssertionError('foreign or changed bytes were readable: '+call)
execute_tool(root,'reader','owner',f,'accepted','project_read',{'path':relative})
path.write_bytes(original+b' ');denied('changed');denied('accepted');path.write_bytes(original)
foreign=path.with_name('unreceipted.json');foreign.write_bytes(original);denied('unreceipted',str(foreign.relative_to(root)))
denied('escape','../source.mp4');denied('foreign-worker',relative.replace('workers/reader/','workers/other/'))
path.unlink();path.symlink_to(foreign);denied('symlink');path.unlink();path.write_bytes(original)
grant=next(x for x in s.operations('reader') if x['kind']=='analysis_artifacts');forged=json.loads(canonical(grant['receipt']));forged['jobId']='foreign-job'
s.db.execute('UPDATE operations SET intent=?,receipt=? WHERE id=?',(canonical(forged),canonical(forged),grant['id']));denied('foreign-job')
s.db.execute('UPDATE operations SET intent=?,receipt=? WHERE id=?',(canonical(grant['intent']),canonical(grant['receipt']),grant['id']))
from vibeedit.myriograph import _database
with _database(root) as db:db.execute("UPDATE jobs SET native_id='foreign-native' WHERE operation='native'")
denied('changed-native-journal')
with _database(root) as db:db.execute('UPDATE jobs SET native_id=? WHERE operation=?',(grant['receipt']['jobId'],'native'))
source=root/'source.mp4';raw=source.read_bytes();source.write_bytes(raw+b' ');denied('changed-source');source.write_bytes(raw)
assert execute_tool(root,'reader','owner',f,'accepted','project_read',{'path':relative})['content']==original.decode()
print(json.dumps({'adversarialCases':9,'originalReadStillValid':True}));s.close()
'''
    result = subprocess.run([sys.executable, '-c', script, str(project)], env=env, check=True, capture_output=True, text=True, timeout=25)
    assert json.loads(result.stdout)['adversarialCases'] == 9
    assert state['nativeCreates'] == 1 and state['creates'] == 1 and state['posts'] == 0
