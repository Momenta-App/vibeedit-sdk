"""Supplemental CPU qualification from exact public archives; requires explicit dispatch.

Only stdlib is imported by this coordinator. Models run in the package's isolated
pinned runtime after fresh gates. Candidate masks remain unreviewed. No upload,
private provider, customer account, GPU, or local Apple Silicon claim is made.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import struct
import subprocess
import sys
import tarfile
import time
import urllib.request

DEADLINE = time.monotonic() + 25 * 60
REPOSITORY = "Momenta-App/vibeedit-sdk"
VERIFIER_SHA256 = "4ba34a70407a869587001906b36102af9e47dc352ec9aaa129d726c844db9fd3"
PACK_DISK = {"transnet": 31_991_029_248, "sam21": 53_991_029_248}
PACK_MEMORY = {"transnet": 6 * 1024 ** 3, "sam21": 8 * 1024 ** 3}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def public_guard():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    repository = event["repository"]
    if (os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or repository.get("full_name") != REPOSITORY
            or repository.get("private") is not False):
        raise ValueError("Exact public repository dispatch is required")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("This proposal qualifies only standard Ubuntu x86_64 CPU")


def resources(pack, *, setup):
    public_guard()
    volumes = {key: shutil.disk_usage(path)._asdict() for key, path in {
        "system": "/", "runnerTemp": os.environ["RUNNER_TEMP"],
    }.items()}
    memory = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable"}:
            count, unit = value.split()
            if unit != "kB":
                raise ValueError("Unknown available-memory unit")
            memory[key] = int(count) * 1024
    if not 0 < memory["MemAvailable"] <= memory["MemTotal"]:
        raise ValueError("Available-memory measurement is invalid")
    load = list(os.getloadavg()[:2])
    if len(load) != 2 or any(not math.isfinite(value) or value < 0 for value in load):
        raise ValueError("Load measurement is unknown")
    percent = 100 * memory["MemAvailable"] / memory["MemTotal"]
    minimum = PACK_DISK[pack] if setup else 25 * 1024 ** 3
    reasons = []
    if any(volume["free"] < minimum for volume in volumes.values()):
        reasons.append("Disk gate failed")
    if percent < 15 or memory["MemAvailable"] < PACK_MEMORY[pack]:
        reasons.append("Available-memory gate failed")
    if any(value > 10 for value in load):
        reasons.append("One/five-minute load gate failed")
    value = {"atUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "pack": pack,
             "setupReservation": setup, "minimumDiskBytes": minimum,
             "minimumAvailableMemoryBytes": PACK_MEMORY[pack], "diskBytes": volumes,
             "memoryBytes": memory, "memoryAvailablePercent": percent, "load1and5": load,
             "reasons": reasons, "status": "blocked" if reasons else "possible"}
    print("VIBEEDIT_MODEL_RESOURCE " + json.dumps(value, sort_keys=True), flush=True)
    if reasons:
        raise RuntimeError("Fresh resource gate blocked model work")
    return value


def child_environment(work):
    # No host/provider/customer credentials, source PYTHONPATH or GitHub tokens.
    value = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}
    value.update(CUDA_VISIBLE_DEVICES="-1", TF_CPP_MIN_LOG_LEVEL="2", OMP_NUM_THREADS="2",
                 OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2", TF_NUM_INTRAOP_THREADS="2",
                 TF_NUM_INTEROP_THREADS="2", UV_NO_CACHE="1", UV_CACHE_DIR=str(work / "ephemeral-uv"),
                 PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1")
    return value


def command(args, work, *, seconds=600):
    remaining = int(DEADLINE - time.monotonic()) - 60
    if remaining <= 0:
        raise RuntimeError("Aggregate execution deadline reached; retaining evidence without retry")
    seconds = min(seconds, remaining)
    process = subprocess.Popen([str(x) for x in args], cwd=work, env=child_environment(work),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=10)
        raise RuntimeError("Owned command timed out; no automatic retry") from None
    if process.returncode:
        raise RuntimeError("Owned command failed: " + (stderr or stdout).decode("utf-8", errors="replace")[-4000:])
    return stdout


def archive_verification(canonical, source, work):
    expected_sha = os.environ["CANONICAL_MANIFEST_SHA256"]
    artifact_id = os.environ["CANONICAL_ARTIFACT_ID"]
    artifact_digest = os.environ["CANONICAL_ARTIFACT_SHA256"]
    run_id = os.environ["CANONICAL_RUN_ID"]
    if not re.fullmatch(r"[a-f0-9]{40}", source) or not re.fullmatch(r"[0-9]+", run_id):
        raise ValueError("Pin full canonical source SHA and numeric run ID")
    if not re.fullmatch(r"[0-9]+", artifact_id) or not re.fullmatch(r"[a-f0-9]{64}", artifact_digest):
        raise ValueError("Pin immutable artifact ID and transport digest")
    request = urllib.request.Request(f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}",
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=30) as response:
        metadata = json.loads(response.read(1024 * 1024))
    if (metadata.get("id") != int(artifact_id) or metadata.get("expired") is not False
            or metadata.get("digest") != "sha256:" + artifact_digest
            or metadata.get("workflow_run", {}).get("id") != int(run_id)
            or metadata.get("workflow_run", {}).get("head_sha") != source):
        raise ValueError("GitHub artifact metadata differs from the reviewed build identity")
    verifier_url = f"https://raw.githubusercontent.com/{REPOSITORY}/{source}/scripts/smoke_release_artifacts.py"
    with urllib.request.urlopen(verifier_url, timeout=30) as response:
        verifier_bytes = response.read(65_537)
        if response.geturl() != verifier_url or len(verifier_bytes) > 65_536 or hashlib.sha256(verifier_bytes).hexdigest() != VERIFIER_SHA256:
            raise ValueError("Canonical verifier source digest differs; no default-branch fallback")
    verifier_file = work / "verified_archive_verifier.py"
    with verifier_file.open("xb") as stream:
        stream.write(verifier_bytes)
    spec = importlib.util.spec_from_file_location("canonical_verifier", verifier_file)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    manifest = canonical / "release-manifest.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    version = value["versions"]
    result = helper.verify_release_inputs(argparse.Namespace(
        manifest=manifest, manifest_sha256=expected_sha, source_revision=source,
        canonical_artifact_id=artifact_id, canonical_artifact_digest=artifact_digest,
        checksums=canonical / "SHA256SUMS",
        wheel=canonical / "python" / f"vibeedit-{version['python']}-py3-none-any.whl",
        npm=canonical / "npm" / f"vibeedit-{version['npm']}.tgz"))
    result["workflowArtifact"].update(runId=run_id, metadataChecked=True)
    result["verifiedHelper"] = {"sourceRevision": source, "sha256": VERIFIER_SHA256, "bytes": len(verifier_bytes), "url": verifier_url}
    return value, result


def download_original(fixture, target):
    source = fixture["source"]
    if source["originalUrl"] != "https://upload.wikimedia.org/wikipedia/commons/c/cb/Tears_of_Steel_1080p.webm":
        raise ValueError("Unexpected public original URL")
    if target.exists():
        raise ValueError("Original/partial source already exists; inspect it rather than replace it")
    started = time.monotonic()
    sha256, sha1, size = hashlib.sha256(), hashlib.sha1(), 0
    request = urllib.request.Request(source["originalUrl"], headers={"User-Agent": "VibeEditModelQualification/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("xb") as output:
        if response.geturl().split("?", 1)[0] != source["originalUrl"]:
            raise ValueError("Unexpected source redirect")
        for block in iter(lambda: response.read(1024 * 1024), b""):
            size += len(block)
            if size > source["bytes"] or time.monotonic() - started > 600 or time.monotonic() > DEADLINE - 60:
                raise RuntimeError("Original source download exceeded its exact bound")
            output.write(block)
            sha256.update(block)
            sha1.update(block)
    if (size, sha256.hexdigest(), sha1.hexdigest()) != (source["bytes"], source["sha256"], source["sha1"]):
        raise ValueError("Original public source byte identity differs")


def source_fixture(fixture, work):
    parent = work / "original.webm"
    source = work / "source-native.mkv"
    download_original(fixture, parent)
    command(["ffmpeg", "-v", "error", "-threads", "1", "-ss", "468", "-i", parent,
             "-map", "0:v:0", "-an", "-sn", "-dn", "-t", "6", "-vf", "setpts=PTS-STARTPTS",
             "-fps_mode", "passthrough", "-c:v", "ffv1", "-level", "3", "-pix_fmt", "yuv420p",
             "-enc_time_base", "1/1000", "-threads", "1", source], work)
    census = json.loads(command(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
        "-show_frames", "-show_entries", "stream=width,height,time_base:frame=best_effort_timestamp",
        "-of", "json", source], work))
    stream = census["streams"][0]
    if (stream["width"], stream["height"], stream["time_base"]) != (1920, 800, "1/1000"):
        raise ValueError("Derived source geometry or native clock differs")
    pts = [int(frame["best_effort_timestamp"]) for frame in census["frames"]]
    if pts != [frame["pts"] for frame in fixture["frames"]]:
        raise ValueError("Derived native presentation census differs")
    hashes = command(["ffmpeg", "-v", "error", "-threads", "1", "-i", source,
        "-map", "0:v:0", "-an", "-fps_mode", "passthrough", "-pix_fmt", "yuv420p",
        "-threads", "1", "-f", "framehash", "-hash", "sha256", "pipe:1"], work).decode("utf-8")
    actual = [line.rsplit(",", 1)[-1].strip() for line in hashes.splitlines() if line and not line.startswith("#")]
    if actual != [frame["sha256"] for frame in fixture["frames"]]:
        raise ValueError("Decoded native pixels differ from all144 reviewed source pins")
    return source, {"parentSha256": digest(parent), "sourceSha256": digest(source),
        "sourceBytes": source.stat().st_size, "clock": census, "all144NativePixelHashesMatch": True,
        "frameHashText": hashes, "encodedContainerMatchesOldLocalFixture": "not assumed; newly pinned derived bytes"}


def emit_packet(pack, files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, path in sorted(files.items()):
            if (Path(name).is_absolute() or ".." in Path(name).parts
                    or Path(name).suffix not in {".json", ".png", ".lock"}
                    or path.is_symlink() or not path.is_file()):
                raise ValueError("Unsafe evidence packet entry")
            data = path.read_bytes()
            if len(data) > 2 * 1024 ** 2 or stream.tell() + len(data) > 8 * 1024 ** 2:
                raise ValueError("Evidence packet exceeded its raw bound; no silent truncation")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o600
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    data = gzip.compress(stream.getvalue(), mtime=0)
    if len(data) > 2 * 1024 ** 2:
        raise ValueError("Evidence packet exceeded2MiB compressed; no upload or truncation")
    encoded = base64.b64encode(data).decode("ascii")
    chunks = [encoded[index:index + 8192] for index in range(0, len(encoded), 8192)]
    header = {"pack": pack, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "chunks": len(chunks),
              "entries": {name: {"sha256": digest(path), "bytes": path.stat().st_size} for name, path in sorted(files.items())}}
    print("VIBEEDIT_MODEL_PACKET_BEGIN " + json.dumps(header, sort_keys=True), flush=True)
    for index, chunk in enumerate(chunks):
        print("VIBEEDIT_MODEL_PACKET_CHUNK " + json.dumps({"pack": pack, "index": index, "base64": chunk}), flush=True)
    print("VIBEEDIT_MODEL_PACKET_END " + json.dumps({"pack": pack, "sha256": header["sha256"], "chunks": len(chunks)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["preflight", "run"])
    parser.add_argument("--pack", choices=PACK_DISK, required=True)
    parser.add_argument("--canonical", type=Path)
    args = parser.parse_args()
    before = resources(args.pack, setup=True)
    if args.mode == "preflight":
        return 0
    if not args.canonical or sys.version_info[:2] != (3, 12):
        raise ValueError("Use the selected Python3.12 and exact canonical directory")
    work = Path(os.environ["RUNNER_TEMP"]) / ("vibeedit-model-" + args.pack)
    work.mkdir(exist_ok=False)
    evidence = work / "evidence"
    evidence.mkdir()
    fixture_file = Path(__file__).parent / "model-fixtures/tos-468-474.json"
    fixture = json.loads(fixture_file.read_text(encoding="utf-8"))
    receipt = {"schemaVersion": "vibeedit.cpuModelQualification.v1", "pack": args.pack,
        "qualified": False, "state": "started", "helperSourceRevision": os.environ.get("GITHUB_SHA"),
        "helperSha256": digest(__file__), "fixtureMetadataSha256": digest(fixture_file),
        "beforeSetupResources": before, "rights": fixture["rights"],
        "limits": ["CPU supplemental only; not local AppleSilicon or SAM3.1MLX", "Sparse masks need human correction/review",
                   "No propagation, full-frame mask coverage, semantic scene accuracy or final editorial acceptance claim",
                   "Public log retention follows current repository setting; retrieve verified packet before expiration"]}
    files = {"fixture.json": fixture_file}
    try:
        manifest, receipt["canonicalVerification"] = archive_verification(args.canonical, os.environ["CANONICAL_SOURCE_SHA"], work)
        receipt["canonicalSourceRevision"] = manifest["source"]["revision"]
        uv = shutil.which("uv")
        if not uv or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise ValueError("Pinned uv and preinstalled FFmpeg/FFprobe are required; no fallback install")
        command([uv, "venv", "--python", sys.executable, work / "launcher"], work, seconds=120)
        sdk = work / "launcher/bin/python"
        command([uv, "pip", "sync", "--python", sdk, "--require-hashes", args.canonical / "requirements-core.lock"], work)
        command([uv, "pip", "install", "--python", sdk, "--no-deps",
                 args.canonical / "python" / f"vibeedit-{manifest['versions']['python']}-py3-none-any.whl"], work)
        receipt["sdkInterpreter"] = json.loads(command([sdk, "-c", "import sys,json,platform,vibeedit;print(json.dumps({'version':sys.version,'machine':platform.machine(),'module':vibeedit.__file__}))"], work))
        if not Path(receipt["sdkInterpreter"]["module"]).is_relative_to(work / "launcher"):
            raise ValueError("SDK imported from outside the exact-wheel launcher")
        receipt["tools"] = {"uv": command([uv, "--version"], work).decode().strip(), "ffmpeg": command(["ffmpeg", "-version"], work).decode().splitlines()[0]}
        source, source_record = source_fixture(fixture, work)
        save(evidence / "source-binding.json", source_record)
        files["source-binding.json"] = evidence / "source-binding.json"
        receipt["beforeModelSetupResources"] = resources(args.pack, setup=True)
        cache = work / "model-cache"
        setup = command([sdk, "-m", "vibeedit", "models", "setup", args.pack, "--cache", cache, "--json"], work, seconds=900)
        receipt["setup"] = json.loads(setup.decode("utf-8"))
        resources(args.pack, setup=False)
        probe = json.loads(command([sdk, "-m", "vibeedit", "models", "probe", args.pack, "--cache", cache, "--json"], work, seconds=240))
        receipt["runtime"] = probe
        receipt["modelInterpreter"] = json.loads(command([cache / args.pack / "env/bin/python", "-c", "import sys,json;print(json.dumps({'version':sys.version,'versionInfo':list(sys.version_info[:3])}))"], work))
        if receipt["modelInterpreter"]["versionInfo"][:2] != [3, 12]:
            raise ValueError("Pinned model runtime changed Python major/minor")
        if not probe.get("available") or probe.get("runtime", {}).get("device") != "cpu":
            raise ValueError("Actual pinned runtime did not report available CPU")
        installed = cache / args.pack / "installed.json"
        files["model-installation.json"] = installed
        files["runtime-requirements.lock"] = cache / args.pack / "requirements.lock"
        if args.pack == "transnet":
            runs = [{"id": "transnet", "extra": ["--threshold", "0.5"]}]
        else:
            runs = [{"id": item["id"], "extra": ["--frames", ",".join(map(str, item["frames"])),
                      "--prompt", json.dumps(item["prompt"], separators=(",", ":"))]} for item in fixture["samPromptProposals"]]
        receipt["runs"] = []
        for item in runs:
            snapshot = resources(args.pack, setup=False)
            target = evidence / (item["id"] + ".json")
            result = command([sdk, "-m", "vibeedit", "models", "run", args.pack, source,
                "--cache", cache, "--output", target, "--max-frames", "144", *item["extra"], "--json"], work, seconds=600)
            receipt["runs"].append({"id": item["id"], "resources": snapshot,
                "result": json.loads(result.decode("utf-8")), "indexSha256": digest(target)})
            files[target.name] = target
            index = json.loads(target.read_text(encoding="utf-8"))
            if args.pack == "sam21":
                if (index["source"]["sha256"] != source_record["sourceSha256"] or index["state"] != "needs-review"
                        or index["clock"]["presentationPts"] != [frame["pts"] for frame in fixture["frames"]]
                        or index["runtime"]["device"] != "cpu" or index["modelPack"] != "sam21"):
                    raise ValueError("Candidate source/state mismatch")
                for frame in index["frames"]:
                    if frame["pts"] != fixture["frames"][frame["frameOrdinal"]]["pts"]:
                        raise ValueError("Candidate native frame/PTS mismatch")
                    for candidate in frame["candidates"]:
                        path = (evidence / candidate["file"]).resolve()
                        if evidence.resolve() not in path.parents or path.is_symlink() or digest(path) != candidate["sha256"]:
                            raise ValueError("Unsafe or corrupted native candidate mask")
                        header = path.read_bytes()[:33]
                        if (len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n"
                                or header[12:16] != b"IHDR" or struct.unpack(">II", header[16:24]) != (1920, 800)):
                            raise ValueError("Native candidate PNG geometry mismatch")
                        files[path.relative_to(evidence).as_posix()] = path
            else:
                prediction = evidence / index["predictions"]["file"]
                if digest(prediction) != index["predictions"]["sha256"]:
                    raise ValueError("Prediction sidecar mismatch")
                files[prediction.name] = prediction
                receipt["observedCutReference"] = fixture["observedHardCutIncomingFrames"]
                single = json.loads(prediction.read_text(encoding="utf-8"))["single"]
                if len(single) != 144 or any(not math.isfinite(float(x)) for x in single):
                    raise ValueError("Prediction census is invalid")
                clusters = []
                for frame, score in enumerate(single):
                    if score <= 0.5:
                        continue
                    if not clusters or frame != clusters[-1][-1] + 1:
                        clusters.append([])
                    clusters[-1].append(frame)
                peaks = [max(cluster, key=lambda frame: single[frame]) for cluster in clusters]
                receipt["cutReview"] = {"threshold": 0.5, "clusterPeakFrames": peaks,
                    "referenceNearestPeakDistanceFrames": {str(frame): min((abs(frame-p) for p in peaks), default=None) for frame in fixture["observedHardCutIncomingFrames"]},
                    "limitations": "Diagnostics only, includes misses/extras; no semantic scene or validated accuracy claim"}
        receipt["state"] = "actual-cpu-inference-needs-review"
    except Exception as error:
        receipt.update(state="failed-or-resource-blocked", failure={"type": type(error).__name__, "message": str(error)[:6000]})
        raise
    finally:
        # Retain bounded partial candidates for forensics too; an orphan PNG is
        # not approved or silently promoted to a complete native result index.
        partial = []
        for path in sorted(evidence.rglob("*.png")):
            relative = path.relative_to(evidence).as_posix()
            if relative not in files:
                partial.append(relative)
                files[relative] = path
        receipt["partialCandidateFilesWithoutCompletedIndex"] = partial
        save(evidence / "receipt.json", receipt)
        files["receipt.json"] = evidence / "receipt.json"
        emit_packet(args.pack, files)


if __name__ == "__main__":
    raise SystemExit(main())
