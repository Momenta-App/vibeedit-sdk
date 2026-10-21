# Optional Pi workers and durable goals

This guide describes the `0.2.0-beta.2` source candidate, which is not yet published or qualified. The previous `0.2.0-beta.1` archives remain immutable. Full Codex/Claude Code, BYOK/managed and crash/recovery acceptance remains open in the [launch ledger](https://github.com/Momenta-App/vibeedit-sdk/blob/v0.2.0-beta.2/docs/launch/PUBLIC-LEDGER.json). Ordinary editing works without Pi or an account.

The Python CLI owns supervision and project state. Its optional runtime pins official `@earendil-works/pi-coding-agent` `1.3.0`, requiring Node >=22.19.0. Installation is project/user-local; it creates no always-on system service.

```sh
vibeedit worker setup --json
vibeedit worker profiles --refresh --json
```

Choose funding explicitly. BYOK sends your OpenRouter credential directly from the local forwarding process to OpenRouter. Enter it through `worker configure --key-stdin`; never place it in argv, a model prompt, a project or Git. Unix config is owner-protected; Windows config uses user-scoped DPAPI. Pi receives a temporary loopback capability rather than that credential.

Managed funding uses your scoped Myriograph customer config and the same prepaid balance as the three analysis services. Provider credentials remain server-side. Follow [Myriograph setup](MYRIOGRAPH.md), then inspect the actual gateway:

```sh
vibeedit worker profiles --funding managed --json
```

Disabled access, insufficient credit, unknown prices or changed scope stop admission. They never switch to BYOK or an internal credential. Funding is metered prepaid with optional explicitly consented auto top-up; there is no monthly subscription grant.

## Specify and run bounded work

Read the shipped [task and goal contracts](../skills/vibeedit-companion/references/contracts.md). A task specifies funding, versioned profile, output JSON Schema, artifact contracts, project-relative references with SHA256 digests, allowed tools, dollar/time/model/tool bounds and `delegationLimit: 0`.

The selectable profiles are `economical-v1`, `visual-v1` and `reviewer-v1`. Inspect their actual model, dated endpoint, provider route and fresh price before choosing; a profile name does not permit a fallback. A visual task needs a later model turn to consume an image tool result. Supported image transport is source-linked PNG/JPEG; direct video transport is unavailable.

The following minimal `task.json` illustrates structured output. Its USD0.20 ceiling is an example, not spending authorization or a current quote. It is not an edit goal or a claim that a source was reviewed.

```json
{
  "task": "Return scope and uncertainty fields through submit_result. State that no source media was supplied; do not claim to have reviewed a video.",
  "funding": "byok",
  "profile": "economical-v1",
  "references": [],
  "referenceDigests": {},
  "tools": [],
  "outputSchema": {
    "type": "object",
    "properties": {"scope": {"type": "string"}, "uncertainty": {"type": "string"}},
    "required": ["scope", "uncertainty"],
    "additionalProperties": false
  },
  "artifacts": [],
  "maxModelCalls": 3,
  "maxToolCalls": 3,
  "maxOutputTokens": 1024,
  "maxRetailMicrousd": 200000,
  "maxSeconds": 60,
  "delegationLimit": 0
}
```

After inspecting the quote and obtaining the applicable allowance:

```sh
vibeedit worker run --project ./edit --id metadata-1 --spec task.json --json
vibeedit worker status --project ./edit --id metadata-1 --json
vibeedit worker events --project ./edit --id metadata-1 --after 0 --json
vibeedit worker steer --project ./edit --id metadata-1 --operation-id revision-1 --message "Keep uncertainty explicit." --json
vibeedit worker cancel --project ./edit --id metadata-1 --json
```

`submit_result` is always available and counts as a tool call. Optional tools provide bounded project reads/images, immutable artifacts and constrained SDK FFmpeg rendering. They provide no arbitrary shell, executable HTML, process, network or purchase tool. This is a controlled tool boundary, not an OS sandbox against hostile local code.

Paid analysis additionally requires exact `analysisPermissions` for operation, service, source SHA and retail cap. Managed analyses and inference share the original server goal allowance. `analysis_status` may download original verified results; bounded JSON reads retain the original worker/source/job/digest grant. Downloading a face ZIP does not imply its contents were understood; import and review its scoped index separately.

## Goals, disconnects and recovery

```sh
vibeedit goal start --project ./edit --id edit-1 --spec goal.json --json
vibeedit goal status --project ./edit --id edit-1 --json
```

A goal requires an objective, acceptance criteria, ordered bounded worker steps, a future Unix deadline, a total allowance covering its children, and completion contracts for an editable composition, playable render and source-linked review. Pause/resume/edit/cancel/export address the same goal; lifecycle mutations require its current `--expected-revision`. The packaged Pi `/goal` extension calls that same lifecycle. Already-admitted steps cannot be rewritten by a later edit.

The detached local supervisor can outlive its parent command. The computer must remain awake, with network access when applicable. Sleep, offline time and disk-full states are visible waits; they do not imply continued progress. Pi finishing a turn, repeated polling or a written plan does not complete an edit goal.

SQLite stores intents before provider/tool sends, original handles, reservations, checkpoints, revisions and lease fences. Pause stops scheduling and propagates cancellation where supported; accepted work and settlement remain observable. Unknown acknowledgements retain their holds. Use original IDs for exact retries:

```sh
vibeedit worker reconcile --project ./edit --id metadata-1 --operation-id ORIGINAL_OPERATION --json
vibeedit worker recover --project ./edit --id metadata-1 --json
```

Reconcile observes the original operation. Recover can adopt an exact committed result only after its artifact contracts and financial/tool settlements validate and no live lease remains. Neither repeats inference to repair an unknown outcome. Do not delete rows/WAL files, reset a campaign counter, release unknown holds or create a replacement paid job after an observer timeout.

BYOK cost enforcement is conservative and local, not proof of a provider-account hard cap. Myriograph is the managed money authority. Provider cost, retail settlement, infrastructure and held allowances remain distinct. Managed replies are completed durable responses buffered into local SSE for Pi; this does not claim upstream token streaming.

For transfer, use [project bundle/restore](PROJECTS.md). It preserves passive goal/operation IDs and holds, excludes credentials and Pi chats, and restores active work paused with new fences. Resume explicitly. Before upgrade or rollback, pause admissions, retain a complete closed/SQLite-backup copy of the project, and verify compatibility with the intended package manifest. No cross-version goal migration or human editorial acceptance is inferred from a successful restore.
