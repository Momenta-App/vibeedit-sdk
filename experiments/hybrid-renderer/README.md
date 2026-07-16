# Hybrid renderer benchmark

This benchmark combines a Python-authored FFmpeg effect, a Python-authored
transition, two generated video sources, procedural audio, and an agent-authored
HTML/CSS/JavaScript motion layer.

```bash
PYTHONPATH=python/src .venv/bin/python \
  experiments/hybrid-renderer/render_benchmark.py /tmp/vibeedit-hybrid
```

It performs three complete renders, verifies each output, and writes the exact
CompositionSpec and timing report beside the review videos.

