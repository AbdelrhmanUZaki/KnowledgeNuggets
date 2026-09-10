/**
 * enforce-context-mode - OpenCode plugin
 * Redirects data-fetching tools to context-mode MCP tools
 *
 * Usage: Add to opencode.json plugin array:
 * "plugin": ["...enforce-context-mode.mjs"]
 *
 * BEHAVIOR: When AI tries blocked tools, shows error with context-mode replacement.
 * The AI learns from error and uses context-mode tools automatically.
 *
 * Configuration via env vars (set in shell, not OpenCode):
 * - ENFORCE_CONTEXT_MODE=0       # Disable plugin entirely
 * - ENFORCE_ALLOW=git,npm        # Allowlist specific tools/patterns
 * - ENFORCE_LOG=1                # Enable session logging
 */

export default async ({ env }) => {
  console.log("[enforce-context-mode] Plugin loaded, env:", JSON.stringify(env));

  // Check if disabled via environment variable
  if (env?.ENFORCE_CONTEXT_MODE === "0" || env?.ENFORCE_CONTEXT_MODE === "false") {
    console.log("[enforce-context-mode] Disabled via ENFORCE_CONTEXT_MODE");
    return null;
  }

  // Default: silent mode (auto-redirect)
  // Set ENFORCE_VERBOSE=1 to show error messages instead
  const verboseMode = env?.ENFORCE_VERBOSE === "1" || env?.ENFORCE_VERBOSE === "true";
  const silentMode = !verboseMode;
  console.log("[enforce-context-mode] Silent mode:", silentMode, "Verbose:", verboseMode);

  // Tool -> context-mode auto-redirect mapping
  const redirectMap = {
    grep: {
      targetTool: "context-mode_ctx_execute",
      transform: (args) => {
        const pattern = args?.pattern || "";
        const path = args?.path || ".";
        const cmd = `grep -r "${pattern}" ${path}`;
        return { language: "shell", code: cmd };
      },
    },
    glob: {
      targetTool: "context-mode_ctx_execute",
      transform: (args) => {
        const pattern = args?.pattern || "*";
        const cmd = `find . -name "${pattern}"`;
        return { language: "shell", code: cmd };
      },
    },
    webfetch: {
      targetTool: "context-mode_ctx_fetch_and_index",
      transform: (args) => {
        return { url: args?.url || "", source: "user-request" };
      },
    },
    websearch: {
      targetTool: "context-mode_ctx_batch_execute",
      transform: (args) => {
        const query = args?.query || "";
        return {
          commands: [{ label: "search", command: `echo 'Search: ${query}'` }],
          queries: [query],
        };
      },
    },
    codesearch: {
      targetTool: "context-mode_ctx_search",
      transform: (args) => {
        return { queries: [args?.query || args?.q || ""] };
      },
    },
  };

  // Bash sub-command -> context-mode redirect
  const bashRedirects = [
    {
      pattern: /^\s*grep\s+/,
      targetTool: "context-mode_ctx_execute",
      transform: (args) => {
        const cmd = args?.command || "";
        return { language: "shell", code: cmd };
      },
    },
    {
      pattern: /^\s*find\s+(\.\S*|\/)/,
      targetTool: "context-mode_ctx_execute",
      transform: (args) => {
        const cmd = args?.command || "";
        return { language: "shell", code: cmd };
      },
    },
    {
      pattern: /^\s*cat\s+/,
      targetTool: "context-mode_ctx_execute_file",
      transform: (args) => {
        const cmd = args?.command || "";
        const fileMatch = cmd.match(/cat\s+['"]?([^'"\s]+)['"]?/);
        const filePath = fileMatch ? fileMatch[1] : "";
        return {
          path: filePath,
          language: "shell",
          code: "console.log(FILE_CONTENT)",
        };
      },
    },
    {
      pattern: /^\s*head\s+/,
      targetTool: "context-mode_ctx_execute",
      transform: (args) => {
        const cmd = args?.command || "";
        return { language: "shell", code: cmd };
      },
    },
    {
      pattern: /^\s*tail\s+/,
      targetTool: "context-mode_ctx_execute",
      transform: (args) => {
        const cmd = args?.command || "";
        return { language: "shell", code: cmd };
      },
    },
    {
      pattern: /^\s*wc\s+/,
      targetTool: "context-mode_ctx_execute",
      transform: (args) => {
        const cmd = args?.command || "";
        return { language: "shell", code: cmd };
      },
    },
  ];

  // Error messages for non-silent mode
  const errorMap = {
    grep: {
      error: "Use context-mode_ctx_execute with grep command instead.",
      replacement: 'ctx_execute("shell", "grep pattern path")',
    },
    Read: {
      error: "Use context-mode_ctx_execute_file for analysis, native Read only for editing.",
      replacement: 'ctx_execute_file(path, "javascript", "process FILE_CONTENT...")',
      analysisKeywords: ["analysis", "process", "analyze", "search", "FILE_CONTENT", "count", "filter", "summarize"],
    },
    bash: {
      error: "Use context-mode_ctx_execute for data processing.",
      blockedSubCommands: ["grep", "rg", "find", "cat", "head", "tail", "wc", "awk", "sed", "curl", "wget"],
    },
    glob: {
      error: "Use context-mode_ctx_execute with find command instead.",
      replacement: 'ctx_execute("shell", "find . -name pattern")',
    },
    webfetch: {
      error: "Use context-mode_ctx_fetch_and_index instead.",
      replacement: 'ctx_fetch_and_index(url, source)',
    },
    websearch: {
      error: "Use context-mode_ctx_batch_execute instead.",
      replacement: 'ctx_batch_execute(commands, queries)',
    },
    codesearch: {
      error: "Use context-mode_ctx_search instead.",
      replacement: 'ctx_search(queries)',
    },
  };

  // Load allowlist from env (comma-separated patterns)
  const allowlist = new Set(
    (env?.ENFORCE_ALLOW || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  );

  const isAllowed = (tool, args) => {
    if (allowlist.size === 0) return false;
    const pattern = tool;
    return Array.from(allowlist).some(
      (p) => pattern === p || (args && args.includes && args.includes(p))
    );
  };

  // Event hook for session.created
  const onSessionCreated = async ({ session }) => {
    if (env?.ENFORCE_LOG === "1" || env?.ENFORCE_LOG === "true") {
      console.log(`[enforce-context-mode] Session started: ${session.id}`);
    }
  };

  return {
    "tool.execute.before": async (input, output) => {
      const tool = input.tool;
      const args = output.args;

      if (isAllowed(tool, args?.command || args?.pattern || args?.filePath)) return null;

      // Handle Read tool - block analysis, allow editing
      if (tool === "Read") {
        const rule = errorMap.Read;
        const filePath = args?.filePath || "";
        const readContent = args?.content || "";
        const searchTerm = args?.text || "";
        const combined = `${filePath} ${readContent} ${searchTerm}`.toLowerCase();
        const hasAnalysisKeyword = rule.analysisKeywords.some(
          (kw) => combined.includes(kw.toLowerCase())
        );
        if (hasAnalysisKeyword) {
          if (silentMode) {
            output.tool = "context-mode_ctx_execute_file";
            output.args = {
              path: filePath,
              language: "shell",
              code: "console.log(FILE_CONTENT)",
            };
            return output;
          }
          throw new Error(`${rule.error}\n\nExample: ${rule.replacement}`);
        }
        return null;
      }

      // Handle bash - check for blocked sub-commands
      if (tool === "bash") {
        const cmd = args?.command || "";
        const cmdLower = cmd.toLowerCase();
        const rule = errorMap.bash;
        const blockedSubCmd = rule.blockedSubCommands.find((c) => cmdLower.includes(c));

        if (blockedSubCmd) {
          if (silentMode) {
            // Try to match bash command to redirect
            for (const redirect of bashRedirects) {
              if (redirect.pattern.test(cmd)) {
                output.tool = redirect.targetTool;
                output.args = redirect.transform(args);
                return output;
              }
            }
            // Fallback: redirect to ctx_execute
            output.tool = "context-mode_ctx_execute";
            output.args = { language: "shell", code: cmd };
            return output;
          }
          const suggestion = blockedSubCmd === "find"
            ? 'ctx_execute("shell", "find . -name pattern")'
            : blockedSubCmd === "cat"
            ? 'ctx_execute_file(path, "javascript", "process FILE_CONTENT...")'
            : 'ctx_execute("shell", "command without ' + blockedSubCmd + '")';
          throw new Error(
            `bash: blocked sub-command '${blockedSubCmd}'\n${rule.error}\nTip: ${suggestion}`
          );
        }
        return null;
      }

      // Handle direct tool redirects (grep, glob, webfetch, websearch, codesearch)
      const redirect = redirectMap[tool];
      if (redirect) {
        if (silentMode) {
          output.tool = redirect.targetTool;
          output.args = redirect.transform(args);
          return output;
        }
        const rule = errorMap[tool];
        throw new Error(`${rule.error}\n\nExample: ${rule.replacement}`);
      }

      return null;
    },
  };
};