"""Offline native transport boundary; actual TS handler coverage is separate."""
import hashlib
import json

import pytest

from vibeedit.myriograph import MyriographError, _canonical, _database, export_recovery, import_recovery, observe, submit


class Faces:
    def __init__(self):
        self.identity = dict(apiUrl='https://customer.example', accountId='account', mode='test', organizationId='org', projectId='project')
        self.calls = []
        self.aliases = {}
        self.job_id = 'a' * 64
        self.unknown = True
        self.changed = None

    def bind_customer(self):
        return

    def check_retail_ceiling(self, service):
        return

    def call(self, path, body=None, *, key=None):
        self.calls.append((path, body, key))
        if path.endswith('/uploads'):
            return {'source':dict(artifactSha256=body['sha256'], byteLength=body['byteLength'], bucket='private', key='original-source', versionId='original-version')}
        if path.endswith('/jobs'):
            intent = {**body, 'maxRetailUsd':str(body['maxRetailUsd'])}
            self.aliases.setdefault(key, dict(schemaVersion='myriograph.faceOperationStatus.v1',originalIdempotencyKey=key,
                requestIntent=intent,requestIntentSha256=hashlib.sha256((_canonical(intent)+'\n').encode()).hexdigest(),
                jobId=self.job_id,state='queued',admissionState='queue_acknowledged',sourceSha256=body['source']['artifactSha256']))
            if self.unknown:
                raise MyriographError('transport_unknown')
            return self.aliases[key]
        if '/operations/' in path:
            if self.changed is not None:
                return self.changed
            value=self.aliases.get(path.rsplit('/',1)[1])
            if value is None:
                raise MyriographError('original_operation_not_found',404)
            return value
        if path.endswith('/resume'):
            raise AssertionError('Alias reconciliation must never resume paid worker execution')
        return dict(jobId=self.job_id,state='extracting')


def unknown(tmp_path,api=None):
    api=api or Faces()
    media=tmp_path/'source.mp4';media.write_bytes(b'controlled-source')
    with pytest.raises(MyriographError,match='transport_unknown'):
        submit(api,tmp_path,'faces',media,{},1.25,'original-face')
    with _database(tmp_path) as db:
        row=dict(db.execute('select * from jobs').fetchone())
    return api,row


def test_face_response_ack_loss_recovery_is_readonly_original_alias_after_portable_restore(tmp_path):
    api,row=unknown(tmp_path)
    with pytest.raises(MyriographError,match='admission_unknown_reconcile_original'):
        observe(api,tmp_path,'original-face')
    restored=tmp_path/'restored';import_recovery(restored,export_recovery(tmp_path))
    before=len(api.calls)
    result=observe(api,restored,'original-face','resume')
    assert result['jobId']==api.job_id and result['reconciledOriginalAdmission']
    assert api.calls[before:]==[('/v1/faces/operations/'+row['idempotency_key'],None,None)]
    with _database(restored) as db:
        after=dict(db.execute('select * from jobs').fetchone())
    assert after['native_id']==api.job_id
    assert all(after[key]==row[key] for key in ['operation','service','intent','request','idempotency_key','identity'])
    assert observe(api,restored,'original-face')['state']=='extracting'
    assert len([call for call in api.calls if call[0].endswith('/jobs')])==1


@pytest.mark.parametrize('changed', ['key','project','source','price','digest','job'])
def test_conflicting_face_alias_never_adopts_or_replaces_original(tmp_path,changed):
    api,row=unknown(tmp_path)
    value=json.loads(json.dumps(next(iter(api.aliases.values()))))
    if changed=='key':value['originalIdempotencyKey']='replacement'
    if changed=='project':value['requestIntent']['source']['key']='foreign-project/source'
    if changed=='source':value['sourceSha256']='b'*64
    if changed=='price':value['requestIntent']['maxRetailUsd']='2.5'
    if changed=='digest':value['requestIntentSha256']='c'*64
    if changed=='job':value['jobId']='replacement-job'
    api.changed=value
    with pytest.raises(MyriographError,match='original_face_operation_binding'):
        observe(api,tmp_path,'original-face','resume')
    with _database(tmp_path) as db:
        after=dict(db.execute('select * from jobs').fetchone())
    assert after==row
    assert len([call for call in api.calls if call[0].endswith('/jobs')])==1


def test_face_queue_unknown_adopts_original_handle_without_queue_or_provider_retry(tmp_path):
    api,row=unknown(tmp_path)
    api.aliases[row['idempotency_key']].update(state='admission_unknown',admissionState='unknown')
    result=observe(api,tmp_path,'original-face','resume')
    assert result['jobId']==api.job_id and result['state']=='admission_unknown'
    assert api.calls[-1]==('/v1/faces/operations/'+row['idempotency_key'],None,None)
    assert len([call for call in api.calls if call[0].endswith('/jobs')])==1


