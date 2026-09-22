# Shared configs

Cross-OS tool configs. Each OS restore script ([`../linux/restore.sh`](../linux/restore.sh), [`../macos/restore.sh`](../macos/restore.sh), [`../windows/restore.ps1`](../windows/restore.ps1)) symlinks them into `$HOME` — safe to re-run.

| Folder | Tool | Restored to |
|---|---|---|
| [`nvim/`](nvim/) | Neovim (NvChad-based) | `~/.config/nvim` (Windows: `~\AppData\Local\nvim`) |
| [`opencode/`](opencode/) | OpenCode + GSD agents/commands | `~/.config/opencode` |
| [`codex/`](codex/) | Codex CLI + GSD agents | `~/.codex` (Linux: `~/.config/codex`) |
| [`gemini/`](gemini/) | Gemini CLI / Antigravity | `~/.gemini` |
| [`agents/`](agents/) | Agent skills (caveman family) | `~/.agents` |
| [`zcode/`](zcode/) | ZCode CLI global config | `~/.zcode/AGENTS.md` + `~/.zcode/cli/config.json` |

Only hand-edited config lives here — caches, sessions, credentials and other machine-local state stay out of the repo.
