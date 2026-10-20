import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from vibeedit.myriograph import Myriograph, MyriographError, _database, _origin, observe, read_config, register_commands, submit


def test_portable_recovery_keeps_original_unknown_send_and_drops_signed_observation(tmp_path):
    from vibeedit.myriograph import export_recovery, import_recovery
    project = tmp_path/'original'
    project.mkdir()
    media = project/'source.mp4'
    media.write_bytes(b'synthetic')
    api = NativeAPI(lose_reply=True)
    with pytest.raises(MyriographError, match='transport_unknown'):
        submit(api, project, 'video', media, {}, 1, 'original')
    with _database(project) as db:
        db.execute('update jobs set response=?', ('{"url":"https://example.test/?credential=temporary"}',))
    data = export_recovery(project)
    assert data['jobs'][0]['response'] is None
    restored = tmp_path/'restored'
    import_recovery(restored, data)
    with pytest.raises(MyriographError, match='admission_unknown_reconcile_original'):
        observe(api, restored, 'original')
    assert len(api.accepted) == 1
    api.lose_reply = False
    assert observe(api, restored, 'original', 'resume')['jobId'] == 'job_original'
    assert len(api.accepted) == 1
    assert api.calls[-1][2] == data['jobs'][0]['idempotency_key']
    with pytest.raises(MyriographError, match='destination_not_empty'):
        import_recovery(restored, data)
    data['jobs'][0]['request'] = '{"url":"https://example.test/secret"}'
    with pytest.raises(MyriographError, match='credentials_or_urls'):
        import_recovery(tmp_path/'unsafe', data)


class NativeAPI:
    """Offline native service boundary, retaining accepted idempotency identities."""
    identity = {"apiUrl": "https://customer.example", "keySha256": "customer"}

    def __init__(self, *, ceiling=True, lose_reply=False):
        self.ceiling = ceiling
        self.lose_reply = lose_reply
        self.accepted = {}
        self.calls = []

    def bind_customer(self):
        return

    def check_retail_ceiling(self, service):
        if not self.ceiling:
            raise MyriographError("server_retail_ceiling_unavailable")

    def call(self, path, body=None, *, key=None):
        self.calls.append((path, body, key))
        if path.endswith('/uploads'):
            return {"uploadId": "upload_original", "uploaded": True}
        if path.endswith('/jobs'):
            self.accepted.setdefault(key, {"jobId": "job_original", "status": "queued"})
            if self.lose_reply:
                raise MyriographError("transport_unknown")
            return self.accepted[key]
        return {"jobId": "job_original", "status": "succeeded"}


def test_server_ceiling_required_before_upload_or_paid_send(tmp_path):
    media = tmp_path / 'source.mp4'
    media.write_bytes(b'synthetic')
    api = NativeAPI(ceiling=False)
    with pytest.raises(MyriographError, match='server_retail_ceiling_unavailable'):
        submit(api, tmp_path, 'video', media, {}, 1, 'first')
    assert not api.calls
    with _database(tmp_path) as db:
        assert db.execute('select state from jobs').fetchone()[0] == 'prepared'


def test_shared_goal_allowance_is_controlled_capability_gated_and_frozen_in_original_admission(tmp_path):
    class GoalAPI(NativeAPI):
        shared = False
        def capabilities(self, service):
            return {'fundingAllowance':{'field':'fundingAllowanceId','sharedGoal':self.shared}}
    media=tmp_path/'source.mp4'
    media.write_bytes(b'synthetic')
    api=GoalAPI()
    with pytest.raises(MyriographError,match='shared_goal_allowance_unavailable'):
        submit(api,tmp_path,'video',media,{},1,'goal-analysis',funding_allowance_id='original-goal')
    assert not api.calls
    api.shared=True
    submit(api,tmp_path,'video',media,{},1,'goal-analysis',funding_allowance_id='original-goal')
    body=[call[1] for call in api.calls if call[0].endswith('/jobs')][0]
    assert body['fundingAllowanceId']=='original-goal'
    with pytest.raises(MyriographError,match='operation_conflict'):
        submit(api,tmp_path,'video',media,{},1,'goal-analysis',funding_allowance_id='replacement-goal')
    with pytest.raises(ValueError,match='controlled'):
        submit(api,tmp_path,'video',media,{'fundingAllowanceId':'bypass'},1,'other')


