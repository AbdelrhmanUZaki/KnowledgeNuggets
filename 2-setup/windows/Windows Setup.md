# Windows Setup

Fresh-install checklist. Configs live next to this file; cross-OS configs are in `../shared/`.

## 1. Install essentials

```powershell
winget install OpenJS.NodeJS Git.Git Microsoft.PowerShell Neovim.Neovim
winget install BurntSushi.ripgrep.MSVC sharkdp.bat junegunn.fzf
winget install jtroo.kanata_gui microsoft.windowsterminal
```

## 2. Apply dotfiles (PowerShell 7+)

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\restore.ps1
```

Copies/symlinks into your profile (backs up existing files first):

| Source | Target |
|---|---|
| `windows/profile.ps1` | `~\Documents\PowerShell\Microsoft.PowerShell_profile.ps1` |
| `windows/windows-terminal.json` | Windows Terminal `settings.json` |
| `windows/kanata.kbd` | `~\AppData\Roaming\kanata\kanata.kbd` (if kanata installed) |
| `../shared/nvim` | `~\AppData\Local\nvim` |
| `../shared/opencode` | `~\.config\opencode` |
| `../shared/codex` | `~\.codex` |
| `../shared/gemini` | `~\.gemini` |
| `../shared/agents` | `~\.agents` |

Note: `restore.ps1` symlinks via PowerShell (needs the symlink link permission — run once from an **elevated** prompt if it fails).

## 3. Keyboard (kanata)

```powershell
kanata -c ~\AppData\Roaming\kanata\kanata.kbd
```

Autostart: press `Win+R`, `shell:startup`, drop a shortcut to `kanata -c <config>` (see `windows/kanata.kbd` layout: Esc → backtick, caps = Esc + scroll layer, space hold = nav arrows).

## 4. Terminal

Windows Terminal reads `windows/windows-terminal.json` — one "One Half Dark" scheme, Vim-friendly split/focus keys. Default profile = PowerShell 7.

## 5. Manual one-time steps

Follow [manual-steps.md](../manual-steps.md): browser sync, Bitwarden, `gh auth login`, WhatsApp/Telegram. Caps→Esc is handled by kanata.

## 6. nvim

- `:MasonInstallAll` after lazy.nvim finishes; `:h nvui`; update with `Lazy sync`.