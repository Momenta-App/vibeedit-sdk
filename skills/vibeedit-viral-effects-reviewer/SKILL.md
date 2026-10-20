---
name: vibeedit-viral-effects-reviewer
description: Review a completed VibeEdit viral source edit after transition decisions and add tasteful additive effects without changing the edit structure. Use to place subject flashes, shimmers, pulses, color/style accents, effect punctuation, and beat-synced visual moments on beats or song details that are not already served by a cut or transition.
---

# VibeEdit Viral Effects Reviewer

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill after the main structure and transition pass are complete. This role makes the edit less boring by adding tasteful visual punctuation, but it must not change the story structure, clip selection, cut order, or transition choices.

Effects are additive. They should give the song another way to be seen when a beat, transient, lyric, or interesting audio moment is not already expressed by a cut, transition, or source action.

## Position In The Pipeline

Run after:

- the main edit structure is complete
- `vibeedit-viral-transition-reviewer` has reviewed cuts and selected transitions
- song beats/transients and section energy are known

Run before:

- final QA/review
- render or acceptance claims

## Downstream Skills

Load downstream skills only when the chosen effect needs them:

- `vibeedit-effects`: default recipe designer for deterministic timeline effects, semantic controls, subject protection, and constructed effect plans.
- `vibeedit-effects-punctuation`: beat flashes, object-only flashes, shakes, zooms, glitches, masks, curtain reveals, color switches, and transition punctuation.
- `vibeedit-segmentation-cutouts`: default mask-driven subject-only flashes, double flashes, additive glows, split-band pulses, shimmer sweeps, and screen/multiply hits.
- `vibeedit models run sam31-mlx`: default execution path for local subject-flash and shimmer tests when SAM3.1 MLX is available. Use it for sparse-frame local SAM3.1 MLX masks on selected active frames.
- `vibeedit models describe sam31-mlx` / `sam21`: inspect exact runtime, device, disk, terms and qualified state before choosing a backend. Do not silently substitute another model. Use the selected real model and persist its output, or record the precise blocker.
- `vibeedit-segmentation-cutouts`: use when the effect needs cutouts, text-behind-subject, foreground/background layering, or object layers.
- `vibeedit models run sam21`: use only after the masking route selects SAM2.1 video segmentation.
- `vibeedit-color-style-recipes`: use for repeatable color switches, grayscale/color intensity changes, red emphasis, contrast grades, grain, or vignette.
- `vibeedit-reverse-curtain-subject-reveal`: includes a no-replacement randomized background within explicit source windows for the combined curtain effect. Standalone mini-video stutter needs a concrete source-range CompositionSpec; this is not an automatic general stutter tool.
- `vibeedit-reverse-curtain-reveal`: use only when an additive reveal effect is intentionally selected and does not restructure the edit.
- `effects`: plan tile/object reveal geometry and implement it with supported SDK layers or an explicit derived visual asset. No dedicated tile/object renderer is bundled; keep it planned until materialized and reviewed.

The packaged `models effect` path materializes reviewed subject-color fills. Full subject-cutout flash transitions, shimmer and split-band pulses require a concrete supported CompositionSpec or derived asset and frame review; invoking SAM alone does not implement them. Direct `maskIds` are not a rendering proof. Preserve these creative recipes as explicit plans until their materialized effect is verified.

Do not edit those downstream skills from this role. Route to them, cite them, and return the exact effect contract they need.

## Effect Taste Rules

- Do not change the main structure, cut order, clip choices, or selected transition plan.
- Prefer restraint: effects should clarify rhythm, attention, or story, not cover weak editing.
- Use single-frame or short subject flashes on close beat clusters; chain one flash per beat when the music has repeated nearby hits.
- When the song has an interesting beat that is not used for a cut, transition, or source impact, consider a flash, shimmer, pulse, or small style accent there.
- Time flashes to the exact beat/transient or source motion contact. A late flash is worse than no flash.
- Avoid effects over dialogue or important facial performance unless they support the moment and do not obscure meaning.
- Do not use decorative full-frame noise when a subject-only effect is requested or when masks are required but unproven.

## Review Workflow

1. Read the locked structure.
   - Require timeline sections, cut list, transition decisions, song anchors, and selected source moments.
   - Treat transition decisions as fixed unless the user explicitly reopens structure.

2. Build an unused-audio-anchor map.
   - List beats, transients, lyric hits, risers, drops, rests, or source-sound details.
   - Mark anchors already handled by a cut, transition, speed ramp, quote, or source action.
   - Select only the anchors where an additive visual moment would improve the edit.

3. Choose effect density.
   - `none`: the edit is already visually complete.
   - `light`: a few flashes or style accents at major unused anchors.
   - `medium`: recurring effects on section turns and selected beat clusters.
   - `heavy`: dense but still readable chains for fast, high-energy music.

4. Plan exact effects.
   - For close beat clusters, use one flash per selected beat and chain them in frame/sample order.
   - For longer sustained moments, use a shimmer, split-band pulse, color switch, or subtle glow.
   - For subject-led moments, route to subject effects and require real mask proof before acceptance.
   - Keep every effect as a concrete operation, not a vague label.

5. Return an additive effect contract.
   - Name selected downstream skill(s).
   - Include timeline frame/time, song anchor, source subject, effect family, duration, blend/style intent, SAM runner command/output path when relevant, and proof state.
   - Mark unexecuted effects as `planned`; do not claim previewed, rendered, reviewed, or accepted.

## Output Shape

```yaml
role: viral_effects_reviewer
proof_state: planned
effect_density:
  weight: none|light|medium|heavy
  rationale: ""
unused_audio_anchors:
  - anchor_id: ""
    timeline_time: ""
    song_reason: ""
    already_served_by: ""
    selected_for_effect: true
effects_plan:
  - effect_id: ""
    timeline_time: ""
    frame: ""
    song_anchor: ""
    source_subject: ""
    effect_family: subject_flash|double_flash|shimmer|pulse|color_switch|shake|zoom|stutter|other
    downstream_skills: []
    duration_frames: 1
    intensity: light|medium|heavy
    sam_execution: none|required|ran|rejected
    sam_artifact_path: ""
    structure_change_allowed: false
    proof_state: planned
rejected_effects: []
blockers: []
next_actions: []
```

## Quality Gates

- The effect pass does not change the structure, clips, cut timing, or transition decisions.
- Every selected effect is tied to a song anchor, source motion, or story attention reason.
- Beat-cluster flashes are one flash per selected beat unless a downstream effect skill gives a concrete reason otherwise.
- Mask-dependent effects must run `vibeedit models run sam31-mlx` or `vibeedit models run sam21` and cite the resulting SAM artifact path. Proxy masks, geometric masks, boxes, and decorative flashes are not valid test outputs.
- Do not promote any effect beyond `planned` without concrete preview/render/review evidence.
