#!/usr/bin/env bash
set -euo pipefail

log()   { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }

APT_PACKAGES=(
  nala rofi tmux xclip konsole gh
  ripgrep fzf bat
  curl wget unzip git build-essential
  python3 python3-pip python3-venv nodejs npm
)

# Optional pentest tools (HTB/OSCP). Empty = skip.
SECURITY_PACKAGES=(
  seclists exploitdb sqlmap nikto hashcat john
)

# --- apt ----------------------------------------------------------------
log "Updating package lists..."
sudo apt update

missing=()
for pkg in "${APT_PACKAGES[@]}" "${SECURITY_PACKAGES[@]}"; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done

if [ ${#missing[@]} -gt 0 ]; then
  log "Installing apt packages: ${missing[*]}"
  sudo apt install -y "${missing[@]}"
else
  log "All apt packages already installed."
fi

# --- Neovim (AppImage) --------------------------------------------------
if command -v nvim >/dev/null 2>&1; then
  log "nvim already installed: $(nvim --version | head -1)"
else
  log "Downloading Neovim AppImage..."
  nvim_ver="v0.12.5"
  wget -q "https://github.com/neovim/neovim/releases/download/${nvim_ver}/nvim-linux-x86_64.appimage" -O /tmp/nvim.appimage
  chmod +x /tmp/nvim.appimage
  sudo mv /tmp/nvim.appimage /usr/bin/nvim
  log "nvim installed to /usr/bin/nvim"
fi

# --- Nerd Font (Agave) ----------------------------------------------------
if fc-list 2>/dev/null | grep -qi 'Agave'; then
  log "Agave Nerd Font already installed."
else
  log "Installing Agave Nerd Font..."
  wget -q "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/Agave.zip" -O /tmp/Agave.zip
  unzip -qo /tmp/Agave.zip -d /tmp/Agave
  sudo mkdir -p /usr/share/fonts/truetype/nerd-fonts
  sudo cp /tmp/Agave/*.ttf /usr/share/fonts/truetype/nerd-fonts/
  sudo fc-cache -f >/dev/null
  rm -rf /tmp/Agave /tmp/Agave.zip
  log "Agave Nerd Font installed."
fi

# --- Snap (Telegram desktop) ----------------------------------------------
if command -v telegram-desktop >/dev/null 2>&1; then
  log "Telegram already installed."
elif command -v snap >/dev/null 2>&1; then
  log "Installing Telegram via snap..."
  sudo snap install telegram-desktop
else
  warn "snap not available; skip Telegram (or: sudo nala install telegram-desktop)"
fi

log "Done. Next: ./linux/restore.sh, then follow linux/Linux Setup.md"