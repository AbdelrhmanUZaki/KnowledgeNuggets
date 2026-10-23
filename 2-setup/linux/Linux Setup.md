# Linux Setup (ParrotOS / Debian)

Fresh-install checklist. Configs live next to this file; cross-OS configs are in `../shared/`.

## 1. Bootstrap packages

```bash
cd 2-setup
./install.sh
```

Installs (idempotent, re-runnable): apt tools, security/wordlist packages, Neovim AppImage, Agave Nerd Font, Telegram, rtk (`~/.local/bin`). Optional pentest packages via `SECURITY_PACKAGES=()`.

### [neru](https://github.com/y3owk1n/neru)

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/y3owk1n/neru/main/scripts/install.sh | bash
```

The script prompts for confirmation — write `y` to accept.

> **Not currently in use (2026-09):** neru conflicts with kanata on KDE Wayland — its evdev keyboard proxy grabs the keyboards but its re-emission doesn't reach KWin, killing the keyboard whenever it runs (v1.54.0). Kanata is more important; revisit when neru fixes remapper coexistence on Wayland.

## 2. Apply dotfiles

```bash
./linux/restore.sh
```

Copies/symlinks into `$HOME` (backs up existing files first):

| Source | Target |
|---|---|
| `linux/bashrc` | `~/.bashrc` |
| `linux/bash_profile` | `~/.bash_profile` |
| `linux/inputrc` | `~/.inputrc` (vi editing mode) |
| `linux/gitconfig` | `~/.gitconfig` (identity, main branch, LFS) |
| `linux/tmux.conf` | `~/.tmux.conf` |
| `linux/kanata.kbd` | `~/.config/kanata/kanata.kbd` (if kanata installed) |
| `../shared/nvim` | `~/.config/nvim` |
| `../shared/opencode` | `~/.config/opencode` |
| `../shared/codex` | `~/.config/codex` |
| `../shared/gemini` | `~/.gemini` |
| `../shared/agents` | `~/.agents` |
| `../shared/zcode/AGENTS.md` | `~/.zcode/AGENTS.md` |
| `../shared/zcode/cli/config.json` | `~/.zcode/cli/config.json` |

Reload: `source ~/.bashrc && tmux source-file ~/.tmux.conf`

> **zcode:** only the CLI global config is synced (rtk instructions + rtk PreToolUse hook). Everything else in `~/.zcode` is machine-local state and stays out of the repo: `v2/` desktop settings/credentials, `cli/agents/` session dirs, `cli/plugins/` cache. Plugin marketplaces are re-added manually (`/plugin marketplace add ...`).

## 3. nvim

- `:MasonInstallAll` after lazy.nvim finishes downloading plugins
- `:h nvui` to learn base46 UI customization
- Update with `Lazy sync`

## 4. Keyboard (kanata)

`kanata.kbd`: `caps` = tap Esc / hold scroll layer, `space` hold = nav arrows.

```bash
sudo nala install -y kanata        # or a release from github.com/jtroo/kanata

# Give your user write access to /dev/uinput (kanata needs it for the virtual keyboard)
sudo usermod -aG input $USER       # log out/in afterwards
printf 'KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="input", MODE="0660"\n' |
  sudo tee /etc/udev/rules.d/50-kanata.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# Link the config (runs only when kanata is installed) and test
./linux/restore.sh
kanata -c ~/.config/kanata/kanata.kbd     # errors land in ~/.log
```

Autostart: add a normal user systemd unit as below, then `systemctl --user enable --now kanata`.

```ini
# ~/.config/systemd/user/kanata.service
[Unit]
Description=Kanata keyboard remapper
After=graphical-session.target

[Service]
ExecStart=/usr/bin/kanata -c %h/.config/kanata/kanata.kbd
Restart=on-failure

