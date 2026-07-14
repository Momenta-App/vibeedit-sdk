---
name: workspace
description: Flexible operating guidance for media/editing workspaces, including project discovery, media inventory, timeline review, local storage boundaries, and safe in-scope editing.
---

# Workspace Skill

Use this skill when the user is working inside a media/editing workspace and wants to inspect or modify project data directly.

## Core Behavior

- Be flexible, but start with a project review gate: project identity, current edit state, timeline/media inventory, existing analysis artifacts, and any collaboration/version guard available.
- Prefer editor-native workspace tools and flows before direct file edits when a live editor or project API exists.
- Treat workspace/project files as source material, but avoid bypassing safer mutation and verification flows when they exist.
- Stay inside the active selected workspace root unless the user explicitly changes scope.
- If the user asks to use editor tools, operate through those tools instead of direct data-file edits.

## Active Workspace Discovery

Use the first reliable source in this order:

1. Explicit path from the user.
2. Injected context, selected workspace, or active project context.
3. Current working directory when it clearly contains project/media files.

Confirm the root contains a plausible project marker, media library, or edit data before treating it as a workspace. Do not place mutable workspaces under test-output, build-output, or watched source trees while an app/dev server is running; those folders can trigger reload loops.

## Workspace Folder Model

A typical editing workspace may include:

- project or sequence files
- media assets: video, audio, images, graphics, captions, proxies, thumbnails
- media metadata and project-to-media links
- analysis artifacts: transcripts, beat maps, scene cuts, detections, cutouts, waveform caches
- render/preview outputs
- content or asset-library folders

When editing timeline/workspace behavior, verify that file changes align with the target workspace's actual structure rather than an assumed schema.

## Project Discovery and Review Gate

Discover usable projects by reading obvious project files, manifests, sequence files, or editor-exported metadata. Before editing, record the project/sequence identity, last modified time, version/collaboration guard if available, track/layer count, item count, transition count, linked media, and relevant analysis artifacts.

## Timeline Structures

Common timeline concepts:

- tracks/layers with order, visibility, lock/mute state, and media type
- clips/items with ids or labels, track/layer targets, source ranges, timeline ranges, type, transforms, speed, volume, and media references
- transitions and markers with valid adjacent material and enough handles
- text/shape/overlay items that may not reference media but still need timing, placement, and readability checks
- audio items with source ranges, gain, fades, ducking, EQ/filter notes, and sync anchors

Preserve the native timing units used by the target editor. If converting between frames, seconds, timecode, samples, or beats, state the conversion.

## Project Editing Guidance

- Reuse existing cached analysis outputs before requesting new analysis.
- If new analysis is needed, use approved or available editor/workspace flows when available.
- Do not install/download external services or models, and do not run standalone media analysis unless explicitly requested by the user.
- In orchestrated production flows, Lead Editor is the only production writer; workspace guidance supports discovery, scope, and safe file/tool handling.
- Directly edit project data only when the user explicitly asks for filesystem/project-file edits or safer editor tools are unavailable and the user accepts that path.
- Prefer narrow, reversible edits over broad rewrites.
- Update related files consistently (for example, project metadata plus media links).
- If a referenced file is missing, report it clearly and continue with recoverable steps.
- Preserve valid structures and existing identifiers.
- Preserve the existing schema/format shape; do not invent optional fields or new IDs unless the edit requires them.
- Validate changed track/layer references and media references against available state.
- Re-read version/collaboration guards immediately before writing when they exist. If the project changed from your review gate, stop and rebase from the latest state.
- Compare before/after with a focused diff and report only meaningful timeline/project changes.
- Keep proof states distinct: `planned`, `dry-run`, `applied`, `confirmed`, `previewed`, `rendered`, and `proven`.

## Efficient Helper Checks

- Find project identities: inspect obvious project/manifest files and ignore malformed or partial folders.
- Check version state: capture modified time, revision/fingerprint/version fields when available, last actor, and update time.
- Identify whether a project changed: compare version guards first, then modified time, then a focused before/after diff of timeline, metadata, and affected fields.
- Validate media references: collect linked media ids/paths from project data and ensure referenced files or metadata exist.
- Compare safely: write temporary comparison output outside watched app/source trees or use in-memory comparisons when a dev app is running.

## Scope Lock Requirement

- Resolve all read/write/edit/shell paths against the active workspace root.
- Reject attempts to traverse outside scope (`..`, absolute external paths, sibling folders).
- If the user needs another folder, ask them to re-scope first, then continue.

## Optional Validation Flow

When a request changes behavior or data flow:

1. Confirm the target file(s) or editor target under the active workspace root.
2. Apply the minimal change.
3. Re-read or re-check affected files/outputs.
4. Report what changed and how to undo manually if needed.
