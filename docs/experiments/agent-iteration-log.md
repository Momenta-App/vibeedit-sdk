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

## 2026-07-17 — progressive-disclosure routing contract

- Commit: working tree after `c8602aa`.
- Hypothesis: shared filters and compact MCP defaults will reduce irrelevant results and context without changing creative implementations.
- User-style task: search 50 predeclared requests through Python, Node, CLI, and MCP; inspect top-k and payload size.
- Backend/environment: local catalog only, macOS Apple Silicon, source mode.
- Commands: focused catalog/CLI/MCP tests and `scripts/benchmark_routing.py`.
- Before/after: exact first-choice remains 38/50 (76%); newly measured top-three recall is 92%.
- Context size: compact top-five responses average 2,406 bytes; zero skill bodies are loaded; one search tool call is used per request.
- Result quality: category, capability, and platform filters are deterministic across Python and Node. MCP now returns at most five compact results and requires `inspect_catalog_item` for full prompts/examples/validation.
- Final task success and wrong-route recovery: not measured by this retrieval-only benchmark and therefore not claimed.
- Regression status: Python catalog/CLI/MCP 16/16, Node CLI 12/12, and TypeScript checks pass.
- Decision: keep.
- Next question: measure route recovery and completed task success with independent agents after exact intent-mode classification improves the remaining template/workflow ties.

## 2026-07-17 — routing intent and role pass

- Commit: working tree after `46ac9b3`.
- Hypothesis: general role cues can separate workflow skills, executable templates, and primitive catalog items without loading skill bodies or adding sentence-specific overrides.
- User-style task: rerun the fixed 50-request suite across templates, fan-edit workflows, text, HTML, color, transitions, tracking, masks, sound, SAM, and unsupported intents.
- Before/after: first-choice accuracy improves from 38/50 (76%) to 46/50 (92%); top-three recall improves from 92% to 98%.
- Context behavior: compact top-five payloads average 2,410.4 bytes versus 2,406.42 before, an effectively unchanged 3.98-byte increase. Search still loads zero skill bodies and uses one call per request.
- Change: Python and JavaScript now share aliases for role-bearing language (`several`/`multiple`, transition singular/plural, `inside`/mask confinement, mixed media, edit intent, and orchestration) plus bounded skill/editor weighting for choose/plan/route requests. Backend names participate in matching.
- Remaining misses: three are underspecified same-look color-family choices (cinematic versus analog/music-video variants); one is a template-versus-segmentation-workflow tie. All but golden-hour remain in the top three. No benchmark-sentence override was added.
- Regression status: Python routing/CLI/MCP tests pass 19/19, Node tests pass 31/31, and TypeScript checks pass.
- Decision: keep.
- Remaining limitation: final task success and wrong-route recovery after tool execution remain unmeasured by this retrieval-only suite.
- Next question: evaluate completed task outcomes with the router contract frozen, rather than optimizing exact IDs for ambiguous style wording.

## 2026-07-17 — container-only incremental remux

- Commit: working tree after `c8602aa`.
- Hypothesis: changing only a compatible output container can stream-copy encoded packets without decoding or rendering video.
- User-style task: revise MP4 output to Matroska while preserving H.264 video.
- Backend/environment: FFmpeg stream-copy remux, macOS Apple Silicon, source mode.
- Commands: `python/tests/test_revision.py`, three-run 30-frame baseline, three-run 1080p/300-frame benchmark, decoded-frame MD5, and a dynamic `testsrc2` contact sheet.
- Small fixture: 0.065428s full versus 0.058901s remux, only 1.11× because process startup dominates. This result is retained rather than hidden.
- 1080p/300-frame result: 2.014070s full versus 0.063070s remux, 31.93× speedup.
- Reuse: 300/300 frames, 22,621 encoded video packet bytes, zero rendered frames.
- Result quality: decoded frame MD5 matches a clean full render exactly. Visual review of frames 0, 22, 44, 66, and 89 from a dynamic source found the full-render and remux rows visually identical; contact-sheet SHA-256 is `e04c847a33dbcc028aada9b9bbe357e9cc39c8cb5a4fb804e2c04eb9cf188b18`.
- Failure retained: the first integration test assumed the minimal fixture always contained `cache`; it is optional. The test now adds the policy explicitly.
- Safety: remux is claimed only for a conservative codec/container compatibility table; incompatible H.264/WebM stays outside incremental execution.
- Decision: keep.
- Remaining limitation: transition, scene-removal, audio-only, and artifact invalidation now have structured plans and dependency edges but are explicitly `planned-not-yet-executed`.
- Next question: implement audio-only remix plus video stream-copy and compare audio samples against a clean render.

