from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from vibeedit import plan_revision, render, render_revision, verify_output


ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "review"
SOURCES = ROOT / "sources"
FPS = 30
WIDTH = 640
HEIGHT = 360
RUN_ID = str(time.time_ns())


def main() -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    SOURCES.mkdir(parents=True, exist_ok=True)
    (REVIEW / "contact-sheet.jpg").unlink(missing_ok=True)
    _generate_sources()
    revisions = _revisions()
    report = {"schemaVersion": "1.0.0", "test": "vibeedit-human-revision-stress", "revisions": []}
    previous_spec = None
    previous_output = None

    for index, revision in enumerate(revisions):
        spec = revision["spec"]
        stem = f"r{index:02d}-{revision['slug']}"
        suffix = ".mkv" if spec["render"]["output"]["container"] == "mkv" else ".mp4"
        output = REVIEW / f"{stem}{suffix}"
        spec["render"]["output"]["uri"] = output.name
        spec_path = REVIEW / f"{stem}.composition.json"
        spec_path.write_text(json.dumps(spec, indent=2) + "\n")
        plan = None if previous_spec is None else plan_revision(previous_spec, spec)
        started = time.perf_counter()
        mode = "full-initial"
        error = None
        try:
            if previous_spec is None:
                render(spec_path, output)
            elif plan["executionStatus"] in {"verified-frame-cache", "verified-audio-remix", "verified-stream-copy-remux", "verified-stream-copy-video-audio-remix", "verified-stream-copy-tail", "verified-stream-copy-tail-audio-remix", "no-work"}:
                mode = "incremental"
                render_revision(previous_spec, spec, previous_output, output)
            else:
                mode = "clean-fallback"
                render(spec_path, output)
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
            mode = "failed-then-clean-fallback"
            render(spec_path, output)
        elapsed = time.perf_counter() - started

        clean_spec = copy.deepcopy(spec)
        clean_spec["cache"] = {"enabled": False, "namespace": f"clean-{stem}"}
        clean_output = ROOT / f".{stem}-clean{suffix}"
        clean_started = time.perf_counter()
        render(clean_spec, clean_output)
        clean_elapsed = time.perf_counter() - clean_started
        verification = verify_output(output, spec["verification"])
        comparison = _compare(output, clean_output)
        provenance = json.loads(output.with_suffix(output.suffix + ".vibeedit.json").read_text())
        clean_output.unlink(missing_ok=True)
        clean_output.with_suffix(clean_output.suffix + ".vibeedit.json").unlink(missing_ok=True)

        report["revisions"].append(
            {
                "index": index,
                "id": stem,
                "label": revision["label"],
                "changeClasses": revision["change_classes"],
                "renderMode": mode,
                "incrementalError": error,
                "elapsedSeconds": round(elapsed, 6),
                "cleanRenderSeconds": round(clean_elapsed, 6),
                "plan": plan,
                "work": provenance.get("work"),
                "verification": {"passed": verification.passed, "errors": verification.errors, "warnings": verification.warnings},
                "cleanComparison": comparison,
                "output": {"file": output.name, "bytes": output.stat().st_size, "sha256": _sha256(output)},
            }
        )
        previous_spec = copy.deepcopy(spec)
        previous_output = output

    report["benchmarks"] = _benchmarks(revisions, report)
    (REVIEW / "stress-test-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (REVIEW / "REVIEW_NOTES.md").write_text(_review_notes(report))
    outputs = [REVIEW / item["output"]["file"] for item in report["revisions"]]
    _contact_sheet(outputs, 0.22, "contact-sheet-early.jpg")
    _contact_sheet(outputs, 0.72, "contact-sheet-late.jpg")
    print(json.dumps({"reviewFolder": str(REVIEW), "revisions": len(report["revisions"]), "failures": [item["id"] for item in report["revisions"] if not item["verification"]["passed"]]}, indent=2))


def _generate_sources() -> None:
    commands = [
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={WIDTH}x{HEIGHT}:rate={FPS}:duration=4", "-vf", "hue=h=28:s=1.5,boxblur=6:1,eq=contrast=1.18:brightness=-0.08", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(SOURCES / "scene-a.mp4")],
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={WIDTH}x{HEIGHT}:rate={FPS}:duration=4", "-vf", "hue=h=205:s=1.35,edgedetect=mode=colormix:high=0.35,eq=contrast=1.2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(SOURCES / "scene-b.mp4")],
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=110:sample_rate=48000:duration=8", "-f", "lavfi", "-i", "sine=frequency=165:sample_rate=48000:duration=8", "-filter_complex", "[0:a]volume=-26dB[a0];[1:a]volume=-30dB[a1];[a0][a1]amix=inputs=2:normalize=0,afade=t=in:st=0:d=0.4,afade=t=out:st=7.2:d=0.8", str(SOURCES / "music.wav")],
    ]
    for command in commands:
        subprocess.run(command, check=True)


