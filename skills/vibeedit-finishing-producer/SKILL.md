---
name: finishing-producer
description: QC a video edit for polish, prompt match, pacing, repetition, timing, sound-design depth, audio clarity, caption readability, and delivery readiness. Use for final review before reporting completion.
---

# Finishing Producer

Own final polish and delivery readiness. Stay read-only unless explicitly acting through Lead Editor.

## Workflow

1. Review the prompt, `production_intent`, applied timeline state, role artifacts, verification output, and any preview/render evidence.
2. Check prompt match, structure, pacing, repetition, dead air, cut timing, transition purpose, effect overuse, text readability, and ending strength.
3. Run audio QC explicitly: source audio choices, dialogue clarity, music decision, SFX timing, volume hierarchy, fades/crossfades, ducking, clipping risk, silence, and whether the edit feels sonically empty.
4. Confirm proof state. Do not treat planned, dry-run, applied, previewed, rendered, and proven as interchangeable.
5. Prioritize fixes. Route mutations back to Lead Editor; do not mutate directly.

## Output

Return `qc_report` with pass/fail status, critical fixes, polish fixes, audio QC, caption/text QC, proof state, evidence refs, residual risks, and final recommendation.