## 2026-07-17 — audio-gain-only incremental remix

- Commit: working tree after `c8602aa`.
- Hypothesis: an audio parameter revision can rebuild only the audio filter graph and stream-copy the prior encoded video.
- User-style task: change one impact gain from -12 dB to -6 dB in a 10-second 1080p/300-frame composition.
- Backend/environment: FFmpeg target-codec audio mix plus stream-copy mux, macOS Apple Silicon, source mode.
- Commands: procedural-SFX and external-WAV equivalence tests plus three full/incremental timing pairs.
- Before/after: 2.018530s full versus 0.121814s incremental mean, a 16.57× speedup.
- Reuse: 300/300 video frames and 22,621 encoded video packet bytes; zero video frames rendered; audio frames 120–149 remixed.
- Result quality: video-frame and decoded-audio framemd5 both match clean full renders exactly for procedural SFX and for a trimmed, delayed, panned, faded external WAV.
- Failed experiment retained: encoding a lossless FLAC intermediate and then AAC changed decoded AAC samples. Encoding AAC once fixed procedural SFX, but the first external-audio attempt shortened the stream because its delayed filter output retained a positive first PTS. `aresample=async=1:first_pts=0` materializes the same leading silence as full A/V muxing; both exact tests then passed.
- Regression status: 106 Python tests, 30 Node tests, TypeScript checks, package validation, clean wheel/npm installs, and the archive audit pass. The audit verified 44 skill clones, 16 preset source files, and zero forbidden entries; canonical Git source comparison was not requested in this local gate.
- Decision: keep.
- Remaining limitation: source-video embedded audio is not independently mixed by the current full renderer, so this claim covers the same explicit audio-clip and procedural-SFX domains as the canonical full render.
- Next question: execute transition-overlap replacement without re-encoding clean ranges.

## 2026-07-17 — rejected monolithic transition cache

- Commit: working tree after `0b66c66`.
- Hypothesis: rebuilding one full lossless FFV1 composite from a cached previous render plus a newly rendered transition overlap would reduce revision latency.
- User-style task: replace a 30-frame crossfade with a wipe in a 300-frame 1080p composition.
- Backend/environment: FFmpeg FFV1 cache and H.264 final encode, macOS Apple Silicon, source mode through `uv`.
- Initial comparison: 7.799261s nominal full mean versus 8.415449s incremental mean, a 0.926779x result and therefore a regression even before control correction. Later audit found the nominal baseline was cache-primed rather than canonical; the fair control is recorded below.
- Reuse accounting: the output was exact and the plan identified 30 rendered/270 reusable frames, but the implementation re-encoded all 300 frames into a monolithic FFV1 intermediate before the final encode.
- Decision: revert the monolithic intermediate design. Retain this negative result so the work counter is not mistaken for elapsed-time improvement.
- Next question: preserve clean ranges as independently addressable lossless segments and concatenate them directly into the final encoder.

## 2026-07-17 — rejected lossless transition-segment cache

- Commit: working tree after `0b66c66`.
- Hypothesis: a content-addressed segment manifest can replace only the dirty transition overlap without rebuilding a monolithic lossless cache.
- User-style task: replace a 30-frame crossfade with a wipe in a 300-frame 1920x1080 composition, with an independently primed cache for each timing sample.
- Backend/environment: FFmpeg lossless segments and deterministic H.264 final encode, macOS Apple Silicon, source mode through `uv`.
- First result: FFV1 segments appeared to improve 7.754292s to 5.431526s (1.427645x), with 30 rendered/270 reused frames and byte-identical output. Audit found that the supposed full baseline also built the lossless cache, so it measured a 7.754292s cache-prime render rather than canonical cache-disabled full rendering. This result is invalid as a speedup claim.
- Corrected control: canonical cache-disabled full samples were 4.744780s, 4.637785s, and 4.661931s; mean 4.681498s.
- Follow-up: lossless H.264 segments reduced cache size while preserving exact encoded video and audio streams. Cache-prime samples were 13.497220s, 13.503817s, and 13.468124s. Warm revisions were 6.011497s, 5.848857s, and 5.869325s; mean 5.909893s, only 0.792146x the corrected full baseline and therefore 26.2% slower.
- Reuse accounting: the prototype rendered 30 transition frames, reused 270 lossless composite frames and 10,581 encoded audio packet bytes, and correctly reported no avoided source decode. Those work counters did not translate into lower latency because lossless-segment decoding plus the required final H.264 encode cost more than direct source compositing.
- Result quality: encoded video and audio stream hashes matched the canonical full render exactly. Visual review confirmed unchanged pre/post-overlap frames and the intended crossfade-to-wipe change; contact-sheet SHA-256 is `ada1169ae24bcc24c1083159bbf72f5bd34566509284f2947db38392d4656797`.
- Decision: revert both segment-cache prototypes and keep transition execution explicitly planned. Preserve the planner correction that does not claim either source decode is avoided.
- Next question: pursue a design that can reuse final encoded GOPs without weakening correctness, or prioritize scene-tail removal where packet-level reuse may be naturally aligned.

