import hashlib
import json
import pathlib
import shutil
import subprocess

import pytest

from vibeedit.examples import create_example, prepare_caption_example, render_example
from vibeedit.project import Project, file_digest
from vibeedit.validation import validate_composition
from vibeedit.verify import verify_output


@pytest.mark.parametrize('identity',['dialogue-quote','talking-head-captions'])
def test_caption_template_binds_native_source_and_immutable_word_baseline(tmp_path,identity):
    root=create_example(identity,tmp_path)
    path=prepare_caption_example(root)
    spec=json.loads(path.read_text(encoding="utf-8"))
    validate_composition(spec)
    project=Project(root)
    state=project.read()
    assert len(state['sources'])==len(state['analysis'])==1
    assert (root/'caption-assets'/'Poppins-Black.ttf').is_file()
    assert 'SIL OPEN FONT LICENSE' in (root/'caption-assets'/'OFL-poppins.txt').read_text(encoding='utf-8')
    assert spec['render']['motionBlendMode']==('difference' if identity=='dialogue-quote' else 'normal')
    source=state['sources'][0];baseline=state['analysis'][0]
    baseline_sha=file_digest(root/baseline['path'])
    captions=spec['timeline']['tracks'][1]['items']
    assert all(item['metadata']['reviewWord']['sourceId']==source['id'] and item['metadata']['reviewWord']['baselineId']==baseline['id'] for item in captions)
    command={'operationId':'approved-word-fix','expectedRevision':state['revision'],'author':'local test fixture correction','sourceId':source['id'],'sourceSha256':source['sha256'],'baselineId':baseline['id'],'domain':'words','action':'set','targetId':captions[0]['metadata']['reviewWord']['targetId'],'payload':{'text':'Listen','startUs':100000,'endUs':700000}}
    project.correct(command)
    applied=project.apply_review(source['id'],'words',expected_revision=project.read()['revision'],baseline_id=baseline['id'])
    revised=json.loads((root/applied['composition']).read_text(encoding="utf-8"))
    item=revised['timeline']['tracks'][1]['items'][0]
    assert item['props']['text']=='Listen' and item['placement']['startFrame']==3 and item['placement']['durationFrames']==18
    assert file_digest(root/baseline['path'])==baseline_sha
    assert file_digest(root/source['path'])==source['sha256']
    assert prepare_caption_example(root)==root/applied['composition']
    with pytest.raises(ValueError,match='preserve corrections'):
        prepare_caption_example(root,media=root/source['path'],words=root/'words.json')


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
@pytest.mark.parametrize('identity',['dialogue-quote','talking-head-captions'])
def test_new_caption_template_renders_and_corrected_words_change_render(tmp_path,identity):
    pytest.importorskip('playwright')
    root=create_example(identity,tmp_path)
    initial=render_example(root,root/'initial.mp4')
    assert initial.is_file() and initial.stat().st_size>0
    spec = json.loads((root / Project(root).read()['composition']).read_text(encoding="utf-8"))
    assert verify_output(initial, spec['verification']).passed
    decoded = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(initial), '-vn', '-ac', '1', '-ar', '8000', '-f', 's16le', 'pipe:1'])
    assert len(decoded) > 40000 and any(decoded)
    project=Project(root);state=project.read();source=state['sources'][0];baseline=state['analysis'][0]
    before=file_digest(initial)
    project.correct({'operationId':'caption-revision','expectedRevision':state['revision'],'author':'local fixture test','sourceId':source['id'],'sourceSha256':source['sha256'],'baselineId':baseline['id'],'domain':'words','action':'set','targetId':'word-0','payload':{'text':'A DIFFERENT OPENING'}})
    project.apply_review(source['id'],'words',expected_revision=project.read()['revision'],baseline_id=baseline['id'])
    revised=render_example(root,root/'revised.mp4')
    assert revised.is_file() and file_digest(revised)!=before
    assert Project(root).read()['composition'].startswith('composition-')
    assert file_digest(root/source['path'])==source['sha256']


def test_beat_template_materializes_source_binding_and_keeps_adjustment(tmp_path):
    root=create_example('beat-synchronized',tmp_path)
    first=render_example(root,root/'initial.mp4')
    project=Project(root);state=project.read()
    spec=json.loads((root/state['composition']).read_text(encoding="utf-8"))
    accent=next(item for track in spec['timeline']['tracks'] for item in track['items'] if item['id']=='drop-accent')
    source=project.source(accent['metadata']['reviewBeat']['sourceId'])
    project.correct({'operationId':'beat-revision','expectedRevision':state['revision'],'author':'local fixture test','sourceId':source['id'],'sourceSha256':source['sha256'],'domain':'beats','action':'set','targetId':'beatmap','payload':{'beats':[{'timeSec':index*.5+(0.1 if index==4 else 0),'strength':1} for index in range(8)]}})
    result=project.apply_review(source['id'],'beats',expected_revision=project.read()['revision'])
    revised=json.loads((root/result['composition']).read_text(encoding="utf-8"))
    accent=next(item for track in revised['timeline']['tracks'] for item in track['items'] if item['id']=='drop-accent')
    assert accent['placement']['startFrame']==63
    second=render_example(root,root/'revised.mp4')
    assert second.is_file() and file_digest(second)!=file_digest(first)
    assert project.read()['composition']==result['composition']


def test_caption_frame_collision_fails_before_creating_partial_project(tmp_path):
    root=create_example('dialogue-quote',tmp_path)
    words=json.loads((root/'words.json').read_text(encoding="utf-8"))
    words['words'][1].update(startUs=1000,endUs=500000)
    words['words'][0].update(startUs=1,endUs=400000)
    (root/'words.json').write_text(json.dumps(words), encoding="utf-8")
    with pytest.raises(ValueError,match='collide on an output frame'):
        prepare_caption_example(root)
    assert not (root/'project.vibeedit.json').exists()


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
def test_negative_caption_inverts_picture_and_clears_before_next_word(tmp_path):
    pytest.importorskip('playwright')
    np=pytest.importorskip('numpy')
    root=create_example('dialogue-quote',tmp_path)
    output=render_example(root,root/'negative.mp4')
    source=root/Project(root).read()['sources'][0]['path']
    def frames(path):
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf',"select='eq(n,10)+eq(n,25)'",'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        return np.frombuffer(raw,np.uint8).reshape(2,360,640,3).astype(np.int16)
    clean,captioned=frames(source),frames(output)
    # On a dark source, the inverted glyphs become bright. The whole picture
    # remains present and the word clears after750ms while its baseline stays1s.
    changed=(abs(clean[0]-captioned[0]).mean(axis=2)>80)
    assert changed.sum()>1500
    assert abs((clean[0]+captioned[0])[changed]-255).mean()<10
    assert abs(clean[1]-captioned[1]).mean()<3
    baseline=Project(root).read()['analysis'][0]
    assert json.loads((root/baseline['path']).read_text(encoding="utf-8"))['words'][0]['endUs']==1000000
