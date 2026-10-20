import { spawn } from "node:child_process"
import { Type } from "@earendil-works/pi-ai"
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent"

// The bridge fixes executable, command, project, fence and artifact namespace.
export default function (pi: ExtensionAPI) {
  const bridge = (name: string, call: string, value: unknown, signal?: AbortSignal) => new Promise<unknown>((resolve, reject) => {
    const executable = process.env.VIBEEDIT_PYTHON
    const project = process.env.VIBEEDIT_WORKER_PROJECT
    const handle = process.env.VIBEEDIT_WORKER_ID
    if (!executable || !project || !handle) return reject(new Error("VibeEdit bounded worker context missing"))
    const child = spawn(executable, ["-m", "vibeedit.worker", "--project", project, "--handle", handle, "--tool", name, "--call-id", call], { stdio: ["pipe", "pipe", "pipe"], env: process.env, signal })
    let data = ""
    child.stdout.setEncoding("utf8")
    child.stdout.on("data", (chunk: string) => { data += chunk; if (Buffer.byteLength(data) > 3 * 1024 * 1024) child.kill() })
    child.stderr.on("data", () => {})
    child.on("error", reject)
    child.on("close", (code) => {
      if (code !== 0) return reject(new Error("Scoped VibeEdit tool failed; reconcile durable intent before retry"))
      try {
        const result = JSON.parse(data)
        if (!result.ok) return reject(new Error("Scoped VibeEdit tool rejected the operation"))
        resolve(result.result)
      } catch { reject(new Error("Invalid scoped tool receipt")) }
    })
    child.stdin.end(JSON.stringify(value))
  })
  const tools: { name: string; description: string; parameters: Type.TSchema }[] = [
    { name: "project_read", description: "Read a compact UTF-8 file explicitly authorized in parent references (64 KiB maximum)", parameters: Type.Object({ path: Type.String() }) },
    { name: "project_image", description: "Inspect an explicitly authorized SHA-pinned PNG/JPEG source-linked frame (2 MiB maximum)", parameters: Type.Object({ path: Type.String() }) },
    { name: "artifact_write", description: "Create an immutable JSON artifact in this worker directory; use a new filename for revisions", parameters: Type.Object({ name: Type.String(), value: Type.Unknown() }) },
    { name: "render_ffmpeg", description: "Render immutable CompositionSpec with bounded FFmpeg using only parent media references; executable HTML/model effects stay with parent", parameters: Type.Object({ compositionPath: Type.String(), outputName: Type.String() }) },
    { name: "analyze", description: "Submit exactly one parent-authorized Myriograph video/faces/speakers operation with its pinned source SHA and explicit retail cap under the SAME server goal allowance; no provider choice or shell", parameters: Type.Object({ operationId: Type.String(), service: Type.Union([Type.Literal("video"), Type.Literal("faces"), Type.Literal("speakers")]), source: Type.String(), sourceSha256: Type.String(), maxRetailMicrousd: Type.Integer({ minimum: 1 }) }) },
    { name: "analysis_status", description: "Observe the ORIGINAL authorized native analysis job and retail settlement; optional bounded verified result download, never a replacement paid submission", parameters: Type.Object({ operationId: Type.String(), download: Type.Optional(Type.Boolean()) }) },
    { name: "submit_result", description: "Validate and durably submit a JSON result matching parent outputSchema; artifact validation still required", parameters: Type.Object({ value: Type.Unknown() }) },
  ]
  for (const tool of tools) {
    pi.registerTool(defineTool({
      ...tool, label: tool.name,
      async execute(call, value, signal) {
        const receipt = await bridge(tool.name, call, value, signal)
        if (tool.name === "project_image" && receipt && typeof receipt === "object" && "imageData" in receipt && "mimeType" in receipt && typeof receipt.imageData === "string" && typeof receipt.mimeType === "string") {
          return { content: [{ type: "image" as const, data: receipt.imageData, mimeType: receipt.mimeType }], details: undefined }
        }
        return { content: [{ type: "text" as const, text: JSON.stringify(receipt) }], details: receipt }
      },
    }))
  }
  pi.on("tool_call", async (event) => {
    if (!tools.some((tool) => tool.name === event.toolName)) return { block: true, reason: "Outside bounded VibeEdit tool contract" }
    return undefined
  })
}
