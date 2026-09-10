import { describe, it, expect } from "bun:test";

describe("enforce-context-mode bugs", () => {
  const createPlugin = async (env = {}) => {
    const { default: pluginFn } = await import("../enforce-context-mode.mjs");
    return pluginFn({ env });
  };

  it("BUG: ENFORCE_ALLOW is ignored for bash", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_PATTERNS: "grep"
    });
    const handler = plugin["tool.execute.before"];
    
    // This should be allowed because it's in the allowlist
    const result = await handler(
      { tool: "bash" },
      { args: { command: "grep something file.txt" } }
    );
    expect(result).toBeNull();
  });

  it("BUG: bash blocks commands with blocked words in paths", async () => {
    const plugin = await createPlugin({ ENFORCE_CONTEXT_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    // This should be allowed because 'grep' is part of a path, not a command
    const result = await handler(
      { tool: "bash" },
      { args: { command: "ls /path/to/my-grep-scripts/script.sh" } }
    );
    expect(result).toBeNull();
  });

  it("BUG: Read blocks files with analysis keywords in name", async () => {
    const plugin = await createPlugin({ ENFORCE_CONTEXT_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    // This should be allowed because we are just reading a file for editing, 
    // even if the filename contains "process"
    const result = await handler(
      { tool: "Read" },
      { args: { filePath: "/src/process-config.js" } }
    );
    expect(result).toBeNull();
  });
});