## 2026-07-17 — verified video-only scene-tail truncation

- Commit: working tree after `2cd568c`.
- Hypothesis: removing a tail exactly at the first removed layer boundary can reuse the approved encoded prefix without decoding sources or rendering frames.
- User-style task: remove the second scene, its 30-frame transition, and tail SFX from a 300-frame 1080p edit, producing a 210-frame video-only revision.
- Backend/environment: FFmpeg packet-counted stream copy, macOS Apple Silicon, source mode through `uv`.
- Full timings: 4.748821s, 4.645047s, 4.999855s; mean 4.797908s.
- Prior-render timings: 7.569177s, 7.550149s, 7.503372s. This is pre-existing approved work and is reported separately rather than included in revision latency.
- Revision timings: 0.622083s, 0.631288s, 0.618982s; mean 0.624118s, a 7.687504x speedup.
- Reuse: zero frames rendered, 210/210 frames reused, 2,810,506 encoded video packet bytes reused, and both source decodes avoided.
- Result quality: every decoded output frame matches the corresponding frame of the approved prior render exactly. Independent clean rerenders score 0.993142 SSIM; visual inspection of frames 0, 105, and 209 found no visible difference. Contact-sheet SHA-256 is `4ec3720da43aae36d83909ad4925a50354db8a1cd81321f78c8fb27c52faea4b`.
- Failed variants retained: timestamp truncation with `-t` leaked two B-frames; exact `-frames:v` packet counting fixed the duration. Retaining AAC under `-shortest` ended one partial packet (16ms) early, so retained-audio tails are explicitly not executable.
- Safety: execution requires unchanged retained layers, all removed layers at or beyond the new end, identical sources/artifacts/render settings, a video-only revised timeline, matching prior composition/output provenance digests, and an independently verified final frame count.
- Decision: keep.
- Remaining limitation: this preserves the already approved encoded prefix rather than reproducing the different compression decisions of a clean re-encode. Mid-scene removal, retained audio, and changed prefix layers remain planned.
- Next question: extend packet-level reuse only where closed-GOP and audio sample boundaries can be proved, while prioritizing artifact-dependent revision execution.

## 2026-07-17 — transitive artifact invalidation audit

- Commit: working tree after `740d58e`.
- Hypothesis: the render graph's tracking-to-mask edge should prevent unchanged serialized masks and their layers from being claimed reusable after tracking changes.
- User-style task: retrack a subject whose SAM mask depends on the tracking artifact, without directly editing the mask or subject layer objects.
- Finding: graph hashes propagated correctly, but the reuse list compared artifact and layer objects directly. It incorrectly listed the unchanged mask and subject layer as reusable.
- Change: dependency-invalidated masks are now explicit `changedArtifacts`; both those masks and every referencing layer are excluded from reusable claims. Required jobs carry both the directly changed tracking artifact and its dependent mask.
- Follow-up finding: analysis artifacts declared `sourceIds`, but their graph hashes and edges omitted those sources. Source hashes and explicit source-to-analysis edges now invalidate derived analysis when source identity changes.
- Result quality: the revised graph changes `artifact:sam-mask` and `layer:subject`; the dirty range remains exactly frames 0–59. Replacing the beat-analysis music source also changes `artifact:beats` without requiring a manual artifact edit. Focused revision tests pass 16/16.
- Decision: keep the correctness fix. Do not expose artifact execution until the canonical renderer consumes the declared mask/tracking artifacts rather than relying on example-specific preprocessing.
- Next question: unify mask consumption with the canonical render path so bounded artifact revisions can be benchmarked against real output rather than planner metadata alone.

