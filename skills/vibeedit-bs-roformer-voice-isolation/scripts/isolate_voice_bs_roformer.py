#!/usr/bin/env python3
"""Optional local audio-separator adapter. No desktop code, model download or remote API."""
from __future__ import annotations
import argparse
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import subprocess

MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
RUNTIME_VERSION = "0.47.0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--input", help="Project-relative original source")
    parser.add_argument("--model-receipt", help="Project-relative customer model/config/rights receipt")
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--duration", type=float)
    args = parser.parse_args()
    try:
        installed = version("audio-separator")
    except PackageNotFoundError:
        installed = None
    if args.probe:
        print(json.dumps({"runtime": "audio-separator", "requiredVersion": RUNTIME_VERSION, "installedVersion": installed, "runtimeReady": installed == RUNTIME_VERSION, "inferenceQualified": False, "modelDistribution": "not bundled; upstream weight license unverified; exact local model/config and rights receipt required"}))
        return
    if not args.project or not args.input or not args.model_receipt:
        parser.error("--project, --input and --model-receipt are required")
    if installed != RUNTIME_VERSION:
        raise SystemExit("Optional runtime unavailable: install audio-separator==0.47.0 in a separate environment; see the skill provenance file")
    project = args.project.expanduser().resolve(strict=True)
    source = scoped(project, args.input)
    model_receipt = json.loads(scoped(project, args.model_receipt).read_text())
    if not all(model_receipt.get(key) for key in ["model", "modelSha256", "config", "configSha256", "license", "licenseUrl", "verifiedBy"]):
        raise ValueError("Model receipt must pin model/config bytes and record verified license rights")
    model = scoped(project, model_receipt["model"])
    config = scoped(project, model_receipt["config"])
    if model.name != MODEL or config.suffix != ".yaml":
        raise ValueError("This adapter is for BS-Roformer 1297 with an explicit YAML config")
    for path, key in [(model, "modelSha256"), (config, "configSha256")]:
        if digest(path) != model_receipt[key]:
            raise ValueError(key + " does not match local bytes")
    metadata = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_format", "-of", "json", str(source)], check=True, text=True, capture_output=True).stdout)
    full_duration = float(metadata["format"]["duration"])
    duration = full_duration - args.start if args.duration is None else args.duration
    if args.start < 0 or duration <= 0 or args.start + duration > full_duration + .001:
        raise ValueError("Select a window within the original source clock")
    identity = {"sourceSha256": digest(source), "modelSha256": digest(model), "configSha256": digest(config), "startUs": round(args.start * 1e6), "durationUs": round(duration * 1e6), "runtime": RUNTIME_VERSION}
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    run = scoped(project, "artifacts/voice-isolation/" + run_id, exists=False)
    # A failed/crashed run remains visible. Never silently overwrite it or pretend it completed.
    run.mkdir(parents=True, exist_ok=False)
    manifest = run / "manifest.json"
    manifest.write_text(json.dumps({**identity, "status": "running", "source": args.input, "modelReceipt": args.model_receipt}, indent=2) + "\n")
    wav = run / "input-padded.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(args.start), "-i", str(source), "-t", str(duration), "-vn", "-af", "apad=whole_dur=2", "-ar", "44100", "-ac", "2", str(wav)], check=True)
    from audio_separator.separator import Separator

    class LocalSeparator(Separator):
        def download_model_files(self, model_filename):
            if model_filename != MODEL:
                raise ValueError("Unexpected model request")
            self.model_is_uvr_vip = False
            return MODEL, "MDXC", "Customer-supplied BS-Roformer 1297", str(model), str(config)

    separator = LocalSeparator(model_file_dir=str(model.parent), output_dir=str(run), output_format="WAV")
    separator.load_model(MODEL)
    outputs = separator.separate(str(wav), custom_output_names={"Vocals": "vocals-padded", "Instrumental": "instrumental-padded"})
    stems = {}
    for label in ["vocals", "instrumental"]:
        candidates = [Path(value) if Path(value).is_absolute() else run / value for value in outputs if Path(value).stem.lower() == label + "-padded"]
        if len(candidates) != 1:
            raise RuntimeError("Runtime did not return the exact expected stem set")
        padded = candidates[0].resolve(strict=True)
        padded.relative_to(run)
        target = run / (label + ".wav")
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(padded), "-t", str(duration), "-c:a", "pcm_s16le", str(target)], check=True)
        stems[label] = {"path": str(target.relative_to(project)), "sha256": digest(target)}
    receipt = {**identity, "status": "needs-listening-review", "source": args.input, "clock": "original-source-microseconds", "modelReceipt": model_receipt, "stems": stems, "inferenceQualified": False}
    manifest.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def scoped(project, value, exists=True):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Use project-relative source/model/config paths")
    cursor = project
    for part in path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Symlink inputs are not allowed")
    path = cursor.resolve(strict=exists)
    path.relative_to(project)
    return path


if __name__ == "__main__":
    main()