def _base_spec() -> dict:
    sources = [
        _source("scene-a", "video", "scene-a.mp4", 120),
        _source("scene-b", "video", "scene-b.mp4", 120),
        _source("music", "audio", "music.wav", 240),
    ]
    return {
        "schemaVersion": "1.0.0",
        "kind": "vibeedit.composition",
        "id": "revision-stress-video",
        "title": "Revision Stress Test",
        "canvas": {"width": WIDTH, "height": HEIGHT, "frameRate": {"numerator": FPS, "denominator": 1}, "backgroundColor": "#050810", "audioSampleRate": 48000},
        "durationFrames": 210,
        "sources": sources,
        "timeline": {
            "tracks": [
                {
                    "id": "V1",
                    "kind": "video",
                    "order": 0,
                    "items": [
                        {"id": "clip-a", "kind": "video", "placement": {"startFrame": 0, "durationFrames": 120}, "source": {"sourceId": "scene-a", "inFrame": 0, "durationFrames": 120}, "effects": [{"id": "stutter", "effectId": "vibeedit://effect/random-frame-stutter", "enabled": True, "params": {"seed": 17, "windowFrames": 4, "intensity": 0.28}, "implementationVersion": "0.1.0"}]},
                        {"id": "clip-b", "kind": "video", "placement": {"startFrame": 90, "durationFrames": 120}, "source": {"sourceId": "scene-b", "inFrame": 0, "durationFrames": 120}, "effects": []},
                        {"id": "crossfade", "kind": "transition", "placement": {"startFrame": 90, "durationFrames": 30}, "transitionId": "vibeedit://transition/crossfade", "fromItemId": "clip-a", "toItemId": "clip-b", "params": {"curve": "linear"}, "implementationVersion": "0.1.0"},
                    ],
                },
                {"id": "M1", "kind": "motion", "order": 10, "items": [_motion("title", 0, 70, "REVISION / ZERO", "SYSTEM UNDER PRESSURE", "#f3ff70"), _motion("chapter", 72, 78, "CUT. LAYER. REBUILD.", "EVERY FRAME ACCOUNTED FOR", "#7be7ff"), _motion("end", 152, 58, "STAY IN SYNC", "PICTURE + SOUND", "#ff729f")]},
                {
                    "id": "A1",
                    "kind": "audio",
                    "order": 0,
                    "items": [
                        {"id": "music-bed", "kind": "audio", "placement": {"startFrame": 0, "durationFrames": 210}, "source": {"sourceId": "music", "inFrame": 0, "durationFrames": 210}, "role": "music", "gainDb": -8, "pan": 0, "fadeInFrames": 8, "fadeOutFrames": 12, "effects": []},
                        _sfx("opening-hit", 8, 18, 62, -13, 101),
                        _sfx("transition-hit", 90, 18, 78, -11, 102),
                        _sfx("final-hit", 174, 18, 54, -12, 103),
                    ],
                },
            ]
        },
        "artifacts": {"masks": [], "tracking": [], "analysis": []},
        "cache": {"enabled": True, "namespace": f"revision-stress-{RUN_ID}"},
        "audio": {"targetLufs": -16, "truePeakDb": -1, "preventImmediateSfxRepeat": True, "ducking": {"musicUnderSfxDb": -3}},
        "render": {"backend": "mixed", "htmlBackend": "chromium", "threads": 1, "output": {"uri": "revision.mp4", "container": "mp4", "videoCodec": "h264", "audioCodec": "aac", "pixelFormat": "yuv420p"}, "deterministic": True},
        "verification": {"durationFrames": 210, "width": WIDTH, "height": HEIGHT, "frameRate": {"numerator": FPS, "denominator": 1}, "hasVideo": True, "hasAudio": True, "maxDurationDriftFrames": 1},
        "provenance": {"generator": "vibeedit-revision-stress-test", "generatorVersion": "1.0.0", "createdAt": "2026-07-17T00:00:00Z", "schemaSource": "schema/composition.schema.json", "catalogVersion": "0.1.0", "skillPackages": ["vibeedit://skill/vibeedit-lead-editor", "vibeedit://skill/vibeedit-project-json-editor"]},
    }


