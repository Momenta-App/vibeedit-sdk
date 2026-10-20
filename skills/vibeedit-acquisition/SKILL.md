---
name: vibeedit-acquisition
description: Find source-provider pages, guide an authorized browser download, and register content-bound VibeEdit source receipts for a video project.
---

# VibeEdit source acquisition

Keep the provider's stable item page, selected file rights and actual downloaded bytes connected. Use the project's source identity and native clock throughout editing and review.

1. Run `vibeedit acquire search "SUBJECT" --json`. This searches the small packaged page catalog and returns provider search pages; it does not search a private movie mirror or promise a final download URL. Open a selected provider/item page using the browser tools actually available to the parent agent. Inspect that item's license, author and intended-use restrictions. The catalog's check date is evidence of a prior inspection, not a new license grant.
2. Admit the item before downloading:

   ```sh
   vibeedit acquire start --project "PROJECT" --id SOURCE_TASK --provider PROVIDER_ID --page "https://provider/item-page" --title "Selected item" --json
   ```

   Use a stable HTTPS page on that provider's listed page host. Keep authentication in the browser. Signed media URLs and search URLs are not source-page identities.
3. Complete one authorized download through the user's browser/provider workflow. Codex may expose computer-use/browser download tools; Claude Code may expose a different browser MCP or require a manual download. Discover the installed capability instead of assuming matching tool names. Record the browser's actual saved file path. If browser access, login or verification is unavailable, retain `SOURCE_TASK`, provide its page/next action and continue unrelated edit work. Do not report an HTML error page, partial file or clicked button as a completed download.
4. Save public rights metadata as JSON containing `license`, `attribution`, `verifiedBy` and optional `licenseUrl`/`notes`. Inspect the downloaded file and the current project revision, then register it:

   ```sh
   vibeedit acquire finish --project "PROJECT" --id SOURCE_TASK --file "SAVED_DOWNLOAD" --rights rights.json --expected-revision REVISION --harness codex --json
   ```

   Set the actual harness label (`codex`, `claude-code`, `pi`, `manual`, `other`). Add `--sha256` when a trusted expected digest exists. The SDK computes the exact SHA-256/size, verifies its project copy and saves native stream clocks. Do not label self-reported rights or timings as independently certified.
5. Use the returned `sourceId` and source-relative path in the composition/analysis/review. Inspect `vibeedit acquire status --project "PROJECT" --id SOURCE_TASK --json` or export the same receipt. An exact finish retry reuses the original source; a stale project revision requires reconciliation of that same operation. Relink moved media by identical content, preserving the original receipt and corrections.

The final media URL may expire. When useful, put it in a private temporary JSON `{ "finalUrl": "..." }` outside the project and pass `--transport-metadata FILE`; the receipt retains only its origin/hash. Never put signed URLs, cookies or keys into argv, page-catalog metadata or exported receipts. Reopen the source page for a renewed download capability. Keep browser authentication and provider purchase decisions with the user under the parent harness's actual authorization rules.

The package distributes provider-page metadata and generated examples. It does not redistribute downloaded stock/movie files, scrape provider catalogs in bulk, or turn a provider's general terms into permission for unrelated automated collection. Match attribution and any derivative-license requirements to the selected item and intended output.
