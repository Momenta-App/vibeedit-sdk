import { spawn } from "node:child_process"
import { dirname, resolve } from "node:path"

const scriptDir = dirname(new URL(import.meta.url).pathname)
const repoDir = resolve(scriptDir, "../../../..")
const harness = resolve(repoDir, ".opencode", "evals", "viral-source-edit-router", "run-viral-source-router-harness.ts")
const args = [harness, ...process.argv.slice(2)]
const child = spawn("bun", args, {
  cwd: repoDir,
  stdio: "inherit",
  env: process.env,
})

child.on("exit", (code, signal) => {
  if (signal) {
    console.error(`viral-source-edit-router validation stopped by ${signal}`)
    process.exit(1)
  }
  process.exit(code ?? 1)
})
