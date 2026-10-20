import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

import pytest

from vibeedit.project import Project, RevisionConflict, create_project, normalize_word, within
from vibeedit.spec import Canvas, Composition, FrameRate


@pytest.fixture
def project(tmp_path):
    composition = Composition(id="fixture", canvas=Canvas(64, 64, FrameRate(30000, 1001)), duration_frames=30)
    spec = tmp_path / "input.json"
    spec.write_text(json.dumps(composition.to_spec()), encoding="utf-8")
    create_project(tmp_path / "space ü", spec)
    project = Project(tmp_path / "space ü")
    media = tmp_path / "generated.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.15", str(media)], check=True)
    project.register_source(media, expected_revision=0)
    return project


def correction(project, **changes):
    source = project.read()["sources"][0]
    return {"operationId": "op-1", "expectedRevision": project.read()["revision"], "author": "human:test", "sourceId": source["id"], "sourceSha256": source["sha256"], "domain": "beats", "action": "set", "targetId": "beatmap", "payload": {"beats": [{"timeSec": 0.1, "strength": 1}]}, **changes}


def test_retry_conflict_restart_and_export(project):
    command = correction(project)
    event = project.correct(command)
    assert project.correct(command) == event
    assert len(Project(project.root).corrections()) == 1
    with pytest.raises(RevisionConflict):
        project.correct({**command, "payload": {"beats": []}})
    with pytest.raises(RevisionConflict):
        project.correct({**command, "operationId": "op-2"})
    assert project.review(command["sourceId"], "beats")["beats"][0]["timeSec"] == 0.1
    project.correct(correction(project, operationId="undo-1", action="undo", payload={"operationId": "op-1"}))
    assert project.review(command["sourceId"], "beats")["beats"] == []


def test_concurrent_revision_is_not_last_writer_wins(project):
    command = correction(project)
    def write(index):
        try:
            return project.correct({**command, "operationId": f"op-{index}"})
        except RevisionConflict:
            return None
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(write, range(2)))
    assert sum(r is not None for r in results) == 1
    assert project.read()["revision"] == 2


def test_timing_offset_is_preserved_without_confidence_upgrade():
    result = normalize_word({"ordinal": 7, "start": 10, "end": 20, "speakerId": None}, {"audioToVideoMillis": -100.125})
    assert result["startUs"] == -90125
    assert result["endUs"] == -80125
    assert result["native"]["speakerId"] is None
    assert result["independentlyVerified"] is False


def test_baseline_refresh_exposes_mapping_conflict(project, tmp_path):
    source = project.read()["sources"][0]
    first = tmp_path / "first.json"
    first.write_text(json.dumps({"schemaVersion": "myriograph.anonymousWords.v1", "sourceSha256": source["sha256"], "words": [{"ordinal": 1, "text": "old"}]}), encoding="utf-8")
    project.import_analysis(source["id"], first, service="speakers", job_id="native-1", schema_version="myriograph.anonymousWords.v1", expected_revision=1)
    baseline_id = project.read()["analysis"][0]["id"]
    project.correct(correction(project, domain="words", baselineId=baseline_id, targetId="1", payload={"text": "new"}))
    assert project.review(source["id"], "words", baseline_id)["machine"]["words"][0]["text"] == "old"
    assert project.review(source["id"], "words", "different")["mappingConflicts"]
    assert not project.review(source["id"], "words", "different")["corrections"]


def test_path_and_source_boundaries(project, tmp_path):
    with pytest.raises(ValueError):
        within(project.root, "../secret")
    (project.root / "escape").symlink_to(tmp_path)
    with pytest.raises(ValueError):
        within(project.root, "escape/input.json")
    with pytest.raises(ValueError):
        project.correct(correction(project, sourceSha256="0" * 64))
    with pytest.raises(ValueError):
        project.correct(correction(project, payload={"beats": [{"timeSec": float("nan") }]}))
    other = tmp_path / "other.wav"
    other.write_bytes(b"changed")
    with pytest.raises(ValueError):
        project.relink(project.read()["sources"][0]["id"], other, expected_revision=1)


