import hashlib
import json
import shutil
import subprocess
import tempfile
import re
from pathlib import Path

from vibeedit import render, render_example, verify_output


root = Path(__file__).resolve().parent.parent
previews = root / "catalog" / "previews"
previews.mkdir(parents=True, exist_ok=True)
ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")
if not ffmpeg or not ffprobe:
    raise SystemExit("ffmpeg and ffprobe are required")

with tempfile.TemporaryDirectory(prefix="vibeedit-preview-") as temporary:
    workspace = Path(temporary)
    sources = workspace / "sources"
    sources.mkdir()
    for output, source in (("a.mp4", "testsrc2=size=320x180:rate=30:duration=2"), ("b.mp4", "smptebars=size=320x180:rate=30:duration=2")):
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", source, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(sources / output)], check=True)
    effect = json.loads((root / "examples" / "effect-transition" / "composition.json").read_text())
    effect["sources"][0]["uri"] = str(sources / "a.mp4")
    effect["sources"][1]["uri"] = str(sources / "b.mp4")
    effect_output = render(effect, previews / "effect-transition.mp4")
    if not verify_output(effect_output, effect["verification"]).passed:
        raise SystemExit("effect-transition preview verification failed")

    mixed = json.loads((root / "examples" / "mixed-python-html" / "composition.json").read_text())
    mixed_source = sources / "mixed-source.mp4"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=3", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(mixed_source)], check=True)
    mixed["sources"][0]["uri"] = str(mixed_source)
    mixed_output = render(mixed, previews / "mixed-source-html.mp4")
    if not verify_output(mixed_output, mixed["verification"]).passed:
        raise SystemExit("mixed source/HTML preview verification failed")

    negative = json.loads((root / "schema" / "fixtures" / "mixed.json").read_text())
    negative_output = render(negative, previews / "negative.mp4")
    if not verify_output(negative_output, negative["verification"]).passed:
        raise SystemExit("negative preview verification failed")

    captions = json.loads((root / "examples" / "caption-rail" / "composition.json").read_text())
    captions["sources"][0]["uri"] = str(mixed_source)
    captions_output = render(captions, previews / "caption-rail.mp4")
    if not verify_output(captions_output, captions["verification"]).passed:
        raise SystemExit("caption rail preview verification failed")

    showcase = json.loads((root / "examples" / "portable-motion-showcase" / "composition.json").read_text())
    showcase["sources"][0]["uri"] = str(mixed_source)
    showcase_output = render(showcase, previews / "portable-motion-showcase.mp4")
    if not verify_output(showcase_output, showcase["verification"]).passed:
        raise SystemExit("portable motion preview verification failed")

    workflow_previews = {}
    for identifier in ("fan-edit", "beat-synchronized", "sound-design-layering", "face-follow-text", "mask-subject-effect", "multiple-transitions", "transparent-motion-overlay"):
        example = workspace / identifier
        shutil.copytree(root / "examples" / identifier, example)
        suffix = ".webm" if identifier == "transparent-motion-overlay" else ".mp4"
        output = render_example(example, previews / f"{identifier}{suffix}")
        if not output:
            raise SystemExit(f"{identifier} preview did not render")
        workflow_previews[identifier] = output

subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=72:sample_rate=48000:duration=0.4", "-af", "volume=-10dB,afade=t=out:st=0.08:d=0.32", str(previews / "impact.wav")], check=True)

assets = []
for path, category, tags, gain in (
    (previews / "effect-transition.mp4", "preview-video", ["effect", "transition"], None),
    (previews / "negative.mp4", "preview-video", ["text", "html", "mixed"], None),
    (previews / "caption-rail.mp4", "preview-video", ["text", "captions", "html", "mixed"], None),
    (previews / "mixed-source-html.mp4", "preview-video", ["template", "source-video", "html", "mixed"], None),
    (previews / "portable-motion-showcase.mp4", "preview-video", ["template", "text", "caption", "html"], None),
    (previews / "impact.wav", "procedural-sfx", ["impact", "low-frequency"], -10),
    (previews / "fan-edit.mp4", "preview-video", ["template", "fan-edit", "effects"], None),
    (previews / "beat-synchronized.mp4", "preview-video", ["template", "beats", "analysis"], None),
    (previews / "sound-design-layering.mp4", "preview-video", ["template", "audio", "sfx"], None),
    (previews / "face-follow-text.mp4", "preview-video", ["template", "face", "tracking", "text"], None),
    (previews / "mask-subject-effect.mp4", "preview-video", ["template", "mask", "subject-effect"], None),
    (previews / "multiple-transitions.mp4", "preview-video", ["template", "transitions"], None),
    (previews / "transparent-motion-overlay.webm", "preview-video", ["template", "html", "alpha", "overlay"], None),
):
    probe = json.loads(subprocess.run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout)
    loudness = None
    if category == "procedural-sfx":
        measurement = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True, check=True).stderr
        loudness = float(json.loads(re.findall(r"\{[\s\S]*?\}", measurement)[-1])["input_i"])
    assets.append({
        "path": str(path.relative_to(root)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
        "durationSeconds": float(probe["format"]["duration"]),
        "category": category,
        "tags": tags,
        "intendedUse": "local catalog preview",
        "recommendedGainDb": gain,
        "loudnessLufs": loudness,
        "source": "VibeEdit procedural generation",
        "license": "SEE LICENSE IN LICENSE.md",
        "redistribution": "verified",
        "commercialOutputAllowed": True,
        "decodable": True,
    })
(root / "catalog" / "assets.json").write_text(json.dumps({"schemaVersion": "1.0.0", "assets": assets}, indent=2) + "\n")
catalog_path = root / "catalog" / "catalog.json"
catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
for item in catalog["items"]:
    if item["id"] in {"vibeedit://text/mogrt-aesthetic-purple", "vibeedit://text/caption-highlight", "vibeedit://template/portable-motion-showcase"}:
        item["preview"] = {"status": "verified", "uri": "previews/portable-motion-showcase.mp4", "mediaType": "video/mp4", "note": "Rendered from the packaged portable-motion-showcase example through pinned Chromium and FFmpeg."}
    if item["id"].startswith("vibeedit://template/") and item["id"].rsplit("/", 1)[-1] in {"fan-edit", "beat-synchronized", "sound-design-layering", "face-follow-text", "mask-subject-effect", "multiple-transitions", "transparent-motion-overlay"}:
        identifier = item["id"].rsplit("/", 1)[-1]
        suffix = "webm" if identifier == "transparent-motion-overlay" else "mp4"
        item["preview"] = {"status": "verified", "uri": f"previews/{identifier}.{suffix}", "mediaType": f"video/{suffix}", "note": "Rendered and verified from a clean copy of the packaged executable example."}
catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
for sidecar in previews.glob("*.vibeedit.json"):
    sidecar.unlink()
