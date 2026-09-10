import { describe, it, expect } from "bun:test";

describe("Signature and Regex fixes", () => {
  const createPlugin = async (env = {}) => {
    const { default: pluginFn } = await import("../enforce-context-mode.mjs");
    return pluginFn({ env: { ENFORCE_LOG: "0", ...env } });
  };

  it("handles single-argument hook signature", async () => {
    const plugin = await createPlugin({ ENFORCE_CONTEXT_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler({ 
        tool: "bash", 
        args: { command: "curl https://example.com" } 
      });
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("The bash sub-command 'curl' is STRICTLY FORBIDDEN.");
    }
  });

  it("handles case-insensitive tool names", async () => {
    const plugin = await createPlugin({ ENFORCE_CONTEXT_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler({ 
        tool: "Bash", 
        args: { command: "curl https://example.com" } 
      });
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("The bash sub-command 'curl' is STRICTLY FORBIDDEN.");
    }
  });

  it("blocks commands without trailing spaces (word boundary check)", async () => {
    const plugin = await createPlugin({ ENFORCE_CONTEXT_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler({ 
        tool: "bash", 
        args: { command: "curl" } 
      });
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("The bash sub-command 'curl' is STRICTLY FORBIDDEN.");
    }
  });

  it("blocks commands followed by operators", async () => {
    const plugin = await createPlugin({ ENFORCE_CONTEXT_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    const commands = ["curl; ls", "curl|grep", "curl&echo"];
    for (const command of commands) {
      try {
        await handler({ tool: "bash", args: { command } });
        throw new Error(`Should have thrown for ${command}`);
      } catch (e) {
        // The plugin might report curl OR grep depending on list order, as long as it blocks.
        expect(e.message).toMatch(/The bash sub-command '(curl|grep)' is STRICTLY FORBIDDEN\./);
      }
    }
  });

  it("blocks complex command structures (subshells, env vars, paths)", async () => {
    const plugin = await createPlugin({ ENFORCE_CONTEXT_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    const commands = [
      "$(curl https://example.com)",
      "`curl https://example.com`",
      "{ curl https://example.com; }",
      "VAR=1 curl https://example.com",
      "FOO=bar BAZ=qux curl https://example.com",
      "/usr/bin/curl https://example.com",
      "./curl https://example.com",
      "echo $(curl)",
      "sudo curl https://example.com",
      "env curl https://example.com",
      "sudo env VAR=1 time curl https://example.com",
      "/usr/local/bin/curl https://example.com",
      "xargs curl"
    ];
    
    for (const command of commands) {
      try {
        await handler({ tool: "bash", args: { command } });
        throw new Error(`Should have thrown for ${command}`);
      } catch (e) {
        expect(e.message).toMatch(/The bash sub-command '(curl|grep)' is STRICTLY FORBIDDEN\./);
      }
    }
  });

  it("allows commands where blocked word is just an argument", async () => {
    const plugin = await createPlugin({ ENFORCE_CONTEXT_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    const commands = [
      "ls curl",
      "echo 'curl'",
      "mycurl",
      "ls /usr/bin/curl"
    ];
    
    for (const command of commands) {
      const result = await handler({ tool: "bash", args: { command } });
      expect(result).toBeNull();
    }
  });});
