---
name: vibeedit-companion
description: Delegate bounded VibeEdit work to the optional pinned Pi companion and manage durable project-local edit goals with artifact and cost evidence.
---

# VibeEdit companion

Use ordinary SDK editing directly when delegation adds little value. Use a worker for a bounded task whose scope, result schema and artifacts the parent can check. Use a durable goal only when the user requests continuing work; goals require explicit bounded steps and finished-edit evidence.

Run `vibeedit worker setup --json` only when Pi is needed. It stages the pinned official runtime locally. `vibeedit worker profiles --refresh --json` reports exact model/provider routes and current prices; catalog availability is separate from real inference qualification.

Select funding explicitly. BYOK uses the user's OpenRouter key through `vibeedit worker configure --key-stdin --json` and owner-protected/OS-protected config. Keep the key out of prompts, argv, projects and receipts. Myriograph-managed inference must use the existing customer account/key and server-enforced prepaid ledger/caps. Run `vibeedit worker profiles --funding managed --json` to verify the deployed capability/profile contract before admission; implementation or capability availability alone does not qualify funded inference. Both paths pin the dated provider endpoint as well as model and route; a changed endpoint requires a deliberate new profile and evidence. Do not borrow operator/provider secrets or silently switch funding paths. Managed funding policy is manual prepaid add-money with optional explicitly consented auto top-up, without recurring subscription allowances.

Read [task and goal contracts](references/contracts.md) when constructing a specification. Supply the parent-authorized project references/SHA digests, tool allowlist, output schema, artifact contracts, model/tool/time/retail bounds and zero nested delegation. Bounded workers expose compact project reads, source-linked PNG/JPEG inspection, immutable JSON artifacts and constrained existing SDK FFmpeg rendering. They provide no arbitrary shell tool or OS sandbox. Executable HTML and heavy models remain explicit parent operations. The optional `analyze` / `analysis_status` tools require exact parent `analysisPermissions`, source digests and retail caps, and use the same original server goal allowance for all three paid services. They fail closed unless the native service advertises shared funding support.

```sh
vibeedit worker run --project "PROJECT" --id TASK_ID --spec task.json --json
vibeedit worker status --project "PROJECT" --id TASK_ID --json
vibeedit worker events --project "PROJECT" --id TASK_ID --after CURSOR --json
vibeedit worker steer --project "PROJECT" --id TASK_ID --operation-id STEER_ID --message "Scoped correction" --json
vibeedit worker cancel --project "PROJECT" --id TASK_ID --json
```

Use exact IDs for retries; conflicting reuse fails. Streaming acceptance is not completion: observe Pi settlement and independently validate requested artifact schemas/digests/renderability. Inspect editorial findings before treating a result as accepted. A source-linked image transport pass does not qualify direct video transport or semantic visual accuracy.

For requested long work, `vibeedit goal start --project "PROJECT" --id GOAL_ID --spec goal.json --json` starts a detached local supervisor; status/pause/resume/edit/cancel/export address that same goal. Mutation commands require the current `--expected-revision`. Pi's packaged `/goal` command reaches the same CLI lifecycle. No always-on service is installed. The computer must be awake/online for applicable work to continue.

Pause stops new admissions and propagates cancellation; already-started work/settlement stays visible. A model finishing a turn or writing a plan does not finish an edit goal. Completion requires the editable composition, playable render and source-linked review artifacts. Goals execute a bounded ordered plan; Pi may adapt within each declared step. `derivedReferences` carries earlier verified artifact bytes into later steps. Model attempts without new SHA-bound artifacts stop at `maxNoProgressCalls` (default3). At most two goals and two workers hold project leases concurrently. Completion validation is separate from human editorial signoff.

Treat a lost acknowledgement, stopped Pi or observation timeout as an original-operation recovery problem. Inspect stored native session/generation/job identities. `worker reconcile --project PROJECT --id TASK_ID --operation-id ORIGINAL_ID --json` observes the original BYOK generation, managed request or native analysis job. An unobserved handle requires original-operation reconciliation while retaining its hold. `worker recover --project PROJECT --id TASK_ID --json` may adopt an exact committed result and verified artifacts only after all financial/tool operations settle and no live lease remains; it never repeats inference. Explicit goal resume can adopt the same committed checkpoint. Never create a replacement paid call, release unknown holds or delete financial/operation history to unblock a retry. Local BYOK reservations are conservative enforcement, not proof of a provider account hard spending limit. Myriograph's ledger remains the remote money authority.

Project bundle/restore preserves passive operation IDs, holds and checkpoints, excludes credentials and Pi chats, and restores active work paused with owners cleared and fences advanced. Resume is explicit. Local protocol, crash and artifact fixtures are documented in `docs/launch/COMPANION.md`; exact-release Codex/Claude runs and real funded editorial journeys remain separately required.

The optional integer `platformBudgetMicros` explicitly allocates actual infrastructure inside the same retail ceiling (default0). The server reserves provider budget as `maxRetailMicros//2-platformBudgetMicros`; infrastructure is never relabeled as OpenRouter usage. A goal owns this split once; native permissions keep exact total caps while the service freezes its own provider/platform estimates. Nonzero child allocations must fit the parent allocation. A new allocation requires explicit scope/budget authority and never raises the original cap automatically.

Native execution may be terminal before platform costs are financially settled. Only the protected native receipt's four true fields (`terminalExecutionProven`, `providerChildrenSettled`, `platformCensusKnown`, `readyForParentSettlement`) permit verified committed artifacts to form an execution checkpoint while worker/child retail caps stay held. Declared later steps can consume those exact SHA-bound bytes. After all steps are ready, close the one original parent, then observe the original native jobs and complete workers/goals only after authoritative retail acknowledgement. A held parent close remains closing with original work/holds; resume performs no replacement inference. Standalone workers use the same close/reconcile rule.
