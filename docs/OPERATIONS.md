# Operations and recovery

Updated 2026-10-20. These are customer recovery instructions and an operating contract for the qualification prerelease. They do not mark launch acceptance complete. All P0–P10, J1–J7 and A01–A20 remain required and open in the [public ledger](https://github.com/Momenta-App/vibeedit-sdk/blob/v0.2.0-beta.2/docs/launch/PUBLIC-LEDGER.json).

## Release identity and qualification

This guide targets Python `0.2.0b2` / npm `0.2.0-beta.2`, with optional Pi `1.3.0`.
Obtain availability, exact hashes and source revision from that version's
[release manifest](https://github.com/Momenta-App/vibeedit-sdk/releases/download/v0.2.0-beta.2/release-manifest.json).
An unavailable manifest means the candidate is unavailable; do not substitute
older archive bytes under its version.

For previous qualification and rollback, the public [v0.2.0-beta.1 prerelease](https://github.com/Momenta-App/vibeedit-sdk/releases/tag/v0.2.0-beta.1) contains Python `0.2.0b1` and npm `0.2.0-beta.1` from source commit `7ff8ff1a9caf1f53d7f8cba7fbbfec97d0dd61e1`. Its [canonical workflow](https://github.com/Momenta-App/vibeedit-sdk/actions/runs/39507366659) passed thirteen listed core jobs: six source-platform checks, one build/attestation job and six installations of the same exact archives. This establishes those recorded portable-core checks, not qualification of beta.2, paid services, optional model inference, editorial accuracy or both complete agent journeys.

| Previous beta.1 release file | SHA256 |
|---|---|
| `release-manifest.json` | `16f5ac1aff3b364e4bf479b30c593fc97e8d8ef84add023518a9c10f7800b341` |
| `vibeedit-0.2.0b1-py3-none-any.whl` | `6e3fbe0759a7064f6f02943770a1902a202a31c0aa46d27498b13ce7fcb50c86` |
| `vibeedit-0.2.0b1.tar.gz` | `e4226498ef6aa77883485376bf1004127cb57b52a67e219d1b12c2dcd7b5adc8` |
| `vibeedit-0.2.0-beta.1.tgz` | `67991e0a828977b3205bec5379a9fd05249168ae877ed1dd08e8533ec4b6113e` |

Download checksums, archive audit and signed provenance from that same release. Verify the exact files before installation; follow the [artifact workflow](https://github.com/Momenta-App/vibeedit-sdk/blob/v0.2.0-beta.2/docs/RELEASE.md). Registry publication and clean public registry installation remain separate gates. These documents may receive a later source commit as a documentation supplement; that does not replace the tag, rebuild archives or change their hashes.

The [Myriograph billing page](https://myrograph.com/billing) is public and production billing is live. Qualification authentication uses a restricted, separate test wallet; it does not make production charges safe to test. New native/managed paid admission and optional automatic top-up remain disabled while the complete signed sandbox-payment and funded customer journeys are unqualified. Neither deployed code nor a successful local fixture establishes those journeys. [Current state](https://github.com/Momenta-App/vibeedit-sdk/blob/v0.2.0-beta.2/docs/launch/STATE.md) records subsequent changes.

## Preserve a recoverable project

Keep source digests, original operation/native job IDs, correction revisions and receipts with the project. Do not move credentials into it. Before an update, transfer or local deletion, make a private portable backup:

```sh
vibeedit project inspect my-edit --json
vibeedit project bundle my-edit --output backup.vibeedit.zip --json
```

The bundle contains registered project material and passive recovery state, not every arbitrary file beside the project. It may contain private media and prompts. Record its returned checksum separately. Restore into a new destination using that exact checksum:

```sh
vibeedit project restore restored-edit --archive backup.vibeedit.zip --sha256 ARCHIVE_SHA256 --json
```

`ARCHIVE_SHA256` is the actual saved digest, not a value to invent. Restore validates membership, lengths and digests and starts no execution. Recovered active goals/workers are paused. Import the original authorized account/project config separately, inspect original paid operations, then decide whether to resume. See [projects and corrections](PROJECTS.md).

## Incident response for customers

If an operation is slow, a process crashes, a payment return is missing credit or the agent loses its connection:

1. Preserve the original project, operation/job handle, account/project/mode, source digest, error code and time. Do not clear its database or choose another operation ID to make the error disappear.
2. Inspect `vibeedit jobs list --project my-edit --json` and `vibeedit jobs status saved-operation --project my-edit --json`. Status observes; a timeout is not a failed job, refund or permission to buy again.
3. For a known original operation, explicitly request `vibeedit jobs resume saved-operation --project my-edit --json` when appropriate. Recovery preserves the original request. It can wake proven-unsent work or reconcile saved responses; unknown physical sends stay fenced. A missing or conflicting original remains a support case, not a replacement request.
4. If you want future native work stopped, use `vibeedit jobs cancel saved-operation --project my-edit --json`. Already dispatched work and settlement may continue. Keep observing the original until its financial outcome is known.
5. Download required evidence before its reported expiry. A refreshed signed download must still belong to the same job and hashes. Retain the original machine output alongside corrections.

For a durable goal, inspect its current revision before changing it:

```sh
vibeedit goal status --project my-edit --id saved-goal --json
vibeedit worker status --project my-edit --id saved-worker --json
vibeedit goal pause --project my-edit --id saved-goal --expected-revision REVISION --json
```

Replace `REVISION` only with the current acknowledged integer. Pause stops future goal work and requests that child work stop; it does not undo a dispatched provider call. The same goal retains its shared funding allowance. Inspect the original worker's events and use its explicit recovery/reconciliation commands after understanding the retained operation. Do not start another worker/goal to evade an unresolved hold. Crash/stop/resume behavior has bounded local checks; full real BYOK/managed crash qualification remains open.

For a lost payment acknowledgement, refresh the original wallet/history and retry only the page's saved original intent where offered. Preserve the original Checkout or automatic-attempt reference. Signed settlement, rather than the return page, determines credit. Disabling optional automatic top-up prevents new attempts; it does not erase sent/unknown attempts or their monthly commitment. Request private support before replacing an unresolved payment.

If a credential expires or is revoked, reauthenticate through the [account page](https://myrograph.com/billing), choose the original account/project/mode and import a key with the necessary scopes. Do not switch wallets, API origins or projects merely to recover a handle. `vibeedit myriograph logout --json` removes the local config only. Remote key revocation and private-file cleanup are separate.

## Support, retention and deletion

[Myriograph support](mailto:support@attentionengine.ai) handles account, billing, retained jobs and deletion requests. [SDK issues](https://github.com/Momenta-App/vibeedit-sdk/issues) handles public package defects. Send minimal references and error codes privately; never put a key, signed URL, card detail or private source in an issue. No response-time guarantee is established by this prerelease.

Current service responses can report expiry/retention metadata. That is not proof of physical erasure from every object version, provider or backup. A universal storage-retention period and exercised remote-deletion acknowledgement are not qualified for this release. The SDK exposes cancellation and export, not a general remote-erasure command. Ask support for the scope and acknowledgement of a deletion request; export needed material first. Revoking access or deleting local media does not cancel charges. Financial history, original unknown operations and unresolved obligations must remain available for reconciliation. Consult the [data-handling information](https://myrograph.com/privacy) and [terms](https://myrograph.com/terms).

## Service operator pause and rollback

Backend changes require the authorized private operating runbook, fresh deployed/source identity checks and the relevant approval. This public guide intentionally contains no infrastructure identifiers, credential locations, raw SQL or private policy configuration. There is no public SDK command that safely rolls back the commercial backend.

During an incident, stop new admissions and new dispatch before changing runtime versions. Keep authenticated original-job status/download, cancellation, original admission recovery, financial outboxes, resource census, settlement and parent-allowance closure running. An unknown provider send, payment or compute resource stays held until authoritative evidence resolves it. A catalog refresh failure must deny new admissions rather than silently raise a cap, change a model or reuse an expired price for a new job. Accepted original work retains its admitted terms within its execution bounds.

Rollback must preserve the current journal readers and reconcilers until all obligations drain. Restoring an older archive or database snapshot over newer financial journals can strand holds or repeat paid work; it is not an acceptable rollback. Preserve immutable source/artifact/configuration references, original acknowledgements, signing configuration, history and schema compatibility. Re-enable work only after the repaired deployed paths and original-operation reconciliation are verified. Customer backups and previous verified package archives support a separate local rollback; inspect schema compatibility before opening a newer project with an older package.

Operational alert delivery and exercised rollback remain acceptance gates. The actual alert diagnostic failed before delivery because the existing encrypted notification topic's key did not authorize the alarm publisher. An encryption-preserving fix is prepared but awaits separate ongoing-cost approval; successful configuration or publish acceptance would still not prove that an operator received an alert. No alert-delivery success is claimed.
