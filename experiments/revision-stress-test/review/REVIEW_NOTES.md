# VibeEdit revision stress review

Open the numbered videos in order. Each composition JSON and the machine-readable report are in this same flat folder.

| Rev | Change | Mode | Time | Reused/rendered | Clean match |
|---|---|---:|---:|---:|---:|
| r00-baseline | Baseline hybrid edit | full-initial | 7.361s | 0/210 | V True / A True (1.000000) |
| r01-text-copy | Change headline copy | incremental | 3.844s | 140/70 | V True / A True (1.000000) |
| r02-text-style | Change headline color and treatment | incremental | 3.836s | 140/70 | V True / A True (1.000000) |
| r03-add-callout | Add a timed callout | incremental | 3.339s | 172/38 | V True / A True (1.000000) |
| r04-move-callout | Move and rewrite the callout | incremental | 3.311s | 160/50 | V True / A True (1.000000) |
| r05-remove-callout | Remove the callout | incremental | 0.052s | 210/0 | V True / A True (1.000000) |
| r06-transition | Tighten and move the transition | clean-fallback | 2.765s | 210/0 | V True / A True (1.000000) |
| r07-effect-heavy | Intensify and retime the stutter effect | clean-fallback | 2.401s | 210/0 | V True / A True (1.000000) |
| r08-effect-remove | Remove the stutter effect | clean-fallback | 2.733s | 210/0 | V True / A True (1.000000) |
| r09-add-sfx | Add a transition-adjacent sound accent | incremental | 0.232s | 210/0 | V True / A True (1.000000) |
| r10-audio-mix | Revise music gain, pan, fades, and impact level | incremental | 0.247s | 210/0 | V True / A True (1.000000) |
| r11-final-copy | Replace the ending message | incremental | 3.738s | 152/58 | V True / A True (1.000000) |
| r12-container | Change only the output container | incremental | 0.248s | 210/0 | V True / A True (1.000000) |
| r13-remove-scene | Remove the second scene and rebuild the dependent tail | clean-fallback | 2.566s | 72/48 | V True / A True (1.000000) |
| r14-broad-rebuild | Restore and broadly revise the composition | clean-fallback | 7.315s | 0/210 | V True / A True (1.000000) |
| r15-no-op | Submit the same composition without semantic changes | incremental | 0.049s | 210/0 | V True / A True (1.000000) |

## Three-trial latency benchmarks

| Class | Incremental mean | Clean mean | Speedup |
|---|---:|---:|---:|
| bounded-text | 3.812s | 7.072s | 1.86x |
| audio-add | 0.232s | 6.732s | 29.07x |
| cross-container-aac | 0.249s | 6.894s | 27.69x |
