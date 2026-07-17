# VibeEdit revision stress review

Open the numbered videos in order. Each composition JSON and the machine-readable report are in this same flat folder.

| Rev | Change | Mode | Time | Reused/rendered | Clean match |
|---|---|---:|---:|---:|---:|
| r00-baseline | Baseline hybrid edit | full-initial | 7.381s | 0/210 | V True / A True (1.000000) |
| r01-text-copy | Change headline copy | incremental | 3.833s | 140/70 | V True / A True (1.000000) |
| r02-text-style | Change headline color and treatment | incremental | 3.800s | 140/70 | V True / A True (1.000000) |
| r03-add-callout | Add a timed callout | incremental | 3.316s | 172/38 | V True / A True (1.000000) |
| r04-move-callout | Move and rewrite the callout | incremental | 3.303s | 160/50 | V True / A True (1.000000) |
| r05-remove-callout | Remove the callout | incremental | 0.050s | 210/0 | V True / A True (1.000000) |
| r06-transition | Tighten and move the transition | clean-fallback | 2.797s | 210/0 | V True / A True (1.000000) |
| r07-effect-heavy | Intensify and retime the stutter effect | clean-fallback | 2.784s | 210/0 | V True / A True (1.000000) |
| r08-effect-remove | Remove the stutter effect | clean-fallback | 2.782s | 210/0 | V True / A True (1.000000) |
| r09-add-sfx | Add a transition-adjacent sound accent | incremental | 0.230s | 210/0 | V True / A True (1.000000) |
| r10-audio-mix | Revise music gain, pan, fades, and impact level | incremental | 0.243s | 210/0 | V True / A True (1.000000) |
| r11-final-copy | Replace the ending message | incremental | 3.743s | 152/58 | V True / A True (1.000000) |
| r12-container | Change only the output container | incremental | 0.244s | 210/0 | V True / A True (1.000000) |
| r13-remove-scene | Remove the second scene and rebuild the dependent tail | clean-fallback | 1.914s | 72/48 | V True / A True (1.000000) |
| r14-broad-rebuild | Restore and broadly revise the composition | clean-fallback | 6.772s | 0/210 | V True / A True (1.000000) |
| r15-no-op | Submit the same composition without semantic changes | incremental | 0.048s | 210/0 | V True / A True (1.000000) |

## Three-trial latency benchmarks

| Class | Incremental mean | Clean mean | Speedup |
|---|---:|---:|---:|
| bounded-text | 3.821s | 6.906s | 1.81x |
| audio-add | 0.229s | 6.723s | 29.42x |
| cross-container-aac | 0.243s | 6.693s | 27.55x |
