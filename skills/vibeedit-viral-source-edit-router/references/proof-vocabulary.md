# Proof Vocabulary

Use these states exactly. Never collapse them into "done" or "ready."

## States

- `planned`: the brief, evidence board, or timeline choices exist, but no editor mutation or render is proven.
- `dry-run`: an assembly, render, import, or validation command checked inputs without making the final mutation.
- `applied`: the project or timeline was changed and the mutation path is known.
- `previewed`: a real preview artifact or live editor surface was inspected.
- `rendered`: an output video/audio/image artifact exists at a cited path.
- `reviewed`: QA inspected the artifact and recorded checks.
- `accepted`: review passed or accepted gaps are explicit and attributable.
- `blocked`: a concrete missing source, artifact, permission, tool, safety gate, or runtime failure stopped progress.

## Claim Rules

- Say `planned`, not `ready`, when the work is still a packet.
- Say `rendered`, not `reviewed`, when a file exists but no QA pass was done.
- Say `reviewed`, not `accepted`, when QA found unresolved issues.
- Say `blocked` only with a concrete blocker and the next useful action.
- Say `unproven` for sync, timing, masks, SFX, effect support, or acceptance that has not been inspected in the artifact.

## Evidence Requirements

Source evidence:

- media path
- transcript/caption/analysis path when used
- source range or nearest known anchor
- reason the moment supports the edit

Timeline evidence:

- timeline range
- source range
- layer type
- sync anchor
- current mutation/render state

Audio/SFX evidence:

- asset path or generation result
- timeline time
- gain/mix intent
- sync reason
- reviewed or unreviewed status

Render/review evidence:

- artifact path
- command or tool path when known
- inspection mode
- pass/fail notes
- accepted gaps

## No-Overclaiming Examples

- "The timeline plan targets the drop at 18.4s; frame sync is unproven until previewed or rendered."
- "The MP4 exists at this path, but I did not run QA, so the state is rendered."
- "The source researcher found candidate quote ranges, but the quote context is unreviewed."
- "The edit is blocked because the requested song file is missing; the next action is to import or select music."