def _revisions() -> list[dict]:
    current = _base_spec()
    revisions = [_revision("baseline", "Baseline hybrid edit", ["baseline"], current)]

    current = copy.deepcopy(current)
    _item(current, "title")["props"]["html"] = _html("REVISION / ONE", "COPY CHANGED, TIMING LOCKED")
    revisions.append(_revision("text-copy", "Change headline copy", ["text-change"], current))

    current = copy.deepcopy(current)
    _item(current, "title")["props"]["css"] = _css("#ffcf5a", style="outline")
    revisions.append(_revision("text-style", "Change headline color and treatment", ["text-style", "effect-style"], current))

    current = copy.deepcopy(current)
    _track(current, "M1")["items"].append(_motion("callout", 112, 38, "CACHE HIT", "ONLY THIS WINDOW IS NEW", "#ffffff", compact=True))
    revisions.append(_revision("add-callout", "Add a timed callout", ["text-add"], current))

    current = copy.deepcopy(current)
    _item(current, "callout")["placement"] = {"startFrame": 124, "durationFrames": 50}
    _item(current, "callout")["props"]["html"] = _html("MOVE IT", "TIMING + COPY REVISED", compact=True)
    revisions.append(_revision("move-callout", "Move and rewrite the callout", ["text-timing", "text-change"], current))

    current = copy.deepcopy(current)
    _track(current, "M1")["items"] = [item for item in _track(current, "M1")["items"] if item["id"] != "callout"]
    revisions.append(_revision("remove-callout", "Remove the callout", ["text-remove"], current))

    current = copy.deepcopy(current)
    clip_b = _item(current, "clip-b")
    clip_b["placement"] = {"startFrame": 102, "durationFrames": 108}
    clip_b["source"]["durationFrames"] = 108
    transition = _item(current, "crossfade")
    transition["placement"] = {"startFrame": 102, "durationFrames": 18}
    transition["params"] = {"curve": "faster"}
    revisions.append(_revision("transition", "Tighten and move the transition", ["transition-change"], current))

    current = copy.deepcopy(current)
    _item(current, "clip-a")["effects"][0]["params"].update({"seed": 41, "windowFrames": 6, "intensity": 0.72})
    revisions.append(_revision("effect-heavy", "Intensify and retime the stutter effect", ["effect-change"], current))

    current = copy.deepcopy(current)
    _item(current, "clip-a")["effects"][0]["enabled"] = False
    revisions.append(_revision("effect-remove", "Remove the stutter effect", ["effect-remove"], current))

    current = copy.deepcopy(current)
    _track(current, "A1")["items"].append(_sfx("accent-hit", 132, 14, 118, -16, 104))
    revisions.append(_revision("add-sfx", "Add a transition-adjacent sound accent", ["audio-add", "sfx"], current))

    current = copy.deepcopy(current)
    music = _item(current, "music-bed")
    music.update({"gainDb": -13, "pan": -0.2, "fadeInFrames": 18, "fadeOutFrames": 24})
    _item(current, "transition-hit")["gainDb"] = -7
    revisions.append(_revision("audio-mix", "Revise music gain, pan, fades, and impact level", ["audio-change", "mix"], current))

    current = copy.deepcopy(current)
    _item(current, "end")["props"]["html"] = _html("NO DRIFT", "AUDIO REUSED VIDEO UNTOUCHED")
    revisions.append(_revision("final-copy", "Replace the ending message", ["text-change"], current))

    current = copy.deepcopy(current)
    current["render"]["output"]["container"] = "mkv"
    revisions.append(_revision("container", "Change only the output container", ["container-change"], current))

    current = copy.deepcopy(current)
    current["durationFrames"] = 120
    current["verification"]["durationFrames"] = 120
    current["timeline"]["tracks"] = [
        {**track, "items": [item for item in track["items"] if item["id"] not in {"clip-b", "crossfade", "chapter", "end", "final-hit", "accent-hit"}]}
        for track in current["timeline"]["tracks"]
    ]
    music = _item(current, "music-bed")
    music["placement"]["durationFrames"] = 120
    music["source"]["durationFrames"] = 120
    revisions.append(_revision("remove-scene", "Remove the second scene and rebuild the dependent tail", ["scene-remove", "timeline-change", "audio-change"], current))

    current = _base_spec()
    current["cache"]["namespace"] = f"revision-stress-rebuild-{RUN_ID}"
    _item(current, "title")["props"]["html"] = _html("REBUILT", "SCENE + TEXT + SOUND RESTORED")
    _item(current, "clip-a")["effects"][0]["params"]["intensity"] = 0.12
    _item(current, "transition-hit")["gainDb"] = -9
    revisions.append(_revision("broad-rebuild", "Restore and broadly revise the composition", ["scene-add", "text-change", "effect-change", "audio-change", "container-change"], current))

    current = copy.deepcopy(current)
    revisions.append(_revision("no-op", "Submit the same composition without semantic changes", ["no-op"], current))
    return revisions


