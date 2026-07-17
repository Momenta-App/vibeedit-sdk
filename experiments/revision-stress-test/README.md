# Revision stress test

This experiment creates one hybrid VibeEdit composition and carries it through
16 human-style review revisions. Run it from the repository root:

```bash
PYTHONPATH=python/src uv run --extra browser python experiments/revision-stress-test/run.py
```

The flat [`review`](review) folder contains every numbered video, its
CompositionSpec and provenance record, two contact sheets, concise review notes,
and the complete machine-readable report.

## Coverage

The chain exercises baseline assembly, text copy and style, adding/moving/
removing text, transition timing, effect intensity and removal, SFX addition,
music gain/pan/fades, final copy, MP4-to-Matroska conversion, scene removal,
broad rebuild, and a semantic no-op.

Every output is compared with a cache-disabled clean render using decoded raw
video and stereo PCM. The harness requires output verification, exact decoded
video, zero audio sample-count delta, and at least 0.9999 audio correlation.

## Improvements retained from the test

- Output filenames no longer turn otherwise bounded revisions into full work.
- Hybrid media bases are cached independently from browser motion overlays.
- Revision work records separate media-base rendering, motion capture/reuse,
  and final video encoding.
- Audio, container, scene-tail, and no-op reuse require trusted composition and
  output provenance.
- MP4-to-Matroska AAC changes rebuild audio directly in the target container
  while stream-copying video, avoiding the 1,024-sample drift found in the
  original packet-copy path.
- Destination-only and semantic no-op revisions copy the verified artifact.

## Remaining gaps

Transition-overlap execution remains planned because two exact prototypes were
slower than a clean render. General effect-stack changes and retained-audio
scene removal also use a clean fallback. Bounded motion changes reuse browser
frames and the media base but still encode the full final video sequence.
