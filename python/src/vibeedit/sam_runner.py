from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    values = argv or sys.argv[1:]
    if len(values) != 4 or values[0] != "segment":
        raise SystemExit("usage: sam-runner segment <video> <output.json> <prompt-json>")
    runtime = Path(os.environ.get("VIBEEDIT_SAM_RUNTIME", ""))
    manifest_path = runtime / "model.json"
    if not manifest_path.is_file():
        raise RuntimeError("VIBEEDIT_SAM_RUNTIME does not contain model.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_root = Path(manifest["source"])
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    masks, metadata = _segment(Path(values[1]), json.loads(values[3]), manifest)
    destination = Path(values[2])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"schemaVersion": "1.0.0", "format": "vibeedit.sam-rle", "model": manifest["id"], "modelVersion": manifest["version"], "width": metadata["width"], "height": metadata["height"], "runtime": metadata["runtime"], "frames": [{"frame": index, "rle": _rle(mask)} for index, mask in enumerate(masks)]}, separators=(",", ":")) + "\n", encoding="utf-8")
    return 0


def _segment(source: Path, prompt, manifest):
    import cv2
    import numpy
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    capture = cv2.VideoCapture(str(source))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    capture.release()
    if not frames:
        raise ValueError(f"video contained no decodable frames: {source}")
    height, width = frames[0].shape[:2]
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    model = build_sam2("configs/sam2.1/sam2.1_hiera_t.yaml", manifest["checkpoint"], device=device, apply_postprocessing=False)
    predictor = SAM2ImagePredictor(model)
    box = _prompt_box(prompt, width, height)
    masks = []
    with torch.inference_mode():
        for frame in frames:
            predictor.set_image(frame)
            predicted, scores, _ = predictor.predict(box=numpy.asarray(box, dtype=numpy.float32), multimask_output=True)
            masks.append(predicted[int(numpy.argmax(scores))].astype(numpy.uint8))
    return masks, {"width": width, "height": height, "runtime": {"device": device, "torch": torch.__version__, "opencv": cv2.__version__, "numpy": numpy.__version__}}


def _prompt_box(prompt, width: int, height: int):
    return _box(prompt.get("boxNormalized") if "boxNormalized" in prompt else prompt.get("box"), width, height)


def _box(value, width: int, height: int):
    if not isinstance(value, list) or len(value) != 4 or not all(isinstance(item, (int, float)) for item in value):
        return [width * 0.2, height * 0.1, width * 0.8, height * 0.9]
    if all(0 <= item <= 1 for item in value):
        return [value[0] * width, value[1] * height, value[2] * width, value[3] * height]
    return [max(0, min(width - 1, value[0])), max(0, min(height - 1, value[1])), max(1, min(width, value[2])), max(1, min(height, value[3]))]


def _rle(mask) -> list[int]:
    counts = []
    current = 0
    count = 0
    for value in mask.reshape(-1):
        bit = int(value != 0)
        if bit == current:
            count += 1
            continue
        counts.append(count)
        current = bit
        count = 1
    counts.append(count)
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