def _revision(slug: str, label: str, change_classes: list[str], spec: dict) -> dict:
    return {"slug": slug, "label": label, "change_classes": change_classes, "spec": copy.deepcopy(spec)}


def _source(identifier: str, kind: str, name: str, duration: int) -> dict:
    path = SOURCES / name
    return {"id": identifier, "kind": kind, "uri": str(path), "identity": {"algorithm": "sha256", "value": _sha256(path)}, "durationFrames": duration, "license": {"status": "generated", "commercialOutputAllowed": True, "redistributionAllowed": True}}


def _motion(identifier: str, start: int, duration: int, headline: str, subtitle: str, accent: str, compact: bool = False) -> dict:
    return {"id": identifier, "kind": "motion", "placement": {"startFrame": start, "durationFrames": duration}, "componentId": "vibeedit://motion/html-css", "props": {"html": _html(headline, subtitle, compact=compact), "css": _css(accent, compact=compact)}, "renderer": "auto", "transparent": True}


def _html(headline: str, subtitle: str, compact: bool = False) -> str:
    placement = "badge" if compact else "panel"
    return f'<main class="stage"><section class="{placement}"><div class="eyebrow">VIBEEDIT STRESS LAB</div><h1>{headline}</h1><p>{subtitle}</p></section></main>'


