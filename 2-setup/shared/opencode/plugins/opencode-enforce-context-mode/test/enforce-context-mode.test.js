import { describe, it, expect } from "bun:test";
import { parseAllowlist } from "../enforce-context-mode.mjs";

describe("parseAllowlist", () => {
  it("returns defaults when value is undefined", () => {
    expect(parseAllowlist(undefined, ["a", "b"])).toEqual(["a", "b"]);
  });

  it("returns defaults when value is empty", () => {
    expect(parseAllowlist("", ["a", "b"])).toEqual(["a", "b"]);
  });

  it("parses comma-separated values", () => {
    expect(parseAllowlist("grep,find,cat", [])).toEqual(["grep", "find", "cat"]);
  });

  it("trims whitespace", () => {
    expect(parseAllowlist(" grep , find ", [])).toEqual(["grep", "find"]);
  });

  it("filters empty strings", () => {
    expect(parseAllowlist("grep,,find", [])).toEqual(["grep", "find"]);
  });

  it("returns defaults when all values are empty", () => {
    expect(parseAllowlist(",,", ["a", "b"])).toEqual(["a", "b"]);
  });
});

describe("enforce-context-mode", () => {
  const createPlugin = async (env = {}) => {
    const { default: pluginFn } = await import("../enforce-context-mode.mjs");
    return pluginFn({ env });
  };

  it("returns empty object when disabled via 0", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "0" });
    expect(plugin).toEqual({});
  });

  it("returns empty object when disabled via false", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "false" });
    expect(plugin).toEqual({});
  });

  it("returns hook when enabled", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "1" });
    expect(typeof plugin["tool.execute.before"]).toBe("function");
  });


  it("blocks grep in hard mode", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler({ tool: "grep" }, { args: { pattern: "foo" } });
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("ctx_execute");
    }
  });


  it("allows glob via allowlist", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_PATTERNS: "*.json"
    });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "glob" },
      { args: { pattern: "*.json" } }
    );
    expect(result).toBeNull();
  });

  it("blocks custom sub-command via OPENCODE_BLOCK_BASH_CMDS", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_BLOCK_BASH_CMDS: "find,grep"
    });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler(
        { tool: "bash" },
        { args: { command: "find . -name foo" } }
      );
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("SYSTEM DIRECTIVE: BASH COMMAND DENIED");
    }
  });

  it("does not block partial matches (wget vs get)", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_BLOCK_BASH_CMDS: "wget"
    });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "bash" },
      { args: { command: "get something" } }
    );
    expect(result).toBeNull();
  });

  it("allows bash via allowlist", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_PATTERNS: "grep"
    });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "bash" },
      { args: { command: "grep foo bar" } }
    );
    expect(result).toBeNull();
  });

  it("allows bash via OPENCODE_ALLOW_BASH_CMDS", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_BASH_CMDS: "curl,wget"
    });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "bash" },
      { args: { command: "curl https://example.com" } }
    );
    expect(result).toBeNull();
  });

  it("blocks bash not in OPENCODE_ALLOW_BASH_CMDS", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_BASH_CMDS: "curl"
    });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler(
        { tool: "bash" },
        { args: { command: "wget https://example.com" } }
      );
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("SYSTEM DIRECTIVE: BASH COMMAND DENIED");
    }
  });

  it("blocks Read with analysis keyword in searchTerm", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler(
        { tool: "Read" },
        { args: { filePath: "somefile.txt", text: "analyze this" } }
      );
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("ctx_execute_file");
    }
  });

  it("allows Read with any filename (even with keywords)", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "Read" },
      { args: { filePath: "search.js", text: "" } }
    );
    expect(result).toBeNull();
  });

  it("blocks glob in hard mode", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler({ tool: "glob" }, { args: { pattern: "*.js" } });
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("ctx_execute");
    }
  });

  it("blocks webfetch in hard mode", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler({ tool: "webfetch" }, { args: { url: "https://example.com" } });
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("ctx_fetch_and_index");
    }
  });

  it("blocks websearch in hard mode", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler({ tool: "websearch" }, { args: { query: "test" } });
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("ctx_batch_execute");
    }
  });

  it("blocks codesearch in hard mode", async () => {
    const plugin = await createPlugin({ OPENCODE_ENFORCE_MODE: "1" });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler({ tool: "codesearch" }, { args: { query: "test" } });
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("ctx_search");
    }
  });

  it("allows multiple OPENCODE_ALLOW_PATTERNS patterns", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_PATTERNS: "*.json,*.md,*.yml"
    });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "glob" },
      { args: { pattern: "*.md" } }
    );
    expect(result).toBeNull();
  });

  it("uses default blocked commands when OPENCODE_BLOCK_BASH_CMDS is empty", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_BLOCK_BASH_CMDS: ""
    });
    const handler = plugin["tool.execute.before"];
    
    try {
      await handler(
        { tool: "bash" },
        { args: { command: "grep foo bar" } }
      );
      throw new Error("Should have thrown");
    } catch (e) {
      expect(e.message).toContain("SYSTEM DIRECTIVE: BASH COMMAND DENIED");
    }
  });


  it("blocks glob via allowlist", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_PATTERNS: "*.json"
    });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "glob" },
      { args: { pattern: "*.json" } }
    );
    expect(result).toBeNull();
  });

  it("allows codesearch via allowlist", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_PATTERNS: "myquery"
    });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "codesearch" },
      { args: { query: "myquery" } }
    );
    expect(result).toBeNull();
  });

  it("allows webfetch via allowlist", async () => {
    const plugin = await createPlugin({ 
      OPENCODE_ENFORCE_MODE: "1",
      OPENCODE_ALLOW_PATTERNS: "example.com"
    });
    const handler = plugin["tool.execute.before"];
    const result = await handler(
      { tool: "webfetch" },
      { args: { url: "https://example.com/api" } }
    );
    expect(result).toBeNull();
  });
});