# Agent-package public entry

This is the static source for the `/agent-package` entry on the existing VibeEdit website. It preserves the agent-installed package scope; the existing desktop site remains independently maintained.

`release.json` is deliberately a candidate with null release identities. The handoff button stays disabled. A deployment must supply reviewed release metadata only after unauthenticated immutable release assets, exact versions/checksums and the full launch acceptance evidence exist. Pin its setup skill and documentation to that release's complete source commit. Do not label a source checkpoint or CI build as launch acceptance.

The page uses local OFL fonts and local CSS/JavaScript. Its root-relative `/agent-package/` paths work with the existing clean-URL configuration. Keep the exact font license notices beside the fonts. It requires the existing site's same-origin CSP; no provider credentials or private operator receipts belong in these files.

For deployment, start from a freshly verified **actual production** source file index and preserve all its source identities/configuration. Add only this directory under `public/agent-package/`; use content-addressed references for unchanged production files. Do not deploy an unrelated dirty website checkout or replace the desktop marketing home with this page. Verify the canonical existing project guard before preview or production commands. Review the concrete preview and compare existing public routes before promotion. Retain the previous deployment identity for rollback.

The operator's deployment packet records preserved file hashes, candidate additions, exact metadata and resulting deployment/route checks. It is separate from public customer package archives and contains no permission to bypass Vercel protection or create another project. Revalidate the live baseline immediately before promotion.
