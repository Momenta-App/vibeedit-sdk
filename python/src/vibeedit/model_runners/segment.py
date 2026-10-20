"""Frame/PTS-bound SAM runners. Inference never downloads implicitly."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def probe(name):
    if name == "transnet":
        import tensorflow
        return {"device": "cpu", "tensorflow": tensorflow.__version__}
    if name == "sam31-mlx":
        import mlx.core as mx
        from importlib.metadata import version
        return {"device": "mlx-metal", "metalAvailable": mx.metal.is_available(), "mlx": version("mlx"), "mlx-vlm": version("mlx-vlm"), "platform": platform.platform()}
    import torch
    return {"device": "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu", "torch": torch.__version__}


def clock(source, max_frames):
    result = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "V:0", "-show_streams", "-show_frames", "-show_entries", "stream=index,time_base,start_pts,width,height:frame=best_effort_timestamp,duration,pkt_duration", "-of", "json", str(source)], timeout=600))
    frames = result.get("frames", [])
    if not frames or len(frames) > max_frames or not 1 <= max_frames <= 120000:
        raise ValueError(f"Frame census {len(frames)} exceeds explicit bound {max_frames}, or source is empty")
    stream = result["streams"][0]
    pts = [int(f["best_effort_timestamp"]) for f in frames]
    if any(b <= a for a, b in zip(pts, pts[1:])):
        raise ValueError("Nonmonotonic source PTS requires an explicit source mapping; no clock will be guessed")
    return stream, frames, pts


def frame_anchor(index, pts, native, time_base, origin):
    """Half-open presentation anchor; never invent an unavailable final duration."""
    duration = int(native[index].get("duration", native[index].get("pkt_duration", 0)))
    end_pts = pts[index + 1] if index + 1 < len(pts) else pts[index] + duration if duration > 0 else None
    return {"frameOrdinal": index, "pts": pts[index], "nativeDurationPts": duration if duration > 0 else None, "endPtsExclusive": end_pts, "startUs": round((pts[index] - origin) * time_base * 1_000_000), "endUs": round((end_pts - origin) * time_base * 1_000_000) if end_pts is not None else None, "timingQuality": "native-presentation-range" if end_pts is not None else "final-duration-unavailable"}


def validate_prompt(name, prompt, width, height):
    allowed = {"text", "box", "scoreThreshold"} if name == "sam31-mlx" else {"box", "boxNormalized"}
    if not isinstance(prompt, dict) or set(prompt) - allowed:
        raise ValueError(f"Unsupported {name} prompt fields; expected {sorted(allowed)}")
    if name == "sam31-mlx":
        if not isinstance(prompt.get("text"), str) or not prompt["text"].strip():
            raise ValueError("SAM3.1 requires explicit prompt.text naming the target")
        threshold = prompt.get("scoreThreshold", .3)
        if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("SAM3.1 scoreThreshold must be finite and in [0,1]")
    elif len(set(prompt) & {"box", "boxNormalized"}) != 1:
        raise ValueError("SAM2.1 requires exactly one explicit box or boxNormalized target")
    for key in ("box", "boxNormalized"):
        if key not in prompt:
            continue
        box = prompt[key]
        if not isinstance(box, list) or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
            raise ValueError("Target box must contain four finite xyxy coordinates")
        bounds = (1, 1) if key == "boxNormalized" else (width, height)
        if not (0 <= box[0] < box[2] <= bounds[0] and 0 <= box[1] < box[3] <= bounds[1]):
            raise ValueError(f"Target {key} must be increasing xyxy inside {'[0,1]' if key == 'boxNormalized' else 'native source pixels'}")


def _predictor(name, runtime, prompt):
    import numpy as np
    if name == "sam31-mlx":
        from mlx_vlm.utils import load_model
        from mlx_vlm.models.sam3.generate import Sam3Predictor
        from mlx_vlm.models.sam3_1.processing_sam3_1 import Sam31Processor
        from transformers import CLIPTokenizer
        config = json.loads((runtime / "artifacts/config.json").read_text())
        if config.get("model_type") not in {"sam3.1_video", "sam3_1"}:
            raise ValueError("Expected SAM3.1 model config; no substitution is allowed")
        model = load_model(runtime / "artifacts")
        if isinstance(model, tuple):
            model = model[0]
        processor = Sam31Processor.from_pretrained(str(runtime / "artifacts"))
        processor._tokenizer = CLIPTokenizer.from_pretrained(str(runtime / "tokenizer"), local_files_only=True)
        predictor = Sam3Predictor(model, processor, score_threshold=prompt.get("scoreThreshold", .3))
        if not isinstance(prompt.get("text"), str) or not prompt["text"].strip():
            raise ValueError("SAM3.1 requires explicit prompt.text naming the target")
        def predict(image):
            result = predictor.predict(image, text_prompt=prompt["text"], **({"boxes": np.asarray([prompt["box"]], dtype=np.float32)} if "box" in prompt else {}))
            return np.asarray(result.masks), np.asarray(result.scores)
        return predict
    import torch
    from vibeedit.sam_runner import _prompt_box
    manifest = json.loads((runtime / "models/sam2.1-hiera-tiny/model.json").read_text())
    sys.path.insert(0, manifest["source"])
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    device = probe(name)["device"]
    predictor = SAM2ImagePredictor(build_sam2("configs/sam2.1/sam2.1_hiera_t.yaml", manifest["checkpoint"], device=device, apply_postprocessing=False))
    box = prompt.get("boxNormalized", prompt.get("box"))
    if not isinstance(box, list) or len(box) != 4 or not all(isinstance(v, (int, float)) and np.isfinite(v) for v in box) or not (box[0] < box[2] and box[1] < box[3]):
        raise ValueError("SAM2.1 target box must be finite increasing xyxy coordinates")
    if "boxNormalized" in prompt and not all(0 <= v <= 1 for v in box):
        raise ValueError("Normalized target box must lie in [0,1]")
    if not ("boxNormalized" in prompt or "box" in prompt):
        raise ValueError("SAM2.1 requires an explicit target box; default center boxes are not editorial evidence")
    def predict(image):
        with torch.inference_mode():
            predictor.set_image(np.asarray(image))
            masks, scores, _ = predictor.predict(box=np.asarray(_prompt_box(prompt, *image.size), dtype=np.float32), multimask_output=True)
        return np.asarray(masks), np.asarray(scores)
    return predict


def run(name, runtime, source, output, prompt, selected, max_frames):
    import numpy as np
    from PIL import Image
    source_digest = _digest(source)
    manifest = json.loads((runtime / "installed.json").read_text())
    device = probe(name)
    key = hashlib.sha256(json.dumps({"sourceSha256": source_digest, "byteLength": source.stat().st_size, "model": manifest["definitionSha256"], "runtime": device, "prompt": prompt, "frames": selected, "maxFrames": max_frames}, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if output.is_file():
        prior = json.loads(output.read_text())
        if prior.get("cacheKey") != key:
            raise ValueError("Output belongs to a different source/model/runtime/prompt/frame selection; choose a new output")
        for frame in prior["frames"]:
            for candidate in frame["candidates"]:
                path = (output.parent / candidate["file"]).resolve()
                if output.parent.resolve() not in path.parents or not path.is_file() or _digest(path) != candidate["sha256"]:
                    raise ValueError("Cached mask is missing, unsafe or altered. Inspect the original result; no inference was repeated")
        return {"output": str(output), "frames": len(prior["frames"]), "state": "reused", "qualification": prior["state"]}
    if output.with_suffix(".masks").exists():
        raise ValueError("Partial mask directory already exists. Inspect the original run or choose a new output; it will not be replaced.")
    stream, native, pts = clock(source, max_frames)
    wanted = selected if selected is not None else list(range(len(pts)))
    if not wanted or wanted != sorted(set(wanted)) or any(type(x) is not int or not 0 <= x < len(pts) for x in wanted):
        raise ValueError("Frames must be unique increasing source ordinals in the frame census")
    if len(wanted) > 1200:
        raise ValueError("One mask run is limited to 1200 selected frames. Split at reviewed shot boundaries.")
    validate_prompt(name, prompt, stream["width"], stream["height"])
    predict = _predictor(name, runtime, prompt)
    capture = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-noautorotate", "-i", str(source), "-map", f"0:{stream['index']}", "-an", "-sn", "-dn", "-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"], stdout=subprocess.PIPE)
    mask_dir = output.with_suffix(".masks")
    mask_dir.mkdir(parents=True)
    records = []
    time_base = Fraction(stream["time_base"])
    origin = int(stream.get("start_pts", pts[0]))
    wanted_set = set(wanted)
    try:
        for index in range(len(pts)):
            data = capture.stdout.read(stream["width"] * stream["height"] * 3)
            if len(data) != stream["width"] * stream["height"] * 3:
                raise ValueError("Decode/probe frame census mismatch; no result index was published")
            if index not in wanted_set:
                continue
            image = Image.frombytes("RGB", (stream["width"], stream["height"]), data)
            if image.size != (stream["width"], stream["height"]):
                raise ValueError("Decoded geometry differs from native geometry (rotation/proxy mapping required)")
            masks, scores = predict(image)
            detections = []
            if not np.isfinite(scores).all():
                raise ValueError("Nonfinite model scores")
            # Preserve every returned candidate. Picking the top score does not prove identity.
            for ordinal, (mask, score) in enumerate(zip(masks, scores)):
                binary = np.squeeze(mask)
                if binary.shape != (image.height, image.width):
                    raise ValueError(f"Mask geometry {binary.shape} differs from source {(image.height, image.width)}")
                binary = (binary > 0).astype(np.uint8) * 255
                path = mask_dir / f"frame-{index:08d}-candidate-{ordinal:03d}.png"
                Image.fromarray(binary).save(path)
                detections.append({"candidate": ordinal, "score": float(score), "file": str(path.relative_to(output.parent)), "sha256": _digest(path), "areaPixels": int(np.count_nonzero(binary))})
            records.append({**frame_anchor(index, pts, native, time_base, origin), "candidates": detections, "status": "needs-review" if detections else "no-detection"})
        extra = capture.stdout.read(1)
        capture.stdout.close()
        if capture.wait(timeout=60) or extra:
            raise ValueError("Decoder census differs from source clock; no index published")
    finally:
        if capture.poll() is None:
            capture.terminate()
            capture.wait(timeout=15)
        if capture.stdout and not capture.stdout.closed:
            capture.stdout.close()
    if _digest(source) != source_digest:
        raise ValueError("Source changed during inference; no result index was published")
    result = {"schemaVersion": "vibeedit.masks.v1", "ok": True, "state": "needs-review", "cacheKey": key, "modelPack": name, "runnerVersion": manifest["runnerVersion"], "definitionSha256": manifest["definitionSha256"], "modelFiles": manifest["files"], "runtime": device, "source": {"sha256": source_digest, "byteLength": source.stat().st_size, "width": stream["width"], "height": stream["height"]}, "clock": {"timeBase": {"numerator": time_base.numerator, "denominator": time_base.denominator}, "originPts": origin, "videoStreamIndex": stream["index"], "nativeFrameCount": len(pts), "presentationPts": pts, "nativeFrameDurationPts": [int(f.get("duration", f.get("pkt_duration", 0))) or None for f in native]}, "prompt": prompt, "frameSelection": wanted, "geometry": {"coordinateSpace": "native-source-pixels", "crop": None, "resize": None}, "frames": records, "limitations": ["Independent per-frame candidates, no stable identity claim", "Not reviewed for cuts, occlusions, contacts or edge quality", "Unselected frames have no mask; never fill them with a later-frame mask"]}
    from jsonschema import Draft202012Validator
    Draft202012Validator(json.loads((Path(__file__).parent / "mask-index.schema.json").read_text())).validate(result)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    temporary.replace(output)
    return {"output": str(output), "frames": len(records), "candidates": sum(len(x["candidates"]) for x in records), "state": "needs-review"}


def main():
    if sys.argv[1] == "probe":
        print(json.dumps(probe(sys.argv[2])))
        return
    _, _, name, runtime, source, output, prompt, frames, max_frames = sys.argv
    print(json.dumps(run(name, Path(runtime), Path(source), Path(output), json.loads(prompt), json.loads(frames), int(max_frames))))


if __name__ == "__main__":
    main()
