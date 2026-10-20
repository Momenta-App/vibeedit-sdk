---
name: fanedit-text
description: Router for fan-edit text, typography, captions, kinetic titles, lyric/dialogue overlays, graphic quote cards, and text-heavy motion graphics. Use this first when a user asks for text on video or a text style, then choose exactly one implementation skill unless the task clearly needs a support/QA skill too.
---

# Fanedit Text Router

## Portable SDK execution

This packaged skill runs in the user's existing agent; no desktop application or open editor tab is required. Resolve local `scripts/` and `references/` from this installed skill directory. The parent agent may perform every role; “Lead Editor” means the one revision-checked writer, not a required external process.

Start with `vibeedit project inspect "$PROJECT" --json`. Use the current CompositionSpec and content-bound source IDs; create a new composition revision and run `vibeedit validate` / `vibeedit render` for concrete output. Persistent review uses `vibeedit review beats|faces|words|video --project "$PROJECT"`, then `vibeedit project apply-review "$PROJECT" --source-id SOURCE --domain DOMAIN --expected-revision REV`. Retain immutable machine baselines and user corrections across rerenders.

Paid intelligence goes through public `vibeedit analyze video|faces|speakers` with a stable operation ID and an existing authorized `--max-retail-usd` ceiling. Observe/recover that original job; timeout never licenses a replacement paid submission. Words, anonymous voice labels and visible face identities remain distinct. Optional masks use explicit `vibeedit models describe` / `models run sam21|sam31-mlx`, reviewed candidate selections and supported `models effect`; never label geometric fixtures as SAM proof. Use user-provided permitted sources and approved SFX manifests; the package carries no movie, quote or private sound library.


Use this as the lightweight entry skill for text-on-video decisions. Do not load every text skill. Pick the smallest matching implementation skill, then read only that skill's `SKILL.md`.

## Routing Rules

1. Identify the text job: fan-edit quote/lyric overlay, captioning, TypeFlow recreation, talking-head graphics, motion graphic, full-screen negative word hits, or media/transcription support.
2. Choose one primary implementation skill from the table below.
3. Add a support skill only when needed for face placement, masks, or QA.
4. Preserve shared rules unless the selected style explicitly overrides them:
   - word timing should follow transcript/lyric word starts when available;
   - stale text should clear before a new speaker or unrelated lyric;
   - avoid covering faces when the chosen style includes face awareness;
   - respect right-side TikTok/Reels UI safe zones when the chosen style requires it;
   - validate with contact sheets, layout data, and final render checks.

## Primary Text Skills

- `negative`: flat bold all-caps word/caption hits with Medium as the default size, plus Small and Extra Small for subtler centered captions. Almost never choose Ultra or Max unless the user explicitly asks for giant/full-screen impact text. Best for centered single-word replacement text with exact timestamps, transcript/caption ingestion, difference blending, and no 3D/shadow/face tracking.
- `negative-face-follow`: flat all-caps one-word text that follows near the active face without covering it, using a difference/invert look and transcript-accurate word timing.
- `vibeedit-compact-3d-typography` with the portable `talking-head-captions` / `dialogue-quote` templates: compact bold fan-edit quote text with red/outline emphasis, face-aware placement, social-safe bounds, flexible line packing, and word-by-word reveals. Best for movie/sports/anime dialogue punches over real footage.
- `vibeedit-compact-3d-typography`: compact one-word or short lyric/quote hits with perspective-tilted 3D flat text, red emphasis, and face-aware placement. Best for sharper lyric accents and title-like hits.
- `typeflow-text-motion`: recreate clean TypeFlow/DaVinci-style kinetic text tutorial/demo clips from a reference MP4 or text brief. Best when the user names TypeFlow or wants literal tutorial-style text motion.
- `embedded-captions`: add designed captions/subtitles to talking-head footage using its identity catalog. Best for captioning every spoken word or packaging a single-subject talking-head clip.
- `graphic-overlays`: add timed graphic overlay cards, lower thirds, quote panels, callouts, and kinetic titles over an existing video. Best for designed cards rather than plain subtitles.
- `talking-head-recut`: package an interview/podcast/talking-head video with transcript-synced graphic cards and overlays. Best when the whole source video plays through and needs editorial dressing.
- `motion-graphics`: create short standalone text-led motion graphics, kinetic typography, title cards, social overlays, animated headlines, or stat hits. Best when the deliverable is authored graphics rather than text over source footage.
- `hyperframes-media`: transcription, captions/subtitles/lyrics/karaoke data, TTS, BGM, SFX, and media preparation for HyperFrames compositions. Best as a media/text-data support skill, not a visual style by itself.

## Support Skills

- `vibeedit-face-tracking-framing`: use when text placement depends on face/person/body detection or avoiding faces.
- `video-review`: use after rendering to audit readability, OCR, face overlap, safe zones, and visual continuity.
- `vibeedit-qa-gap-discipline`: use when reviewing a reusable fan-edit text skill or formal render QA.

## Selection Hints

- If the user asks for bold flat all-caps word hits, use `negative` and default to `medium`.
- Use `negative` `ultra` or `max` only for rare full-screen impact moments or when the user explicitly asks for giant text.
- If the user asks for one word at a time near/following a face, use `negative-face-follow`.
- If the user says "same style as the Creed text" or wants bold social quote text over real footage, use `vibeedit-compact-3d-typography` with the portable `talking-head-captions` / `dialogue-quote` templates.
- If the text should be minimal, punchy, and mostly one word at a time with 3D/perspective, use `vibeedit-compact-3d-typography`.
- If the user provides a text-animation reference clip, use `typeflow-text-motion`.
- If the user asks for captions/subtitles on talking-head footage, use `embedded-captions`.
- If the user asks for lower thirds, quote cards, data cards, or editorial panels, use `graphic-overlays` or `talking-head-recut`.
- If there is no source footage and the text itself is the video, use `motion-graphics`.

## Counting

This router points to 10 primary text-related target skills: 9 implementation/style skills plus 1 media/text-data support skill. Counting this `fanedit-text` router itself, there are 11 text-related skills in this tree. It also points to 3 support/QA skills for placement and review.
