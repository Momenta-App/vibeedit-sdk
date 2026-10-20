# Portable projects and review

Create a project with a source-free CompositionSpec, then import media. Import
copies exact bytes into content-addressed project storage and records a streamed
native clock census. The `project.vibeedit.json` snapshot is readable by any
agent; the project SQLite journal serializes corrections and revision changes.

```sh
vibeedit project create my-edit --composition composition.json --json
vibeedit project import my-edit --media source.mp4 --expected-revision 0 --json
vibeedit project inspect my-edit --json
vibeedit review words --project my-edit --source-id SOURCE_ID --baseline-id BASELINE_SHA --json
```

Use `beats`, `faces` or `video` for the other focused review interfaces. The
returned loopback URL is a project capability: give it only to the intended local
browser. It does not upload media. The service binds to 127.0.0.1, validates Host
and mutation Origin, and uses a per-port session cookie. Each project has its own
service and token. Browser drafts are provisional until the saved revision is
acknowledged. A stale revision requires review of the concurrent change.

Imported analysis retains the original service job ID, source digest, schema
version and exact immutable baseline. Human changes are append-only overlays;
refreshing a baseline exposes prior corrections as mapping conflicts. Anonymous
voices, visual people and confirmed speaker links have separate meanings. An
unresolved identity stays unresolved. Word times without an explicit audio/video
projection remain on the first decoded audio-sample clock. Human correction of
one boundary does not certify the other machine boundaries.

`project correct --command-file FILE` applies the same commands as the browser.
Every command carries an operation ID, expected revision, author, source ID and
SHA256. Word/face commands also bind a baseline ID. Exact operation retries
reconcile; changed reuse and stale edits fail. Undo is another recorded command.
`project export` exports the document and complete correction journal as JSON.
`project apply-review` builds a new CompositionSpec for explicit `reviewBeat` or
`reviewWord` layer bindings; it preserves the parent composition and refuses
unmapped timing. The agent renders and inspects that composition before delivery.

Register generated masks, review strips and render receipts before transfer:

```sh
vibeedit project register-artifact my-edit --category masks --artifact masks/reviewed-run --source-id SOURCE_ID --expected-revision REVISION --json
vibeedit project bundle my-edit --output backup.vibeedit.zip --json
vibeedit project restore restored-edit --archive backup.vibeedit.zip --sha256 ARCHIVE_SHA256 --json
```

The bundle contains registered source media/clocks, analysis, generated artifact
trees, composition ancestors, corrections and passive goal/job recovery state.
It contains private creative material and prompts: share it deliberately. It
excludes API keys, browser sessions, Pi chats, executable runtime installations
and local service capabilities. Per-file lengths/digests, path safety, membership
and a total byte ceiling are checked before a restored project is published.
Restore requires a new directory and starts no execution. Active recovered goals
and workers are paused; inspect original paid handles before explicit resume.
Unknown admissions and outstanding financial holds remain unknown/held.

Use `--omit-media` for a smaller bundle. The original source digest and clock
remain; `project relink --source-id ID --media FILE --expected-revision REVISION`
accepts only identical bytes. A transcoded proxy is a different source and must
carry an explicit mapping. Never relabel it as the original. Arbitrary unregistered
files, external URIs and private runtime state are not swept into backups.

Native face results use the indexed import adapter rather than flattening the
package into an invented JSON service response:

```sh
vibeedit project import-faces my-edit --source-id SOURCE_ID --archive original.faces.zip --job-id NATIVE_JOB_SHA256 --sha256 ARCHIVE_SHA256 --archive-bytes BYTES --expected-revision REVISION --json
vibeedit review faces --project my-edit --source-id SOURCE_ID --json
```

The import retains every native ZIP member, exact native frame/geometry evidence,
source/job/library pins, unresolved groups and a sealed paginated index. Preview
buttons decode the exact saved PTS from the original source; a neighboring frame
is never substituted. A selected portrait is a local overlay. Merge, split,
assignment and restore use the actual current customer-scoped library revision.
The original command is saved before transmission and remains pending after an
unknown acknowledgement. Retry replays that same body; a stale library requires
comparison rather than an automatic rebase. Only Myriograph's applied revision
acknowledgement marks the saved change applied. The original machine package
remains immutable. Library identity counts include aliases and are not a verified
number of people; native CFR coverage does not qualify VFR source identity.

For negative word captions inside footage, use the existing `html-css` motion
component with white text on transparency and set `render.motionBlendMode` to
`difference` on an `html` or `mixed` composition. The whole motion stack blends
against decoded source pixels using its alpha; this setting applies to every
motion layer. CSS difference blending inside an isolated transparent iframe alone
cannot invert the video. Keep other treatments in a separate render pass.
An HTML text node can contain `{{text}}`; the renderer substitutes the escaped
`props.text` value. This lets source-bound `reviewWord` corrections update designed
captions while preserving their HTML/CSS. Use one stable occurrence per word and
explicit start/end frames; interpolated subtitle timing is a styling preview,
not verified word alignment.