def test_native_handle_exact_retry_source_conflict_and_recovery(tmp_path):
    media = tmp_path / 'source.mp4'
    media.write_bytes(b'synthetic')
    api = NativeAPI()
    result = submit(api, tmp_path, 'speakers', media, {'maxDurationSeconds': 1}, 1, 'first')
    assert result['jobId'] == 'job_original'
    assert submit(api, tmp_path, 'speakers', media, {'maxDurationSeconds': 1}, 1, 'first') == result
    assert len(api.accepted) == 1
    assert observe(api, tmp_path, 'first', 'resume')['jobId'] == 'job_original'
    assert api.calls[-1][0] == '/v1/voices/jobs/job_original/recover'
    with pytest.raises(MyriographError, match='operation_conflict'):
        submit(api, tmp_path, 'speakers', media, {'maxDurationSeconds': 2}, 1, 'first')
    media.write_bytes(b'changed')
    with pytest.raises(MyriographError, match='operation_conflict'):
        submit(api, tmp_path, 'speakers', media, {'maxDurationSeconds': 1}, 1, 'first')


def test_lost_admission_acknowledgement_never_replaced_after_restart(tmp_path):
    media = tmp_path / 'source.mp4'
    media.write_bytes(b'synthetic')
    api = NativeAPI(lose_reply=True)
    with pytest.raises(MyriographError, match='transport_unknown'):
        submit(api, tmp_path, 'video', media, {}, 1, 'first')
    with _database(tmp_path) as db:
        row = db.execute('select * from jobs').fetchone()
        frozen_key, frozen_body = row['idempotency_key'], row['request']
        assert row['state'] == 'admission_unknown'
        assert json.loads(frozen_body)['maxRetailUsd'] == 1
    api.lose_reply = False
    with pytest.raises(MyriographError, match='admission_unknown_reconcile_original'):
        submit(api, tmp_path, 'video', media, {}, 1, 'first')
    assert len(api.accepted) == 1
    assert next(iter(api.accepted)) == frozen_key
    assert len([c for c in api.calls if c[0].endswith('/jobs')]) == 1


def test_credential_permissions_and_private_route_exclusion(tmp_path):
    config = tmp_path/'customer.json'
    config.write_text(json.dumps({'apiUrl':'https://customer.example','apiKey':'private-customer-key'}))
    config.chmod(0o600)
    api = Myriograph(read_config(config))
    assert 'private-customer-key' not in json.dumps(api.identity)
    with pytest.raises(ValueError, match='public Myriograph route'):
        api.call('/internal/v1/faces/jobs')
    with pytest.raises(ValueError):
        _origin('https://user:secret@example.com')
    with pytest.raises(ValueError):
        _origin('https://example.com/path?key=secret')
    config.chmod(0o644)
    if __import__('os').name != 'nt':
        with pytest.raises(ValueError, match='owner-only'):
            read_config(config)


def test_cli_registration_preserves_exact_operation_and_cap(tmp_path):
    parser = argparse.ArgumentParser()
    register_commands(parser.add_subparsers(required=True))
    args = parser.parse_args(['analyze', 'faces', 'source.mp4', '--project', str(tmp_path), '--operation', 'exact-original', '--max-retail-usd', '1.25', '--json'])
    assert args.service == 'faces' and args.operation == 'exact-original' and args.max_retail_usd == 1.25
    assert callable(args.handler)


def test_native_face_zip_binding_member_digest_and_expansion_limit(tmp_path):
    import zipfile
    from vibeedit.myriograph import _verify_face_archive
    source_sha = 'a' * 64
    payload = b'{"nativePts":42}'
    manifest = {'schemaVersion':'myriograph.faceIdentityResult.v2','jobId':'original-job','sourceSha256':source_sha,
                'files':[{'path':'source.json','sha256':hashlib.sha256(payload).hexdigest(),'byteLength':len(payload)}]}
    archive = tmp_path/'faces.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('manifest.json',json.dumps(manifest))
        z.writestr('source.json',payload)
    assert _verify_face_archive(archive,'original-job',source_sha,10000)['jobId'] == 'original-job'
    with pytest.raises(MyriographError,match='face_package_binding'):
        _verify_face_archive(archive,'replacement-job',source_sha,10000)
    with pytest.raises(MyriographError,match='expansion_limit'):
        _verify_face_archive(archive,'original-job',source_sha,1)
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('manifest.json',json.dumps(manifest))
        z.writestr('source.json',b'changed')
    with pytest.raises(MyriographError,match='member_integrity'):
        _verify_face_archive(archive,'original-job',source_sha,10000)


