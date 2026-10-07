"""Reproducible preparation for codecs missing from the pinned CEF build.

Files remain artifacts; Chromium still owns presentation and composition. The
opaque SDR path preserves decoded YUV, source PTS and rotation, and makes every
VP9 frame independently decodable. Originals and authoring files are untouched.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from fractions import Fraction
from pathlib import Path


def prepare_cef_media(source: Path, browser_version, processes, canceled):
    from vibeedit.browser_render import BrowserRenderError, _sha256

    inspected = json.loads(
        media_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(source),
            ],
            processes=processes,
            canceled=canceled,
            timeout=30,
        )
    )
    video = next(
        (stream for stream in inspected["streams"] if stream["codec_type"] == "video"),
        None,
    )
    if not video or video["codec_name"] in {"vp8", "vp9", "av1", "theora"}:
        return source, None
    if video.get("pix_fmt") not in {"yuv420p", "nv12"} or video.get(
        "color_transfer"
    ) in {"smpte2084", "arib-std-b67"}:
        raise BrowserRenderError(
            f"Automatic CEF normalization currently requires opaque 8-bit SDR 4:2:0; prepare {source.name} explicitly"
        )
    started = time.perf_counter()
    version = (
        media_command(["ffmpeg", "-version"], processes, canceled)
        .decode()
        .splitlines()[0]
    )
    identity = _sha256(source)
    recipe = {
        "sourceSha256": identity,
        "ffmpeg": version,
        "browser": browser_version,
        "codec": "vp9",
        "losslessDecodedYUV": True,
        "allIntra": True,
        "container": "mp4",
        "timeBase": video["time_base"],
        "audio": "opus if present",
        "revision": 2,
    }
    key = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()
    cache = Path.home() / "Library/Caches/vibeedit/browser-media"
    cache.mkdir(parents=True, exist_ok=True)
    output = cache / (key + ".mp4")
    metadata = cache / (key + ".json")
    cached = json.loads(metadata.read_text()) if metadata.is_file() else None
    if output.is_file() and cached and _sha256(output) == cached["preparedSha256"]:
        return output, {
            **cached,
            "cacheHit": True,
            "preparationSeconds": time.perf_counter() - started,
        }
    with tempfile.TemporaryDirectory(
        prefix="vibeedit-normalize-", dir=cache
    ) as temporary:
        staged = Path(temporary) / "video.mp4"
        command = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-copyts",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libvpx-vp9",
            "-lossless",
            "1",
            "-g",
            "1",
            "-deadline",
            "realtime",
            "-cpu-used",
            "6",
            "-row-mt",
            "1",
            "-threads",
            "4",
            "-fps_mode",
            "passthrough",
            "-enc_time_base:v",
            video["time_base"],
            "-video_track_timescale",
            str(Fraction(video["time_base"]).denominator),
            "-c:a",
            "libopus",
            "-b:a",
            "192k",
        ]
        for field, flag in [
            ("color_space", "-colorspace"),
            ("color_transfer", "-color_trc"),
            ("color_primaries", "-color_primaries"),
            ("color_range", "-color_range"),
        ]:
            if video.get(field) not in {None, "unknown", "unspecified"}:
                command += [flag, video[field]]
        media_command(
            [*command, "-movflags", "+faststart", str(staged)],
            processes,
            canceled,
            timeout=120,
        )
        if _sha256(source) != identity:
            raise BrowserRenderError("Source changed during media preparation")
        record = {
            **recipe,
            "originalCodec": video["codec_name"],
            "originalDimensions": [video["width"], video["height"]],
            "preparedSha256": _sha256(staged),
            "cacheHit": False,
            "preparationSeconds": time.perf_counter() - started,
        }
        os.replace(staged, output)
        metadata.write_text(json.dumps(record, indent=2) + "\n")
    return output, record


def media_command(command, processes, canceled, timeout=30):
    from vibeedit.browser_render import BrowserRenderError

    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        processes.add(process)
        try:
            if canceled.is_set():
                process.kill()
            output = process.communicate(timeout=timeout)[0]
            if process.returncode:
                errors.seek(0)
                raise BrowserRenderError(
                    f"Media preparation failed: {errors.read(4096).decode(errors='replace')}"
                )
            return output
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            processes.discard(process)


SOURCE_HINT_ADAPTER = r"""(() => {
  if (globalThis.__veNormalizeSourceHints) return;
  globalThis.__veSourceHints = [];
  const inspect = node => {
    if (node.nodeType !== 1) return;
    const sources = node.matches('source') ? [node] : [...node.querySelectorAll('source')];
    for (const source of sources) {
      const type = source.getAttribute('type');
      const src = new URL(source.src, document.baseURI);
      if (!type || src.origin !== location.origin ||
          !/\.(mp4|m4v|mov|mkv|avi|mts|ts|mxf)$/i.test(src.pathname) ||
          !/avc1|hvc1|hev1|mp4v/i.test(type) ||
          document.createElement('video').canPlayType(type)) continue;
      if (globalThis.__veSourceHints.length >= 100) throw new Error('Too many unsupported source type hints');
      globalThis.__veSourceHints.push({src: src.href, originalType: type});
      source.removeAttribute('type');
      if (source.parentElement instanceof HTMLMediaElement) source.parentElement.load();
    }
  };
  globalThis.__veNormalizeSourceHints = () => inspect(document.documentElement);
  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(inspect)))
    .observe(document, {childList: true, subtree: true});
})()"""
