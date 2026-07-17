# Fan-edit revision review

Open the numbered videos in order. Specs, provenance, two contact sheets, and the JSON report are in this same flat folder. The companion general stress sequence covers text add/change/move/remove; this sequence preserves the fan-edit no-text default.

| Rev | Change | Mode | Time | Reused/rendered | Clean match |
|---|---|---:|---:|---:|---:|
| r00-baseline | Five-moment hook/setup/build/drop/aftershock baseline | full-initial | 0.390s | 0/180 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r01-hook-punch | Add a restrained two-frame hook stutter | clean-fallback | 0.377s | 0/180 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r02-tighter-bridge | Tighten the setup-to-build bridge from six frames to two | clean-fallback | 0.373s | 0/180 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r03-effect-contrast | Increase build instability and remove drop stutter | clean-fallback | 0.367s | 0/180 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r04-add-pre-drop-sfx | Add one selective pre-drop accent | incremental | 0.223s | 180/0 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r05-rebalance-audio | Lower and pan music while increasing drop impact | incremental | 0.234s | 180/0 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r06-remove-pre-drop-sfx | Remove the extra accent after review | incremental | 0.221s | 180/0 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r07-remove-aftershock | Remove the ending beat while retaining the approved video prefix | incremental | 0.331s | 150/0 | clean V False, approved V True, SSIM 0.998943 / A True (1.000000) |
| r08-no-op | Resubmit the approved composition without semantic changes | incremental | 0.049s | 150/0 | clean V False, approved V True, SSIM 0.998943 / A True (1.000000) |
| r09-restore-micro-aftershock | Restore a twelve-frame resolving image and real final impact | clean-fallback | 0.341s | 0/162 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r10-tighten-micro-aftershock | Cut the resolving image to six frames after full-speed review | clean-fallback | 0.333s | 0/156 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r11-soften-hook-stutter | Reduce the hook stutter to a one-frame punctuation | clean-fallback | 0.345s | 0/156 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r12-final-impact-mix | Raise and deepen the final impact without touching picture | incremental | 0.209s | 156/0 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r13-final-loudness | Lift the deliberately quiet synthetic mix to -19 LUFS with safe peak headroom | incremental | 0.196s | 156/0 | clean V True, approved V False, SSIM 1.000000 / A True (1.000000) |
| r14-final-approved-no-op | Resubmit the final approved fan edit unchanged | incremental | 0.051s | 156/0 | clean V True, approved V True, SSIM 1.000000 / A True (1.000000) |

Final audio: -19.4 LUFS integrated, -2.4 dBFS true peak.

## Three-trial latency benchmarks

| Class | Incremental mean | Clean mean | Speedup |
|---|---:|---:|---:|
| audio-rebalance | 0.227s | 0.367s | 1.61x |
| retained-audio-tail-removal | 0.338s | 0.330s | 0.98x |
