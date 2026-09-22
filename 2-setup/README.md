# Setup

Fresh-install checklists and dotfiles for my machines. Pick your OS, run its restore script, done — safe to re-run, backs up existing files first.

| Folder | Contents |
|---|---|
| [`linux/`](linux/) | Linux dotfiles + [setup checklist](linux/Linux%20Setup.md) |
| [`macos/`](macos/) | macOS dotfiles + [setup checklist](macos/macOS%20Setup.md) |
| [`windows/`](windows/) | Windows dotfiles + [setup checklist](windows/Windows%20Setup.md) |
| [`shared/`](shared/) | Cross-OS tool configs (nvim, opencode, codex, gemini, agents, zcode) |

Apply dotfiles with the restore script for your OS: `linux/restore.sh`, `macos/restore.sh`, or `windows/restore.ps1`. Each one also symlinks everything in `shared/` into `$HOME`.

Also here:

- [`install.sh`](install.sh) — Linux bootstrap packages (idempotent)
- [`manual-steps.md`](manual-steps.md) — one-time manual setup (browser sync, Bitwarden, `gh auth login`, ...)
- [`networking.md`](networking.md) — optional static IP / DNS
- [`Setup & Tools.md`](Setup%20&%20Tools.md) — tools & tips (fuzzing, Burp extensions, wordlists, ...)
