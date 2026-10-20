import { resolve } from "node:path"

// Validate an explicit portable dry-run plan; no private desktop harness is loaded.
const path = process.argv[2]
if (!path) throw new Error("Usage: bun validate_viral_source_edit_router.ts /project/path/edit-plan.json")
const plan = await Bun.file(resolve(path)).json()
for (const key of ["package_id", "source_profile", "song_profile", "clip_plan", "transition_plan", "effects_plan", "proof_ledger", "renderability"]) {
  if (plan[key] === undefined) throw new Error(`Missing plan field: ${key}`)
}
if (!Array.isArray(plan.clip_plan)) throw new Error("clip_plan must be an array")
if (plan.renderability.state !== "planned" && plan.renderability.state !== "blocked") {
  throw new Error("This validator qualifies dry-run packages only; rendered/reviewed acceptance needs source-bound video proof")
}
console.log(JSON.stringify({ ok: true, packageId: plan.package_id, state: plan.renderability.state, proof: "plan structure only; no rendered or editorial acceptance" }))
