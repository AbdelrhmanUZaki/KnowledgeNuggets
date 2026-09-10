# opencode-enforce-context-mode

> Blocks inefficient tools and guides AI to use context-mode MCP tools.

[![npm version](https://img.shields.io/npm/v/opencode-enforce-context-mode.svg)](https://www.npmjs.com/package/opencode-enforce-context-mode)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## What & Why

This plugin stops the AI from flooding your context with large data dumps. When it tries to use inefficient tools, it gets blocked and shown the correct alternative.

[context-mode](https://github.com/mksglu/context-mode) is the proper solution. This plugin is a workaround until OpenCode fixes the hooks.

Once OpenCode fixes the issue and context-mode updates, you won't need this plugin.

> **Issue:** [OpenCode #14808](https://github.com/anomalyco/opencode/issues/14808)

## Install

Add to your `opencode.json` (either global or project):

```json
{
  "plugin": ["opencode-enforce-context-mode"]
}
```

The plugin works immediately with strict defaults. If you need to customize it, you can optionally set environment variables in your shell (e.g., `~/.zshrc`):

```bash
# Example overrides:
export OPENCODE_ENFORCE_MODE=1                 # 0=off, 1=block (default)
export OPENCODE_ALLOW_PATTERNS="*.json,test/"  # Skip enforcement for these patterns
export OPENCODE_ALLOW_BASH_CMDS="curl,wget"    # Explicitly allow these bash commands
export OPENCODE_BLOCK_BASH_CMDS="find,grep"    # Override default blocked commands
```

## Configuration

All configuration for this plugin is handled via environment variables in your shell (e.g., exported in your `~/.zshrc` or `~/.bashrc`).

| Environment Variable | Values | Default | Example |
|----------------------|--------|---------|---------|
| `OPENCODE_ENFORCE_MODE` | `0` = off, `1` = block | `1` | `export OPENCODE_ENFORCE_MODE=1` |
| `OPENCODE_ALLOW_PATTERNS` | comma-separated patterns to completely skip | none | `export OPENCODE_ALLOW_PATTERNS="*.json,example.com"` |
| `OPENCODE_ALLOW_BASH_CMDS` | comma-separated bash commands to allow | none | `export OPENCODE_ALLOW_BASH_CMDS="curl,wget"` |
| `OPENCODE_BLOCK_BASH_CMDS` | override the default blocked bash commands | (see list below) | `export OPENCODE_BLOCK_BASH_CMDS="find,cat,awk"` |

*(Default blocked commands: `grep,rg,find,cat,head,tail,wc,awk,sed,curl,wget`)*



## Blocked Tools → Use Instead

| Blocked | Use This |
|---------|----------|
| `grep` | `ctx_execute("shell", "grep pattern path")` |
| `glob` | `ctx_execute("shell", "find . -name '*.js'")` |
| `webfetch` | `ctx_fetch_and_index(url, source, force=true)` |
| `websearch` | `ctx_batch_execute(commands, queries)` |
| `codesearch` | `ctx_search(queries)` |
| `Read` (analysis) | `ctx_execute_file(path, "js", "process...")` |

## How It Works

1. **Proactive AI Guidance**: The plugin injects environment constraints directly into the first user message using OpenCode's `experimental.chat.messages.transform` hook. The AI immediately knows to use `ctx_*` tools instead of native ones on its very first try.
2. **Aggressive Enforcement**: If the AI somehow attempts to run a forbidden command, it is met with an aggressively worded system directive designed to force immediate compliance:

```
> curl https://example.com

<tool_execution_error>
SYSTEM DIRECTIVE: BASH COMMAND DENIED
FATAL: The bash sub-command 'curl' is STRICTLY FORBIDDEN.
REASON: You are attempting to run a forbidden command that floods the context window. Use context-mode_ctx_execute instead.

REQUIRED ACTION: YOU MUST USE THE FOLLOWING INSTEAD:
>>> ctx_fetch_and_index(url, source, force=true) <<<

🛑 FATAL: DO NOT RETRY THIS COMMAND. PROCEED IMMEDIATELY TO THE SUGGESTED REPLACEMENT. 🛑
</tool_execution_error>
```

## Develop

```bash
bun install
bun test
```

## License

[MIT](LICENSE)