def _css(accent: str, compact: bool = False, style: str = "solid") -> str:
    title = f"color:{accent};-webkit-text-stroke:1px rgba(255,255,255,.65)" if style == "outline" else f"color:{accent}"
    size = "46px" if compact else "68px"
    align = "align-items:flex-end;justify-content:flex-end;padding:34px" if compact else "align-items:center;justify-content:center;padding:42px"
    return f"""
html,body{{margin:0;width:100%;height:100%;background:transparent;overflow:hidden;font-family:Arial,sans-serif}}
.stage{{position:absolute;inset:0;display:flex;{align};color:white}}
.panel,.badge{{position:relative;max-width:86%;padding:20px 26px;border:1px solid rgba(255,255,255,.32);background:linear-gradient(135deg,rgba(5,8,16,.82),rgba(5,8,16,.2));backdrop-filter:blur(10px);box-shadow:0 20px 70px rgba(0,0,0,.45);animation:enter .72s cubic-bezier(.16,.8,.2,1) both}}
.badge{{max-width:64%;padding:14px 18px}}
.eyebrow{{font-size:12px;font-weight:800;letter-spacing:.28em;color:rgba(255,255,255,.72);margin-bottom:9px}}
h1{{margin:0;font-size:{size};line-height:.93;letter-spacing:-.045em;{title};text-shadow:0 8px 30px rgba(0,0,0,.55)}}
p{{margin:10px 0 0;font-size:16px;font-weight:700;letter-spacing:.12em;color:white}}
.panel:after,.badge:after{{content:'';position:absolute;left:-1px;bottom:-1px;width:52%;height:3px;background:{accent};box-shadow:0 0 22px {accent}}}
@keyframes enter{{from{{opacity:0;transform:translateY(30px) scale(.96);filter:blur(8px)}}to{{opacity:1;transform:none;filter:none}}}}
"""


def _sfx(identifier: str, start: int, duration: int, frequency: int, gain: int, seed: int) -> dict:
    return {"id": identifier, "kind": "sound_effect", "placement": {"startFrame": start, "durationFrames": duration}, "soundEffectId": "vibeedit://sfx/impact-procedural", "params": {"frequency": frequency}, "gainDb": gain, "variationSeed": seed, "avoidImmediateRepeat": True}


def _track(spec: dict, identifier: str) -> dict:
    return next(track for track in spec["timeline"]["tracks"] if track["id"] == identifier)


def _item(spec: dict, identifier: str) -> dict:
    return next(item for track in spec["timeline"]["tracks"] for item in track["items"] if item["id"] == identifier)


def _compare(output: Path, reference: Path) -> dict:
    result = {"videoExact": _decoded_md5(output, "0:v:0") == _decoded_md5(reference, "0:v:0")}
    output_audio = _has_audio(output)
    reference_audio = _has_audio(reference)
    result["audioPresent"] = output_audio
    if output_audio != reference_audio:
        result.update({"audioExact": False, "audioSampleDelta": None, "audioCorrelation": None, "audioSnrDb": None, "passed": False})
        return result
    if not output_audio:
        result.update({"audioExact": True, "audioSampleDelta": 0, "audioCorrelation": 1.0, "audioSnrDb": None, "passed": result["videoExact"]})
        return result
    left = _decoded_pcm(output)
    right = _decoded_pcm(reference)
    count = min(len(left), len(right))
    dot = sum(int(left[index]) * int(right[index]) for index in range(count))
    left_energy = sum(int(left[index]) ** 2 for index in range(count))
    right_energy = sum(int(right[index]) ** 2 for index in range(count))
    error = sum((int(left[index]) - int(right[index])) ** 2 for index in range(count))
    correlation = dot / (left_energy * right_energy) ** 0.5 if left_energy and right_energy else 1.0
    result.update({"audioExact": left == right, "audioSampleDelta": len(left) - len(right), "audioCorrelation": correlation, "audioSnrDb": 10 * __import__("math").log10(right_energy / error) if error else None})
    result["passed"] = result["videoExact"] and result["audioSampleDelta"] == 0 and correlation >= 0.9999
    return result


def _decoded_md5(path: Path, stream: str) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", stream, "-f", "md5", "-"], capture_output=True, text=True, check=True).stdout.strip()


def _decoded_pcm(path: Path):
    import array

    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", "0:a:0", "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "2", "-ar", "48000", "-"], capture_output=True, check=True)
    samples = array.array("h")
    samples.frombytes(result.stdout)
    return samples


