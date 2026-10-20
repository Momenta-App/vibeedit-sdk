"""Actual HTTPS customer boundary and pinned Pi with nonbilling managed fixture.

No deployed Myriograph/OpenRouter call, wallet credit, provider reasoning or launch acceptance.
"""
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import threading
import time

import pytest
from vibeedit.worker import PROFILES, PROVIDERS, PROVIDER_MODELS, _managed_hash, companion_path
from vibeedit.spec import Composition, Canvas, FrameRate


@pytest.fixture
def gateway(tmp_path):
    if not shutil.which('openssl'):
        pytest.skip('OpenSSL required for actual HTTPS protocol qualification')
    cert, key = tmp_path/'cert.pem', tmp_path/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',str(key),'-out',str(cert),'-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1'],check=True,capture_output=True)
    state = {'allowances':{}, 'requests':{}, 'mode':'complete', 'creates':0, 'posts':0, 'closed':0, 'closePosts':0, 'closeHolds':0, 'cancelPosts':0, 'nativeJobs':{}, 'nativeCreates':0, 'sourcePuts':0, 'nativeMode':'complete', 'firstRequestSeen':threading.Event(), 'releaseFirst':threading.Event()}
    composition = Composition('managed-proof',Canvas(320,180,FrameRate(30)),30,created_at='2026-10-20T00:00:00Z').to_spec()
    steps=[('artifact_write',{'name':'composition.json','value':composition}),('render_ffmpeg',{'compositionPath':'workers/managed-proof/artifacts/composition.json','outputName':'proof.mp4'}),('submit_result',{'value':{'answer':42}})]
    profile={'id':'economical-v1','model':PROFILES['economical-v1'],'provider':'OpenRouter','providerRoute':PROVIDERS['economical-v1'],'providerModelName':PROVIDER_MODELS['economical-v1'],'contextWindow':4096,'inputUsdPerToken':'0.00000001','outputUsdPerToken':'0.00000001','checkedAtUnix':int(time.time()),'expiresAtUnix':int(time.time())+1200,'retailMultiplier':2,'pricingVersion':'fixture-no-billing','input':['text','image'],'inferenceQualified':False}
    profile['pricingDigest']=_managed_hash(profile)
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,value,status=200):
            payload=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def do_PUT(self):
            assert not self.headers.get('Authorization')
            payload=self.rfile.read(int(self.headers['Content-Length']))
            assert hashlib.sha256(payload).hexdigest()==self.path.rsplit('/',1)[1]
            state['sourcePuts']+=1
            self.send({'ok':True})
        def do_GET(self):
            if self.path.startswith('/fixture-artifact/'):
                assert not self.headers.get('Authorization')
                job=state['nativeJobs'][self.path.rsplit('/',1)[1]]
                return self.send({'schemaVersion':'myriograph.fixtureResult.v1','sourceSha256':job['sourceSha256'],'findings':['nonbilling protocol fixture only']})
            assert self.headers.get('Authorization')=='Bearer customer-fixture'
            if self.path.startswith(('/v1/video/jobs/','/v1/faces/jobs/','/v1/voices/jobs/')):
                pieces=self.path.split('/');job=state['nativeJobs'][pieces[4]]
                if pieces[-1]=='download':
                    payload=json.dumps({'schemaVersion':'myriograph.fixtureResult.v1','sourceSha256':job['sourceSha256'],'findings':['nonbilling protocol fixture only']}).encode()
                    return self.send({'artifacts':[{'kind':'result','url':'https://127.0.0.1:'+str(server.server_port)+'/fixture-artifact/'+job['jobId'],'sha256':hashlib.sha256(payload).hexdigest(),'byteLength':len(payload)}]})
                if state['nativeMode']=='parent-platform':
                    final=state['allowances'][job['fundingAllowanceId']]['state']=='closed'
                    return self.send({**job,'settlement':{'schemaVersion':'myriograph.customerSettlement.v1','state':'settled' if final else 'held','retailMicros':4 if final else None,'providerCostMicros':1 if final else None,'platformCostMicros':1 if final else None,'parentReservationId':job['fundingAllowanceId'],'terminalExecutionProven':True,'providerChildrenSettled':True,'platformCensusKnown':True,'readyForParentSettlement':True,'childReservationIds':['child-'+job['jobId']]}})
                return self.send({**job, **({'settlement':{'schemaVersion':'myriograph.customerSettlement.v1','state':'settled','retailMicros':2,'providerCostMicros':1,'parentReservationId':job['fundingAllowanceId'],'childReservationId':'child-'+job['jobId'],'usageEventId':'usage-'+job['jobId']}} if state['nativeMode']=='complete' else {})})
            if self.path in ['/v1/video/capabilities','/v1/faces/capabilities','/v1/voices/capabilities']:
                return self.send({'retailCeiling':{'field':'maxRetailUsd','enforced':True,'currency':'USD'},'fundingAllowance':{'field':'fundingAllowanceId','sharedGoal':True}})
            if self.path=='/v1/video/billing': return self.send({'mode':'test','accountId':'account-fixture'})
            if self.path=='/v1/companion/capabilities':
                return self.send({'schemaVersion':'myriograph.companion.v1','enabled':True,'funding':'metered-prepaid','automaticPaidRetries':0,'retailCeiling':{'enforced':True},'profiles':{'economical-v1':profile},'requestPath':'/v1/companion/requests','allowancePath':'/v1/companion/allowances','transport':'durable-request-poll; buffered','videoTransport':False})
            if self.path.startswith('/v1/companion/allowances/'):
                row=state['allowances'][self.path.rsplit('/',1)[1]]
                if row['state']=='closing' and state['closeHolds']==0:
                    row['state']='closed';state['closed']+=1
                return self.send(row)
            if self.path.startswith('/v1/companion/requests/'):
                return self.send(state['requests'][self.path.rsplit('/',1)[1]])
            if self.path=='/test/stats': return self.send({'posts':state['posts'],'creates':state['creates']})
            self.send({'error':{'code':'not_found'}},404)
        def do_POST(self):
            assert self.headers.get('Authorization')=='Bearer customer-fixture'
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            operation=self.headers.get('Idempotency-Key')
            if self.path in ['/v1/video/uploads','/v1/voices/uploads','/v1/faces/uploads']:
                if '/faces/' in self.path: return self.send({'source':{'artifactSha256':body['sha256'],'byteLength':body['byteLength'],'bucket':'fixture','key':body['sha256']}})
                return self.send({'uploadId':'upload-'+body['sha256'],'uploaded':False,'url':'https://127.0.0.1:'+str(server.server_port)+'/fixture-upload/'+body['sha256']})
            if self.path in ['/v1/video/jobs','/v1/voices/jobs','/v1/faces/jobs']:
                assert body['fundingAllowanceId'] in state['allowances']
                state['nativeCreates']+=1
                identity='native-'+str(state['nativeCreates'])
                source=body['source']['artifactSha256'] if 'source' in body else body['uploadId'].removeprefix('upload-')
                state['nativeJobs'][identity]={'jobId':identity,'state':'completed','sourceSha256':source,'fundingAllowanceId':body['fundingAllowanceId']}
                return self.send({'jobId':identity,'state':'accepted'},202)
            if self.path=='/v1/companion/allowances':
                assert operation and operation not in state['allowances']
                state['creates']+=1
                state['allowances'][operation]={'operationId':operation,'allowanceId':operation,'state':'active','retailCapMicros':body['maxRetailMicros'],'platformBudgetMicros':body.get('platformBudgetMicros',0),'fundingStatus':{'schemaVersion':'myriograph.customerAllowance.v1','state':'admitted','reservationId':operation,'retailCeilingMicros':body['maxRetailMicros'],'remainingRetailMicros':body['maxRetailMicros'],'heldChildRetailMicros':0,'settledRetailMicros':0,'unresolvedChildCount':0}}
                return self.send(state['allowances'][operation],201)
            if self.path.startswith('/v1/companion/requests/') and self.path.endswith('/cancel'):
                identity=self.path.split('/')[-2];state['requests'][identity]['cancelRequested']=True;state['cancelPosts']+=1
                return self.send(state['requests'][identity])
            if self.path.endswith('/close'):
                identity=self.path.split('/')[-2];state['closePosts']+=1
                state['allowances'][identity]['state']='closing' if state['closeHolds'] else 'closed'
                if not state['closeHolds']:state['closed']+=1
                return self.send(state['allowances'][identity])
            if self.path=='/v1/companion/requests':
                assert operation not in state['requests'] and body['allowanceId'] in state['allowances']
                assert body['pricingDigest']==profile['pricingDigest'] and 'stream' not in body and 'provider' not in body and 'model' not in body
                state['posts']+=1;index=state['posts']-1
                if state.get('pauseFirst') and index==0:
                    state['firstRequestSeen'].set()
                    assert state['releaseFirst'].wait(10)
                message={'role':'assistant','content':'Completed reviewed fixture.'}
                finish='stop'
                selected_steps=state.get('stepsOverride',steps)
                if index<len(selected_steps) and selected_steps[index] is not None:
                    name,args=selected_steps[index]
                    if name=='artifact_write' and args.get('value',{}).get('sourceSha256')=='__render_sha__':
                        args={**args,'value':{**args['value'],'sourceSha256':hashlib.sha256(Path(state['renderPath']).read_bytes()).hexdigest()}}
                    message['tool_calls']=[{'id':'tool-'+str(index),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}];message['content']=None;finish='tool_calls'
                response={'id':'gen-original-'+str(index),'object':'chat.completion','created':int(time.time()),'model':profile['model'],'choices':[{'index':0,'message':message,'finish_reason':finish}],'usage':{'prompt_tokens':20,'completion_tokens':20,'total_tokens':40,'cost':.000001}}
                row={'schemaVersion':'myriograph.companion.v1','operationId':operation,'allowanceId':body['allowanceId'],'requestSha256':_managed_hash(body),'providerCapMicros':body['maxRetailMicros']//2,'retailCapMicros':body['maxRetailMicros'],'state':'held' if state['mode']=='held' else 'settled','response':response,'settlement':{'schemaVersion':'myriograph.customerSettlement.v1','state':'settled','retailMicros':2,'providerCostMicros':1,'childReservationId':'child-'+str(index),'parentReservationId':body['allowanceId'],'requestIdentity':operation,'usageEventId':'usage-'+str(index)}}
                if state['mode']=='held': row['settlement']={'state':'held','retailMicros':None,'providerCostMicros':None}
                state['requests'][operation]=row
                return self.send({key:value for key,value in row.items() if key not in {'response','settlement'}},202)
            if self.path=='/test/release':
                for row in state['requests'].values():
                    row['state']='settled';row['settlement']={'schemaVersion':'myriograph.customerSettlement.v1','state':'settled','retailMicros':2,'providerCostMicros':1,'childReservationId':'child-original','parentReservationId':row['allowanceId'],'usageEventId':'usage-original'}
                return self.send({'ok':True})
            self.send({'error':{'code':'not_found'}},404)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key);server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    config_home=tmp_path/'config';folder=config_home/'vibeedit';folder.mkdir(parents=True,mode=0o700)
    config=folder/'myriograph.json';config.write_text(json.dumps({'apiUrl':'https://127.0.0.1:'+str(server.server_port),'apiKey':'customer-fixture'}));config.chmod(0o600)
    env={**os.environ,'XDG_CONFIG_HOME':str(config_home),'SSL_CERT_FILE':str(cert),'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
    yield state,env
    server.shutdown();server.server_close();thread.join(timeout=2)


def test_real_pi_managed_https_buffered_tools_and_retail_settlement(tmp_path,gateway):
    if not (companion_path()/'node_modules/@earendil-works/pi-coding-agent/package.json').is_file():
        pytest.skip('Pinned official Pi dependency required')
    state,env=gateway
    project=tmp_path/'managed project ü';project.mkdir();(project/'project.vibeedit.json').write_text('{"schemaVersion":"vibeedit.project.v1","id":"managed-project"}')
    script='''import json,sys
from vibeedit.goals import Store
from vibeedit.worker import run_worker,companion_path
s=Store(sys.argv[1]);s.create('worker','managed-proof',{'task':'Produce the supplied bounded composition, render, then structured result','funding':'managed','profile':'economical-v1','tools':['artifact_write','render_ffmpeg'],'references':[],'outputSchema':{'type':'object','required':['answer'],'properties':{'answer':{'const':42}},'additionalProperties':False},'artifacts':[{'path':'workers/managed-proof/artifacts/composition.json','kind':'composition'},{'path':'workers/managed-proof/artifacts/proof.mp4','kind':'render'}],'maxModelCalls':6,'maxToolCalls':6,'maxOutputTokens':1024,'maxRetailMicrousd':1000000,'maxSeconds':30,'delegationLimit':0});s.close()
run_worker(sys.argv[1],'managed-proof',runtime=companion_path())
s=Store(sys.argv[1]);r=s.get('managed-proof');assert r['status']=='complete',r;ops=[o for o in s.operations('managed-proof') if o['kind']=='inference'];assert len(ops)==4;assert sum(o['settled_microusd'] for o in ops)==8;assert all(o['receipt']['settlement']['providerCostMicros']==1 for o in ops);print(json.dumps({'state':r['status'],'retailMicros':8,'calls':len(ops),'funding':'nonbilling HTTPS fixture'}))
'''
    result=subprocess.run([sys.executable,'-c',script,str(project)],env=env,check=True,text=True,capture_output=True,timeout=45)
    assert json.loads(result.stdout)['retailMicros']==8
    assert state['posts']==4 and state['creates']==1 and state['closed']==1
    assert (project/'workers/managed-proof/artifacts/proof.mp4').stat().st_size>1000


def test_unknown_managed_request_keeps_hold_and_reconciles_original(tmp_path,gateway):
    state,env=gateway;state['mode']='held'
    project=tmp_path/'held project';project.mkdir();(project/'project.vibeedit.json').write_text('{"schemaVersion":"vibeedit.project.v1","id":"held-project"}')
    script='''import json,sys,urllib.request,urllib.error
from vibeedit.goals import Store
from vibeedit.worker import _funding,managed_profile,ManagedFundingProxy,reconcile_inference,cancel_managed_operations
spec={'task':'Review','funding':'managed','profile':'economical-v1','tools':[],'references':[],'outputSchema':{'type':'object'},'artifacts':[],'maxModelCalls':3,'maxToolCalls':3,'maxOutputTokens':64,'maxRetailMicrousd':1000000,'maxSeconds':10,'delegationLimit':0}
s=Store(sys.argv[1]);s.create('worker','held',spec);fence=s.claim('held','owner');customer=_funding(spec);profile=managed_profile(customer,spec);proxy=ManagedFundingProxy(sys.argv[1],'held',spec,profile,customer,'owner',fence)
try:
 body=json.dumps({'model':profile['model'],'stream':True,'messages':[{'role':'user','content':'No billed inference'}]}).encode()
 for attempt in range(2):
  request=urllib.request.Request('http://127.0.0.1:'+str(proxy.server.server_port)+'/v1/chat/completions',data=body,headers={'Authorization':'Bearer '+proxy.token,'Content-Type':'application/json'})
  try: urllib.request.urlopen(request,timeout=5);raise AssertionError('unknown send must refuse')
  except urllib.error.HTTPError as error: assert error.code==409
 ops=[o for o in s.operations('held') if o['kind']=='inference'];assert len(ops)==1 and ops[0]['state']=='unknown' and ops[0]['reserved_microusd']>0
 assert customer.call('/test/stats')['posts']==1
 assert cancel_managed_operations(s,'held')[0]['state']=='held'
 assert cancel_managed_operations(s,'held')[0]['state']=='held'
 assert [o for o in s.operations('held') if o['kind']=='inference'][0]['state']=='unknown'
 customer.call('/test/release',{})
 result=reconcile_inference(s,'held',ops[0]['id']);assert result['settlement']['retailMicros']==2
 assert customer.call('/test/stats')['posts']==1
 print(json.dumps({'originalRemoteId':result['managedOperationId'],'retailMicros':2,'providerCalls':1,'replayed':False}))
finally: proxy.close();s.close()
'''
    result=subprocess.run([sys.executable,'-c',script,str(project)],env=env,check=True,text=True,capture_output=True,timeout=20)
    assert json.loads(result.stdout)['replayed'] is False and state['posts']==1 and state['cancelPosts']==1


def test_one_server_allowance_is_shared_across_goal_workers(tmp_path,gateway):
    state,env=gateway
    project=tmp_path/'goal project';project.mkdir();(project/'project.vibeedit.json').write_text('{"schemaVersion":"vibeedit.project.v1","id":"goal-project"}')
    script='''import sys
from vibeedit.goals import Store
from vibeedit.worker import _funding,ensure_managed_allowance,close_managed_allowance
s=Store(sys.argv[1]);s.create('goal','goal',{'maxRetailMicrousd':1500000,'platformBudgetMicros':250000})
spec={'funding':'managed','parentGoalId':'goal','maxRetailMicrousd':1000000}
s.create('worker','first',spec);s.create('worker','second',spec);customer=_funding(spec)
a=ensure_managed_allowance(s,'first',spec,customer);b=ensure_managed_allowance(s,'second',spec,customer);assert a==b;assert len(s.operations('goal'))==1
r=close_managed_allowance(s,'goal');assert r['state']=='closed';assert close_managed_allowance(s,'goal')['state']=='closed';s.close()
'''
    subprocess.run([sys.executable,'-c',script,str(project)],env=env,check=True,text=True,capture_output=True,timeout=15)
    assert state['creates']==1 and state['closed']==1
    assert next(iter(state['allowances'].values()))['retailCapMicros']==1500000
    assert next(iter(state['allowances'].values()))['platformBudgetMicros']==250000


@pytest.mark.parametrize('complete',[True,False])
def test_three_analysis_tools_share_parent_and_preserve_unpriced_holds(tmp_path,gateway,complete):
    state,env=gateway
    if not complete: state['nativeMode']='missing-settlement'
    project=tmp_path/'analysis project';project.mkdir();(project/'project.vibeedit.json').write_text('{"schemaVersion":"vibeedit.project.v1","id":"analysis-project"}')
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=10:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(project/'source.mp4')],check=True)
    script='''import sys,json,hashlib
from vibeedit.goals import Store
from vibeedit.worker import execute_tool,validate_task,close_managed_allowance
root=sys.argv[1];complete=sys.argv[2]=='True'
from pathlib import Path
sha=hashlib.sha256((Path(root)/'source.mp4').read_bytes()).hexdigest()
permissions=[{'operationId':'original-'+service,'service':service,'source':'source.mp4','sourceSha256':sha,'maxRetailMicrousd':10000,'options':{}} for service in ['video','faces','speakers']]
spec={'task':'Analyze the permitted source only','funding':'byok','profile':'economical-v1','tools':['analyze','analysis_status'],'references':['source.mp4'],'referenceDigests':{'source.mp4':sha},'outputSchema':{'type':'object'},'artifacts':[],'maxModelCalls':3,'maxToolCalls':20,'maxOutputTokens':64,'maxRetailMicrousd':100000,'maxSeconds':30,'delegationLimit':0,'analysisPermissions':permissions,'parentGoalId':'analysis-goal'}
validate_task(spec);s=Store(root);s.create('goal','analysis-goal',{'maxRetailMicrousd':200000});s.create('worker','analysis-worker',spec);s.intent('analysis-goal','child','child_allowance',{'workerId':'analysis-worker'},reserve=100000,cap=200000);f=s.claim('analysis-worker','owner')
for permission in permissions:
 args={key:permission[key] for key in ['operationId','service','source','sourceSha256','maxRetailMicrousd']}
 first=execute_tool(root,'analysis-worker','owner',f,'submit-'+permission['service'],'analyze',args);assert first['jobId']
 again=execute_tool(root,'analysis-worker','owner',f,'same-operation-'+permission['service'],'analyze',args);assert again['jobId']==first['jobId']
 status=execute_tool(root,'analysis-worker','owner',f,'status-'+permission['service'],'analysis_status',{'operationId':permission['operationId'],'download':complete and permission['service']=='video'})
 if complete and permission['service']=='video': assert status['artifacts'][0]['sha256'] and not Path(status['artifacts'][0]['path']).is_absolute()
ops=[o for o in s.operations('analysis-worker') if o['kind']=='analysis'];assert len(ops)==3
assert all(o['state']==('settled' if complete else 'waiting') for o in ops)
assert sum(o['settled_microusd'] or 0 for o in ops)==(6 if complete else 0)
assert sum(o['reserved_microusd'] for o in ops)==30000
assert len([o for o in s.operations('analysis-goal') if o['kind']=='managed_allowance'])==1
if complete: close_managed_allowance(s,'analysis-goal')
print(json.dumps({'nativeOperations':len(ops),'retailMicros':6 if complete else None,'unknownHoldsRetained':not complete,'singleParent':True}));s.close()
'''
    result=subprocess.run([sys.executable,'-c',script,str(project),str(complete)],env=env,check=True,text=True,capture_output=True,timeout=25)
    assert json.loads(result.stdout)['singleParent'] is True
    assert state['nativeCreates']==3 and state['creates']==1 and state['sourcePuts']==2
    assert len({row['fundingAllowanceId'] for row in state['nativeJobs'].values()})==1


