# Agent iteration log

## 2026-07-17 — bounded text revision baseline

- Commit: `4554b50` (pre-change baseline)
- Hypothesis: a content-addressed frame dependency can avoid Chromium work outside a changed text layer's placement while preserving a clean full-render result.
- User-style task: change `FIRST CUT` to `REVISED CUT` during frames 10–19 of a 30-frame 320×180 composition.
- Backend/environment: mixed persistent Chromium and FFmpeg, macOS Apple Silicon, source mode through `uv`.
- Command: inline `uv run --extra browser --extra test python` benchmark using the packaged mixed fixture.
- Full-render timings: 1.555246s cold, 1.415116s warm, 1.420194s warm; mean 1.463519s.
- Rendered frames: 30 per run; cache hits: 0; 20 clean frames were reusable but discarded.
- Agent token estimate: not measured in this runtime-only experiment.
- Result quality: three outputs had equal byte size (8,203 bytes); the focused render suite passed 10/10 before the change.
- Human review: bounded title was visible only in its intended range; no visual change was intended outside frames 10–19.
- Regression status: baseline Node CLI 11/11, Python render 10/10, and type checks passed.
- Decision: keep the benchmark and implement a bounded frame-cache vertical slice.
- Next question: does the revised path capture exactly 10 frames, reuse 20, produce byte-identical output to a clean render, and improve latency over three runs?

- First-contact note: bare `PYTHONPATH=python/src python3 -m vibeedit --help` failed because the host interpreter lacked the declared `jsonschema` dependency. The supported `uv run --extra test python -m vibeedit --help` source environment passed.

## 2026-07-17 — bounded composite-frame reuse

- Commit: working tree after `4554b50`.
- Hypothesis: unchanged final motion frames can be reused by hashing their active ordered layers rather than the whole CompositionSpec.
- User-style task: repeat the same bounded text revision with an independently primed cache for each timing sample.
- Backend/environment: mixed persistent Chromium and FFmpeg, macOS Apple Silicon, source mode through `uv`.
- Commands: focused `python/tests/test_revision.py` plus an inline three-run benchmark.
- Incremental timings: 0.916966s, 0.924800s, 0.923717s; mean 0.921828s.
- Before/after: 1.463519s to 0.921828s mean, a 37.0% reduction and 1.59× speedup.
- Rendered frames and cache hits: 10 captured, 20 restored per revision; 66.7% frame reuse.
- Agent token estimate: not measured in this runtime-only experiment.
- Result quality: incremental and clean full-render MP4 files are byte-identical in the integration test.
- Human review: no changed pixels are expected outside the title placement; byte identity to the clean revised output verifies the assembled result at this size/codec.
- Regression status: focused revision tests pass 2/2; broader validation follows.
- Decision: keep.
- Remaining limitation: this slice avoids Chromium capture for clean ranges but still sends a complete frame sequence through FFmpeg. Source decode, audio remux, and GOP-aware range replacement remain future work.
- Next question: can the same graph contract safely distinguish text color, timing, transitions, audio-only changes, and artifact dependencies before extending the renderer?

## 2026-07-17 — compact catalog routing baseline and first ranking pass

- Commit: working tree after the bounded revision slice.
- Hypothesis: deterministic token-weighted ranking can route natural agent requests without loading catalog entries or skill bodies into context.
- User-style task: 50 predeclared requests spanning basic edits, fan edits, captions, kinetic type, HTML, color, transitions, masks/tracking, beat/sound, SAM, and unsupported intents.
- Backend/environment: local Python catalog, source mode through `uv`; no model or network calls.
- Command: `uv run --extra test python scripts/benchmark_routing.py`.
- Baseline: literal full-query substring search selected 5/50 correctly (10%); those five were unsupported requests correctly returning no result. The other 45 natural requests returned no result.
- After: deterministic ranked retrieval selected 38/50 correctly (76%) and still rejected all five unsupported/quarantined requests.
- Context behavior: search scores compact metadata only; no skill bodies are loaded. Compact results now contain stable ID, intent, category, required capability, backends, determinism, parameter count, preview status, compatibility, estimated setup cost, confidence, and reason.
- Result quality: 12 misses remain. Several are relevant same-family alternatives (analog versus cinematic golden-hour/neo-noir/bleach-bypass); others are template-versus-workflow ties that need intent classification rather than benchmark-specific overrides.
- Regression status: focused Python and Node catalog/CLI validation follows.
- Decision: keep the general ranking pass; do not tune against individual benchmark sentences yet.
- Next question: add explicit task-mode/category/platform filters and score top-k relevance separately from exact first-ID accuracy.