[Install]
WantedBy=default.target
```

If skipping kanata, set Caps → Esc via GNOME settings (see section 5).

### KDE window tiling (Krohnkite)

```bash
./linux/kde-tiling.sh   # then log out/in once — KWin reads shortcuts at login
```

Installs the maintained Plasma 6 fork (Codeberg — krohnkite.com still points at
the abandoned Plasma 5 repo), enables it, and applies the key scheme:

- `Alt+1..9, Alt+0` -> switch to virtual desktop 1..10
- `Alt+H/J/K/L` focus, `Alt+Shift+H/J/K/L` move window, `Alt+Ctrl+H/J/K/L` resize
- `Alt+Return` open Konsole, `Alt+Shift+Return` set master, `Alt+F` float,
  `Alt+T` tile / `Alt+M` monocle, `Alt+\` next layout
- `lv3:ralt_alt` in `kxkbrc`: right Alt acts as plain Alt — both Alts trigger
  everything above; costs the AltGr special characters on the `eg` layout

Gotchas:

- KWin reads `kglobalshortcutsrc` only at login — live edits and `kwin
  reconfigure` do NOT hot-apply shortcut changes.
- Don't toggle Krohnkite on/off at runtime: reload cycles crash apps. It loads
  once at login. Also avoid the kglobalaccel DBus query methods
  (`actionList` / `globalShortcutsByKey`) on this Plasma 6.6 build — they
  abort `kwin_wayland`; use the Shortcuts GUI or `kde-tiling.sh` instead.
- Plain Plasma workspace navigation stays available: `Meta+Ctrl+Left/Right`,
  Overview `Meta+W`, Grid `Meta+G`.
- On the `eg` layout the number row emits Arabic-Indic digits, so `Alt+digit`
  desktop switching needs the EN layout active.

## 5. Manual one-time steps

Follow [manual-steps.md](../manual-steps.md): browser sync, Bitwarden, `gh auth login`, WhatsApp/Telegram QR, VS Code, Caps → Esc (only if not using kanata).

## 6. Optional: static IP / DNS

See [networking.md](../networking.md).

## 7. NVIDIA drivers on Ubuntu (HP ZBook / hybrid graphics)

Symptom: random hard freezes or sudden power-offs while working on Linux; Windows is stable.

Likely cause: the open-source `nouveau` driver is loaded for the NVIDIA GPU.

Check:

```bash
lspci -k | grep -A2 'VGA compatible controller: NVIDIA'
```

If it shows `Kernel driver in use: nouveau`, install the recommended proprietary driver:

```bash
sudo apt update
sudo ubuntu-drivers install
sudo reboot
```

Verify after reboot:

```bash
lspci -k | grep -A2 'VGA compatible controller: NVIDIA'
# should show: Kernel driver in use: nvidia
```

If Secure Boot is enabled, enroll the MOK key at the next boot; if it is disabled, no extra step is needed.

## 8. HP ZBook 15 G6 fan / thermal shutdown fix

Symptom: laptop suddenly powers off on Linux after the CPU hits 100°C; fan works in Windows but not in Linux (`sensors` shows `pwm1: N/A`).

Cause: the HP firmware exposes fan/thermal control to Windows but hides it from Linux.

Fix: add these kernel parameters to GRUB:

```bash
sudo nano /etc/default/grub
```

Change:
```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
```

To:
```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash acpi_osi=! acpi_osi=\"Windows 2012\" acpi_enforce_resources=lax"
```

Then update GRUB and reboot:

```bash
sudo update-grub
sudo reboot
```

Verify:

```bash
s-tui
# Press "Stress" and run for a few minutes; the fan should spin and CPU should stay below ~90°C
```

Also enable `thermald` so it can throttle short temperature spikes before the fan reacts:

```bash
sudo systemctl enable --now thermald
```

> **Note:** I am still testing whether both the GRUB edit and `thermald` are required, or if `thermald` alone is enough. For now I keep both active.
> Optional extra safety: limit CPU max performance to 70% with `echo 70 | sudo tee /sys/devices/system/cpu/intel_pstate/max_perf_pct`.

## 9. Wayland session: river-classic

A lightweight **dynamic-tiling Wayland** desktop (dwm tag model) that keeps GNOME intact
as the fallback session. Full guide: [`river-classic/README.md`](river-classic/README.md).

```bash
cd 2-setup/linux/river-classic
./install.sh          # deps (sudo) → build wlroots 0.20.2 + river-classic v0.3.17 → GDM entry → config
./restore.sh          # re-apply the config only (symlinks ~/.config/{river,waybar} → repo)
```

Then log out and pick **river-classic** in the GDM gear menu.

| Piece | What it gives you |
|---|---|
| `river-classic` v0.3.17 (Zig build) | compositor: dynamic tiling, dwm tags, runtime keybinds |
| `waybar` (solarized dark) | flat top bar: workspaces, clock, volume/brightness/wifi/bluetooth/battery, DND bell, screenshots, power |
| `system-panel.py` | GNOME-style **System Menu** popover (wlr-layer-shell, docked under the bar): toggle tiles, live sliders, session row |
| `init` | boots dunst/swaybg/waybar, exports the dbus/session env, Alt-based tag binds |

Keybinds: `Alt+1..9` switch tag, `Alt+Shift+1..9` **move the window to a tag**, `Super+Shift+Return` terminal
(foot), `Super+P` launcher (fuzzel), `Alt+B` hide/show the bar.

> The config is symlinked into `~/.config`, so **edits in the repo are live** — change
> `config/waybar/style.css` and the bar reloads it.

## 10. AI-agent sandbox VMs (agent-vm + vmup + ZCode Remote SSH)

Every project gets its own isolated Debian VM (own kernel, docker inside), and
the ZCode GUI connects to it over SSH while staying on the host — see
[`vmup/README.md`](vmup/README.md) for the full context, security model, and
troubleshooting (including the Lima nerdctl download fix).

```bash
# Prerequisites (once): limactl, agent-vm, and the base VM — see vmup/README.md
cd ~/github/<project>
vmup          # create/start the VM, pin its SSH port, refresh the ssh alias
# ZCode: Projects '+' → Remote Connection → SSH → alias 'vm-<project>'
```

`restore.sh` links `vmup` into `~/.local/bin` automatically.

## App overview

- **`nala`** – modern front-end for `apt`
- **`rofi`** – launcher. Set shortcut `Super + Space` → `rofi -show drun`
- **`konsole`** – terminal; set font size + Nerd Font for nvim
- **`tmux`** – multiplexer (`tmux.conf`)
- **`gh`** – GitHub CLI (`gh auth login`)
- **river-classic** – dynamic-tiling Wayland session: compositor + waybar + system panel (see §9)