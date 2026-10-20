import json
import pathlib
import wave

import pytest

from vibeedit.acquisition import finish, providers, start, status
from vibeedit.project import Project, RevisionConflict, create_project, file_digest
from vibeedit.spec import Composition, Canvas, FrameRate


@pytest.fixture
def source_project(tmp_path):
    composition = tmp_path/'composition.json'
    Composition('acquisition-proof', Canvas(320,180,FrameRate(30)),30).write(composition)
    root = tmp_path/'project sources ü'
    create_project(root, composition)
    audio = tmp_path/'browser download.wav'
    with wave.open(str(audio),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(48000)
        output.writeframes(b'\x00\x00'*4800)
    return root, audio


def test_source_page_intent_exact_retry_and_missing_browser_keep_handle(source_project):
    root, audio = source_project
    first = start(root,'download-1','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Example.jpg','Example image')
    assert first['state']=='awaiting_browser'
    assert start(root,'download-1','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Example.jpg','Example image')==first
    assert status(root,'download-1')['page']['pageUrl']==first['page']['pageUrl']
    with pytest.raises(ValueError,match='conflicting'):
        start(root,'download-1','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Other.jpg','Other')
    assert not Project(root).read()['sources']


def test_download_receipt_persists_source_clock_and_never_signed_url(source_project):
    root, audio = source_project
    start(root,'download-1','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Example.jpg','Synthetic receipt fixture, not the remote image')
    rights={'license':'generated fixture','attribution':'VibeEdit generated silence','verifiedBy':'automated local test'}
    result=finish(root,'download-1',audio,rights,expected_revision=0,expected_sha256=file_digest(audio),final_url='https://upload.wikimedia.org/path?signature=do-not-store-this-token',harness='codex')
    assert result['state']=='complete'
    source=Project(root).source(result['receipt']['sourceId'])
    assert source['sha256']==file_digest(audio)
    assert (root/source['clock']).is_file()
    receipt=json.loads((root/result['receipt']['receiptPath']).read_text(encoding="utf-8"))
    assert receipt['download']['transport']['finalUrlStored'] is False
    assert receipt['page']['pageUrl']=='https://commons.wikimedia.org/wiki/File:Example.jpg'
    assert 'do-not-store-this-token' not in json.dumps(receipt)
    retry=finish(root,'download-1',audio,rights,expected_revision=0,final_url='https://upload.wikimedia.org/path?signature=do-not-store-this-token',harness='codex')
    assert retry['reused'] is True
    assert len(Project(root).read()['sources'])==1
    assert Project(root).read()['revision']==1


def test_existing_source_can_retain_multiple_independent_page_receipts(source_project):
    root,audio=source_project
    rights={'license':'generated fixture','attribution':'VibeEdit','verifiedBy':'local test'}
    start(root,'first','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Example.jpg','First fixture')
    first=finish(root,'first',audio,rights,expected_revision=0)
    start(root,'second','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Other.wav','Second fixture')
    finish(root,'second',audio,rights,expected_revision=1)
    sources=Project(root).read()['sources']
    assert len(sources)==1
    assert [r['operationId'] for r in sources[0]['acquisition']['receipts']]==['first','second']
    assert Project(root).source(first['receipt']['sourceId'])['sha256']==file_digest(audio)


def test_stale_project_revision_leaves_same_acquisition_resumable(source_project):
    root,audio=source_project
    rights={'license':'generated fixture','attribution':'VibeEdit','verifiedBy':'local test'}
    start(root,'retry','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Example.wav','Fixture')
    Project(root).update(0,lambda value:None)
    with pytest.raises(RevisionConflict):
        finish(root,'retry',audio,rights,expected_revision=0)
    assert status(root,'retry')['state']=='accepting'
    finish(root,'retry',audio,rights,expected_revision=1)
    assert status(root,'retry')['state']=='complete'
    assert len(Project(root).read()['sources'])==1


def test_partial_wrong_digest_and_private_page_urls_are_rejected(source_project,tmp_path):
    root,audio=source_project
    rights={'license':'generated','attribution':'VibeEdit','verifiedBy':'test'}
    with pytest.raises(ValueError,match='stable item page'):
        start(root,'url','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Example.jpg?token=secret','Fixture')
    with pytest.raises(ValueError,match='page host'):
        start(root,'wronghost','wikimedia-commons','https://upload.wikimedia.org/file.mp4','Fixture')
    start(root,'download','wikimedia-commons','https://commons.wikimedia.org/wiki/File:Example.wav','Fixture')
    with pytest.raises(ValueError,match='digest differs'):
        finish(root,'download',audio,rights,expected_revision=0,expected_sha256='0'*64)
    partial=tmp_path/'download.crdownload';partial.write_bytes(b'partial')
    with pytest.raises(ValueError,match='completed'):
        finish(root,'download',partial,rights,expected_revision=0)
    assert status(root,'download')['state']=='awaiting_browser'


def test_provider_catalog_contains_only_page_metadata():
    result=providers('nature animation')
    assert result['providers']
    assert all('{query}' not in p['searchUrl'] for p in result['providers'])
    assert all('downloadUrl' not in p for p in result['providers'])
    assert any(p['id']=='wikimedia-commons' for p in result['providers'])
