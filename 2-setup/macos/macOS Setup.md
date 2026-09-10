# macOS Setup

Fresh-install checklist. Configs live next to this file; cross-OS configs are in `../shared/`.

## 1. Install essentials

```bash
brew install ripgrep fzf bat tmux neovim git gh yabai skhd
brew install --cask warp
brew install jtroo/kanata/kanata
```

Quick Install (Linux/macOS) — installs to `~/.local/bin` (already on `PATH` via `bashrc`):

```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
```

## 2. Apply dotfiles

```bash
./macos/restore.sh
```

Copies/symlinks into `$HOME` (backs up existing files first):

| Source | Target |
|---|---|
| `macos/bashrc` | `~/.bashrc` |
| `macos/bash_profile` | `~/.bash_profile` |
| `macos/tmux.conf` | `~/.tmux.conf.local` |
| `macos/yabai` | `~/.config/yabai` |
| `macos/skhd/.skhdrc` | `~/.skhdrc` |
| `macos/warp` | `~/.warp` |
| `macos/karabiner` | `~/.config/karabiner` |
| `../shared/nvim` | `~/.config/nvim` |
| `../shared/opencode` | `~/.config/opencode` |
| `../shared/codex` | `~/.codex` |
| `../shared/gemini` | `~/.gemini` |
| `../shared/agents` | `~/.agents` |

Reload: `source ~/.bashrc`

## 3. Start window manager + hotkeys

yabai/skhd may need their unsigned helper installed once (see the yabai wiki "SIP" instructions). Then:

```bash
yabai --start-service
skhd --start-service
```

Reference: `macos/skhd/.skhdrc` (alt-key window focus/move, app launchers, spaces).

## 4. Keyboard (kanata)

LaunchDaemon is per-user — edit `macos/launchdaemons/io.dreamsofcode.kanata.plist`, replace `<USERNAME>` in the config path, then:

```bash
sudo cp macos/launchdaemons/io.dreamsofcode.kanata.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/io.dreamsofcode.kanata.plist
```

If instead you prefer Karabiner, its config is under `macos/karabiner/` (Caps = Esc + scroll, Space = nav; homerow mods disabled in favor of kanata).

## 5. Manual one-time steps

Follow [manual-steps.md](../manual-steps.md): browser sync, Bitwarden, `gh auth login`, WhatsApp/Telegram, VS Code. Skip Caps→Esc (already handled by kanata/karabiner).

## 6. nvim

- `:MasonInstallAll` after lazy.nvim finishes; `:h nvui`; update with `Lazy sync`.