def test_beat_correction_reaches_editable_composition_and_audio_render(project, tmp_path):
    from vibeedit.render import render
    source = project.read()["sources"][0]
    path = project.root / "composition.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["sources"] = [{"id":source["id"], "kind":"audio", "uri":source["path"], "identity":{"algorithm":"sha256","value":source["sha256"]}}]
    spec["timeline"]["tracks"] = [{"id":"music", "kind":"audio", "order":0, "items":[{"id":"hit", "kind":"audio", "placement":{"startFrame":0,"durationFrames":4}, "source":{"sourceId":source["id"],"inFrame":0,"durationFrames":4}, "metadata":{"reviewBeat":{"sourceId":source["id"],"index":0}}}]}]
    path.write_text(json.dumps(spec), encoding="utf-8")
    project.correct(correction(project))
    result = project.apply_review(source["id"], "beats", expected_revision=2)
    revised = project.root / result["composition"]
    revised_spec = json.loads(revised.read_text(encoding="utf-8"))
    assert revised_spec["timeline"]["tracks"][0]["items"][0]["placement"]["startFrame"] == 3
    assert json.loads(path.read_text(encoding="utf-8"))["timeline"]["tracks"][0]["items"][0]["placement"]["startFrame"] == 0
    output = tmp_path / "beat-adjusted.mp4"
    render(revised, output)
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(output), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"])
    import array
    samples = array.array("h", raw)
    assert max(abs(v) for v in samples[:400]) < 100
    assert max(abs(v) for v in samples[900:1200]) > 500


def test_native_census_retains_vfr_nonzero_pts_and_decimal_integers(project, tmp_path):
    media = tmp_path / "vfr origin ü.mkv"
    subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","color=s=64x64:r=30000/1001","-vf","setpts=PTS+2/TB+if(gte(N\\,2)\\,1/(30*TB)\\,0)","-frames:v","4","-fps_mode","vfr","-c:v","libx264",str(media)],check=True)
    state = project.register_source(media, expected_revision=project.read()["revision"])
    source = next(s for s in state["sources"] if s["path"].endswith('.mkv'))
    records = [json.loads(line) for line in (project.root/source["clock"]).read_text(encoding="utf-8").splitlines()]
    frames = [record for record in records if record["kind"] == "frame"]
    assert [record["frameOrdinal"] for record in frames] == list(range(4))
    assert all(isinstance(record["pts"], str) for record in frames)
    assert int(frames[0]["pts"]) > 0
    assert len({int(b["pts"])-int(a["pts"]) for a,b in zip(frames,frames[1:])}) > 1
    assert records[-1]["complete"] is True and records[-1]["nativeFrameCounts"]["0"] == 4
    assert normalize_word({"ordinal":0,"start":0,"end":1},{})["videoProjectionAvailable"] is False


def test_undo_rebuilds_bound_beat_layer_from_its_preserved_original(project):
    source = project.read()["sources"][0]
    path = project.root / "composition.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["timeline"]["tracks"] = [{"id":"accent","kind":"audio","order":0,"items":[{"id":"impact","kind":"sound_effect","placement":{"startFrame":7,"durationFrames":2},"soundEffectId":"vibeedit://sfx/impact-procedural","params":{},"metadata":{"reviewBeat":{"sourceId":source["id"],"index":0}}}]}]
    path.write_text(json.dumps(spec), encoding="utf-8")
    event = project.correct(correction(project))
    result = project.apply_review(source["id"],"beats",expected_revision=2)
    assert json.loads((project.root/result["composition"]).read_text(encoding="utf-8"))["timeline"]["tracks"][0]["items"][0]["placement"]["startFrame"] == 3
    project.correct(correction(project,operationId="undo-edit",action="undo",payload={"operationId":event["operationId"]}))
    result = project.apply_review(source["id"],"beats",expected_revision=4)
    assert result["ok"] is True
    assert json.loads((project.root/result["composition"]).read_text(encoding="utf-8"))["timeline"]["tracks"][0]["items"][0]["placement"]["startFrame"] == 7


def test_disabled_audio_layer_does_not_leak_into_render(project, tmp_path):
    from vibeedit.render import render
    spec = json.loads((project.root/"composition.json").read_text(encoding="utf-8"))
    spec["timeline"]["tracks"] = [{"id":"accent","kind":"audio","order":0,"items":[{"id":"impact","kind":"sound_effect","placement":{"startFrame":0,"durationFrames":4,"enabled":False},"soundEffectId":"vibeedit://sfx/impact-procedural","params":{}}]}]
    output = tmp_path/"disabled.mp4"
    render(spec, output)
    actual = json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-of","json",str(output)]))
    assert not any(stream["codec_type"] == "audio" for stream in actual["streams"])


