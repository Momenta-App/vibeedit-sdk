# Competitive agent-video evaluation

This is an evidence log for the `agent-video-revision-v1` protocol in
`benchmarks/competitive`. It deliberately separates identical-task measurements
from repository research and does not rank systems before blind review and an
adversarial audit are complete.

## Status

- VibeEdit baseline output: correct, but the timing run is superseded pending an
  immutable post-fix rerun.
- video-use retained-harness run: complete and integrity-verified.
- Remotion identical-task run: complete; native and manual paths separated.
- HyperFrames identical-task run: complete but not strictly comparable because
  every output has 5.333 ms of container/audio duration drift.
- Blind evaluation: in progress.
- Adversarial audit: first pass complete; one evidence blocker remains.
- Comparative winner claim: not available.

## Reproduction contract

The task uses a generated 10-second, 1920x1080, 30 fps video and a generated
220 Hz WAV. The initial H.264/AAC output mixes music at -12 dB. The only revision
raises music gain to -6 dB and must preserve every decoded video frame. Each
implementation receives the same manifest and assets, renders three full
references and three revisions, and reports setup, retries, work reuse, output
verification, and decoded stream equivalence. System identities are hidden from
the later evaluator.

Asset identities for this run:

- `source.mp4`: 7,669,813 bytes, SHA-256
  `ecc97f7b014c310c019098d0af8401691c7a3c2a6398cdfb11b79b8ac15a726d`
- `music.wav`: 960,078 bytes, SHA-256
  `5d4a71476152bfdd84c239a3a9b523b6c94754576b3631680d4460ad36a3d9be`
- FFmpeg: 8.1.1

## VibeEdit baseline

The superseded mutable run was measured from parent commit
`403a0bac83e085f2e3d75369e73639234b4ae4d1` plus the
provenance correction in this milestone. The initial render took 10.239305
seconds. Full revised renders took 9.573717, 9.417288, and 9.505564 seconds
(9.498856-second mean). Incremental revisions took 0.312729, 0.283811, and
0.276983 seconds (0.291175-second mean), a 32.622548x measured speedup over full
revised rendering.

The revision planner classified only the audio range as dirty and selected an
audio remix plus remux. Runtime provenance reported 0 frames rendered, 300
frames reused, and 7,225,515 encoded video bytes reused. Verification passed at
1920x1080, 30 fps, 300 frames, with zero duration drift. Decoded video and audio
both matched the independently full-rendered revised reference exactly. An
independent loudness probe measured -36.1/-32.6 dB mean/max before and
-30.1/-26.6 dB after, the requested +6 dB change.

An audit during this milestone corrected `decodeWorkAvoided`: the video source
decode is avoided, while the music source is necessarily decoded for the remix.

Agent-token and retry fields remain null because this baseline was created by
the supervising implementation session rather than a blinded competitor agent.
It is a render-engine baseline, not yet a complete agent-experience score.

## Competitor repository research

### video-use

Research used pinned commit
`92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66` (2026-07-01), MIT license.
At that revision, video-use is a shell-agent skill and orchestration layer over
FFmpeg with optional HyperFrames, Remotion, Manim, and PIL paths, rather than a
standalone render SDK. Its standard transcription path requires ElevenLabs,
while a credential-free helper render is possible.

A research-only 2-second helper smoke render completed in 0.35 seconds and was
deterministic across a repeat, but it did not use this benchmark's assets or
task and therefore is not a competitive timing. Source inspection and repeated
smoke execution found transcript-file caching by stem, but no content-addressed
dependency graph, dirty-range plan, partial stitch, or documented audio-only
revision path; the helper extracted and rebuilt segments again on repeat. These
are contextual observations pending its independent identical-task run.

The independent identical-task implementation completed with no failed render
attempts. Setup took 6.9743 seconds. Its initial output took 1.5202 seconds;
three full revised renders took 3.9455, 3.1095, and 4.5031 seconds (3.8527-second
mean). Three audio-only revisions took 0.7020, 0.7488, and 0.6308 seconds
(0.6939-second mean), a 5.55x within-system speedup. Runtime accounting reported
0 frames rendered, 300 reused, and 9,636,084 H.264 packet bytes reused per
incremental revision.

