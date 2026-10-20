---
name: vibeedit-viral-transition-reviewer
description: Review a completed VibeEdit viral source edit structure before effects, decide where cuts should stay plain or receive light, medium, or heavy transitions, and route to transition skills such as subject flash, segmentation cutouts, generic transition editing, reverse curtain reveal, tile object reveal, or random-frame stutter. Use after the main timeline structure exists and before the additive effects pass.
---

# VibeEdit Viral Transition Reviewer

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this skill after the main edit structure is planned or assembled, but before the effects pass. This role reviews every cut from one source clip to the next and decides whether the cut should stay clean or become a transition moment.

The transition reviewer may change timeline structure and clip selection when the transition is a centerpiece. This is especially true for subject-masking transitions: a weak clip-B first frame makes the transition worse, so replace or shift clip B when needed to land on a stronger segmentable subject.

## Position In The Pipeline

Run after:

- source, story, song, action/sync, quote, SFX, and assembly planning have produced a main structure
- the edit has a cut list or timeline map
- song energy and style direction are known enough to judge transition weight

Run before:

- `vibeedit-viral-effects-reviewer`
- final QA/review
- render or acceptance claims

## Downstream Skills

Load downstream skills only when the chosen transition needs them:

- `vibeedit-transition-editor`: default transition logic, cut flow, beat cuts, motion cuts, speed ramps, slides, wipes, zooms, and transition-paired sound notes.
- `vibeedit-segmentation-cutouts`: favorite/default hero transition when clip B has a strong first-frame subject and a mask-driven reveal would focus story attention.
- `vibeedit models run sam31-mlx`: default execution path for subject-flash transitions in local tests when SAM3.1 MLX is available. Use it for sparse-frame local SAM3.1 MLX masks for 4, 6, 8, or 20 frame reveals.
- `vibeedit models describe sam31-mlx` / `sam21`: inspect exact runtime, device, disk, terms and qualified state before choosing a backend. Do not silently substitute another model. Use the selected real model and persist its output, or record the precise blocker.
- `vibeedit-segmentation-cutouts`: use for frame-accurate clip-B-over-clip-A cutout placement and no-jump landing contracts.
- `vibeedit models run sam21`: use only after the masking route selects SAM2.1 video segmentation.
- `vibeedit-reverse-curtain-reveal`: use for black-bar center reveals, optionally with subject cutouts or stuttered backgrounds.
- `vibeedit-reverse-curtain-subject-reveal`: use after reverse curtain selects a masked subject reveal variant.
- `effects`: design grid/tile transitions using concrete supported layers or derived visual assets; no dedicated tracked tile/object renderer is bundled. Model detection alone is not a rendered transition.
- `vibeedit-reverse-curtain-subject-reveal`: provides the combined curtain/randomized-frame background variant. For standalone stutter, specify exact non-repeating source frames/ranges in a CompositionSpec and render/review the result.
- `vibeedit-effects`: use only for constructed transition recipes that are not better owned by a specific transition skill.

The packaged `models effect` path materializes reviewed subject-color fills. Full subject-cutout flash transitions, shimmer and split-band pulses require a concrete supported CompositionSpec or derived asset and frame review; invoking SAM alone does not implement them. Direct `maskIds` are not a rendering proof. Preserve these creative recipes as explicit plans until their materialized effect is verified.

Do not edit those downstream skills from this role. Route to them, cite them, and return the exact transition contract they need.

## Transition Weight

Assign one weight to the overall edit and one decision to each cut.

- `none`: clean cut; the source motion, quote, or beat already carries the moment.
- `light`: subtle motion bridge, short dissolve, micro zoom, tiny whip, or one-frame accent; low frequency.
- `medium`: visible transition on selected section turns or strong beats; moderate frequency.
- `heavy`: frequent and complex transition language for high-energy or fast-paced songs, but still tied to story and readable clip choices.

Weight is driven by song energy, cut density, source motion, platform style, and story clarity. Higher energy and faster pacing allow heavier transitions, but they do not require a transition at every cut.

## Review Workflow

1. Read the main structure.
   - Require a cut list, timeline plan, or assembly plan.
   - Record the source clip before and after each cut, timeline frame/time, song section, beat/transient proximity, story function, and clip-B first-frame subject quality.

2. Choose the edit-level transition posture.
   - Decide `none`, `light`, `medium`, or `heavy`.
   - Explain how that posture matches the song energy and edit style.
   - Record how often transitions should appear and where clean cuts are stronger.

3. Review every cut.
   - Keep clean cuts when the source motion, impact, quote, or rhythm is already clear.
   - Use a transition when it clarifies a story turn, emphasizes a beat, hides a continuity jump, introduces a stronger subject, or creates a memorable center point.
   - Avoid stacking complex transitions on weak moments.

4. Prefer subject flash only when it earns the attention.
   - Clip B must start with a strong person, face, body, prop, vehicle, creature, or grouped subject.
   - The subject must be segmentable in the first active frames.
   - The transition should focus the story, not merely decorate a random cut.
   - If clip B is weak, shift or replace clip B before forcing the transition.

5. Return a transition contract.
   - Name selected downstream skill(s).
   - Include exact cut id, timeline range, source A/B ranges, active frame count, SAM runner command/output path when relevant, weight, SFX needs, and proof state.
   - Mark unexecuted transitions as `planned`; do not claim previewed, rendered, reviewed, or accepted.

## Output Shape

```yaml
role: viral_transition_reviewer
proof_state: planned
edit_transition_posture:
  weight: none|light|medium|heavy
  frequency: ""
  rationale: ""
cuts_reviewed:
  - cut_id: ""
    timeline_time: ""
    from_clip: ""
    to_clip: ""
    song_anchor: ""
    decision: clean_cut|transition
    weight: none|light|medium|heavy
    transition_family: ""
    downstream_skills: []
    timeline_or_clip_change_allowed: true
    requested_timeline_adjustment: ""
    sam_execution: none|required|ran|rejected
    sam_artifact_path: ""
    sfx_note: ""
    proof_state: planned
transition_plan: []
rejected_transitions: []
blockers: []
next_actions: []
```

## Quality Gates

- Every cut has a decision, including clean cuts.
- Subject-flash transitions must prove or request a strong clip-B subject in the first active frames.
- Mask-dependent transitions must run `vibeedit models run sam31-mlx` or `vibeedit models run sam21` and cite the resulting SAM artifact path. Proxy masks, geometric masks, boxes, and decorative flashes are not valid test outputs.
- Timeline changes are allowed only for transition quality, story focus, or no-jump landing needs.
- Do not promote any transition beyond `planned` without concrete preview/render/review evidence.