def _has_audio(path: Path) -> bool:
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return bool(result.stdout.strip())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contact_sheet(outputs: list[Path], ratio: float, name: str) -> None:
    thumbnails = []
    for index, output in enumerate(outputs):
        thumbnail = ROOT / f".thumb-{index:02d}.jpg"
        duration = float(json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(output)], capture_output=True, text=True, check=True).stdout)["format"]["duration"])
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{duration * ratio:.6f}", "-i", str(output), "-frames:v", "1", "-vf", "scale=320:180", str(thumbnail)], check=True)
        thumbnails.append(thumbnail)
    inputs = [part for thumbnail in thumbnails for part in ("-i", str(thumbnail))]
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", f"xstack=inputs={len(thumbnails)}:layout=" + "|".join(f"{(index % 4) * 320}_{(index // 4) * 180}" for index in range(len(thumbnails))), "-frames:v", "1", str(REVIEW / name)], check=True)
    for thumbnail in thumbnails:
        thumbnail.unlink(missing_ok=True)


def _review_notes(report: dict) -> str:
    rows = ["| Rev | Change | Mode | Time | Reused/rendered | Clean match |", "|---|---|---:|---:|---:|---:|"]
    for item in report["revisions"]:
        work = item.get("work") or {}
        audio = item["cleanComparison"].get("audioCorrelation")
        rows.append(f"| {item['id']} | {item['label']} | {item['renderMode']} | {item['elapsedSeconds']:.3f}s | {work.get('framesReused', '?')}/{work.get('framesRendered', '?')} | V {item['cleanComparison']['videoExact']} / A {item['cleanComparison']['audioExact']} ({audio:.6f}) |")
    benchmarks = ["\n## Three-trial latency benchmarks\n", "| Class | Incremental mean | Clean mean | Speedup |", "|---|---:|---:|---:|"]
    benchmarks.extend(f"| {item['name']} | {item['incrementalMeanSeconds']:.3f}s | {item['cleanMeanSeconds']:.3f}s | {item['speedup']:.2f}x |" for item in report["benchmarks"])
    return "# VibeEdit revision stress review\n\nOpen the numbered videos in order. Each composition JSON and the machine-readable report are in this same flat folder.\n\n" + "\n".join(rows + benchmarks) + "\n"


def _benchmarks(revisions: list[dict], report: dict) -> list[dict]:
    results = []
    cases = [("bounded-text", 0, 1), ("audio-add", 8, 9), ("cross-container-aac", 11, 12)]
    for name, previous_index, revised_index in cases:
        incremental_samples = []
        clean_samples = []
        for trial in range(3):
            previous = copy.deepcopy(revisions[previous_index]["spec"])
            revised = copy.deepcopy(revisions[revised_index]["spec"])
            previous_output = REVIEW / report["revisions"][previous_index]["output"]["file"]
            prime = None
            if name == "bounded-text":
                namespace = f"stress-benchmark-text-{RUN_ID}-{trial}"
                previous["cache"] = {"enabled": True, "namespace": namespace}
                revised["cache"] = {"enabled": True, "namespace": namespace}
                prime = ROOT / f".benchmark-{name}-{trial}-prime.mp4"
                previous_output = render(previous, prime)
            incremental_output = ROOT / f".benchmark-{name}-{trial}{Path(report['revisions'][revised_index]['output']['file']).suffix}"
            started = time.perf_counter()
            render_revision(previous, revised, previous_output, incremental_output)
            incremental_samples.append(time.perf_counter() - started)
            clean = copy.deepcopy(revised)
            clean["cache"] = {"enabled": False, "namespace": f"stress-benchmark-clean-{name}-{trial}"}
            clean_output = ROOT / f".benchmark-{name}-{trial}-clean{incremental_output.suffix}"
            started = time.perf_counter()
            render(clean, clean_output)
            clean_samples.append(time.perf_counter() - started)
            for output in (prime, incremental_output, clean_output):
                if output is None:
                    continue
                output.unlink(missing_ok=True)
                output.with_suffix(output.suffix + ".vibeedit.json").unlink(missing_ok=True)
        incremental_mean = sum(incremental_samples) / len(incremental_samples)
        clean_mean = sum(clean_samples) / len(clean_samples)
        results.append({"name": name, "incrementalSamplesSeconds": incremental_samples, "cleanSamplesSeconds": clean_samples, "incrementalMeanSeconds": incremental_mean, "cleanMeanSeconds": clean_mean, "speedup": clean_mean / incremental_mean})
    return results


if __name__ == "__main__":
    main()
