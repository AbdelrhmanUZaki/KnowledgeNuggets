/**
 * opencode-enforce-context-mode
 * OpenCode plugin that redirects data-fetching tools to context-mode MCP tools
 * 
 * Protects your context window from flooding by enforcing better tool usage.
 * 
 * Usage: Add to opencode.json plugin array:
 *   "plugin": ["...enforce-context-mode.mjs"]
 * 
 * Config (set as shell environment variables):
 *   ENFORCE_CONTEXT_MODE=0|dry-run|warn|1  (default: 1)
 *   ENFORCE_ALLOW=pattern1,pattern2      (allowlist for patterns)
 *   ENFORCE_ALLOW_COMMANDS=cmd1,cmd2    (add to allowed bash commands)
 *   ENFORCE_BLOCK=cmd1,cmd2           (bash sub-commands to block)
 *   ENFORCE_LOG=1                      (verbose logging)
 */
export default async () => {
  const env = process.env;
  const mode = (env?.ENFORCE_CONTEXT_MODE || "1").toLowerCase();
  
  if (mode === "0" || mode === "false") {
    return null;
  }
  
  const isDryRun = mode === "dry-run" || mode === "warn";
  
  const defaultBlockedSubCommands = ["grep", "rg", "find", "cat", "head", "tail", "wc", "awk", "sed", "curl", "wget"];
  const blockedSubCommands = parseAllowlist(env?.ENFORCE_BLOCK, defaultBlockedSubCommands);
  
  const allowlist = parseAllowlist(env?.ENFORCE_ALLOW, []);
  
  const allowCommands = parseAllowlist(env?.ENFORCE_ALLOW_COMMANDS, []);
  
  const enforceMap = {
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
      replacement: 'ctx_execute("shell", "command")',
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
  
  const log = (msg) => {
    if (env?.ENFORCE_LOG === "1" || env?.ENFORCE_LOG === "true") {
      console.log(`[enforce-context-mode] ${msg}`);
    }
  };
  
  const isAllowed = (tool, args) => {
    const values = [
      tool,
      args?.command || "",
      args?.pattern || "",
      args?.filePath || "",
      args?.url || "",
      args?.query || "",
    ].join(" ").toLowerCase();
    if (allowlist.some(p => values.includes(p.toLowerCase()))) return true;
    
    if (tool === "bash" && args?.command) {
      const cmd = args.command.toLowerCase();
      return allowCommands.some(c => cmd.includes(c.toLowerCase()));
    }
    return false;
  };
  
  const handleViolation = (tool, error, replacement) => {
    if (isDryRun) {
      log(`VIOLATION: ${tool} - ${error}`);
      return null;
    }
    throw new Error(`${error}\n\nExample: ${replacement}`);
  };
  
  const getBlockedSubCommand = (cmd) => {
    const cmdLower = cmd.toLowerCase();
    return blockedSubCommands.find(c => {
      const escaped = c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(^|[|&;])\\s*${escaped}\\s`);
      return regex.test(cmdLower);
    });
  };
  
  const getSubCommandSuggestion = (subCmd) => {
    if (subCmd === "find") return 'ctx_execute("shell", "find . -name pattern")';
    if (subCmd === "cat") return 'ctx_execute_file(path, "javascript", "process FILE_CONTENT...")';
    return `ctx_execute("shell", "command without ${subCmd}")`;
  };
  
  return {
    "tool.execute.before": async (input, output) => {
      const tool = input.tool;
      const args = output.args;
      const rule = enforceMap[tool];
      
      if (!rule) return null;
      
      if (tool === "Read") {
        const searchTerm = args?.text || "";
        
        const isAnalysisIntent = rule.analysisKeywords?.some(kw => {
          const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          const regex = new RegExp(`\\b${escaped}\\b`);
          return regex.test(searchTerm.toLowerCase());
        });
        
        if (isAnalysisIntent) {
          return handleViolation(tool, rule.error, rule.replacement);
        }
        return null;
      }
      
      if (isAllowed(tool, args)) {
        return null;
      }
      
      if (tool === "bash") {
        const cmd = args?.command || "";
        const blockedSubCmd = getBlockedSubCommand(cmd);
        
        if (blockedSubCmd) {
          const suggestion = getSubCommandSuggestion(blockedSubCmd);
          
          if (isDryRun) {
            log(`VIOLATION: bash blocked sub-command '${blockedSubCmd}' - ${rule.error}`);
            return null;
          }
          throw new Error(
            `bash: blocked sub-command '${blockedSubCmd}'\n` +
            `${rule.error}\n` +
            `Tip: Remove '${blockedSubCmd}' or use:\n` +
            `${suggestion}`
          );
        }
        return null;
      }
      
      if (["glob", "grep", "webfetch", "websearch", "codesearch"].includes(tool)) {
        return handleViolation(tool, rule.error, rule.replacement);
      }
      
      return null;
    },
  };
};

function parseAllowlist(value, defaults) {
  if (!value) return defaults;
  const parsed = value.split(",").map(s => s.trim()).filter(Boolean);
  return parsed.length > 0 ? parsed : defaults;
}

export { parseAllowlist };