def test_project_database_cannot_alias_another_project(project, tmp_path):
    other = tmp_path/"other-project"
    other.mkdir()
    (other/"project.vibeedit.json").write_text((project.root/"project.vibeedit.json").read_text(encoding="utf-8"), encoding="utf-8")
    (other/".vibeedit").symlink_to(project.root/".vibeedit")
    with pytest.raises(ValueError, match="escapes"):
        Project(other)


def test_word_restore_human_assignment_and_undo_reach_composition(project, tmp_path):
    source = project.read()["sources"][0]
    baseline = tmp_path / "words.json"
    baseline.write_text(json.dumps({"schemaVersion": "myriograph.anonymousWords.v1", "sourceSha256": source["sha256"], "words": [{"ordinal": 0, "text": "Hello", "speakerId": "voice-1"}]}), encoding="utf-8")
    project.import_analysis(source["id"], baseline, service="speakers", job_id="words-original", schema_version="myriograph.anonymousWords.v1", expected_revision=1)
    baseline_id = project.read()["analysis"][0]["id"]
    path = project.root / "composition.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["timeline"]["tracks"] = [{"id": "captions", "kind": "motion", "order": 0, "items": [{"id": "word", "kind": "motion", "placement": {"startFrame": 0, "durationFrames": 3}, "componentId": "vibeedit://text/caption-rail", "props": {"text": "Hello"}, "renderer": "html", "transparent": True, "metadata": {"reviewWord": {"sourceId": source["id"], "baselineId": baseline_id, "targetId": "0"}}}]}]
    path.write_text(json.dumps(spec), encoding="utf-8")
    def edit(identity, action, payload):
        return project.correct(correction(project, domain="words", baselineId=baseline_id, targetId="0", operationId=identity, action=action, payload=payload))
    def apply():
        result = project.apply_review(source["id"], "words", baseline_id=baseline_id, expected_revision=project.read()["revision"])
        assert result["ok"]
        return json.loads((project.root / result["composition"]).read_text(encoding="utf-8"))["timeline"]["tracks"][0]["items"][0]
    with pytest.raises(ValueError, match="both"):
        edit("partial-time", "set", {"startUs": 0})
    with pytest.raises(ValueError, match="human-reviewed"):
        edit("automatic-person", "assign", {"personId": "person-1"})
    edit("delete", "delete", {})
    assert apply()["placement"]["enabled"] is False
    edit("restore", "restore", {"text": "Welcome", "startUs": 0, "endUs": 100000})
    restored = apply()
    assert restored["placement"]["enabled"] is True and restored["props"]["text"] == "Welcome"
    edit("person", "assign", {"personId": "person-1", "confirmation": "human-reviewed"})
    assert apply()["metadata"]["reviewedPersonLink"]["status"] == "human-confirmed"
    edit("undo-person", "undo", {"operationId": "person"})
    assert "reviewedPersonLink" not in apply()["metadata"]
    assert project.review(source["id"], "words", baseline_id)["machine"]["words"][0]["speakerId"] == "voice-1"


def test_reviewed_composition_is_immutable_and_new_edits_are_explicit(project):
    project.correct(correction(project))
    reviewed = project.apply_review(project.read()["sources"][0]["id"], "beats", expected_revision=2)
    path = project.root / reviewed["composition"]
    original = path.read_bytes()
    revised = json.loads(path.read_text(encoding="utf-8"))
    revised["metadata"]["intentionalEdit"] = True
    path.write_text(json.dumps(revised), encoding="utf-8")
    with pytest.raises(RevisionConflict, match="immutable"):
        project.apply_review(project.read()["sources"][0]["id"], "beats", expected_revision=3)
    with pytest.raises(RevisionConflict, match="immutable"):
        project.use_composition("composition.json", expected_revision=3)
    path.write_bytes(original)
    replacement = project.root / "revision.json"
    replacement.write_text(json.dumps(revised), encoding="utf-8")
    adopted = project.use_composition("revision.json", expected_revision=3)
    assert adopted["composition"] == "revision.json"
    assert project.apply_review(project.read()["sources"][0]["id"], "beats", expected_revision=4)["ok"]
