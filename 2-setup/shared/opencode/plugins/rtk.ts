import { execFile } from "node:child_process"
import { promisify } from "node:util"

// RTK OpenCode plugin — rewrites commands to use rtk for token savings.
// Requires: rtk >= 0.23.0 in PATH.
//
// This is a thin delegating plugin: all rewrite logic lives in `rtk rewrite`,
// which is the single source of truth (src/discover/registry.rs).
// To add or change rewrite rules, edit the Rust registry — not this file.
//
// OpenCode V2 plugin shape: default-export an object with `id` and `setup()`.
// (V1's `export const Plugin = async ({ $ }) => ({ hooks })` no longer loads.)

const execFileAsync = promisify(execFile)

interface ToolExecuteBefore {
  tool: string
  input: Record<string, unknown> | undefined
}

interface PluginContext {
  tool: {
    hook(
      name: "execute.before",
      callback: (event: ToolExecuteBefore) => Promise<void> | void,
    ): Promise<unknown>
  }
}

async function run(file: string, args: string[]): Promise<string> {
  const { stdout } = await execFileAsync(file, args, { timeout: 10_000 })
  return String(stdout)
}

export default {
  id: "rtk",
  async setup(ctx: PluginContext) {
    try {
      await run("which", ["rtk"])
    } catch {
      console.warn("[rtk] rtk binary not found in PATH — plugin disabled")
      return
    }

    await ctx.tool.hook("execute.before", async (event) => {
      const tool = String(event?.tool ?? "").toLowerCase()
      if (tool !== "bash" && tool !== "shell") return
      const input = event?.input
      if (!input || typeof input !== "object") return

      const command = input.command
      if (typeof command !== "string" || !command) return

      try {
        const rewritten = (await run("rtk", ["rewrite", command])).trim()
        if (rewritten && rewritten !== command) {
          input.command = rewritten
        }
      } catch {
        // rtk rewrite failed — pass through unchanged
      }
    })
  },
}
