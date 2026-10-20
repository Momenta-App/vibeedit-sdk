---
name: vibeedit-setup
description: Install and verify VibeEdit for this project, then make and revise an editable video using its existing media runtime and creative skills.
---

# Give your agent VibeEdit

Inspect the project, operating system, Python (3.11+), Node (20+; Pi needs
22.19+) and FFmpeg first. Preserve the user's tools and files. Install only
what this task needs, in project-local isolated environments. Ordinary editing
requires no account, API key or Pi companion.

1. Read the published release manifest linked from the SDK launch page. If you
   received only this skill URL, fetch its relative `scripts/setup.py` and the
   release manifest from that same official release. Verify the setup script
   SHA256 against the manifest before running it. Use
   `scripts/setup.py --manifest URL --project PROJECT --harness codex` (or
   `claude`). It downloads the exact hash-bound wheel, verifies its version,
   installs it into an isolated environment, runs doctor, and installs this
   small router. Core dependencies are installed from the release's hash-locked
   requirements; this bootstrap does not resolve a different future dependency set.
   Follow its returned absolute command; do not rely on aliases.
   The installer requires Python 3.11+. If missing, retain progress and ask the
   user to install Python from python.org or use an already-installed uv Python.
   Do not replace system Python or request admin permissions.
2. Read doctor output and fix relevant missing dependencies. FFmpeg/FFprobe are
   external tools; explain the platform-specific package-manager action before
   changing unrelated global tools. Browser, models and Pi are optional and
   install only when the selected workflow needs them. Show download/disk needs.
3. Use `examples list --details --json` and compact `catalog search` to select a
   starting point. Install only selected creative skills with `skills install`.
   On returning projects use `skills check`/`update`; preserve modified skills.
4. For a free first edit create `basic-generated`, render it, and verify it.
   Preserve the CompositionSpec and render report. For user clips/music, create a
   project, register sources by digest, then build the existing CompositionSpec.
   Open `review video --project PATH --source-id ID --json` on the actual render.
   Inspect frames/audio, save source-linked revision notes and execute one revision.
5. For fan edits load direction, hook/body, story selection, pacing, typography,
   sound and finishing skills relevant to the brief. A template render alone is
   not editorial proof. Inspect story, beat alignment, readable text, framing,
   masks, audio and the ending. Keep editable layers and source provenance.
6. Use local `review beats|faces|words|video` for focused human corrections.
   Saved project revisions are authoritative; browser storage is only a draft.
   Machine baselines remain immutable. Resolve stale revisions/mapping conflicts.
7. Use `models list` before optional local model setup. Inspect actual platform,
   disk/memory and qualified devices. SAM 2.1, SAM 3.1 and MLX are distinct.
   Never label geometric masks or a different model as a successful model run.
8. If paid intelligence is needed, use Myriograph's public signup/key/funding
   links and customer credentials only. Quote an enforced maximum retail amount
   and obtain a bounded allowance. Keep native job handles; a wait timeout ends
   observation, not the job. Missing evidence/identity stays uncertain.
9. Worker and goal commands are optional. Keep BYOK and managed funding explicit,
   propagate parent permissions, and inspect durable receipts before retrying.
   A sleeping local computer is waiting, not continuing work.

Never copy private libraries, developer credentials or movie/reference media
into a release. Deliver editable composition/project, source receipts, beatmap,
review/correction export and playable output. State capability and accuracy limits.
