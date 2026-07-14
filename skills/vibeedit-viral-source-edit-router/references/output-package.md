# Output Package

Use this shape for plans, packets, handoffs, manifests, and review summaries. Omit empty sections only when the omission is explicit and harmless.

```yaml
edit_type: vibeedit-viral-source-edit-router
proof_state: planned
brief:
  thesis: ""
  target_runtime: ""
  aspect_ratio: source-native
  text_overlays: none
workspace_paths:
  sources: []
  analysis: []
  audio: []
  outputs: []
roles:
  producer: {}
  source_researcher: {}
  style_analyst: {}
  story_editor: {}
  song_analyst: {}
  action_sync_planner: {}
  quote_moment_curator: {}
  sfx_planner: {}
  assembly_planner: {}
  viral_transition_reviewer: {}
  viral_effects_reviewer: {}
  qa_review: {}
  memory_wiki_editor: {}
source_board:
  selected: []
  rejected: []
timeline_plan: []
transition_plan:
  posture:
    weight: none
    frequency: ""
    rationale: ""
  cuts_reviewed: []
audio_plan:
  music: []
  dialogue: []
  source_sound: []
  sfx: []
effects_plan:
  density:
    weight: none
    rationale: ""
  unused_audio_anchors: []
  events: []
assembly_plan:
  renderer_or_editor: ""
  dimensions: source-native
  fps: source-native
  codec: ""
  dry_run_command: ""
  apply_command: ""
qa_plan:
  checks: []
  current_results: []
memory_notes:
  store: []
  do_not_store: []
gaps: []
next_actions: []
```

## Minimum Selected Moment Fields

```yaml
- id: ""
  source_path: ""
  source_range: ""
  timeline_range: ""
  role: hook|build|turn|peak|aftershock|loop|bridge
  evidence: ""
  sync_anchor: ""
  proof_state: planned
```

## Minimum SFX Fields

```yaml
- id: ""
  timeline_time: ""
  asset_path: ""
  generation_needed: false
  gain_intent: ""
  sync_reason: ""
  proof_state: planned
```

## Minimum Transition Decision Fields

```yaml
- cut_id: ""
  timeline_time: ""
  from_clip: ""
  to_clip: ""
  decision: clean_cut|transition
  weight: none|light|medium|heavy
  transition_family: ""
  downstream_skills: []
  requested_timeline_adjustment: ""
  proof_state: planned
```

## Minimum Effect Event Fields

```yaml
- effect_id: ""
  timeline_time: ""
  song_anchor: ""
  source_subject: ""
  effect_family: ""
  downstream_skills: []
  structure_change_allowed: false
  proof_state: planned
```

## Handoff Footer

End unfinished work with:

- highest proven state
- concrete blocker or gap
- exact next command, inspection, or decision
- no-overclaiming note for any unrendered, unreviewed, or unaccepted work
