# Fan-edit revision review

Open the numbered videos in order. Specs, provenance, two contact sheets, and the JSON report are in this same flat folder. The companion general stress sequence covers text add/change/move/remove; this sequence preserves the fan-edit no-text default.

| Rev | Change | Mode | Time | Reused/rendered | Clean match |
|---|---|---:|---:|---:|---:|
| r00-baseline | Five-moment hook/setup/build/drop/aftershock baseline | full-initial | 0.385s | 0/180 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r01-hook-punch | Add a restrained two-frame hook stutter | clean-fallback | 0.373s | 0/180 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r02-tighter-bridge | Tighten the setup-to-build bridge from six frames to two | clean-fallback | 0.366s | 0/180 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r03-effect-contrast | Increase build instability and remove drop stutter | clean-fallback | 0.360s | 0/180 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r04-add-pre-drop-sfx | Add one selective pre-drop accent | incremental | 0.221s | 180/0 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r05-rebalance-audio | Lower and pan music while increasing drop impact | incremental | 0.222s | 180/0 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r06-remove-pre-drop-sfx | Remove the extra accent after review | incremental | 0.216s | 180/0 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r07-remove-aftershock | Remove the ending beat while retaining the approved video prefix | incremental | 0.325s | 150/0 | clean V False, approved V True, SSIM 0.998943 / A True (1.000000) |
| r08-no-op | Resubmit the approved composition without semantic changes | incremental | 0.047s | 150/0 | clean V False, approved V True, SSIM 0.998943 / A True (1.000000) |

## Three-trial latency benchmarks

| Class | Incremental mean | Clean mean | Speedup |
|---|---:|---:|---:|
| audio-rebalance | 0.222s | 0.361s | 1.63x |
| retained-audio-tail-removal | 0.327s | 0.317s | 0.97x |
