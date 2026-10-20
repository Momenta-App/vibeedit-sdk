# VibeEdit Pi companion

This package adds a `/goal` command to official Pi and contains the bounded extension used by the VibeEdit worker. It does not install another `vibeedit` command. Version 0.2.0-beta.1 is a private embedded runtime manifest inside the main VibeEdit candidate archive. It is not a separately published npm package. Install the `/goal` extension with the exact main package (`pi install npm:vibeedit@EXACT` after publication); its archive/checksum is the release identity.

Use the installed VibeEdit CLI:

```sh
vibeedit worker setup --json
vibeedit worker profiles --refresh --json
vibeedit worker configure --key-stdin --json < /secure/customer-openrouter-key
vibeedit worker run --project /path/to/project --id edit-review --spec task.json --json
vibeedit worker status --project /path/to/project --id edit-review --json
```

The key file is an input supplied by the user, never a project deliverable. Prefer your agent's secure credential input facilities; never echo a key into shell history or put it in an argv flag. Unix config is owner-only; Windows config uses user-scoped DPAPI. Do not copy credential config into a project or release archive.

A task must give explicit funding, exact profile, project references and SHA-256 digests, allowed tools, JSON output schema, artifact contracts, retail/time/model/tool bounds and zero nested delegation. The runtime disables arbitrary shell and discovered Pi resources. It is not an OS sandbox. Use source-linked PNG/JPEG frames for bounded visual inspection; direct video transport is not available in this candidate.

Workers and goals retain original identities and visible holds after indeterminate sends. Inspect and reconcile the original operation rather than submitting a replacement. A model turn ending is not goal completion. Goal completion checks an editable composition, playable render and source-linked review; it does not claim human editorial acceptance.

Managed access has a thin client for the actual candidate Myriograph prepaid gateway contract. It runs only when deployed capabilities explicitly enable the pinned metered-prepaid/retail contract, using the public customer key and same account ledger. Inference replies are buffered through durable request polling; there is no upstream token streaming or direct video input. One goal allowance covers its delegated work, with original-handle recovery and authoritative retail settlement. Production funding and both parent-harness journeys still need qualification. Optional auto top-up uses explicit Myriograph consent; no recurring subscription or separate local wallet is introduced.

See `docs/launch/COMPANION.md` in the source archive for the complete state, source pins, local test evidence, exact remaining acceptance and recovery instructions. Local fixture tests do not qualify real provider inference, managed funding or a public launch.