def test_native_face_resume_requires_exact_status_snapshot(tmp_path):
    class Faces(NativeAPI):
        def call(self, path, body=None, *, key=None):
            self.calls.append((path,body,key))
            if path.endswith('/uploads'):
                return {'source':{'artifactSha256':source_sha,'byteLength':9,'versionId':'original-version'}}
            if path.endswith('/jobs'):
                return {'jobId':'face_original','state':'held'}
            if path.endswith('/resume'):
                assert body == {'expectedStatusSha256':'b'*64}
                return {'jobId':'face_original','state':'queued'}
            return {'jobId':'face_original','state':'held','statusRevisionSha256':'b'*64}
    media = tmp_path/'source.mp4'
    media.write_bytes(b'synthetic')
    source_sha = hashlib.sha256(media.read_bytes()).hexdigest()
    api = Faces()
    assert submit(api,tmp_path,'faces',media,{},1,'face-edit')['jobId'] == 'face_original'
    result = observe(api,tmp_path,'face-edit','resume')
    assert result['state'] == 'queued'
    assert api.calls[-1][0].endswith('/face_original/resume')


def test_explicit_resume_reconciles_same_original_admission_key_body(tmp_path):
    media=tmp_path/'source.mp4';media.write_bytes(b'synthetic')
    api=NativeAPI(lose_reply=True)
    with pytest.raises(MyriographError,match='transport_unknown'):
        submit(api,tmp_path,'video',media,{},1,'recover-original')
    before=api.calls[-1]
    api.lose_reply=False
    result=observe(api,tmp_path,'recover-original','resume')
    assert result['jobId']=='job_original' and result['reconciledOriginalAdmission']
    assert api.calls[-1]==before
    assert len(api.accepted)==1


def test_windows_managed_config_requires_user_protection_and_explicit_import(tmp_path, monkeypatch):
    import vibeedit.myriograph as module
    path=tmp_path/'customer.json'
    original=dict(apiUrl='https://customer.example',apiKey='private-customer-key')
    path.write_text(json.dumps(original))
    monkeypatch.setattr(module,'_WINDOWS',True)
    with pytest.raises(ValueError,match='Import the customer config'):
        module.read_config(path)
    assert module.read_config(path,allow_unprotected_import=True)==original
    # Exercise storage/reader policy at the OS boundary; actual Windows DPAPI
    # qualification still requires the clean Windows customer journey.
    def protect(value,*,protect):
        return b'protected-'+value if protect else value.removeprefix(b'protected-')
    monkeypatch.setattr(module,'_windows_credential',protect)
    module._save_private(path,original)
    assert original['apiKey'] not in path.read_text()
    assert module.read_config(path)==original
    monkeypatch.setattr(module,'_WINDOWS',False)
    with pytest.raises(ValueError,match='original Windows user'):
        module.read_config(path)


def test_source_upload_admission_has_stable_tenant_service_and_source_idempotency(tmp_path):
    from vibeedit.myriograph import _upload_source
    class Uploads(NativeAPI):
        def call(self,path,body=None,*,key=None):
            assert path.endswith('/uploads')
            assert key and len(key)==80
            self.calls.append((path,body,key))
            return dict(uploadId='original-upload',uploaded=True)
    api=Uploads()
    media=tmp_path/'video.mp4';media.write_bytes(b'synthetic')
    source=dict(sha256=hashlib.sha256(media.read_bytes()).hexdigest(),byteLength=9,contentType='video/mp4')
    one=_upload_source(api,'video',media,source,funding_allowance_id='original-goal')
    _upload_source(api,'video',media,source,funding_allowance_id='original-goal')
    assert one==dict(uploadId='original-upload')
    assert api.calls[0]==api.calls[1]
    _upload_source(api,'video',media,source,funding_allowance_id='different-goal')
    assert api.calls[-1][2]!=api.calls[0][2]