def test_detached_two_step_goal_recovers_supervisor_death_with_real_pi(tmp_path,gateway):
    from vibeedit.goals import Store
    if not (companion_path()/'node_modules/@earendil-works/pi-coding-agent/package.json').is_file():
        pytest.skip('Pinned official Pi dependency required')
    state,env=gateway
    project=tmp_path/'crash goal project ü';project.mkdir();(project/'project.vibeedit.json').write_text('{"schemaVersion":"vibeedit.project.v1","id":"crash-goal-project"}')
    composition=Composition('goal-proof',Canvas(320,180,FrameRate(30)),30,created_at='2026-10-20T00:00:00Z').to_spec()
    composition_path='workers/crash-goal-step-1/artifacts/composition.json'
    render_path='workers/crash-goal-step-1/artifacts/proof.mp4'
    review_path='workers/crash-goal-step-2/artifacts/review.json'
    state['stepsOverride']=[('artifact_write',{'name':'composition.json','value':composition}),('render_ffmpeg',{'compositionPath':composition_path,'outputName':'proof.mp4'}),('submit_result',{'value':{'answer':42}}),None,('artifact_write',{'name':'review.json','value':{'sourceSha256':'__render_sha__','findings':['Protocol fixture proves source binding only; not editorial review']}}),('submit_result',{'value':{'answer':42}}),None]
    state['renderPath']=str(project/render_path);state['pauseFirst']=True
    config=tmp_path/'runtime-config';runtime=config/'runtime/pi-1.3.0';runtime.mkdir(parents=True)
    (runtime/'node_modules').symlink_to(companion_path()/'node_modules',target_is_directory=True)
    lock=companion_path()/'package-lock.json';shutil.copyfile(lock,runtime/'package-lock.json')
    (runtime/'ready.json').write_text(json.dumps({'piVersion':'1.3.0','lockSha256':hashlib.sha256(lock.read_bytes()).hexdigest()}))
    env={**env,'VIBEEDIT_CONFIG_HOME':str(config)}
    common={'task':'Make the declared bounded fixture artifacts','funding':'managed','profile':'economical-v1','tools':['artifact_write','render_ffmpeg'],'references':[],'outputSchema':{'type':'object','required':['answer'],'properties':{'answer':{'const':42}},'additionalProperties':False},'maxModelCalls':6,'maxToolCalls':6,'maxOutputTokens':1024,'maxRetailMicrousd':1000000,'maxSeconds':30,'delegationLimit':0}
    spec={'objective':'Create a render then source-linked review across a supervisor crash','acceptance':['editable composition','playable render','source-bound review fixture'],'steps':[{**common,'artifacts':[{'path':composition_path,'kind':'composition'},{'path':render_path,'kind':'render'}]},{**common,'artifacts':[{'path':review_path,'kind':'review'}],'derivedReferences':[{'step':0,'path':composition_path},{'step':0,'path':render_path}]}],'maxRetailMicrousd':2000000,'deadlineUnix':time.time()+90,'completionArtifacts':[{'path':composition_path,'kind':'composition'},{'path':render_path,'kind':'render'},{'path':review_path,'kind':'review'}]}
    store=Store(project);store.create('goal','crash-goal',spec);store.close()
    supervisor=subprocess.Popen([sys.executable,'-m','vibeedit.goals','--project',str(project),'--handle','crash-goal'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        assert state['firstRequestSeen'].wait(10)
        supervisor.kill();supervisor.wait(timeout=5)
        state['releaseFirst'].set()
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            store=Store(project)
            child=store.get('crash-goal-step-1');goal=store.get('crash-goal');store.close()
            if child['status']=='complete' and goal['lease_until']<=time.time(): break
            time.sleep(.1)
        assert child['status']=='complete' and goal['lease_until']<=time.time()
        result=subprocess.run([sys.executable,'-m','vibeedit.cli','goal','resume','--project',str(project),'--id','crash-goal','--expected-revision',str(goal['revision']),'--json'],env=env,check=True,capture_output=True,text=True,timeout=10)
        assert json.loads(result.stdout)['goal']['status']=='active'
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            store=Store(project);goal=store.get('crash-goal');store.close()
            if goal['status']!='active': break
            time.sleep(.1)
        assert goal['status']=='complete',goal
        store=Store(project)
        second=store.get('crash-goal-step-2')
        assert second['spec']['referenceDigests'][render_path]==hashlib.sha256((project/render_path).read_bytes()).hexdigest()
        assert len([op for op in store.operations('crash-goal') if op['kind']=='managed_allowance'])==1
        assert len([op for op in store.operations('crash-goal') if op['kind']=='child_allowance'])==2
        assert len([event for event in store.events('crash-goal') if event['kind']=='checkpoint'])==2
        store.close()
        assert state['posts']==7 and state['creates']==1 and state['closed']==1
    finally:
        state['releaseFirst'].set()
        if supervisor.poll() is None: supervisor.kill();supervisor.wait(timeout=5)


def test_platform_parent_close_reconciles_execution_checkpoints_without_early_release(tmp_path,gateway):
    state,env=gateway
    state['nativeMode']='parent-platform';state['closeHolds']=1
    project=tmp_path/'platform goal';project.mkdir();(project/'project.vibeedit.json').write_text('{"schemaVersion":"vibeedit.project.v1","id":"platform-proof"}')
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=10:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(project/'source.mp4')],check=True)
    script='''import sys,json,hashlib,time
from pathlib import Path
from vibeedit.goals import Store,validate_goal,bind_step_references,supervise
from vibeedit.worker import execute_tool,committed_artifacts,verify_artifacts,execution_checkpoint
from vibeedit.spec import Composition,Canvas,FrameRate
root=Path(sys.argv[1]);sha=hashlib.sha256((root/'source.mp4').read_bytes()).hexdigest()
comp='workers/platform-goal-step-1/artifacts/composition.json';render='workers/platform-goal-step-1/artifacts/render.mp4';review='workers/platform-goal-step-2/artifacts/review.json'
common={'task':'Bounded nonbilling financial checkpoint fixture','funding':'byok','profile':'economical-v1','tools':['artifact_write','render_ffmpeg','analyze','analysis_status'],'references':['source.mp4'],'referenceDigests':{'source.mp4':sha},'outputSchema':{'type':'object'},'artifacts':[],'maxModelCalls':3,'maxToolCalls':10,'maxOutputTokens':64,'maxRetailMicrousd':200000,'maxSeconds':30,'delegationLimit':0,'analysisPermissions':[{'operationId':'platform-native','service':'video','source':'source.mp4','sourceSha256':sha,'maxRetailMicrousd':10000,'options':{}}]}
first={**common,'artifacts':[{'path':comp,'kind':'composition'},{'path':render,'kind':'render'}]}
second={**common,'tools':['artifact_write'],'analysisPermissions':[],'derivedReferences':[{'step':0,'path':comp},{'step':0,'path':render}],'artifacts':[{'path':review,'kind':'review'}]}
spec=validate_goal({'objective':'Keep actual platform holds until original parent close','acceptance':['verified execution distinct from financial completion'],'steps':[first,second],'maxRetailMicrousd':400000,'platformBudgetMicros':10000,'deadlineUnix':time.time()+90,'completionArtifacts':first['artifacts']+second['artifacts']})
s=Store(root);s.create('goal','platform-goal',spec)
task=bind_step_references(s,'platform-goal',0);s.create('worker','platform-goal-step-1',task);s.intent('platform-goal','platform-goal:child:1','child_allowance',{'workerId':'platform-goal-step-1','taskDigest':s.get('platform-goal-step-1')['digest']},reserve=200000,cap=400000);f=s.claim('platform-goal-step-1','owner')
args={key:first['analysisPermissions'][0][key] for key in ['operationId','service','source','sourceSha256','maxRetailMicrousd']}
execute_tool(root,'platform-goal-step-1','owner',f,'native-submit','analyze',args)
status=execute_tool(root,'platform-goal-step-1','owner',f,'native-status','analysis_status',{'operationId':'platform-native'})
assert status['settlement']['state']=='held' and status['settlement']['readyForParentSettlement']
execute_tool(root,'platform-goal-step-1','owner',f,'composition','artifact_write',{'name':'composition.json','value':Composition('proof',Canvas(320,180,FrameRate(30)),30).to_spec()})
execute_tool(root,'platform-goal-step-1','owner',f,'render','render_ffmpeg',{'compositionPath':comp,'outputName':'render.mp4'})
execute_tool(root,'platform-goal-step-1','owner',f,'submit','submit_result',{'value':{'scope':'financial protocol fixture'}})
checkpoint=committed_artifacts(s,'platform-goal-step-1');s.update('platform-goal-step-1','waiting',{'executionCheckpoint':checkpoint});s.db.execute("UPDATE records SET lease_until=0 WHERE id='platform-goal-step-1'")
assert execution_checkpoint(s,'platform-goal-step-1')['financialState'].startswith('held')
task=bind_step_references(s,'platform-goal',1);assert len(task['derivedFrom'])==2
s.create('worker','platform-goal-step-2',task);s.intent('platform-goal','platform-goal:child:2','child_allowance',{'workerId':'platform-goal-step-2','taskDigest':s.get('platform-goal-step-2')['digest']},reserve=200000,cap=400000);f=s.claim('platform-goal-step-2','review-owner')
execute_tool(root,'platform-goal-step-2','review-owner',f,'review','artifact_write',{'name':'review.json','value':{'sourceSha256':hashlib.sha256((root/render).read_bytes()).hexdigest(),'findings':['Protocol fixture only; no editorial signoff']}})
execute_tool(root,'platform-goal-step-2','review-owner',f,'submit','submit_result',{'value':{'scope':'financial protocol fixture'}})
s.update('platform-goal-step-2','complete',committed_artifacts(s,'platform-goal-step-2'));s.db.execute("UPDATE records SET lease_until=0 WHERE id='platform-goal-step-2'");s.close()
supervise(root,'platform-goal')
s=Store(root);assert s.get('platform-goal')['status']=='waiting';assert s.get('platform-goal-step-1')['status']=='waiting'
analysis=[op for op in s.operations('platform-goal-step-1') if op['kind']=='analysis'][0];assert analysis['state']=='waiting' and analysis['settled_microusd'] is None and analysis['reserved_microusd']==10000
child=[op for op in s.operations('platform-goal') if op['kind']=='child_allowance' and op['intent']['workerId']=='platform-goal-step-1'][0];assert child['state']!='settled'
assert len([e for e in s.events('platform-goal') if e['kind']=='execution_checkpoint'])==1
print(json.dumps({'revision':s.get('platform-goal')['revision'],'nativeOriginal':analysis['receipt']['jobId'],'holdMicros':10000}));s.close()
'''
    first=subprocess.run([sys.executable,'-c',script,str(project)],env=env,text=True,capture_output=True,timeout=25)
    assert first.returncode==0,first.stderr
    receipt=json.loads(first.stdout);assert receipt['holdMicros']==10000 and state['closed']==0 and state['closePosts']==1
    state['closeHolds']=0
    subprocess.run([sys.executable,'-m','vibeedit','goal','resume','--project',str(project),'--id','platform-goal','--expected-revision',str(receipt['revision']),'--json'],env=env,check=True,text=True,capture_output=True,timeout=15)
    from vibeedit.goals import Store
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        store=Store(project);goal=store.get('platform-goal');store.close()
        if goal['status'] in {'complete','blocked','failed'}:break
        time.sleep(.1)
    assert goal['status']=='complete',goal
    store=Store(project)
    assert store.get('platform-goal-step-1')['status']=='complete'
    operation=next(op for op in store.operations('platform-goal-step-1') if op['kind']=='analysis')
    assert operation['state']=='settled' and operation['settled_microusd']==4 and operation['receipt']['jobId']==receipt['nativeOriginal']
    assert all(op['state']=='settled' for op in store.operations('platform-goal') if op['kind']=='child_allowance')
    store.close()
    assert state['creates']==1 and state['closed']==1 and state['closePosts']==1 and state['nativeCreates']==1 and state['posts']==0


