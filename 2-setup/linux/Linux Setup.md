# Linux Setup (ParrotOS / Debian)

Fresh-install checklist. Configs live next to this file; cross-OS configs are in `../shared/`.

## 1. Bootstrap packages

```bash
cd 2-setup
./install.sh
```

Installs (idempotent, re-runnable): apt tools, security/wordlist packages, Neovim AppImage, Agave Nerd Font, Telegram, rtk (`~/.local/bin`). Optional pentest packages via `SECURITY_PACKAGES=()`.

## 2. Apply dotfiles

```bash
./linux/restore.sh
```

Copies/symlinks into `$HOME` (backs up existing files first):

| Source | Target |
|---|---|
| `linux/bashrc` | `~/.bashrc` |
| `linux/bash_profile` | `~/.bash_profile` |
| `linux/tmux.conf` | `~/.tmux.conf` |
| `linux/kanata.kbd` | `~/.config/kanata/kanata.kbd` (if kanata installed) |
| `../shared/nvim` | `~/.config/nvim` |
| `../shared/opencode` | `~/.config/opencode` |
| `../shared/codex` | `~/.config/codex` |
| `../shared/gemini` | `~/.gemini` |
| `../shared/agents` | `~/.agents` |

Reload: `source ~/.bashrc && tmux source-file ~/.tmux.conf`

## 3. nvim

- `:MasonInstallAll` after lazy.nvim finishes downloading plugins
- `:h nvui` to learn base46 UI customization
- Update with `Lazy sync`

## 4. Keyboard (kanata)

```bash
sudo apt install kanata        # or grab a release from github.com/jtroo/kanata
kanata -c ~/.config/kanata/kanata.kbd
```

Add a normal user systemd unit for autostart (see `linux/kanata.kbd` layout: `caps` = Esc + scroll layer, `space` hold = nav arrows).

## 5. Manual one-time steps

Follow [manual-steps.md](../manual-steps.md): browser sync, Bitwarden, `gh auth login`, WhatsApp/Telegram QR, VS Code, Caps → Esc (only if not using kanata).

## 6. Optional: static IP / DNS

See [networking.md](../networking.md).

## App overview

- **`nala`** – modern front-end for `apt`
- **`rofi`** – launcher. Set shortcut `Super + Space` → `rofi -show drun`
- **`konsole`** – terminal; set font size + Nerd Font for nvim
- **`tmux`** – multiplexer (`tmux.conf`)
- **`gh`** – GitHub CLI (`gh auth login`)