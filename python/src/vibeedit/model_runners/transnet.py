#!/usr/bin/env python3
"""Optional local shot detection. Only `setup` downloads; no cloud/API calls."""
import argparse
import bisect
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

COMMIT = "85cef72af9a916bdfd7cc94a670c9cdfbf12d1ed"
MODEL_SHA = "8ac2a52c5719690d512805b6eaf5ce12097c1d8860b3d9de245dcbbc3100f554"
FILES = {
    "upstream.py": ("inference/transnetv2.py", 8045, "f55b3a75727d1502438707ac15e8f6257a736817e713e2113e4b84176500ca65"),
    "LICENSE": ("LICENSE", 1072, "a8d7a056688ccedebe89f18fd60f1a47128df94cb82669cd02459934919cbb6f"),
    "weights/saved_model.pb": ("inference/transnetv2-weights/saved_model.pb", 5933260, MODEL_SHA),
    "weights/variables/variables.data-00000-of-00001": ("inference/transnetv2-weights/variables/variables.data-00000-of-00001", 30516656, "b8c9dc3eb807583e6215cabee9ca61737b3eb1bceff68418b43bf71459669367"),
    "weights/variables/variables.index": ("inference/transnetv2-weights/variables/variables.index", 5526, "8b99e28b4ad11372d9a1ad9703298c2e370df14859da4245fdbe818e92dd403f"),
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")
    os.replace(f.name, path)


def verify_cache(cache):
    for name, (_, size, checksum) in FILES.items():
        path = cache / name
        if not path.is_file() or path.stat().st_size != size or digest(path) != checksum:
            raise ValueError(f"Missing or invalid cached file: {path}. Run setup; remove only this file if corrupt.")


def setup(cache):
    for name, (remote, size, checksum) in FILES.items():
        target = cache / name
        if target.exists():
            if target.stat().st_size != size or digest(target) != checksum:
                raise ValueError(f"Cached file is invalid: {target}. Remove only this file and rerun setup.")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        host = "media.githubusercontent.com/media" if name.startswith("weights/") else "raw.githubusercontent.com"
        url = f"https://{host}/soCzech/TransNetV2/{COMMIT}/{remote}"
        with urllib.request.urlopen(url, timeout=120) as reply:
            data = reply.read(size + 1)
        if len(data) != size or hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError(f"Upstream integrity check failed for {remote}; no file was installed.")
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as f:
            f.write(data)
        os.replace(f.name, target)
    verify_cache(cache)
    return {"state": "ready", "cache": str(cache), "upstreamCommit": COMMIT, "downloadedVideo": False}


def build_index(source, pts, time_base, end_pts, scenes, threshold, estimated_end=False, origin_pts=None):
    if not pts or any(type(p) is not int for p in pts) or any(b <= a for a, b in zip(pts, pts[1:])):
        raise ValueError("Expected native strictly increasing presentation timestamps")
    tb = Fraction(time_base)
    origin_pts = pts[0] if origin_pts is None else origin_pts
    if type(origin_pts) is not int or origin_pts > pts[0]:
        raise ValueError("First displayed frame precedes the declared video stream origin")
    if tb <= 0 or end_pts <= pts[-1]:
        raise ValueError("Invalid presentation time base or final duration")
    if not scenes or any(len(s) != 2 or not 0 <= s[0] <= s[1] < len(pts) for s in scenes):
        raise ValueError("Detector scene indices exceed the decoded frame census")
    if any(b[0] <= a[1] for a, b in zip(scenes, scenes[1:])):
        raise ValueError("Detector scenes must be ordered and non-overlapping")
    # Upstream inclusive scenes can omit transition interiors. Keep them verbatim;
    # partition by scene starts so the suggested source ranges cover every frame.
    boundaries = sorted({0, len(pts), *(int(s[0]) for s in scenes)})
    def stamp(i):
        p = pts[i] if i < len(pts) else end_pts
        return round((p - origin_pts) * tb * 1_000_000)
    shots = []
    for ordinal, (start, end) in enumerate(zip(boundaries, boundaries[1:]), 1):
        anchors = sorted({start, (start + end - 1) // 2, end - 1})
        shots.append({"id": f"shot_{ordinal:06}", "startFrame": start, "endFrameExclusive": end,
                      "startUs": stamp(start), "endUs": stamp(end),
                      "startMicros": stamp(start), "endMicros": stamp(end),
                      "anchors": [{"frameIndex": i, "pts": pts[i], "timestampMicros": stamp(i)} for i in anchors]})
    return {"schemaVersion": "vibeedit.localShots.v1", "source": source,
            "detector": {"name": "TransNetV2", "upstreamCommit": COMMIT, "savedModelSha256": MODEL_SHA, "threshold": threshold},
            "clock": {"timeBase": {"numerator": tb.numerator, "denominator": tb.denominator}, "originPts": origin_pts,
                      "presentationPts": pts, "endPtsExclusive": end_pts, "lastFrameDurationEstimated": estimated_end},
            "frameCount": len(pts), "durationMicros": stamp(len(pts)), "detectorScenesInclusive": scenes, "shots": shots,
            "boundaryMeaning": "candidate visual transitions; contiguous partition assigns transition interiors to preceding shot; verify edit points"}


def detect(video, output, cache, threshold, max_frames):
    verify_cache(cache)  # Detection never downloads implicitly.
    source = {"sha256": digest(video), "byteLength": video.stat().st_size}
    if output.exists():
        old = json.loads(output.read_text())
        if (old.get("source") == source and old.get("detector", {}).get("threshold") == threshold
                and old["detector"].get("upstreamCommit") == COMMIT and old["detector"].get("savedModelSha256") == MODEL_SHA
                and old["clock"].get("originPolicy") == "stream-start-pts.v1"):
            sidecar = output.parent / old["predictions"]["file"]
            if not sidecar.is_file() or digest(sidecar) != old["predictions"]["sha256"]:
                raise ValueError("Cached prediction sidecar is missing or changed; inspect the saved run before retrying")
            return {"state": "reused", "output": str(output), "shots": len(old["shots"])}
        raise ValueError("Output belongs to different source/settings; choose a new output path")
    prediction_path = output.with_suffix(".predictions.json")
    if prediction_path.exists():
        raise ValueError(f"Prediction sidecar exists without a complete index: {prediction_path}; inspect it before retrying")
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "V:0", "-show_streams", "-show_frames",
            "-show_entries", "stream=index,time_base,start_pts,avg_frame_rate:frame=best_effort_timestamp,duration,pkt_duration", "-of", "json", str(video)], timeout=600))
    frames = probe.get("frames", [])
    if not 0 < len(frames) <= max_frames:
        raise ValueError(f"Native frame census {len(frames)} exceeds bound {max_frames}, or video is empty; no model inference ran")
    stream = probe["streams"][0]
    pts = [int(f["best_effort_timestamp"]) for f in frames]
    tb = Fraction(stream["time_base"])
    origin = int(stream.get("start_pts", 0))
    duration = int(frames[-1].get("duration", frames[-1].get("pkt_duration", 0)))
    estimated = duration <= 0
    if estimated:
        duration = pts[-1] - pts[-2] if len(pts) > 1 else round(1 / Fraction(stream["avg_frame_rate"]) / tb)
    # Validate the clock before decoding or importing the model runtime.
    build_index(source, pts, tb, pts[-1] + duration, [[0, len(pts) - 1]], threshold, estimated, origin)
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import numpy as np
    spec = importlib.util.spec_from_file_location("transnet_official", cache / "upstream.py")
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="transnet-local-") as temp:
        raw = Path(temp) / "frames.rgb"
        subprocess.run(["ffmpeg", "-v", "error", "-noautorotate", "-i", str(video), "-map", "0:V:0", "-an", "-sn", "-dn",
                        "-vf", "scale=48:27", "-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", str(raw)], check=True, timeout=600)
        if raw.stat().st_size != len(pts) * 27 * 48 * 3:
            raise ValueError("Decode/probe frame counts disagree; no timing map will be guessed")
        video_frames = np.memmap(raw, dtype=np.uint8, mode="r", shape=(len(pts), 27, 48, 3))
        model = upstream.TransNetV2(model_dir=str(cache / "weights"))
        single, many = model.predict_frames(video_frames)
        if len(single) != len(pts) or len(many) != len(pts) or not np.isfinite(single).all() or not np.isfinite(many).all():
            raise ValueError("Invalid model prediction count or values")
        scenes = model.predictions_to_scenes(single, threshold=threshold).tolist()
        if digest(video) != source["sha256"]:
            raise ValueError("Source changed during analysis; results were not published")
        write_json(prediction_path, {"sourceSha256": source["sha256"], "single": single.tolist(), "many": many.tolist()})
        result = build_index(source, pts, tb, pts[-1] + duration, scenes, threshold, estimated, origin)
        result["clock"].update(originPolicy="stream-start-pts.v1", videoStreamIndex=int(stream["index"]))
        result["detector"]["runtime"] = {"tensorflow": upstream.tf.__version__, "numpy": np.__version__}
        result["predictions"] = {"file": prediction_path.name, "sha256": digest(prediction_path)}
        write_json(output, result)
        del video_frames
    return {"state": "completed", "output": str(output), "shots": len(result["shots"]), "frames": len(pts), "uploaded": False}