def test_standalone_byok_native_worker_recovers_original_parent_without_new_inference(tmp_path,gateway):
    state,env=gateway
    state['nativeMode']='parent-platform'
    project=tmp_path/'standalone native';project.mkdir();(project/'project.vibeedit.json').write_text('{"schemaVersion":"vibeedit.project.v1","id":"standalone-native-proof"}')
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=10:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(project/'source.mp4')],check=True)
    script='''import sys,json,hashlib
from pathlib import Path
from vibeedit.goals import Store
from vibeedit.worker import execute_tool,committed_artifacts,recover_artifacts,validate_task
root=Path(sys.argv[1]);sha=hashlib.sha256((root/'source.mp4').read_bytes()).hexdigest()
permission={'operationId':'standalone-native','service':'video','source':'source.mp4','sourceSha256':sha,'maxRetailMicrousd':10000,'options':{}}
spec=validate_task({'task':'Original native financial recovery fixture','funding':'byok','profile':'economical-v1','tools':['analyze','analysis_status','artifact_write'],'references':['source.mp4'],'referenceDigests':{'source.mp4':sha},'outputSchema':{'type':'object'},'artifacts':[{'path':'workers/standalone/artifacts/receipt.json','kind':'json'}],'analysisPermissions':[permission],'platformBudgetMicros':5000,'maxModelCalls':3,'maxToolCalls':10,'maxOutputTokens':64,'maxRetailMicrousd':100000,'maxSeconds':30,'delegationLimit':0})
s=Store(root);s.create('worker','standalone',spec);f=s.claim('standalone','owner')
s.intent('standalone','original-rpc','rpc_prompt',{'promptSha256':'a'*64},owner='owner',fence=f)
args={key:permission[key] for key in ['operationId','service','source','sourceSha256','maxRetailMicrousd']}
original=execute_tool(root,'standalone','owner',f,'analyze','analyze',args)
status=execute_tool(root,'standalone','owner',f,'status','analysis_status',{'operationId':'standalone-native'})
assert status['settlement']['state']=='held'
execute_tool(root,'standalone','owner',f,'artifact','artifact_write',{'name':'receipt.json','value':{'nativeJobId':original['jobId'],'scope':'nonbilling protocol only'}})
execute_tool(root,'standalone','owner',f,'submit','submit_result',{'value':{'nativeJobId':original['jobId']}})
s.update('standalone','waiting',{'executionCheckpoint':committed_artifacts(s,'standalone')});s.db.execute("UPDATE records SET lease_until=0 WHERE id='standalone'")
result=recover_artifacts(s,'standalone');assert result['status']=='complete'
operation=next(op for op in s.operations('standalone') if op['kind']=='analysis');assert operation['receipt']['jobId']==original['jobId'] and operation['settled_microusd']==4
assert next(op for op in s.operations('standalone') if op['kind']=='rpc_prompt')['receipt']['transport']=='original RPC disposition unknown'
assert not any(op['kind']=='inference' for op in s.operations('standalone'))
print(json.dumps({'sameNativeJob':operation['receipt']['jobId'],'retailMicros':4,'modelCalls':0}));s.close()
'''
    result=subprocess.run([sys.executable,'-c',script,str(project)],env=env,text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['modelCalls']==0
    assert state['creates']==1 and state['closed']==1 and state['closePosts']==1 and state['nativeCreates']==1 and state['posts']==0
