"""Native contract/clock/preview fixtures, explicitly no face inference or accuracy proof."""
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from vibeedit.face_review import import_face_package, page_groups, page_appearances, preview_request, render_preview, prepare_library_command


def native_fixture(root, *, mapping=True, changed_pts=False, old_v1=False):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg required for actual source preview boundary")
    source = root / "native source ü.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=blue:s=64x48:r=24000/1001:d=0.1252", "-frames:v", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_frames", "-of", "json", str(source)]))
    stream = probe["streams"][0]
    pts = [int(f["best_effort_timestamp"]) for f in probe["frames"]]
    job, runtime, cache = "2"*64, "3"*64, "4"*64
    person, other = "person_"+"5"*32, "person_"+"6"*32
    assigned = {"personId": person, "status": "single", "evidence": "synthetic contract fixture"}
    unknown = {"personId": None, "status": "uncertain", "evidence": "explicit unresolved fixture"}
    second = {"personId": other, "status": "single", "evidence": "second synthetic fixture"}
    groups = {"G00009": assigned, "G00010": unknown, "G00011": second}
    ref = {"bucket": "fixture", "key": "source", "versionId": "version1", "artifactSha256": sha, "byteLength": source.stat().st_size}
    library = {"libraryId": "creator-one", "revision": {**ref, "key": "revision", "artifactSha256": "8"*64}, "embeddingSpaceSha256": "9"*64}
    spec = {"schemaVersion": "myriograph.faceIdentityJob.v1" if old_v1 else "myriograph.faceIdentityJob.v2", "source": ref, "runtimeSha256": runtime}
    if not old_v1:
        spec.update(library=library, frameRange=None)
    native_source = {"schemaVersion": "myriograph.faceSource.v1" if old_v1 else "myriograph.faceSource.v2", "jobId": job, "specification": spec, "width": 64, "height": 48, "frameCount": 3, "rate": "24000/1001", "timeBase": stream["time_base"], "faceObservationCount": 4}
    if not old_v1:
        native_source.update(sourceFrameRange=[0,3], sourceTotalFrameCount=3, maximumAllowedClockResidualMicros=1000)
    provenance = {"schemaVersion": "myriograph.faceProvenance.v1", "jobId": job, "sourceSha256": sha, "runtimeSha256": runtime, "nativeConsumerProof": {"allNativePtsVerified": True, "allFramesCropsEmbeddingsAndMembershipsVerified": True, "sourceSha256": sha, "frameCount": 3}}
    if not old_v1:
        provenance["library"] = {"input": library, "nativeRangeUnits": [{"cacheId": cache, "frameRange": [0,3], "requestedRange": [0,3]}]}
    people = {"schemaVersion": "myriograph.facePeople.v1", "people": [{"personId": person, "appearanceGroupIds": ["G00009"], "name": None}, {"personId": other, "appearanceGroupIds": ["G00011"], "name": None}], "appearanceGroups": groups, "groupStatusCounts": {"single":2,"uncertain":1}}
    tracks = []
    for tid, group, first, last, count in [("track-1","G00009",0,2,2),("track-2","G00010",1,1,1),("track-3","G00011",2,2,1)]:
        tracks.append({"trackId": tid, "appearanceGroupId": group, "firstFrameOrdinal": first, "lastFrameOrdinal": last, "frameCount": count, **groups[group]})
    from fractions import Fraction
    frames = []
    observations = 0
    for ordinal in range(3):
        faces = []
        for tid, group in ([('track-1','G00009')] if ordinal==0 else [('track-2','G00010')] if ordinal==1 else [('track-1','G00009'),('track-3','G00011')]):
            face = {"faceId": "face-"+str(observations), "trackId": tid, "appearanceGroupId": group, "personId": groups[group]["personId"], "identityStatus": groups[group]["status"], "embeddingRow": observations, "bbox": [.125,.125,.25,.5], "landmarks": [{"x":.2,"y":.2}]*5, "detectorScore": .95, "cropSha256": "a"*64}
            if not old_v1:
                face.update(nativeCacheId=cache, nativeEmbeddingRow=observations)
            faces.append(face); observations += 1
        value = pts[ordinal] + (37 if changed_pts and ordinal==1 else 0)
        frames.append({"frameOrdinal":ordinal,"pts":value,"timestampMicros":round(value*Fraction(stream['time_base'])*1_000_000),"faces":faces})
    members = {"source.json": native_source, "people.json": people, "tracks.json": {"tracks":tracks}, "provenance.json":provenance}
    if mapping and not old_v1:
        appearance_keys = {g:cache+":G0000"+str(i+2) for i,g in enumerate(groups)}
        members["library-mapping.json"] = {"schemaVersion":"myriograph.faceLibraryAppearances.v1","jobId":job,"sourceSha256":sha,"frameRange":[0,3],"appearances":{appearance_keys[g]:r for g,r in groups.items()},"reviewBinding":{"library":library,"sourceMappingSha256":"b"*64,"appearanceGroupKeys":appearance_keys}}
    raw = {name:json.dumps(value).encode() for name,value in members.items()}
    raw["faces.jsonl"] = b"".join((json.dumps(frame)+"\n").encode() for frame in frames)
    manifest = {"schemaVersion":"myriograph.faceIdentityResult.v1" if old_v1 else "myriograph.faceIdentityResult.v2","jobId":job,"sourceSha256":sha,"runtimeSha256":runtime,"files":[{"path":name,"sha256":hashlib.sha256(body).hexdigest(),"byteLength":len(body)}for name,body in raw.items()]}
    archive = root / "faces.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as zipped:
        for name,body in raw.items():zipped.writestr(name,body)
        zipped.writestr("manifest.json",json.dumps(manifest))
    identity = {"job_id":job,"source_sha256":sha,"archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),"archive_bytes":archive.stat().st_size,"source_byte_length":source.stat().st_size}
    return source, archive, identity


def test_native_import_preserves_bytes_clocks_null_groups_and_exact_keys(tmp_path):
    source, archive, identity = native_fixture(tmp_path)
    imported = import_face_package(archive,tmp_path/'review',**identity)
    assert (tmp_path/'review/native.faces.zip').read_bytes()==archive.read_bytes()
    groups = page_groups(imported['indexPath'],limit=2)
    assert groups['total']==3 and groups['nextOffset']==2
    assert groups['groups'][0]['id']=='G00009'
    assert groups['groups'][0]['appearanceKey']=='4'*64+':G00002'
    assert groups['groups'][1]['personId'] is None
    appearances = page_appearances(imported['indexPath'],group_id='G00009',limit=1)
    assert appearances['total']==2 and appearances['nextOffset']==1
    assert appearances['appearances'][0]['frameOrdinal']==0
    assert appearances['appearances'][0]['endUs']>0
    last = page_appearances(imported['indexPath'],start_frame=2)['appearances'][0]
    assert last['endUs'] is None and last['timingQuality']=='range-final-duration-unavailable'
    request = preview_request(imported['indexPath'],last['id'])
    assert request['pts']==last['pts'] and request['bbox']==[.125,.125,.25,.5]
    assert request['groupId']==last['groupId'] and request['personId']==last['personId']
    first=appearances['appearances'][0]
    first_request=preview_request(imported['indexPath'],first['id'])
    assert first_request['groupId']==first['groupId'] and first_request['personId']==first['personId']
    draft = prepare_library_command(imported['indexPath'],operation_id='review1',expected_revision_sha256='c'*64,action={'kind':'assign','groupIds':['G00009'],'personId':None})
    assert draft['state']=='pending' and draft['body']['expectedRevisionSha256']=='c'*64
    assert draft['body']['operation']['appearanceKeys']==['4'*64+':G00002']
    with pytest.raises(ValueError,match='portrait changes are local'):
        prepare_library_command(imported['indexPath'],operation_id='portrait1',expected_revision_sha256='c'*64,action={'kind':'portrait'})


def test_actual_source_frame_and_portrait_preview_use_exact_native_pts(tmp_path):
    source, archive, identity = native_fixture(tmp_path)
    imported = import_face_package(archive,tmp_path/'review',**identity)
    appearance = page_appearances(imported['indexPath'],start_frame=2,limit=1)['appearances'][0]
    request = preview_request(imported['indexPath'],appearance['id'])
    result = render_preview(imported['indexPath'],source,request,tmp_path/'preview.png')
    assert Path(result['output']).read_bytes().startswith(b'\x89PNG')
    portrait = render_preview(imported['indexPath'],source,request,tmp_path/'portrait.png',portrait=True,max_width=128)
    assert portrait['cropNativePixels']=={'x':8,'y':6,'width':16,'height':24}
    with pytest.raises(ValueError,match='differs from saved'):
        render_preview(imported['indexPath'],source,{**request,'pts':request['pts']+1},tmp_path/'wrong.png')
    assert not (tmp_path/'wrong.png').exists()


def test_old_native_packages_remain_readable_without_fabricated_cloud_selectors(tmp_path):
    source, archive, identity = native_fixture(tmp_path,mapping=False)
    imported = import_face_package(archive,tmp_path/'review',**identity)
    assert imported['cloudAppearanceSelectorsAvailable'] is False
    with pytest.raises(ValueError,match='do not synthesize'):
        prepare_library_command(imported['indexPath'],operation_id='split1',expected_revision_sha256='c'*64,action={'kind':'split','groupIds':['G00009'],'fromPersonId':'person_'+'5'*32})
    assert prepare_library_command(imported['indexPath'],operation_id='merge1',expected_revision_sha256='c'*64,action={'kind':'merge','fromPersonId':'person_'+'5'*32,'toPersonId':'person_'+'6'*32})['state']=='pending'


def test_v1_source_local_package_is_not_claimed_as_a_cloud_library(tmp_path):
    source, archive, identity = native_fixture(tmp_path,old_v1=True)
    imported = import_face_package(archive,tmp_path/'review',**identity)
    assert page_groups(imported['indexPath'])['library'] is None
    with pytest.raises(ValueError,match='no persistent cloud library'):
        prepare_library_command(imported['indexPath'],operation_id='merge1',expected_revision_sha256='c'*64,action={'kind':'merge','fromPersonId':'person_'+'5'*32,'toPersonId':'person_'+'6'*32})


def test_native_clock_drift_and_transport_corruption_do_not_publish_import(tmp_path):
    source, archive, identity = native_fixture(tmp_path,changed_pts=True)
    with pytest.raises(ValueError,match='frame/PTS clock'):
        import_face_package(archive,tmp_path/'bad',**identity)
    assert not (tmp_path/'bad').exists()
    with pytest.raises(ValueError,match='SHA256/length mismatch'):
        import_face_package(archive,tmp_path/'bad',**{**identity,'archive_sha256':'f'*64})
    assert not (tmp_path/'bad').exists()


def test_zip_escape_and_modified_index_fail_closed(tmp_path):
    source, archive, identity = native_fixture(tmp_path)
    imported = import_face_package(archive,tmp_path/'review',**identity)
    with Path(imported['indexPath']).open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='index changed'):
        page_groups(imported['indexPath'])
    with zipfile.ZipFile(archive,'a') as zipped:zipped.writestr('../escape',b'unsafe')
    identity.update(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),archive_bytes=archive.stat().st_size)
    with pytest.raises(ValueError,match='Unsafe native face package'):
        import_face_package(archive,tmp_path/'escaped',**identity)
    assert not (tmp_path/'escape').exists()


