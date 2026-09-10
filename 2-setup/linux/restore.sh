#!/usr/bin/env bash
# Restore Linux dotfiles + shared configs into $HOME.
# Safe to re-run; backs up existing files to ~/.dotfiles-backup-<timestamp>/.
set -euo pipefail

SETUP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINUX="$SETUP/linux"
SHARED="$SETUP/shared"
BACKUP_DIR="$HOME/.dotfiles-backup-$(date +%Y%m%d-%H%M%S)"

link() {
  local src="$1" dst="$2"

  if [ -L "$dst" ]; then
    printf 'skip   %-30s (already a symlink)\n' "$dst"
  elif [ -e "$dst" ]; then
    mkdir -p "$BACKUP_DIR"
    mv "$dst" "$BACKUP_DIR/"
    ln -s "$src" "$dst"
    printf 'backup %-30s -> %s\n' "$dst" "$BACKUP_DIR/"
  else
    ln -s "$src" "$dst"
    printf 'linked %-30s -> %s\n' "$dst" "$src"
  fi
}

echo "== Linux dotfiles =="
link "$LINUX/bashrc"       "$HOME/.bashrc"
link "$LINUX/bash_profile" "$HOME/.bash_profile"
link "$LINUX/tmux.conf"    "$HOME/.tmux.conf"
if command -v kanata >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/kanata"
  link "$LINUX/kanata.kbd" "$HOME/.config/kanata/kanata.kbd"
else
  echo "note   kanata not installed; skipping kanata.kbd (see Linux Setup.md)"
fi

echo
echo "== shared configs =="
link "$SHARED/nvim"                 "$HOME/.config/nvim"
link "$SHARED/opencode"             "$HOME/.config/opencode"
link "$SHARED/codex"                "$HOME/.config/codex"
link "$SHARED/gemini"               "$HOME/.gemini"
link "$SHARED/agents"               "$HOME/.agents"

echo
echo "Done. Reload with: source ~/.bashrc && tmux source-file ~/.tmux.conf"