All outputs were H.264/AAC, 1920x1080, 30 fps, exactly 300 decoded frames, and
10.000 seconds. The supervising session independently re-probed the final pair
and reproduced the reported encoded H.264 SHA-256
`c49bbc5743da6426eec96c79faa146b60bc95848462f65abaf8259650cfcb7f7`
and decoded PCM SHA-256
`55876fb793f959d37456f3bac05c1eba7c87b6652579ad7d50c4469481ba6e88`
for both full and incremental revisions. Loudness changed by exactly +6.0 dB.

This efficient revision was an agent-authored FFmpeg extension, not a native
video-use EDL/helper feature: the pinned EDL has no external audio placement or
gain field, its helper expects source audio, and the supplied source video is
silent. The protocol permits a discovered general-purpose FFmpeg path, so the
timing is retained, but native expressibility is scored separately. Agent token
telemetry was unavailable; 17 orchestration tool calls were observed through
report creation. The original run retained outputs and a summary report but not
an executable harness, per-command raw logs, or timestamps. Its output hashes
are independently auditable; its timings, failure count, and tool-call count are
provisional until the retained-harness rerun completes.

The serialized retained-harness rerun closed that timing-evidence blocker. It
used a fresh network clone and run-local empty UV cache, logged 47 exact commands
with timestamps, exit codes, and raw output, then made the completed tree
read-only. Setup took 6.0732 seconds. Full revised renders took 1.5665, 1.6241,
and 1.5729 seconds (1.5878-second mean); external FFmpeg revisions took 0.4074,
0.4010, and 0.4051 seconds (0.4045-second mean), a descriptive 3.925x within-run
speedup. All correctness and reuse hashes reproduced. The report SHA-256 is
`91fca4d4403685cc088b6736665a23a05892ac213cac4ee3789679cfa95b67f4`;
the verified manifest SHA-256 is
`0eb359adc7ee82134e3d7c98d4841fe2022baf9122440be7212cea87150385f6`.

### Remotion

Research used official repository commit
`90efe2abe379c39f48b4b4f6b5d13afb935859be` (2026-07-17), package version
4.0.490. The root uses the custom two-tier Remotion License, with free-use
eligibility restrictions and a Company License requirement for larger
for-profit organizations; only selected subpackages carry separate MIT terms.
No Remotion source may be incorporated into VibeEdit based on this evaluation.

The primary runtime is Node with Chrome Headless Shell; the renderer package
bundles its FFmpeg binaries. A direct deterministic 10-second 1080p smoke
render on Apple Silicon took 18.54 seconds cold including a 93.5 MB browser
download and 5.75 seconds warm. Two warm outputs were byte-identical and their
decoded video frames matched. The default silent AAC track extended the probed
container duration to 10.048 seconds, so this smoke does not satisfy the
competitive task contract and is not a comparable timing.

Remotion supports an explicit `frameRange`/`--frames` render primitive; a manual
31-frame range rendered as a standalone 1.088-second MP4 in 2.12 seconds.
Source and documentation review found no built-in dependency-aware dirty-range
planner, prior-final reuse, or automatic patch/stitch revision loop. Its
advanced `combineChunks()` API can join separately rendered chunks but places
cache design and artifact risk on the application. An independent identical-task
implementation is in progress to measure the best honest documented path.

The identical-task run retained project source, outputs, command logs, frame
hashes, and probes. Setup took 3.67 seconds. Three manifest-valid full revised
renders, including exact-duration AAC finishing, took 19.98, 15.37, and 11.97
seconds. Three native-only revision rerenders took 14.07, 13.57, and 14.84
seconds (14.16-second mean), rendered all 300 frames, and reused none. Three
manual FFmpeg stream-copy revisions took 0.41, 0.44, and 0.41 seconds, reusing
all frames and 13,860,783 encoded-video bytes. The manual outputs matched the
full reference exactly, were 10.000 seconds, and applied +6 dB. A supervising
probe reproduced full-versus-manual frame/audio equality. The manual path is an
external optimization baseline, not a Remotion feature; native Remotion AAC
required finishing because its direct output carried 10.048 seconds of padding.