def test_current_library_head_allows_cross_video_target_and_rejects_altered_revision(tmp_path):
    source, archive, identity = native_fixture(tmp_path)
    imported = import_face_package(archive,tmp_path/'review',**identity)
    value = {'schemaVersion':'myriograph.faceLibraryRevision.v1','organizationId':'fixture-org','projectId':'fixture-project','libraryId':'creator-one','embeddingSpaceSha256':'9'*64,'parentRevisionSha256':'8'*64,'sequence':1,'identityIds':['person_'+'5'*32,'person_'+'6'*32,'person_'+'7'*32],'contributions':[],'aliases':{},'appearanceOverrides':{},'operation':{'kind':'create'}}
    raw = (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
    sha = hashlib.sha256(raw).hexdigest()
    revision = {'value':value,'reference':{'bucket':'fixture','key':'revisions/'+sha+'.json','versionId':'head-v1','artifactSha256':sha,'byteLength':len(raw)}}
    draft = prepare_library_command(imported['indexPath'],operation_id='cross-video',expected_revision_sha256=sha,action={'kind':'merge','fromPersonId':'person_'+'5'*32,'toPersonId':'person_'+'7'*32},library_revision=revision)
    assert draft['body']['operation']['toPersonId']=='person_'+'7'*32
    assert draft['libraryRevisionReference']==revision['reference']
    revision['value']['identityIds'].append('person_'+'f'*32)
    with pytest.raises(ValueError,match='scope/hash/length changed'):
        prepare_library_command(imported['indexPath'],operation_id='tampered',expected_revision_sha256=sha,action={'kind':'merge','fromPersonId':'person_'+'5'*32,'toPersonId':'person_'+'f'*32},library_revision=revision)
