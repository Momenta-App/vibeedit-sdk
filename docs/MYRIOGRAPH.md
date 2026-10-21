# Myriograph accounts, credit and paid services

Updated 2026-10-20 for the [v0.2.0-beta.1 qualification prerelease](https://github.com/Momenta-App/vibeedit-sdk/releases/tag/v0.2.0-beta.1). This is not a completed launch: all A01–A20 acceptance criteria remain open. See [launch state](https://github.com/Momenta-App/vibeedit-sdk/blob/v0.2.0-beta.2/docs/launch/STATE.md) for current evidence and [operations](OPERATIONS.md) for recovery and release identities.

The public [Myriograph account, API-key and billing page](https://myrograph.com/billing) serves the updated customer interface. The canonical [API origin](https://u83j0k7e5m.execute-api.ca-central-1.amazonaws.com) and [video API specification](https://myrograph.com/openapi.json) are separate entry points. Production billing uses real money. The restricted qualification sandbox has a separate test wallet and test-mode payment flow; it is not a public source of free compute.

Currently verified: public billing assets and API routing to authentication checks, separate test/live webhook configuration, restricted sandbox authentication setup, and bounded local/core archive checks. Actual new-customer email verification, scoped-key issuance, sandbox Checkout and signed credit settlement, three paid services, managed execution and optional automatic top-up still need their complete customer journeys. New paid native/managed admission and automatic top-up remain disabled during qualification. A visible form or a capability response does not establish that its paid path is ready.

## Connect your agent

Local editing does not require a Myriograph account. When paid services are available, the same account funds video understanding, persistent face identity, anonymous speaker/word evidence and optional managed companion inference. BYOK inference uses your own provider credential; paid Myriograph analysis still requires Myriograph credit.

Sign in through the billing page with your email code. Select an existing account you own or administer, then choose a stable project ID and the key's services, allowed operations and billing authority. The organization selection identifies the commercial account; the project is a namespace within that account, not another wallet or an invitation to an organization. Keep the same account/project selection when returning to original jobs.

Use the smallest useful scopes. Service and project grants govern analysis and results; billing authority governs wallet changes. A companion-only key does not gain video-analysis authority merely because it can manage funding. A scoped key can list and revoke itself; wider key administration requires the existing account authority. Scope controls and cross-project isolation are implemented, but their full new-customer qualification remains open.

Save the private JSON config from Myriograph and import it without putting its key in a command or chat:

```sh
vibeedit myriograph login --import-config /private/path/myriograph-api.json --json
vibeedit myriograph status --json
vibeedit myriograph billing --json
```

The downloaded file contains a credential. Store it privately and keep it out of Git, screenshots, shared transcripts and project bundles. On macOS/Linux, import requires an owner-only file; `chmod 600 /private/path/myriograph-api.json` sets those permissions. The imported Windows credential uses protection bound to the current Windows user; retain or securely remove the original downloaded file deliberately. Browser sign-out does not revoke an API key.

To reauthenticate, sign in again and import an authorized config for the original API origin, account, mode and project. A replacement key needs the original operation's scopes. Rotate by saving the new config, reconnecting with the old key to revoke it, then importing the new config. Revoking a key does not cancel jobs, erase records or immediately invalidate already issued signed links. `vibeedit myriograph logout --json` removes the local stored config; remote revocation is a separate action. No internal credential is used as a fallback.

## Credit, quotes and consent

Access is metered prepaid: add money manually, with optional automatic top-up. There is no companion subscription or monthly credit grant. The account balance is shared; project scopes do not create separate balances.

Manual refill opens Stripe Checkout. Check the displayed account and test/live mode before proceeding. Returning from Checkout is not proof of payment or credit: refresh the original wallet/history and wait for signed settlement. A failed or uncertain payment keeps its original identity; avoid creating another Checkout to resolve a missing acknowledgement. Test and live credit are not interchangeable.

Automatic top-up is optional and remains disabled during qualification. Its implemented flow first sets up a payment method, then requires explicit consent to a refill threshold, refill amount, monthly automatic-charge ceiling and terms version. Setup alone does not authorize charges. Disabling prevents new automatic attempts; already submitted or uncertain attempts remain observable and count toward the safety ceiling. A refund does not silently restore that month's automatic-charge allowance. Signed success, failure, cancellation, refund and duplicate-event behavior remain launch qualification gates.

Before paid work, your agent must read capabilities and pricing terms, explain the conservative hold and obtain a permitted retail ceiling. Quotes identify their version/expiry and distinguish provider usage from separately declared quoted or measured compute. Published compute metering is not a claim to reproduce the provider's or AWS's final invoice. Unknown costs remain held; a timeout does not establish zero cost. A shared goal allowance must cover inference and delegated analysis together, including its declared compute allocation. Do not create another allowance merely to continue the same goal.

## Submit once, observe the original

Inspect the installed command and service options first:

```sh
vibeedit analyze video --help
vibeedit analyze faces --help
vibeedit analyze speakers --help
vibeedit jobs --help
```

Submission requires the local project path, source file, a stable `--operation`, and an explicit `--max-retail-usd`. `--options` accepts the selected service's JSON options; it cannot override the durable source, funding allowance or retail cap. These are paid actions when enabled. Only supply a numerical cap after the user authorizes it. The optional `--funding-allowance-id` attaches the original server allowance when the service explicitly supports shared-goal funding.

For an operation already submitted, these commands retain its original identity:

```sh
vibeedit jobs list --project my-edit --json
vibeedit jobs status saved-operation --project my-edit --json
vibeedit jobs watch saved-operation --project my-edit --wait-seconds 30 --json
vibeedit jobs download saved-operation --project my-edit --destination saved-evidence --json
```

A watch timeout ends observation only. Preserve the project journal, operation ID and native job handle. `jobs resume` is an explicit recovery action: it may reconcile accounting or continue a server-proven unsent original intent. It does not permit replacement of an uncertain paid send. `jobs cancel` requests that future work stop; already dispatched work can finish and incur charges. Neither command proves that held credit is released. Follow the original status and authoritative settlement to completion; see [incident recovery](OPERATIONS.md).

Downloads verify declared hashes, byte lengths and source bindings. Refresh an expired signed link from the same original job. Do not treat the link as the job's durable identity or share it publicly. Face packages retain their native structure; use the [project import and review workflow](PROJECTS.md) for corrections.

## Review, export and data handling

Machine evidence needs review. Anonymous acoustic groups, visual identities and confirmed word-to-person links are distinct; a visible face match does not establish who spoke. A corrected word boundary does not certify other timings. Preserve the machine baseline and append human corrections. Source-bound local corrections and supported cloud face-library changes have different persistence acknowledgements; only an applied remote revision proves a cloud change.

Download the original analysis and save corrections before their reported expiry. Export a [portable project bundle](PROJECTS.md) before deleting local work. Bundles exclude credentials and sessions but can contain private media, prompts, analysis and passive job/goal recovery state; share them deliberately. Restore starts no paid work and does not resolve unknown holds.

There is no SDK command that promises remote source/job erasure. Cancellation, local deletion, key revocation and a job's expiry are not proof of deletion from object storage, provider systems or backups. Exact service-wide retention periods, automated deletion and deletion acknowledgement are not freshly qualified for this release; use the current service response and [data-handling page](https://myrograph.com/privacy), then request clarification or deletion through [Myriograph support](mailto:support@attentionengine.ai). Financial history and unsettled obligations must remain reconcilable. Do not assume deletion refunds a paid operation. See also the current [service terms](https://myrograph.com/terms).

For package problems, use [SDK issues](https://github.com/Momenta-App/vibeedit-sdk/issues). Send account, payment and deletion details privately to Myriograph support. Include the original operation/job reference, time, mode, error code and package version; exclude credentials, payment-card data, signed URLs and private media from public reports.
