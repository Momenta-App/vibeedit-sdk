import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vibeedit.model_masks import export_masks, read_review, render_subject_effect
from vibeedit.validation import validate_composition


def _fixture(root):
    Image = pytest.importorskip("PIL.Image")
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg required for real mask-render boundary")
    source = root / "source ü space.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=blue:s=32x24:r=24:d=0.125", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    native = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_frames", "-of", "json", str(source)]))
    pts = [int(f["best_effort_timestamp"]) for f in native["frames"]]
    stream = native["streams"][0]
    n,d = map(int,stream["time_base"].split("/"))
    mask = root / "mask.png"
    alpha = Image.new("L",(32,24));alpha.paste(255,(8,4,24,20));alpha.save(mask)
    index = root / "model-index.json"
    index.write_text(json.dumps({"schemaVersion":"vibeedit.masks.v1","modelPack":"sam31-mlx","definitionSha256":"d"*64,"runtime":{"device":"synthetic-test-no-inference"},"cacheKey":"c"*64,"source":{"sha256":sha,"byteLength":source.stat().st_size,"width":32,"height":24},"clock":{"originPts":int(stream["start_pts"]),"timeBase":{"numerator":n,"denominator":d},"nativeFrameCount":3,"presentationPts":pts},"frames":[{"frameOrdinal":1,"pts":pts[1],"candidates":[{"candidate":0,"file":"mask.png","sha256":hashlib.sha256(mask.read_bytes()).hexdigest()}]}]}), encoding="utf-8")
    review = root / "review.json"
    review.write_text(json.dumps({"schemaVersion":"vibeedit.mask-review.v1","indexSha256":hashlib.sha256(index.read_bytes()).hexdigest(),"sourceSha256":sha,"reviewed":True,"author":"synthetic boundary test; not SAM quality evidence","mode":"sparse","selections":[{"frameOrdinal":1,"candidate":0}]}), encoding="utf-8")
    return source,index,review


def test_review_requires_exact_baseline_source_and_provenance(tmp_path):
    source,index,review = _fixture(tmp_path)
    data=json.loads(review.read_text(encoding="utf-8"));data["indexSha256"]="f"*64;review.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError,match="different or refreshed"):
        read_review(index,review)


def test_lossless_mask_adapter_requires_explicit_sparse_review(tmp_path):
    source,index,review = _fixture(tmp_path)
    output=tmp_path/"export.json"
    result=export_masks(index,review,output,composition_start_frame=24)
    assert result["mask"]["startFrame"]==24
    assert result["mask"]["durationFrames"]==3
    assert result["lossReport"]["sparseInactiveFrames"]==[0,2]
    payload=json.loads(output.read_text(encoding="utf-8"))
    assert payload["frames"][0]["rle"]==[32*24]
    assert sum(payload["frames"][1]["rle"])==32*24
    with pytest.raises(ValueError,match="already exists"):
        export_masks(index,review,output)


def test_subject_effect_has_exact_source_mapping_and_editable_composition(tmp_path):
    source,index,review = _fixture(tmp_path)
    result=render_subject_effect(index,review,source,tmp_path/"effect")
    report=json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert report["encodedFrameCount"]==report["frameCount"]==3
    assert report["activeOutputFrames"]==[1]
    assert [row["sourceFrameOrdinal"]for row in report["frames"]]==[0,1,2]
    assert all(row["preEncodingOutsideMaskDeltaMax"]==0 for row in report["frames"])
    spec=json.loads(Path(result["composition"]).read_text(encoding="utf-8"));validate_composition(spec)
    assert spec["sources"][1]["metadata"]["parentSourceSha256"]==hashlib.sha256(source.read_bytes()).hexdigest()
    # This is a geometric renderer boundary fixture, explicitly not SAM proof.
    assert report["state"]=="needs-review"
    assert "not measured"in report["lossReport"]["postEncodingOutsideMaskLeakage"]


def test_dense_review_rejects_missing_frame_decisions(tmp_path):
    source,index,review = _fixture(tmp_path)
    data=json.loads(review.read_text(encoding="utf-8"));data["mode"]="dense";review.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError,match="every native frame"):
        read_review(index,review)


def test_explicit_frame_map_retains_every_repeated_native_anchor(tmp_path):
    source,index,review = _fixture(tmp_path)
    manifest=json.loads(index.read_text(encoding="utf-8"))
    mapping={"schemaVersion":"vibeedit.source-frame-map.v1","sourceSha256":manifest["source"]["sha256"],"frameRate":{"numerator":24,"denominator":1},"sourceFrameOrdinals":[0,1,1,2]}
    result=render_subject_effect(index,review,source,tmp_path/"mapped",mapping=mapping)
    report=json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert report["activeOutputFrames"]==[1,2]
    assert report["encodedFrameCount"]==4
    assert report["lossReport"]["repeatedSourceFrames"]=={"1":2}
    assert [r["sourcePts"]for r in report["frames"]]==[manifest["clock"]["presentationPts"][i]for i in mapping["sourceFrameOrdinals"]]


def test_explicit_frame_map_rejects_zero_denominator_before_render(tmp_path):
    source,index,review = _fixture(tmp_path)
    mapping={"schemaVersion":"vibeedit.source-frame-map.v1","sourceSha256":json.loads(index.read_text(encoding="utf-8"))["source"]["sha256"],"frameRate":{"numerator":24,"denominator":0},"sourceFrameOrdinals":[0,1,2]}
    with pytest.raises(ValueError,match="positive integer"):
        render_subject_effect(index,review,source,tmp_path/"invalid-map",mapping=mapping)
    assert not (tmp_path/"invalid-map").exists()
