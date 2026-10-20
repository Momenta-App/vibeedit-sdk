# Myriograph account and paid services

**Launch candidate:** the [launch status](LAUNCH_STATUS.md) records what is qualified. New unified service adapters, scoped issuance and capped auto top-up must be verified after deployment; source tests alone do not establish availability.

Use the existing [Myriograph signup, API-key and billing page](https://u83j0k7e5m.execute-api.ca-central-1.amazonaws.com/billing). Its account owns prepaid credit. Local VibeEdit editing does not require an account. Myriograph provides three paid services: persistent face identity, anonymous speaker/word evidence and video understanding. Optional managed companion inference is separately metered against the same account.

Sign in through the browser with your email code. Select an existing account you own or administer, choose a stable project ID, then select services, operations and billing authority. A project ID is a namespace within that commercial account, not a new wallet or an invitation to another organization. Only existing account membership authorizes key creation. New scoped keys cannot read another project's jobs or use ungranted services. Existing account-owner keys retain their authority; select the original project to recover its handles.

Save the page's config privately and import it:

```sh
vibeedit myriograph login --import-config /private/path/myriograph-api.json --json
vibeedit myriograph status --json
vibeedit myriograph billing --json
```

The config includes the API origin, customer key and selected organization/project IDs. Keep it out of Git, shared transcripts and project bundles. Import uses user-private storage; Windows protects the stored key for the current user. Revoked credentials never fall back to an internal key. `logout` removes the local config; revoke the key in Myriograph to invalidate remote access. To rotate, save a new key with the intended scopes, then revoke the old key. Original account/project job identities remain usable by an authorized replacement key.

Add prepaid credit through Stripe Checkout. The page displays test/live mode; the restricted launch sandbox uses its own wallet and test cards. Test credit never becomes live credit. Payment return alone is not credit confirmation: signed settlement must grant it. Quotes reserve a conservative retail amount before paid work; final accounting distinguishes reported provider usage and quoted/measured infrastructure from provider invoices. A timeout does not prove zero cost.

Automatic top-up is optional. First set up a payment method through Stripe, then explicitly accept the refill threshold, refill amount and monthly automatic-charge ceiling. Setup alone does not enable charges. Disable stops new automatic charges; submitted or uncertain payments retain their original identities and count toward the safety ceiling. This is metered prepaid access, with no subscription or monthly credit grant. Failed/unknown payments must be observed and reconciled rather than replaced automatically.

The agent must inspect service capabilities and the exact quote, obtain the user's permitted retail cap, and preserve its operation ID:

```sh
vibeedit analyze video source.mp4 --project my-edit --operation chosen-operation-id --max-retail-usd AUTHORIZED_CAP --options video-options.json --json
vibeedit jobs status chosen-operation-id --project my-edit --json
vibeedit jobs resume chosen-operation-id --project my-edit --json
vibeedit jobs download chosen-operation-id --project my-edit --destination saved-evidence --json
```

Use `faces` or `speakers` for the other native services and their declared option schemas. `AUTHORIZED_CAP` is a placeholder for an explicitly authorized number, not a suggested budget. An observation timeout keeps the original job/operation. Resume reconciles it; it does not authorize a new purchase. Download verification retains source identity, original schema and artifact hashes.

Review important evidence. Anonymous acoustic groups, visual face identities and confirmed word-to-person links remain separate. A face match does not establish who spoke, and edited word timing does not qualify unreviewed boundaries. Preserve machine baselines and append human corrections through [project review](PROJECTS.md).

Service responses declare retention and expiry. Download required originals and corrections before expiry; revoking a key does not itself erase submitted work or financial records. Project bundles can contain private media and prompts even though credentials and sessions are excluded. Export before deleting local project files. Remote deletion/support and operating evidence remain launch gates until exercised; do not assume local deletion cancels a cloud job or refunds its hold.
