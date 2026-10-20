"""Real native-package/loopback/source preview integration; no identity accuracy claim."""
import json
import threading
from pathlib import Path

import pytest

from test_face_review import native_fixture
from test_project import project
from test_review import request
from vibeedit.portable import bundle_project, restore_project
from vibeedit.project import Project
from vibeedit.review import ReviewServer


def test_indexed_face_review_portrait_and_portable_persistence(project, tmp_path):
    fixture = tmp_path / 'native-fixture'
    fixture.mkdir()
    source, archive, identity = native_fixture(fixture)
    project.register_source(source, expected_revision=1)
    source_id = project.read()['sources'][-1]['id']
    imported = project.import_faces(source_id, archive, job_id=identity['job_id'], archive_sha256=identity['archive_sha256'], archive_bytes=identity['archive_bytes'], expected_revision=2)
    baseline_id = imported['analysis'][-1]['id']
    server = ReviewServer(project, 'faces', source_id, baseline_id)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        groups = json.loads(request(server, '/api/faces/groups?limit=2')[1])
        assert groups['total'] == 3 and groups['nextOffset'] == 2
        assert 'native' not in groups['groups'][0] and set(groups['library']) == {'libraryId', 'embeddingSpaceSha256'}
        appearances = json.loads(request(server, '/api/faces/appearances?groupId=G00009&limit=1')[1])
        appearance = appearances['appearances'][0]
        assert appearance['frameOrdinal'] == 0 and appearances['total'] == 2
        status, raw, headers = request(server, '/api/faces/preview?appearanceId=' + appearance['id'] + '&portrait=1')
        assert status == 200 and raw.startswith(b'\x89PNG') and headers['Content-Type'] == 'image/png'
        command = {'operationId': 'portrait-user-choice', 'expectedRevision': 3, 'sourceId': source_id, 'baselineId': baseline_id, 'action': {'kind': 'portrait', 'appearanceId': appearance['id']}}
        saved = json.loads(request(server, '/api/faces/corrections', command)[1])
        assert saved['remoteStatus'] == 'local-note' and saved['event']['payload']['previewRequest']['pts'] == appearance['pts']
        assert json.loads(request(server, '/api/faces/corrections', command)[1]) == saved
        assert len(Project(project.root).corrections()) == 1
        assert request(server, '/api/faces/corrections', {**command, 'operationId': 'stale-choice'})[0] == 409
        with pytest.raises(ValueError, match='original saved cloud command'):
            project.correct({'operationId': 'false-ack', 'expectedRevision': 4, 'author': 'human:test', 'sourceId': source_id, 'sourceSha256': identity['source_sha256'], 'baselineId': baseline_id, 'domain': 'faces', 'action': 'acknowledge', 'targetId': 'creator-one', 'payload': {'operationId': 'portrait-user-choice', 'commandSha256': 'c'*64, 'appliedRevisionSha256': 'd'*64}})
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    bundle = tmp_path / 'portable.zip'
    exported = bundle_project(project.root, bundle)
    restored_path = tmp_path / 'restored'
    restore_project(bundle, restored_path, expected_sha256=exported['sha256'])
    restored = Project(restored_path)
    assert restored.corrections() == project.corrections()
    baseline = restored.review(source_id, 'faces', baseline_id)['machine']
    assert (restored_path / baseline['index']).is_file()
    assert (restored_path / baseline['nativeManifest']).is_file()
    assert any(record['kind'] == 'directory' for record in restored.read()['reviews'])
