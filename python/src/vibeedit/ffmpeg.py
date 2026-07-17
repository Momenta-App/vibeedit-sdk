from __future__ import annotations

import json
import shutil
import subprocess
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

from vibeedit.spec import JSONObject
from vibeedit.effects import video_effect_filter
from vibeedit.transitions import transition_filter


class FFmpegUnavailableError(RuntimeError):
    pass


class FFmpegRenderError(RuntimeError):
    pass


def ffmpeg_path() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise FFmpegUnavailableError("ffmpeg was not found on PATH; run `vibeedit doctor` for setup guidance")
    return executable


def ffprobe_path() -> str:
    executable = shutil.which("ffprobe")
    if not executable:
        raise FFmpegUnavailableError("ffprobe was not found on PATH; run `vibeedit doctor` for setup guidance")
    return executable


def probe(path: str | Path) -> JSONObject:
    result = subprocess.run(
        [ffprobe_path(), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise FFmpegRenderError(result.stderr.strip() or f"ffprobe failed with exit code {result.returncode}")
    return json.loads(result.stdout)


def render_generated(spec: JSONObject, output: str | Path | None = None) -> Path:
    canvas = spec["canvas"]
    rate = canvas["frameRate"]
    duration = Fraction(spec["durationFrames"] * rate["denominator"], rate["numerator"])
    destination = Path(output or spec["render"]["output"]["uri"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    unsupported = [
        item
        for track in spec["timeline"]["tracks"]
        for item in track["items"]
        if item["kind"] in {"video", "image", "motion", "transition"}
    ]
    if unsupported:
        kinds = ", ".join(sorted({item["kind"] for item in unsupported}))
        raise FFmpegRenderError(f"generated FFmpeg backend cannot render {kinds}; select the mixed dispatcher")

    color = canvas.get("backgroundColor", "#000000").removeprefix("#")
    frame_rate = f'{rate["numerator"]}/{rate["denominator"]}'
    command = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f'color=c=0x{color}:s={canvas["width"]}x{canvas["height"]}:r={frame_rate}:d={float(duration):.9f}',
    ]
    sound_effects = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "sound_effect"]
    for item in sound_effects:
        frequency = float(item["params"].get("frequency", 72))
        effect_duration = Fraction(item["placement"]["durationFrames"] * rate["denominator"], rate["numerator"])
        command.extend(["-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate={canvas.get('audioSampleRate', 48000)}:duration={float(effect_duration):.9f}"])

    if sound_effects:
        chains = []
        labels = []
        for index, item in enumerate(sound_effects, 1):
            delay = round(item["placement"]["startFrame"] * 1000 * rate["denominator"] / rate["numerator"])
            effect_duration = item["placement"]["durationFrames"] * rate["denominator"] / rate["numerator"]
            fade_start = max(0.0, effect_duration * 0.2)
            fade_duration = max(0.001, effect_duration - fade_start)
            label = f"sfx{index}"
            chains.append(f"[{index}:a]volume={item.get('gainDb', 0)}dB,afade=t=out:st={fade_start:.6f}:d={fade_duration:.6f},adelay={delay}|{delay}[{label}]")
            labels.append(f"[{label}]")
        chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad,atrim=0:{float(duration):.9f}[audio]")
        command.extend(["-filter_complex", ";".join(chains), "-map", "0:v:0", "-map", "[audio]"])
    else:
        command.extend(["-map", "0:v:0", "-an"])

    output_settings = spec["render"]["output"]
    codecs = {"h264": "libx264", "hevc": "libx265", "vp9": "libvpx-vp9", "av1": "libaom-av1"}
    command.extend(
        [
            "-c:v",
            codecs.get(output_settings["videoCodec"], output_settings["videoCodec"]),
            "-pix_fmt",
            output_settings.get("pixelFormat", canvas.get("pixelFormat", "yuv420p")),
            "-r",
            frame_rate,
            "-frames:v",
            str(spec["durationFrames"]),
            *_thread_arguments(spec, complex_filter=bool(sound_effects)),
            "-map_metadata",
            "-1",
        ]
    )
    if sound_effects:
        command.extend(["-c:a", output_settings.get("audioCodec", "aac"), "-ar", str(canvas.get("audioSampleRate", 48000))])
    if output_settings["container"] == "mp4":
        command.extend(["-movflags", "+faststart"])
    command.append(str(destination))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise FFmpegRenderError(result.stderr.strip() or f"ffmpeg failed with exit code {result.returncode}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise FFmpegRenderError("ffmpeg returned success without a non-empty output")
    return destination


def render_frame_sequence(spec: JSONObject, sequence: str | Path, output: str | Path) -> Path:
    destination = Path(output)
    command = _frame_encoder_command(spec, ["-framerate", _frame_rate(spec), "-i", str(sequence)], destination)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise FFmpegRenderError(result.stderr.strip() or f"ffmpeg failed with exit code {result.returncode}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise FFmpegRenderError("ffmpeg returned success without a non-empty output")
    return destination


def render_audio_mix(spec: JSONObject, output: str | Path, base: str | Path = ".", *, audio_codec: str = "flac") -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rate = spec["canvas"]["frameRate"]
    sources = {source["id"]: source for source in spec["sources"]}
    audio_clips = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "audio"]
    sound_effects = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "sound_effect"]
    if not audio_clips and not sound_effects:
        raise FFmpegRenderError("audio-only revision requires at least one audio clip or sound effect")
    command = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y"]
    for item in audio_clips:
        source = sources.get(item["source"]["sourceId"])
        if not source:
            raise FFmpegRenderError(f"missing source: {item['source']['sourceId']}")
        path = Path(source["uri"])
        path = path if path.is_absolute() else Path(base) / path
        if not path.is_file():
            raise FFmpegRenderError(f"source file does not exist: {path}")
        command.extend(["-i", str(path)])
    for item in sound_effects:
        duration = Fraction(item["placement"]["durationFrames"] * rate["denominator"], rate["numerator"])
        command.extend(["-f", "lavfi", "-i", f"sine=frequency={float(item['params'].get('frequency', 72))}:sample_rate={spec['canvas'].get('audioSampleRate', 48000)}:duration={float(duration):.9f}"])
    chains = []
    labels = []
    for index, item in enumerate(audio_clips):
        start = Fraction(item["source"]["inFrame"] * rate["denominator"], rate["numerator"])
        duration = Fraction(item["source"]["durationFrames"] * rate["denominator"], rate["numerator"])
        delay = round(item["placement"]["startFrame"] * 1000 * rate["denominator"] / rate["numerator"])
        pan = max(-1.0, min(1.0, float(item.get("pan", 0))))
        filters = [f"atrim=start={float(start):.9f}:duration={float(duration):.9f}", "asetpts=PTS-STARTPTS", "aformat=channel_layouts=stereo", f"volume={item.get('gainDb', 0)}dB", f"pan=stereo|c0={1 - max(0.0, pan):.6f}*c0|c1={1 + min(0.0, pan):.6f}*c1"]
        fade_in = item.get("fadeInFrames", 0) * rate["denominator"] / rate["numerator"]
        fade_out = item.get("fadeOutFrames", 0) * rate["denominator"] / rate["numerator"]
        if fade_in:
            filters.append(f"afade=t=in:st=0:d={fade_in:.9f}")
        if fade_out:
            filters.append(f"afade=t=out:st={max(0.0, float(duration) - fade_out):.9f}:d={fade_out:.9f}")
        filters.append(f"adelay={delay}|{delay}")
        label = f"audio{index}"
        chains.append(f"[{index}:a]{','.join(filters)}[{label}]")
        labels.append(f"[{label}]")
    for index, item in enumerate(sound_effects, len(audio_clips)):
        delay = round(item["placement"]["startFrame"] * 1000 * rate["denominator"] / rate["numerator"])
        duration = item["placement"]["durationFrames"] * rate["denominator"] / rate["numerator"]
        fade_start = max(0.0, duration * 0.2)
        fade_duration = max(0.001, duration - fade_start)
        label = f"sfx{index}"
        chains.append(f"[{index}:a]volume={item.get('gainDb', 0)}dB,afade=t=out:st={fade_start:.6f}:d={fade_duration:.6f},adelay={delay}|{delay}[{label}]")
        labels.append(f"[{label}]")
    total = Fraction(spec["durationFrames"] * rate["denominator"], rate["numerator"])
    chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,aresample=async=1:first_pts=0,apad,atrim=0:{float(total):.9f}[audio]")
    command.extend(["-filter_complex", ";".join(chains), "-map", "[audio]", "-c:a", audio_codec, "-ar", str(spec["canvas"].get("audioSampleRate", 48000)), "-map_metadata", "-1", str(destination)])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise FFmpegRenderError(result.stderr.strip() or f"ffmpeg failed with exit code {result.returncode}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise FFmpegRenderError("ffmpeg returned success without a non-empty audio mix")
    return destination


@contextmanager
def frame_stream_encoder(spec: JSONObject, output: str | Path):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = _frame_encoder_command(spec, ["-f", "image2pipe", "-framerate", _frame_rate(spec), "-vcodec", "png", "-i", "pipe:0"], destination)
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        process.terminate()
        raise FFmpegRenderError("ffmpeg did not expose the frame-stream pipes")
    try:
        yield process.stdin
    except BaseException:
        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
        raise
    process.stdin.close()
    error = process.stderr.read().decode(errors="replace").strip()
    return_code = process.wait()
    if return_code:
        raise FFmpegRenderError(error or f"ffmpeg failed with exit code {return_code}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise FFmpegRenderError("ffmpeg returned success without a non-empty output")


def _frame_rate(spec: JSONObject) -> str:
    rate = spec["canvas"]["frameRate"]
    return f'{rate["numerator"]}/{rate["denominator"]}'


def _thread_arguments(spec: JSONObject, *, complex_filter: bool = False) -> list[str]:
    threads = str(spec["render"].get("threads", 1))
    return (["-filter_complex_threads", threads] if complex_filter else []) + ["-threads", threads]


def _frame_encoder_command(spec: JSONObject, input_arguments: list[str], destination: Path) -> list[str]:
    canvas = spec["canvas"]
    rate = canvas["frameRate"]
    duration = Fraction(spec["durationFrames"] * rate["denominator"], rate["numerator"])
    frame_rate = _frame_rate(spec)
    command = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", *input_arguments]
    sound_effects = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "sound_effect"]
    for item in sound_effects:
        frequency = float(item["params"].get("frequency", 72))
        effect_duration = Fraction(item["placement"]["durationFrames"] * rate["denominator"], rate["numerator"])
        command.extend(["-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate={canvas.get('audioSampleRate', 48000)}:duration={float(effect_duration):.9f}"])
    if sound_effects:
        chains = []
        labels = []
        for index, item in enumerate(sound_effects, 1):
            delay = round(item["placement"]["startFrame"] * 1000 * rate["denominator"] / rate["numerator"])
            effect_duration = item["placement"]["durationFrames"] * rate["denominator"] / rate["numerator"]
            fade_start = max(0.0, effect_duration * 0.2)
            fade_duration = max(0.001, effect_duration - fade_start)
            label = f"sfx{index}"
            chains.append(f"[{index}:a]volume={item.get('gainDb', 0)}dB,afade=t=out:st={fade_start:.6f}:d={fade_duration:.6f},adelay={delay}|{delay}[{label}]")
            labels.append(f"[{label}]")
        chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad,atrim=0:{float(duration):.9f}[audio]")
        command.extend(["-filter_complex", ";".join(chains), "-map", "0:v:0", "-map", "[audio]"])
    else:
        command.extend(["-map", "0:v:0", "-an"])
    settings = spec["render"]["output"]
    codecs = {"h264": "libx264", "hevc": "libx265", "vp9": "libvpx-vp9", "av1": "libaom-av1"}
    command.extend(["-c:v", codecs.get(settings["videoCodec"], settings["videoCodec"]), "-pix_fmt", settings.get("pixelFormat", "yuv420p"), "-r", frame_rate, "-frames:v", str(spec["durationFrames"]), *_thread_arguments(spec, complex_filter=bool(sound_effects)), "-map_metadata", "-1"])
    if sound_effects:
        command.extend(["-c:a", settings.get("audioCodec", "aac"), "-ar", str(canvas.get("audioSampleRate", 48000))])
    if settings["container"] == "mp4":
        command.extend(["-movflags", "+faststart"])
    command.append(str(destination))
    return command


def render_overlay_sequence(spec: JSONObject, sequence: str | Path, output: str | Path, base: str | Path = ".") -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = _overlay_encoder_command(spec, ["-framerate", _frame_rate(spec), "-i", str(sequence)], destination, base)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise FFmpegRenderError(result.stderr.strip() or f"ffmpeg failed with exit code {result.returncode}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise FFmpegRenderError("ffmpeg returned success without a non-empty output")
    return destination


@contextmanager
def overlay_frame_stream_encoder(spec: JSONObject, output: str | Path, base: str | Path = "."):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = _overlay_encoder_command(
        spec,
        ["-f", "image2pipe", "-framerate", _frame_rate(spec), "-vcodec", "png", "-i", "pipe:0"],
        destination,
        base,
    )
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        process.terminate()
        raise FFmpegRenderError("ffmpeg did not expose the overlay frame-stream pipes")
    try:
        yield process.stdin
    except BaseException:
        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)
        raise
    process.stdin.close()
    error = process.stderr.read().decode(errors="replace").strip()
    return_code = process.wait()
    if return_code:
        raise FFmpegRenderError(error or f"ffmpeg failed with exit code {return_code}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise FFmpegRenderError("ffmpeg returned success without a non-empty output")


def _overlay_encoder_command(spec: JSONObject, overlay_input_arguments: list[str], destination: Path, base: str | Path) -> list[str]:
    canvas = spec["canvas"]
    rate = canvas["frameRate"]
    frame_rate = f'{rate["numerator"]}/{rate["denominator"]}'
    total = Fraction(spec["durationFrames"] * rate["denominator"], rate["numerator"])
    clip = next(item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "video")
    if clip["placement"]["startFrame"] != 0 or clip["placement"]["durationFrames"] != spec["durationFrames"]:
        raise FFmpegRenderError("mixed source-video overlay currently requires one full-duration clip starting at frame zero")
    source = next((item for item in spec["sources"] if item["id"] == clip["source"]["sourceId"]), None)
    if not source:
        raise FFmpegRenderError(f'missing source: {clip["source"]["sourceId"]}')
    source_path = Path(source["uri"])
    source_path = source_path if source_path.is_absolute() else Path(base) / source_path
    if not source_path.is_file():
        raise FFmpegRenderError(f"source file does not exist: {source_path}")

    command = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_path), *overlay_input_arguments]
    sound_effects = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "sound_effect"]
    for item in sound_effects:
        duration = Fraction(item["placement"]["durationFrames"] * rate["denominator"], rate["numerator"])
        command.extend(["-f", "lavfi", "-i", f"sine=frequency={float(item['params'].get('frequency', 72))}:sample_rate={canvas.get('audioSampleRate', 48000)}:duration={float(duration):.9f}"])

    start = Fraction(clip["source"]["inFrame"] * rate["denominator"], rate["numerator"])
    duration = Fraction(clip["source"]["durationFrames"] * rate["denominator"], rate["numerator"])
    video_filters = [
        f"trim=start={float(start):.9f}:duration={float(duration):.9f}",
        "setpts=PTS-STARTPTS",
        f"fps={frame_rate}",
        f"scale={canvas['width']}:{canvas['height']}:force_original_aspect_ratio=decrease",
        f"pad={canvas['width']}:{canvas['height']}:(ow-iw)/2:(oh-ih)/2:color=black",
        "setsar=1",
        "format=yuv420p",
        "settb=AVTB",
    ]
    video_filters.extend(
        video_effect_filter(effect["effectId"], effect.get("params", {}))
        for effect in clip.get("effects", [])
        if effect.get("enabled", True)
    )
    chains = [
        f"[0:v]{','.join(video_filters)}[base]",
        f"[1:v]fps={frame_rate},format=rgba,setpts=PTS-STARTPTS,settb=AVTB[overlay]",
        "[base][overlay]overlay=0:0:shortest=1:format=auto[video]",
    ]
    has_source_audio = any(stream.get("codec_type") == "audio" for stream in probe(source_path).get("streams", []))
    audio_labels = []
    if has_source_audio:
        chains.append(f"[0:a]atrim=start={float(start):.9f}:duration={float(duration):.9f},asetpts=PTS-STARTPTS,apad,atrim=0:{float(total):.9f}[sourceaudio]")
        audio_labels.append("[sourceaudio]")
    for index, item in enumerate(sound_effects, 2):
        delay = round(item["placement"]["startFrame"] * 1000 * rate["denominator"] / rate["numerator"])
        effect_duration = item["placement"]["durationFrames"] * rate["denominator"] / rate["numerator"]
        fade_start = max(0.0, effect_duration * 0.2)
        fade_duration = max(0.001, effect_duration - fade_start)
        label = f"sfx{index}"
        chains.append(f"[{index}:a]volume={item.get('gainDb', 0)}dB,afade=t=out:st={fade_start:.6f}:d={fade_duration:.6f},adelay={delay}|{delay}[{label}]")
        audio_labels.append(f"[{label}]")
    audio_label = None
    if len(audio_labels) > 1:
        chains.append(f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:duration=longest:normalize=0,apad,atrim=0:{float(total):.9f}[audio]")
        audio_label = "audio"
    if len(audio_labels) == 1:
        audio_label = audio_labels[0][1:-1]

    command.extend(["-filter_complex", ";".join(chains), "-map", "[video]"])
    command.extend(["-map", f"[{audio_label}]"] if audio_label else ["-an"])
    settings = spec["render"]["output"]
    codecs = {"h264": "libx264", "hevc": "libx265", "vp9": "libvpx-vp9", "av1": "libaom-av1"}
    command.extend(["-c:v", codecs.get(settings["videoCodec"], settings["videoCodec"]), "-pix_fmt", settings.get("pixelFormat", "yuv420p"), "-r", frame_rate, "-frames:v", str(spec["durationFrames"]), *_thread_arguments(spec, complex_filter=True), "-map_metadata", "-1"])
    if audio_label:
        command.extend(["-c:a", settings.get("audioCodec", "aac"), "-ar", str(canvas.get("audioSampleRate", 48000))])
    if settings["container"] == "mp4":
        command.extend(["-movflags", "+faststart"])
    command.append(str(destination))
    return command


def render_media(spec: JSONObject, output: str | Path | None = None, base: str | Path = ".") -> Path:
    canvas = spec["canvas"]
    rate = canvas["frameRate"]
    frame_rate = f'{rate["numerator"]}/{rate["denominator"]}'
    destination = Path(output or spec["render"]["output"]["uri"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    sources = {source["id"]: source for source in spec["sources"]}
    clips = sorted(
        (item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "video"),
        key=lambda item: item["placement"]["startFrame"],
    )
    if not 1 <= len(clips) <= 2:
        raise FFmpegRenderError("alpha media renderer supports one or two video clips")
    transitions = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "transition"]
    if len(clips) == 2 and len(transitions) != 1:
        raise FFmpegRenderError("two-clip alpha render requires exactly one transition")
    command = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y"]
    for clip in clips:
        source = sources.get(clip["source"]["sourceId"])
        if not source:
            raise FFmpegRenderError(f"missing source: {clip['source']['sourceId']}")
        path = Path(source["uri"])
        path = path if path.is_absolute() else Path(base) / path
        if not path.is_file():
            raise FFmpegRenderError(f"source file does not exist: {path}")
        command.extend(["-i", str(path)])
    audio_clips = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "audio"]
    for item in audio_clips:
        source = sources.get(item["source"]["sourceId"])
        if not source:
            raise FFmpegRenderError(f"missing source: {item['source']['sourceId']}")
        path = Path(source["uri"])
        path = path if path.is_absolute() else Path(base) / path
        if not path.is_file():
            raise FFmpegRenderError(f"source file does not exist: {path}")
        command.extend(["-i", str(path)])
    sound_effects = [item for track in spec["timeline"]["tracks"] for item in track["items"] if item["kind"] == "sound_effect"]
    for item in sound_effects:
        duration = Fraction(item["placement"]["durationFrames"] * rate["denominator"], rate["numerator"])
        command.extend(["-f", "lavfi", "-i", f"sine=frequency={float(item['params'].get('frequency', 72))}:sample_rate={canvas.get('audioSampleRate', 48000)}:duration={float(duration):.9f}"])

    chains = []
    for index, clip in enumerate(clips):
        start = Fraction(clip["source"]["inFrame"] * rate["denominator"], rate["numerator"])
        duration = Fraction(clip["source"]["durationFrames"] * rate["denominator"], rate["numerator"])
        filters = [
            f"trim=start={float(start):.9f}:duration={float(duration):.9f}",
            "setpts=PTS-STARTPTS",
            f"fps={frame_rate}",
            f"scale={canvas['width']}:{canvas['height']}:force_original_aspect_ratio=decrease",
            f"pad={canvas['width']}:{canvas['height']}:(ow-iw)/2:(oh-ih)/2:color=black",
            "setsar=1",
            "format=yuv420p",
            "settb=AVTB",
        ]
        filters.extend(
            video_effect_filter(effect["effectId"], effect.get("params", {}))
            for effect in clip.get("effects", [])
            if effect.get("enabled", True)
        )
        chains.append(f"[{index}:v]{','.join(filters)}[clip{index}]")

    video_label = "clip0"
    if len(clips) == 2:
        transition = transitions[0]
        offset_frames = transition["placement"]["startFrame"] - clips[0]["placement"]["startFrame"]
        chains.append(
            f"[clip0][clip1]{transition_filter(transition['transitionId'], transition.get('params', {}), duration_frames=transition['placement']['durationFrames'], offset_frames=offset_frames, numerator=rate['numerator'], denominator=rate['denominator'])}[video]"
        )
        video_label = "video"

    audio_label = None
    labels = []
    for offset, item in enumerate(audio_clips, len(clips)):
        start = Fraction(item["source"]["inFrame"] * rate["denominator"], rate["numerator"])
        duration = Fraction(item["source"]["durationFrames"] * rate["denominator"], rate["numerator"])
        delay = round(item["placement"]["startFrame"] * 1000 * rate["denominator"] / rate["numerator"])
        pan = max(-1.0, min(1.0, float(item.get("pan", 0))))
        filters = [
            f"atrim=start={float(start):.9f}:duration={float(duration):.9f}",
            "asetpts=PTS-STARTPTS",
            "aformat=channel_layouts=stereo",
            f"volume={item.get('gainDb', 0)}dB",
            f"pan=stereo|c0={1 - max(0.0, pan):.6f}*c0|c1={1 + min(0.0, pan):.6f}*c1",
        ]
        fade_in = item.get("fadeInFrames", 0) * rate["denominator"] / rate["numerator"]
        fade_out = item.get("fadeOutFrames", 0) * rate["denominator"] / rate["numerator"]
        if fade_in:
            filters.append(f"afade=t=in:st=0:d={fade_in:.9f}")
        if fade_out:
            filters.append(f"afade=t=out:st={max(0.0, float(duration) - fade_out):.9f}:d={fade_out:.9f}")
        filters.append(f"adelay={delay}|{delay}")
        label = f"clipaudio{offset}"
        chains.append(f"[{offset}:a]{','.join(filters)}[{label}]")
        labels.append(f"[{label}]")
    if sound_effects:
        for offset, item in enumerate(sound_effects, len(clips) + len(audio_clips)):
            delay = round(item["placement"]["startFrame"] * 1000 * rate["denominator"] / rate["numerator"])
            duration = item["placement"]["durationFrames"] * rate["denominator"] / rate["numerator"]
            fade_start = max(0.0, duration * 0.2)
            fade_duration = max(0.001, duration - fade_start)
            label = f"sfx{offset}"
            chains.append(f"[{offset}:a]volume={item.get('gainDb', 0)}dB,afade=t=out:st={fade_start:.6f}:d={fade_duration:.6f},adelay={delay}|{delay}[{label}]")
            labels.append(f"[{label}]")
    if labels:
        total = Fraction(spec["durationFrames"] * rate["denominator"], rate["numerator"])
        chains.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,apad,atrim=0:{float(total):.9f}[audio]")
        audio_label = "audio"

    command.extend(["-filter_complex", ";".join(chains), "-map", f"[{video_label}]"])
    command.extend(["-map", f"[{audio_label}]"] if audio_label else ["-an"])
    settings = spec["render"]["output"]
    codecs = {"h264": "libx264", "hevc": "libx265", "vp9": "libvpx-vp9", "av1": "libaom-av1"}
    command.extend(["-c:v", codecs.get(settings["videoCodec"], settings["videoCodec"]), "-pix_fmt", settings.get("pixelFormat", "yuv420p"), "-r", frame_rate, "-frames:v", str(spec["durationFrames"]), *_thread_arguments(spec, complex_filter=True), "-map_metadata", "-1"])
    if audio_label:
        command.extend(["-c:a", settings.get("audioCodec", "aac"), "-ar", str(canvas.get("audioSampleRate", 48000))])
    if settings["container"] == "mp4":
        command.extend(["-movflags", "+faststart"])
    command.append(str(destination))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise FFmpegRenderError(result.stderr.strip() or f"ffmpeg failed with exit code {result.returncode}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise FFmpegRenderError("ffmpeg returned success without a non-empty output")
    return destination