## 2026-07-17 — SAM 3.1 quarantine routing audit

- Commit: working tree after `1ae0450`.
- Hypothesis: a locally declared SAM 3.1 manifest must not bypass the product's explicit quarantine.
- Finding: the external-provider validator accepted either `sam.2.1` or `sam.3.1`; a checksum-shaped SAM 3.1 manifest could make generic segmentation and doctor capability output appear available despite the documented quarantine.
- Change: provider registration now accepts only `sam.2.1`. Doctor reports SAM 3.1 as unconditionally unavailable with no provider or version until the quarantine requirements are deliberately changed in source.
- Regression status: focused vision tests pass 12/12 with the vision and test extras, including approved external SAM 2.1 execution/cache reuse and rejected SAM 3.1 registration.
- Decision: keep. No SAM 3.1 code, weights, setup, or support claim was added.
- Next question: improve approved SAM 2.1 revision reuse only through real inference and canonical mask-consumption evidence.

## 2026-07-17 — 16-round hybrid human-revision stress test

- Commit: working tree after `a4658d5`.
- Hypothesis: a real hybrid edit can survive repeated text, transition, effect, audio, container, scene, broad-rebuild, and no-op revisions without picture/audio drift, while supported narrow changes avoid unnecessary work.
- User-style task: create one 210-frame 640×360/30fps video from two generated source clips, a crossfade, deterministic stutter, three HTML/CSS text sections, music, and procedural SFX; retain 16 numbered review versions in a flat folder.
- Backend/environment: mixed persistent Chromium + Python/FFmpeg, H.264/AAC MP4 and Matroska, macOS Apple Silicon, source mode through `uv`.
- Commands: `PYTHONPATH=python/src uv run --extra browser python experiments/revision-stress-test/run.py`, decoded raw-video MD5, decoded stereo PCM comparison, `verify_output`, and three isolated timing trials for text, SFX, and cross-container AAC revisions.
- Revision coverage: baseline; text copy; text style; add/move/remove callout; transition timing; effect intensity; effect removal; SFX addition; music gain/pan/fades; ending copy; container change; scene removal; broad rebuild; semantic no-op.
- Baseline findings: changing the output URI alongside text incorrectly classified the revision as full; hybrid text changes rebuilt the unchanged media base; MP4→Matroska AAC packet copy added 1,024 samples (21.33ms); audio/container reuse did not verify the prior artifact provenance; URI-only revisions were classified as container work.
- Improvements retained: output URI is non-semantic in revision classification and render-graph output hashes; unchanged hybrid media bases are content-addressed and cached with FFmpeg/runtime provenance; work records distinguish motion capture/reuse, media-base rendering, and final encoding; audio/container reuse verifies the prior composition and output digest; cross-family AAC revisions rebuild audio directly into the target container while stream-copying video; destination-only/no-op revisions copy the verified artifact without rendering.
- Three-trial bounded-text result: incremental samples 3.803052s, 3.811254s, 3.820865s (mean 3.811724s) versus clean samples 7.242653s, 6.749887s, 7.223812s (mean 7.072117s), 1.855359× speedup. Each revision captured 70/210 motion frames, reused 140 overlay frames, reused the unchanged media base, and still encoded 210 final video frames.
- Three-trial SFX-add result: incremental samples 0.230524s, 0.230269s, 0.234015s (mean 0.231603s) versus clean mean 6.731590s, 29.065225× speedup; zero video frames rendered and 210 reused.
- Three-trial MP4→Matroska AAC result: incremental samples 0.248521s, 0.252460s, 0.245983s (mean 0.248988s) versus clean mean 6.894196s, 27.688856× speedup; video is stream-copied and audio is rebuilt/encoded for the target container.
- Result quality: all 16 retained outputs pass dimensions, 210/120-frame duration as applicable, frame-rate, stream-presence, and drift verification. Every output matches its clean reference by decoded raw-video MD5. Every decoded audio comparison is exact with zero sample delta after the fixes, including the container revision.
- Visual review: early and late 4×4 contact sheets confirm the intended copy, callout, scene, transition/effect, removal, and rebuild states. The review folder contains the numbered outputs, CompositionSpecs, provenance records, contact sheets, review notes, and machine-readable report without nested folders.
- Failure retained: transition-overlap replacement remains planned because the prior exact segment prototypes were slower than clean rendering. Effect-stack changes and the mixed retained-audio scene removal also use a clean fallback. This test does not claim partial execution for those classes.
- Regression status: focused revision and mixed-render tests pass 22/22 before the integrated gate.
- Decision: keep all five system improvements and the stress harness/evidence.
- Next question: reduce the remaining full-sequence final encode for bounded motion changes, and pursue transition reuse only with a final-encoded GOP design that beats the clean control.