### HyperFrames

Research used official HeyGen repository tag 0.7.61 at commit
`c268f5ba85f2c9af751db1f33819fcb60c7848b0` (2026-07-17), Apache-2.0.
The runtime requires Node 22+, FFmpeg/ffprobe, and a resolved Chrome executable;
Docker is optional but recommended by its documentation for cross-platform
byte reproducibility. A cold scaffold took about 27 seconds and installed or
overwrote global agent skills under `~/.agents/skills` and `~/.claude/skills`,
which is a material setup mutation for evaluation environments.

A credential-free research smoke at 320x180, 30 fps, and one second rendered in
7.58 seconds wall time initially and 3.34 seconds warm. Repeat outputs were
byte-identical. This is not the competitive task or resolution and cannot be
compared with VibeEdit. A one-line title revision changed the composition hash
and again captured all 30 frames, taking 1.5 seconds inside the render pipeline.

The release has a content-addressed persistent cache for frames extracted from
source videos, keyed by source identity and extraction parameters. Source and
log inspection found no persistent rendered-composite cache, semantic dependency
graph, dirty-range preflight, audio-only remux plan, or stitched reuse of a prior
finished render. Static-frame deduplication within one render and distributed
frame-range retry support solve different problems. An independent identical-task
run is in progress; because prior research warmed shared browser/font/npm state
and installed global skills, that run must disclose inherited state.

The isolated identical-task run forced fresh package, Chrome, and font caches
under a temporary HOME while disclosing that inherited skills supplied
instructions. Native revised renders took 11.707, 11.323, and 10.892 seconds,
captured all 300 output frames, and reused only the source-extraction cache.
Manual stream-copy/remix revisions took 0.297, 0.302, and 0.296 seconds, reused
all frames and 13,916,008 H.264 payload bytes, and matched the system's full
reference exactly with a +6 dB change. However, all native and optimized MP4s
reported 10.005333-second container/audio duration. Under the task's strict
no-drift wording this run is recorded as near-valid and non-comparable. Four
failed setup, check, and optimization attempts are retained; the sub-0.31-second
path is not a native HyperFrames revision capability.

## Interpretation rules

- Compare identical-task revision speedups within each system only descriptively;
  encoder settings differ, so neither absolute times nor speedup magnitudes rank
  systems in v1.
- Do not compare the research-only Remotion smoke timing with VibeEdit timings.
- Do not compare the research-only HyperFrames smoke timing with VibeEdit timings.
- Do not infer visual preference: the revision is intended to preserve video,
  and blind evaluation has not run.
- Do not infer a winner from routing or preflight quality alone.
- Exact stream equality is measured against each system's own full revised
  reference, while cross-system output quality is evaluated separately.
- Competitor source and generated work remain outside release archives.

## Adversarial audit

The first audit verified asset identities, pinned video-use commit/license,
dimensions, frame rate, duration, decoded stream equivalence, +6 dB gain,
deterministic repeats, and encoded-video packet reuse. It found two evidence
blockers: the VibeEdit run directory was mutable and overwritten during audit,
and the video-use timing report lacked a retained harness and raw command logs.
The VibeEdit harness now requires a new run directory, captures source and
environment state, hashes every result artifact, and refuses overwrite. The
video-use retained-harness rerun completed and its manifest verified; the
remaining evidence-chain blocker is the post-fix immutable VibeEdit rerun.

The audit also found and prompted two SDK corrections: audio revision provenance
no longer claims music decoding was avoided, and render-graph downstream nodes
now hash their upstream layer/source/artifact dependencies. A gain change must
therefore change `mix:audio` and `output:final` while leaving
`composite:video` stable. The current benchmark remains unsuitable for an agent
preference claim because supervisor/agent token telemetry is absent, and audio
channel/bitrate plus encoder settings are not normalized across systems.
