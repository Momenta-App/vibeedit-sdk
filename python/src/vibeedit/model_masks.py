"""Reviewed model candidates -> existing masks and explicit derived visual layers.

This module never runs inference and never creates a substitute segmentation.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter
from fractions import Fraction
from itertools import groupby
from pathlib import Path

from vibeedit.model_runners.segment import clock, frame_anchor
from vibeedit.spec import Canvas, Composition, FrameRate, Mask, Placement, SourceMedia, SourceRange, Track, VideoClip
from vibeedit.validation import validate_composition


def _execute(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:] or "Source/mask media operation failed; inspect the retained partial output before retrying")
    return result.stdout


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_review(index_path, review_path):
    index_path = Path(index_path).resolve(strict=True)
    review_path = Path(review_path).resolve(strict=True)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if index.get("schemaVersion") != "vibeedit.masks.v1":
        raise ValueError("Expected a source-bound VibeEdit SAM candidate index")
    if review.get("schemaVersion") != "vibeedit.mask-review.v1" or review.get("reviewed") is not True or not review.get("author"):
        raise ValueError("Mask export requires a reviewed selection with author/provenance")
    if review.get("indexSha256") != _digest(index_path) or review.get("sourceSha256") != index["source"]["sha256"]:
        raise ValueError("Mask review targets a different or refreshed baseline/source")
    if review.get("mode") not in {"sparse", "dense"}:
        raise ValueError("Review mode must explicitly choose sparse or dense; missing frames are never guessed")
    available = {frame["frameOrdinal"]: frame for frame in index["frames"]}
    if len(available) != len(index["frames"]) or any(type(k) is not int or not 0 <= k < index["clock"]["nativeFrameCount"] for k in available):
        raise ValueError("Mask baseline has repeated or out-of-census native frame ordinals")
    selected = {}
    for choice in review.get("selections", []):
        ordinal = choice["frameOrdinal"]
        if type(ordinal) is not int or ordinal in selected or ordinal not in available:
            raise ValueError("Reviewed source frame is absent, repeated or invalid")
        candidates = {candidate["candidate"]: candidate for candidate in available[ordinal]["candidates"]}
        if type(choice["candidate"]) is not int or choice["candidate"] not in candidates:
            raise ValueError("Reviewed candidate is absent from this source frame")
        candidate = candidates[choice["candidate"]]
        path = (index_path.parent / candidate["file"]).resolve()
        if index_path.parent not in path.parents or not path.is_file() or _digest(path) != candidate["sha256"]:
            raise ValueError("Reviewed candidate file is missing, outside the index root or changed")
        selected[ordinal] = {**candidate, "path": path, "pts": available[ordinal]["pts"]}
    if not selected:
        raise ValueError("Select at least one reviewed real candidate")
    empty = review.get("emptyFrames", [])
    if any(type(x) is not int or x in selected or not 0 <= x < index["clock"]["nativeFrameCount"] for x in empty) or len(set(empty)) != len(empty):
        raise ValueError("Explicit empty frames must be valid distinct non-selected source ordinals")
    if review["mode"] == "dense" and set(selected) | set(empty) != set(range(index["clock"]["nativeFrameCount"])):
        raise ValueError("Dense export requires a selection or explicit empty decision for every native frame")
    return index, review, selected


def export_masks(index_path, review_path, output, *, mask_id="reviewed-subject", composition_start_frame=0):
    from PIL import Image
    index, review, selected = read_review(index_path, review_path)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Mask export already exists; retain the original or choose a new output")
    if type(composition_start_frame) is not int or composition_start_frame < 0:
        raise ValueError("Composition start frame must be a nonnegative integer")
    width, height = index["source"]["width"], index["source"]["height"]
    frames = []
    for ordinal in range(index["clock"]["nativeFrameCount"]):
        if ordinal not in selected:
            frames.append({"frame": ordinal, "rle": [width * height], "sourcePts": index["clock"].get("presentationPts", [None] * index["clock"]["nativeFrameCount"])[ordinal], "decision": "explicit-inactive-sparse-frame" if review["mode"] == "sparse" else "reviewed-empty"})
            continue
        with Image.open(selected[ordinal]["path"]) as image:
            if image.size != (width, height):
                raise ValueError("Reviewed mask dimensions differ from native source")
            values = image.convert("L").tobytes()
        if any(x not in {0, 255} for x in values):
            raise ValueError("Only reviewed hard alpha is supported by this lossless RLE adapter")
        runs = [(bit != 0, sum(1 for _ in group)) for bit, group in groupby(values)]
        counts = ([0] if runs[0][0] else []) + [count for _, count in runs]
        frames.append({"frame": ordinal, "sourcePts": selected[ordinal]["pts"], "rle": counts, "candidateSha256": selected[ordinal]["sha256"]})
    provenance = {"generator": "vibeedit.models.export", "implementationVersion": "vibeedit.models.v1", "model": index["modelPack"], "parameters": {"reviewSha256": _digest(review_path), "indexSha256": _digest(index_path), "mode": review["mode"], "author": review["author"]}, "sourceIdentities": [index["source"]["sha256"]], "cacheKey": index["cacheKey"]}
    payload = {"schemaVersion": "1.0.0", "format": "vibeedit.sam-rle", "model": index["modelPack"], "modelVersion": index["definitionSha256"], "width": width, "height": height, "runtime": index["runtime"], "frames": frames, "source": index["source"], "clock": index["clock"], "review": review, "provenance": provenance}
    _write(output, payload)
    mask = Mask(mask_id, "rle", composition_start_frame, len(frames), output.name, "vibeedit.sam-mask+json", provenance).to_spec()
    report = {"schemaVersion": "vibeedit.mask-export.v1", "ok": True, "mask": mask, "artifactSha256": _digest(output), "lossReport": {"alpha": "lossless binary row-major RLE", "candidateSelection": "unselected candidates retained in original immutable index; not combined", "sparseInactiveFrames": sorted(set(range(len(frames))) - set(selected)) if review["mode"] == "sparse" else [], "timing": "source native ordinals retained. A different composition time base requires an explicit source-frame map; this descriptor does not infer it.", "directRenderer": "Mask metadata alone is not a rendered subject effect. Use models effect or a declared mask-capable renderer."}}
    _write(output.with_suffix(output.suffix + ".adapter.json"), report)
    return report


def _frame_mapping(source, index, mapping, max_frames):
    stream, frames, pts = clock(source, max_frames)
    if len(pts) != index["clock"]["nativeFrameCount"] or int(stream.get("start_pts", pts[0])) != index["clock"]["originPts"] or Fraction(stream["time_base"]) != Fraction(index["clock"]["timeBase"]["numerator"], index["clock"]["timeBase"]["denominator"]):
        raise ValueError("Native source clock differs from the reviewed index")
    if mapping is not None:
        if not isinstance(mapping, dict):
            raise ValueError("Explicit source-frame mapping must be a JSON object")
        if mapping.get("schemaVersion") != "vibeedit.source-frame-map.v1" or mapping.get("sourceSha256") != index["source"]["sha256"]:
            raise ValueError("Explicit frame map must be bound to this exact source")
        value = mapping.get("frameRate", {})
        if not isinstance(value, dict) or any(type(value.get(k)) is not int or value[k] < 1 for k in ["numerator", "denominator"]):
            raise ValueError("Explicit composition frame rate requires positive integer numerator/denominator")
        rate = Fraction(value["numerator"], value["denominator"])
        ordinals = mapping["sourceFrameOrdinals"]
        if not ordinals or len(ordinals) > 120000 or any(type(x) is not int or not 0 <= x < len(pts) for x in ordinals):
            raise ValueError("Explicit mapping contains invalid source ordinals")
        return stream, frames, pts, rate, ordinals
    metadata = json.loads(_execute(["ffprobe", "-v", "error", "-select_streams", "V:0", "-show_entries", "stream=avg_frame_rate", "-of", "json", str(source)]))
    value = metadata["streams"][0].get("avg_frame_rate", "0/0").split("/")
    rate = Fraction(int(value[0]), int(value[1])) if len(value) == 2 and all(v.isdigit() for v in value) and int(value[1]) > 0 else Fraction(0, 1)
    tb = Fraction(stream["time_base"])
    if rate <= 0 or any(abs(Fraction(p - pts[0]) - Fraction(i, 1) / rate / tb) > 1 for i, p in enumerate(pts)):
        raise ValueError("VFR/irregular source requires an explicit source-frame map and rational composition rate; no average-fps timing will be guessed")
    return stream, frames, pts, rate, list(range(len(pts)))


def render_subject_effect(index_path, review_path, source, output_dir, *, mapping=None, color="#ffffff", max_frames=1200):
    from PIL import Image, ImageChops
    index, review, selected = read_review(index_path, review_path)
    source = Path(source).resolve(strict=True)
    if _digest(source) != index["source"]["sha256"] or source.stat().st_size != index["source"]["byteLength"]:
        raise ValueError("Effect source differs from the mask source identity")
    if len(color) != 7 or not color.startswith("#"):
        raise ValueError("Color must be #rrggbb")
    rgb = tuple(int(color[i:i+2], 16) for i in [1, 3, 5])
    stream, native, pts, rate, ordinals = _frame_mapping(source, index, mapping, max_frames)
    for ordinal, mask in selected.items():
        if pts[ordinal] != mask["pts"]:
            raise ValueError("Mask source PTS differs from original source frame")
    if not set(selected) & set(ordinals):
        raise ValueError("Explicit frame map excludes every reviewed active mask; no subject effect would be rendered")
    destination = Path(output_dir).resolve()
    space = stream["width"] * stream["height"] * 4 * (len(pts) + len(ordinals)) + 500_000_000
    ancestor = next(p for p in destination.parents if p.exists())
    if shutil.disk_usage(ancestor).free < space:
        raise RuntimeError(f"Insufficient effect-output disk headroom: conservative frame+encoding estimate {space} bytes. Choose another output directory.")
    if destination.exists():
        raise ValueError("Effect output directory exists; preserve the original run or choose a new path")
    destination.mkdir(parents=True)
    native_dir = destination / "native-frames"
    native_dir.mkdir()
    masks_dir = destination / "reviewed-masks"
    masks_dir.mkdir()
    for ordinal, mask in selected.items():
        target = masks_dir / f"source-{ordinal:08d}.png"
        shutil.copy2(mask["path"], target)
        if _digest(target) != mask["sha256"]:
            raise ValueError("Reviewed mask changed while exporting the effect")
        selected[ordinal] = {**mask, "path": target}
    shutil.copy2(index_path, destination / "model-index.original.json")
    shutil.copy2(review_path, destination / "mask-review.original.json")
    _execute(["ffmpeg", "-nostdin", "-v", "error", "-noautorotate", "-i", str(source), "-map", f"0:{stream['index']}", "-an", "-sn", "-dn", "-fps_mode", "passthrough", str(native_dir / "%08d.png")])
    if len(list(native_dir.glob("*.png"))) != len(pts):
        raise ValueError("Decoded native source census differs from mask index")
    if _digest(source) != index["source"]["sha256"]:
        raise ValueError("Source changed while decoding; no effect index published")
    output_frames = destination / "render-frames"
    output_frames.mkdir()
    rows = []
    for output_ordinal, source_ordinal in enumerate(ordinals):
        with Image.open(native_dir / f"{source_ordinal+1:08d}.png") as raw:
            original = raw.convert("RGB")
        if original.size != (index["source"]["width"], index["source"]["height"]):
            raise ValueError("Native decoded source geometry differs from mask geometry")
        treated = original
        if source_ordinal in selected:
            with Image.open(selected[source_ordinal]["path"]) as raw:
                alpha = raw.convert("L")
            if alpha.size != original.size or any(x not in {0,255} for x in alpha.tobytes()):
                raise ValueError("Subject effects require reviewed native-size binary alpha")
            treated = Image.composite(Image.new("RGB", original.size, rgb), original, alpha)
            outside = Image.composite(ImageChops.difference(treated, original), Image.new("RGB", original.size), ImageChops.invert(alpha))
            if outside.getbbox() is not None:
                raise ValueError("Pre-encoding effect leaked outside reviewed alpha")
            preview = Image.new("RGB", (original.width * 3, original.height))
            preview.paste(original, (0,0)); preview.paste(alpha.convert("RGB"), (original.width,0)); preview.paste(treated, (original.width*2,0))
            preview.save(destination / f"review-output-{output_ordinal:08d}.png")
        treated.save(output_frames / f"{output_ordinal:08d}.png")
        rows.append({"outputFrameOrdinal": output_ordinal, "sourceFrameOrdinal": source_ordinal, "sourcePts": pts[source_ordinal], "sourceAnchor": frame_anchor(source_ordinal, pts, native, Fraction(stream["time_base"]), int(stream.get("start_pts", pts[0]))), "maskSha256": selected[source_ordinal]["sha256"] if source_ordinal in selected else None, "maskFile": f"reviewed-masks/source-{source_ordinal:08d}.png" if source_ordinal in selected else None, "active": source_ordinal in selected, "preEncodingOutsideMaskDeltaMax": 0})
    output = destination / "subject-effect.mp4"
    _execute(["ffmpeg", "-nostdin", "-v", "error", "-framerate", f"{rate.numerator}/{rate.denominator}", "-start_number", "0", "-i", str(output_frames / "%08d.png"), "-frames:v", str(len(ordinals)), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-movflags", "+faststart", str(output)])
    encoded = json.loads(_execute(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height,avg_frame_rate", "-of", "json", str(output)]))["streams"][0]
    if int(encoded["nb_read_frames"]) != len(ordinals) or Fraction(encoded["avg_frame_rate"]) != rate:
        raise ValueError("Encoded frame census/rational clock differs from explicit mapping")
    # The derived video is an editable source/layer. Masks and original media stay
    # referenced separately; the common renderer never has to ignore a maskId.
    composition = Composition("reviewed-subject-effect", Canvas(stream["width"], stream["height"], FrameRate(rate.numerator, rate.denominator)), len(ordinals), output_uri="final.mp4")
    composition.sources.extend([
        SourceMedia("parent-source", "video", Path(os.path.relpath(source, destination)).as_posix(), index["source"]["sha256"], duration_frames=len(pts), metadata={"role":"immutable-parent", "sourceClock":index["clock"]}),
        SourceMedia("subject-effect-derived", "video", output.name, _digest(output), duration_frames=len(ordinals), metadata={"parentSourceSha256": index["source"]["sha256"], "modelIndexSha256": _digest(index_path), "reviewSha256": _digest(review_path), "effect": {"kind":"reviewed-subject-solid-fill", "color":color}, "frameMapping":"effect-report.json", "audio":"silent visual derivative; preserve original audio in parent composition"})])
    composition.timeline.add_track(Track("V1", "video", 0, [VideoClip("subject-effect-layer", Placement(0,len(ordinals)), SourceRange("subject-effect-derived",0,len(ordinals)))]))
    spec = composition.to_spec()
    validate_composition(spec)
    _write(destination / "composition.json", spec)
    counts = Counter(ordinals)
    report = {"schemaVersion":"vibeedit.subject-effect.v1", "ok":True, "state":"needs-review", "renderKind":"subject_effect", "modelPack":index["modelPack"], "modelIndexSha256":_digest(index_path), "reviewSha256":_digest(review_path), "source":index["source"], "sourceClock":index["clock"], "frameRate":{"numerator":rate.numerator,"denominator":rate.denominator}, "frameCount":len(ordinals), "encodedFrameCount":int(encoded["nb_read_frames"]), "activeOutputFrames":[r["outputFrameOrdinal"] for r in rows if r["active"]], "frames":rows, "output":{"file":output.name,"sha256":_digest(output),"byteLength":output.stat().st_size}, "composition":"composition.json", "effect":{"kind":"solid-fill","color":color}, "lossReport":{"nativeToCompositionMapping":"explicit" if mapping else "native-CFR-ordinal-identity; one-tick rational quantization tolerance", "droppedSourceFrames":sorted(set(range(len(pts)))-set(ordinals)),"repeatedSourceFrames":{str(k):v for k,v in counts.items() if v>1},"audio":"not copied; original source audio is retained by parent reference and needs explicit composition timing", "encoding":"H.264 yuv420p is lossy; full-resolution pre-encoding source/mask/effect review strips retained", "postEncodingOutsideMaskLeakage":"not measured; no acceptance upgrade", "sourcePortability":"original source remains referenced by relative path; project export must include/relink it"}, "acceptance":"Mask identity and rendered visibility require visual review; successful encoding is not A09/A14 acceptance"}
    if _digest(source) != index["source"]["sha256"]:
        raise ValueError("Source changed during effects; no report published")
    _write(destination / "effect-report.json",report)
    return {"schemaVersion":"vibeedit.subject-effect.v1","ok":True,"state":"needs-review","output":str(output),"composition":str(destination/"composition.json"),"report":str(destination/"effect-report.json")}