def test_missing_alias_retains_original_send_fence_and_account_scope_required(tmp_path):
    api,row=unknown(tmp_path)
    api.aliases.clear()
    with pytest.raises(MyriographError,match='original_face_operation_not_found'):
        observe(api,tmp_path,'original-face','resume')
    with _database(tmp_path) as db:
        assert dict(db.execute('select * from jobs').fetchone())==row
    for identity in [dict(api.identity,accountId='other-account'),dict(api.identity,projectId='other-project')]:
        api.identity=identity
        count=len(api.calls)
        with pytest.raises(MyriographError,match='original_customer_credentials_required'):
            observe(api,tmp_path,'original-face','resume')
        assert len(api.calls)==count


def test_explicit_resume_continues_only_proven_unsent_original_after_readonly_binding(tmp_path):
    class Continuation(Faces):
        def call(self,path,body=None,*,key=None):
            if path.endswith('/recover') and '/operations/' in path:
                self.calls.append((path,body,key))
                original=self.aliases[path.split('/')[-2]]
                assert body=={'expectedRequestIntentSha256':original['requestIntentSha256']}
                original.update(state='queued',admissionState='queue_acknowledged',resumeOriginalAllowed=False)
                return original
            return super().call(path,body,key=key)
    api,row=unknown(tmp_path,Continuation())
    api.aliases[row['idempotency_key']].update(state='admission_unknown',admissionState='funding_unknown',resumeOriginalAllowed=True)
    result=observe(api,tmp_path,'original-face','resume')
    path='/v1/faces/operations/'+row['idempotency_key']
    assert api.calls[-2][0:2]==(path,None)
    assert api.calls[-1]==(path+'/recover',{'expectedRequestIntentSha256':api.aliases[row['idempotency_key']]['requestIntentSha256']},None)
    assert result['jobId']==api.job_id and result['state']=='queued'
    assert len([call for call in api.calls if call[0].endswith('/jobs')])==1


def test_continuation_ack_loss_keeps_original_send_fence_then_recovers_without_another_post(tmp_path):
    class LostContinuation(Faces):
        def call(self,path,body=None,*,key=None):
            if path.endswith('/recover') and '/operations/' in path:
                self.calls.append((path,body,key))
                self.aliases[path.split('/')[-2]].update(state='queued',admissionState='queue_acknowledged',resumeOriginalAllowed=False)
                raise MyriographError('transport_unknown')
            return super().call(path,body,key=key)
    api,row=unknown(tmp_path,LostContinuation())
    api.aliases[row['idempotency_key']].update(state='admission_unknown',admissionState='funded_unsent',resumeOriginalAllowed=True)
    with pytest.raises(MyriographError,match='transport_unknown'):observe(api,tmp_path,'original-face','resume')
    with _database(tmp_path) as db:assert dict(db.execute('select * from jobs').fetchone())==row
    result=observe(api,tmp_path,'original-face','resume')
    assert result['jobId']==api.job_id and result['state']=='queued'
    assert len([call for call in api.calls if call[0].endswith('/recover')])==1
    assert len([call for call in api.calls if call[0].endswith('/jobs')])==1


def test_unknown_queue_never_continues_even_with_inconsistent_server_advisory(tmp_path):
    api,row=unknown(tmp_path)
    api.aliases[row['idempotency_key']].update(state='admission_unknown',admissionState='queue_unknown',resumeOriginalAllowed=True)
    assert observe(api,tmp_path,'original-face','resume')['jobId']==api.job_id
    assert not any(path.endswith('/recover') for path,_,_ in api.calls)


def test_continuation_cannot_replace_native_handle_after_the_readonly_original_lookup(tmp_path):
    class Replacement(Faces):
        def call(self,path,body=None,*,key=None):
            if path.endswith('/recover') and '/operations/' in path:
                self.calls.append((path,body,key))
                return {**self.aliases[path.split('/')[-2]],'jobId':'b'*64}
            return super().call(path,body,key=key)
    api,row=unknown(tmp_path,Replacement())
    api.aliases[row['idempotency_key']].update(state='admission_unknown',admissionState='funding_unknown',resumeOriginalAllowed=True)
    with pytest.raises(MyriographError,match='original_face_operation_binding'):observe(api,tmp_path,'original-face','resume')
    with _database(tmp_path) as db:assert dict(db.execute('select * from jobs').fetchone())==row
