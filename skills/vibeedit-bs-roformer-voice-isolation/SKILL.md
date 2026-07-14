---
name: vibeedit-bs-roformer-voice-isolation
description: Use when a VibeEdit task needs high-quality vocal isolation, instrumental/no-vocals extraction, or both stems from a song, music video, movie quote, edit, or timestamped source clip. Prefer BS-Roformer 1297 for consistent vocal/instrumental stems when quality matters more than speed.
---

# VibeEdit BS-Roformer Voice And Instrumental Isolation

Use this skill when the user asks to isolate, extract, separate, or clean up vocals/voice, remove vocals, create an instrumental, or produce both vocal and instrumental stems from audio or video.

## Model Choice

Use **BS-Roformer 1297**:

- Model filename: `model_bs_roformer_ep_317_sdr_12.9755.ckpt`
- App tool: `packages/desktop/scripts/vocal-isolation/isolate-voice-bs-roformer.py`
- Skill-local wrapper: `scripts/isolate_voice_bs_roformer.py`
- Best for: high-quality vocal stems, instrumental/no-vocals stems, fan edits, lyric/voice analysis, quote isolation, and removing backing track or vocals from a music video/song.
- Tradeoff: slower than Demucs/Kim Vocal/UVR-MDX, but the user selected it as the good and consistent model.

For clips under 2 seconds, this tool pads the extracted audio to a model-safe duration before separation and trims the resulting stems back to the requested duration. Earlier raw BS-Roformer runs failed on ~0.7s and ~1.1s clips without padding.

## Quick Tool Use

Run:

```bash
python packages/desktop/scripts/vocal-isolation/isolate-voice-bs-roformer.py \
  --input /absolute/path/to/song-or-video.mp4
```

By default, the tool writes both stems:

- `vocals.wav`
- `instrumental.wav`
- `manifest.json`

The default output location is deterministic:

```text
<source-dir>/.vibeedit/derived-assets/
  <source-filename-slug>__sha256-<source-hash-prefix>/
    bs-roformer-1297/
      s<start-ms>-e<end-ms>/
        vocals.wav
        instrumental.wav
        manifest.json
```

Use `--output-root` only when the project has a known derived-asset root. The final path remains deterministic below that root.

## Timestamp And Frame Ranges

For full songs, omit range arguments.

For a section of a song, video, or movie:

```bash
python packages/desktop/scripts/vocal-isolation/isolate-voice-bs-roformer.py \
  --input /absolute/path/to/movie.mp4 \
  --start 01:12:03.500 \
  --end 01:12:11.250
```

Or use duration:

```bash
python packages/desktop/scripts/vocal-isolation/isolate-voice-bs-roformer.py \
  --input /absolute/path/to/video.mp4 \
  --start 42.25 \
  --duration 8.5
```

For frame-specific requests:

```bash
python packages/desktop/scripts/vocal-isolation/isolate-voice-bs-roformer.py \
  --input /absolute/path/to/video.mp4 \
  --start-frame 1800 \
  --end-frame 2040
```

The tool uses the source video frame rate from `ffprobe`; pass `--frame-rate 24000/1001` if the source metadata is missing or the user gives a timeline-specific frame rate.

## Stem Selection

Default to `--stems both`. This creates both stems every time so downstream agents can reuse either output without rerunning the model.

Use `--stems vocals` or `--stems instrumental` only when disk/runtime constraints matter or the user explicitly asks for one stem.

## Runtime Expectations

The wrapper expects:

- `ffmpeg` and `ffprobe` on `PATH`
- `audio-separator` installed in a Python 3.11 environment
- The BS-Roformer model available in `AUDIO_SEPARATOR_MODEL_DIR`, or downloaded by `audio-separator` into the configured model cache.

If available, the wrapper automatically reuses the local gauntlet environment:

`fan_Edit_Data/agent-artifacts/vocal-isolation-eval/.venv/bin/audio-separator`

To force a runtime or model cache:

```bash
AUDIO_SEPARATOR_BIN=/path/to/audio-separator \
AUDIO_SEPARATOR_MODEL_DIR=/path/to/models \
python packages/desktop/scripts/vocal-isolation/isolate-voice-bs-roformer.py \
  --input /path/in.mp3 \
  --output-root /path/derived-assets
```

## Agent Guidance

When a user asks for “best”, “clean”, “consistent”, “voice only”, “highest quality”, “remove voice”, “instrumental”, “karaoke”, or “no vocals”, use this skill first.

When a user asks for a fast preview, mention that BS-Roformer is slower and ask only if latency matters. Otherwise run it.

Preserve the original media. Do not overwrite source files.

Prefer the deterministic derived-asset output path. The `manifest.json` is part of the asset contract: it ties the stems to the exact source hash, source path, model, start/end timestamps, optional frame range, and output files. When using the stems later, reference the manifest and the specific stem path (`vocals.wav` or `instrumental.wav`).

If a source file is imported into another project, keep or recreate its `.vibeedit/derived-assets/...` directory so the vocal/instrumental stems travel with the media identity and timestamp range.
