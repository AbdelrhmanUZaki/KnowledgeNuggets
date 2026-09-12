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

## App overview

- **`nala`** – modern front-end for `apt`
- **`rofi`** – launcher. Set shortcut `Super + Space` → `rofi -show drun`
- **`konsole`** – terminal; set font size + Nerd Font for nvim
- **`tmux`** – multiplexer (`tmux.conf`)
- **`gh`** – GitHub CLI (`gh auth login`)