## 2026-07-17 — five-clip fan-edit revisions and retained-audio tail execution

- Commit: working tree after `9d61e7a`.
- Hypothesis: a canonical fan edit should support more than two clips and should remove a final moment without re-encoding its approved video prefix or drifting retained music/SFX.
- User-style task: create a hook/setup/build/drop/aftershock edit, then add and remove stutter, tighten a transition with valid source handles, add/remove an accent, rebalance music/drop impact, remove the aftershock, and submit a no-op revision.
- Backend/environment: Python/FFmpeg, five generated H.264 sources plus explicit WAV music and procedural SFX, 320×180/30 fps, macOS Apple Silicon source mode.
- Change: the media renderer now validates and executes arbitrary adjacent clip chains containing clean cuts and explicit transition overlaps. Effect output is normalized to the exact requested duration. Scene-tail execution can safely trim the retained last clip, packet-copy the approved video prefix, rebuild revised audio, and write provenance with separate video reuse and audio-remix accounting.
- Revision evidence: nine retained fan-edit outputs all pass stream/duration verification. Effect and transition changes correctly use clean fallback; three audio revisions reuse all 180 video frames; aftershock removal reuses all 150 retained video frames and remixes frames 0–149; the no-op copies the verified artifact.
- Quality: audio is exact to the clean render with zero sample delta and 1.0 correlation. The removed-tail video is exact to the approved prior prefix. It is not decoded-pixel-identical to an independently shortened H.264 encode because GOP decisions change; SSIM against that clean encode is 0.998943.
- Three-trial audio-rebalance result: 0.220953s, 0.221093s, 0.222488s incremental (0.221511s mean) versus 0.363782s, 0.358617s, 0.361693s clean (0.361364s mean), 1.631356× speedup.
- Three-trial retained-audio tail result: 0.334682s, 0.323580s, 0.323500s incremental (0.327254s mean) versus 0.316513s, 0.317779s, 0.317903s clean (0.317399s mean), 0.969884×. Keep for exact approved-prefix continuity and drift safety, not speed at this resolution.
- Failure retained: the first comparison incorrectly treated clean-reencode pixel identity as the only valid equivalence basis. The evidence now reports both clean-render comparison and exact approved-artifact-prefix comparison.
- Decision: keep. The flat review folder contains every output, CompositionSpec, provenance sidecar, two contact sheets, notes, and the machine report.
- Next question: measure retained-audio tail removal at 1080p and pursue final-encoded GOP reuse for bounded effect/transition changes only if it beats canonical clean rendering.

## 2026-07-17 — isolated rerun of the 16-round hybrid stress sequence

- Hypothesis: the text/effect/transition/audio/container stress sequence remains correct under the stricter multi-clip timeline contract and fresh-cache timing controls.
- Finding: the old transition revision moved only the transition object and no longer matched its clip overlap. The case now moves/trims the incoming clip and source handle consistently. A second finding showed static cache namespaces could reuse completed outputs from an earlier run and inflate speedups.
- Change: every harness run and bounded-text benchmark trial now receives an isolated cache namespace. Prior completed renders cannot count as fresh incremental work.
- Corrected three-trial results: bounded text 3.820514s incremental versus 6.905942s clean (1.807595×); SFX addition 0.228506s versus 6.723188s (29.422344×); cross-container AAC 0.242934s versus 6.692744s (27.549676×).
- Quality: all 16 outputs pass verification and match their clean controls exactly for decoded video and audio with zero sample delta. Coverage includes text copy/style/add/move/remove, valid transition retiming, effect change/removal, SFX addition, music mix, container change, scene removal, broad rebuild, and no-op.
- Decision: keep the stricter timeline case and isolated timing controls; discard the cache-contaminated 137.74× text figure.
