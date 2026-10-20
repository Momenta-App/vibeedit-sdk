# VibeEdit agent package launch state

Updated: 2026-10-20. **Implementation active; full launch incomplete.** A [qualification prerelease](https://github.com/Momenta-App/vibeedit-sdk/releases/tag/v0.2.0-beta.1) is public; it does not establish full launch acceptance. All P0–P10, J1–J7 and A01–A20 remain mandatory. No acceptance criterion is marked passed. The complete task/acceptance ledger is [PUBLIC-LEDGER.json](PUBLIC-LEDGER.json); [LAUNCH_STATUS.md](../LAUNCH_STATUS.md) explains the current qualification limits.

## Source ownership

The authoritative public implementation is the existing [VibeEdit SDK](https://github.com/Momenta-App/vibeedit-sdk), branch `agent-package-launch`, based on `988a3e796afb8b5b985880d5b65354312e56e632`. Owned code uses MIT. Public optional model/runtime/font sources retain their upstream terms. Private native service source, model weights, source movies, credentials and raw operator records are excluded from package/public source publication. Existing desktop applications and donor working trees are preserved.

Root owns project/setup/source/correction contracts, integration, launch ledger and publication. The commercial owner owns existing Myriograph account/API/payment/credit adapters and deployment. The companion owner owns Pi/goal protocol and actual parent-agent qualification. The model/creative owner owns optional model qualification and bounded template checks after shared contracts are fixed.

## Current implementation and deployed state

- Historical checkpoint `d966c864caa5b6bf4c3aeebfa5c6e81cf14ff894` has attested candidate archives: Python `0.2.0b1`, npm `0.2.0-beta.1`, Pi `1.3.0`. Its [workflow39496324164](https://github.com/Momenta-App/vibeedit-sdk/actions/runs/39496324164) passed13jobs: six source platforms, build/attestation and six installations of the same immutable archives. [PLATFORM-CANDIDATE.json](PLATFORM-CANDIDATE.json) records only the checks actually performed.
- Renderer and preview repairs at `0d2a41aaba75c1cd8e2f4b7efbe9456ded0b8cab` passed all13jobs in [workflow39504114006](https://github.com/Momenta-App/vibeedit-sdk/actions/runs/39504114006). Decoded alpha/composite checks cover actual pixels, and previews match their implementations. Current code `7ff8ff1a9caf1f53d7f8cba7fbbfec97d0dd61e1` also repairs durable worker reading of original verified native JSON results, including Windows paths, and makes the setup skill name its exact manifest. Final [canonical workflow39507366659](https://github.com/Momenta-App/vibeedit-sdk/actions/runs/39507366659) passed all13jobs; hashes and signed provenance are independently verified. Older archives remain historical evidence.
- Myriograph remains the existing account, API, Stripe and shared prepaid-credit authority. The user's amended policy is metered prepaid funding with manual refill and optional explicitly consented auto top-up. There is no companion subscription or included monthly credit grant. Managed access and goal financial/recovery requirements remain mandatory.
- Six additive database migrations and reviewed existing-stack runtime updates are applied. Separate provider/worker runtime references break the immutable face configuration cycle. Auth/billing-only sandbox activation is complete for the single approved test identity with a separate wallet and bounded campaign; actual browser login-code request succeeded and private user verification is pending. Paid native/managed/auto-top-up admission and catalog/model activation remain OFF. Existing financial journals, resources, live billing SPA/client and original job identities are preserved; actual payment, signed settlement, paid calls and managed execution remain required.
- One cloud image build failed terminally because its role could not pull the pinned private base image. Its original handle/logs are retained. The separately reviewed exact read-only policy and corrected original build succeeded; the image is deployed. Original Stripe test/live webhook subscriptions now include the required setup/failure/cancellation events with existing endpoints/secrets preserved. The reviewed billing SPA and all customer API namespaces are live on [Myriograph billing](https://myrograph.com/billing), through reassignment of its existing custom-domain alias to the exact reviewed deployment; no rebuild or protection change occurred. A real operator-alert diagnostic failed before delivery because the alarm could not use the existing encrypted topic key; its fix is under review. No unknown paid operation is replaced.
- The public setup entry has a protected preview. Production has not been promoted; the setup handoff remains disabled until release metadata and all launch gates are established.

## Qualification and open work

All11phases,7journeys and20acceptance criteria are mapped to implementation and bounded evidence in the ledger. Local fixtures, preview deployment and a green CI matrix do not establish full customer/editorial acceptance.

- **P0/P1/P9/P10:** exact source/artifact identity, registry publication, both clean parent agents, update/rollback/privacy/retention and final public setup remain required. Source/registry permissions are established. Exact GitHub qualification archives are public; npm/PyPI publication and complete clean-agent journeys remain pending.
- **P2/P7:** complete fresh browser email/signup/account/project/key selection, sandbox funding, signed exactly-once settlement, three original paid services, metered funding and consent/failure/disable/refund recovery. Test credit still funds real compute; approved external spending is bounded independently and no real card charge is authorized.
- **P3:** local source-bound words/faces/beats/render review and correction persistence have bounded tests. Real paid face/word evidence, cloud persistence, identity uncertainty and final editorial application remain required. Nominal-rate browser frame stepping remains approximate for variable-rate media.
- **P4:** public model sources/artifacts are pinned. Fresh TransNet, SAM2.1, SAM3.1 and Apple Silicon MLX inference, actual cut/occlusion/contact mask review and a real mask-derived effect remain unqualified. Local SAM execution is blocked until required disk/memory/load safety gates pass; none is waived. The original bounded Linux CPU attempt verified exact final archives and resource gates, then stopped before inference on a runner tool prerequisite; the repair is under review. Actual standard Apple runner has sufficient disk and native Metal but only7GiB physical RAM and excessive load; it does not satisfy SAM3.1 MLX’s16GB requirement.
- **P5/P6:** local Pi BYOK/managed and durable goal fixtures pass bounded checks. Both parent agents must complete real funded tasks and multistep goals across disconnect/crash/stop/resume with original handles, reservations, artifacts and exact cost reconciliation.
- **P8:** animation/dialogue revisions apply the user's in-video inverse/per-word caption feedback; licensed bundles restore and rerender bit-identically through the candidate wheel. Browser playback reached both endings. Word timing is provisional subtitle interpolation, not qualified ASR; independent listening/human acceptance are not invented. Three materially different fan edits, paid caption production, every advertised template and actual source acquisition still require their complete journeys.

## Candidate artifact identities

These exact7ff candidate archives passed the listed final core matrix. Full launch acceptance remains open; the exact qualification prerelease is public and anonymously verified.

| Artifact | SHA256 |
|---|---|
| Release manifest | `16f5ac1aff3b364e4bf479b30c593fc97e8d8ef84add023518a9c10f7800b341` |
| Python wheel | `6e3fbe0759a7064f6f02943770a1902a202a31c0aa46d27498b13ce7fcb50c86` |
| Python source archive | `e4226498ef6aa77883485376bf1004127cb57b52a67e219d1b12c2dcd7b5adc8` |
| npm archive | `67991e0a828977b3205bec5379a9fd05249168ae877ed1dd08e8533ec4b6113e` |

## Customer and operating entry points

[Myriograph signup, keys and billing](https://u83j0k7e5m.execute-api.ca-central-1.amazonaws.com/billing) · [API](https://u83j0k7e5m.execute-api.ca-central-1.amazonaws.com) · [customer guide](../MYRIOGRAPH.md) · [support](https://github.com/Momenta-App/vibeedit-sdk/issues). Existing billing entry is live; newly deployed disabled components are not a completed customer launch.

Before resuming, read this state and the complete ledger, revalidate deployed and source identities, preserve dirty donor work and continue independent work around a blocked dependency. Observation timeout never authorizes a replacement paid job. Rollback disables new admissions/dispatch first and retains new readers/outboxes/reconcilers until every obligation drains; never restore an old ZIP over active journals or drop financial history.

Original operator history and raw receipts are retained privately, including the preceding state snapshot SHA256 `03176028caabe7648e538d4b43572ea3244d2ce0553a7e29df0ec709a711fe0f`. Publish only curated identities and supported outcomes. Do not copy private credentials, account identifiers, media or screenshots into this public state.
