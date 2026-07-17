# Competitive agent-video benchmark

This benchmark compares systems on identical generated assets and revision
requests. Clone competitors into separate temporary directories and record exact
commits and licenses. Nothing from competitor checkouts belongs in VibeEdit
release archives.

## Protocol

1. Run `python prepare_assets.py <workdir>` once. Record FFmpeg version and the
   emitted SHA-256 identities.
2. Give each implementation agent only `task-manifest.json`, the generated
   assets, its assigned system documentation, and the same time/model budget.
3. Capture setup commands/time, agent input/output tokens, tool calls, failures,
   retries, time to preview, time to valid output, and all produced files.
4. Run each timed render three times. Keep cold setup/cache timings separate from
   warm timings. Never count a pre-rendered output as implementation work.
5. Verify dimensions, frame rate, duration, streams, and decoded stream hashes.
6. Replace system names with random labels before visual/reliability review.
7. Give a separate adversarial evaluator commands, logs, cache state, and output
   hashes to look for hidden setup, unfair shortcuts, and unsupported claims.

`run_vibeedit.py` is the VibeEdit implementation harness and requires a new,
nonexistent `--run-dir` for every execution. It records source/environment state
and writes a SHA-256 manifest; it refuses to overwrite prior evidence. Competitor harnesses
must satisfy the same manifest rather than imitate VibeEdit internals.

The audio-gain revision permits any documented system-native incremental path.
General-purpose FFmpeg is allowed only when the implementation agent discovers
and records it under the same context/tool budget. This prevents VibeEdit from
receiving a hidden tool advantage while still measuring whether each system
makes the efficient path discoverable.

Do not summarize a routing-only benchmark as final task success. Do not claim a
visual preference before blind evaluation is complete.
