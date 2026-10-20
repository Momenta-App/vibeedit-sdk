import { spawn } from "node:child_process"
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

export default function (pi: ExtensionAPI) {
  pi.registerCommand("goal", {
    description: "VibeEdit durable goal: /goal status ID | start ID spec.json | pause/resume/cancel ID REVISION | edit ID REVISION spec.json | export ID. Project is current directory.",
    handler: async (input, ctx) => {
      const parts = input.trim().split(/\s+/)
      const action = parts[0] || "status"
      if (!["status", "start", "edit", "pause", "resume", "cancel", "export"].includes(action) || !parts[1]) {
        ctx.ui.notify("Use /goal status ID, start ID spec.json, pause/resume/cancel ID REVISION or export ID", "warning")
        return
      }
      const args = ["goal", action, "--project", ctx.cwd, "--id", parts[1], "--json"]
      if (action === "start") {
        if (!parts[2]) return ctx.ui.notify("Goal start requires an explicit bounded spec.json", "warning")
        args.push("--spec", parts.slice(2).join(" "))
      }
      if (["pause", "resume", "cancel", "edit"].includes(action)) {
        if (!/^\d+$/.test(parts[2] || "")) return ctx.ui.notify("Lifecycle mutation requires current revision from status", "warning")
        args.push("--expected-revision", parts[2])
        if (action === "edit") {
          if (!parts[3]) return ctx.ui.notify("Goal edit requires an explicit bounded spec.json", "warning")
          args.push("--spec", parts.slice(3).join(" "))
        }
      }
      const result = await new Promise<string>((resolve, reject) => {
        const child = spawn(process.env.VIBEEDIT_CLI || "vibeedit", args, { cwd: ctx.cwd, stdio: ["ignore", "pipe", "pipe"] })
        let text = ""
        child.stdout.setEncoding("utf8")
        child.stdout.on("data", (data: string) => { text += data; if (Buffer.byteLength(text) > 2 * 1024 * 1024) child.kill() })
        child.stderr.on("data", () => {})
        child.on("error", reject)
        child.on("close", (code) => code === 0 ? resolve(text) : reject(new Error("VibeEdit goal command failed; inspect CLI status")))
      })
      pi.sendMessage({ customType: "vibeedit-goal", content: result, display: true }, { triggerTurn: false })
    },
  })
}