def plan(index, shot_ids, context, fps, window, dimension):
    if not math.isfinite(context) or context < 0:
        raise ValueError("Context must be a nonnegative finite number")
    if fps != "all" and (not math.isfinite(float(fps)) or not .25 <= float(fps) <= 8 or float(fps) * window > 24):
        raise ValueError("Use FPS0.25–8 and FPS×window<=24, or all")
    if not 1 <= window <= 30 or dimension not in [256, 384, 512, 768, 1024, 2048]:
        raise ValueError("Unsupported window length or frame dimension")
    pts = index["clock"]["presentationPts"]
    tb = index["clock"]["timeBase"]
    times = [round((p - index["clock"]["originPts"]) * Fraction(tb["numerator"], tb["denominator"]) * 1_000_000) for p in pts]
    wanted = set(shot_ids)
    known = {shot["id"] for shot in index["shots"]}
    if not wanted or not wanted <= known:
        raise ValueError("Select existing shot IDs explicitly; no automatic paid fan-out")
    requests = []
    for shot in index["shots"]:
        if shot["id"] not in wanted:
            continue
        start = max(0, shot["startMicros"] - round(context * 1e6))
        end = min(index["durationMicros"], shot["endMicros"] + round(context * 1e6))
        count = bisect.bisect_left(times, end) - bisect.bisect_left(times, start)
        if fps == "all" and count > 1200:
            raise ValueError("Selected every-frame range exceeds1200frames; split or narrow it before analysis")
        settings = {"startSeconds": start / 1e6, "endSeconds": end / 1e6, "maxDurationSeconds": math.ceil(index["durationMicros"] / 1e6),
                    "sampleFps": "all" if fps == "all" else float(fps), "windowSeconds": window, "maxFrameDimension": dimension}
        if fps == "all":
            settings.update(maxFrames=count, framesPerWindow=12)
        requests.append({"shotId": shot["id"], "selectedNativeFrames": count, "settings": settings})
    return {"sourceSha256": index["source"]["sha256"], "requests": requests, "submitted": False,
            "note": "Verify upload fingerprint and live capabilities; add a focused prompt, budget and distinct checkpoint before submitting chosen ranges"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, default=Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "vibeedit/transnet-v2" / COMMIT)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="Download and verify official code, license and36.5MBmodel; no video uploaded")
    run = sub.add_parser("detect")
    run.add_argument("video", type=Path)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--threshold", type=float, default=.5)
    run.add_argument("--max-frames", type=int, default=120000)
    follow = sub.add_parser("plan")
    follow.add_argument("index", type=Path)
    follow.add_argument("--shot", action="append", required=True)
    follow.add_argument("--context-seconds", type=float, default=.25)
    follow.add_argument("--sample-fps", default="4")
    follow.add_argument("--window-seconds", type=float, default=6)
    follow.add_argument("--max-frame-dimension", type=int, default=512)
    follow.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.command == "setup":
        result = setup(args.cache.resolve())
    elif args.command == "detect":
        if not math.isfinite(args.threshold) or not 0 < args.threshold < 1 or args.max_frames < 1:
            p.error("Threshold must be between0and1 and max-frames positive")
        result = detect(args.video.resolve(strict=True), args.output.resolve(), args.cache.resolve(), args.threshold, args.max_frames)
    else:
        result = plan(json.loads(args.index.read_text()), args.shot, args.context_seconds, args.sample_fps, args.window_seconds, args.max_frame_dimension)
        if args.output.exists():
            p.error("Plan output exists; choose a new path")
        write_json(args.output, result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
