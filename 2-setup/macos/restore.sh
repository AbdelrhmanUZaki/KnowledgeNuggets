#!/usr/bin/env bash
# Restore macOS dotfiles + shared configs into $HOME.
# Safe to re-run; backs up existing files to ~/.dotfiles-backup-<timestamp>/.
set -euo pipefail

MAC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP="$(dirname "$MAC")"
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

echo "== macOS dotfiles =="
link "$MAC/bashrc"          "$HOME/.bashrc"
link "$MAC/bash_profile"    "$HOME/.bash_profile"
link "$MAC/tmux.conf"       "$HOME/.tmux.conf.local"
link "$MAC/yabai"           "$HOME/.config/yabai"
link "$MAC/.yabairc"        "$HOME/.yabairc" 2>/dev/null || true
link "$MAC/skhd/.skhdrc"    "$HOME/.skhdrc"
link "$MAC/warp"            "$HOME/.warp"
mkdir -p "$HOME/.config/karabiner"
link "$MAC/karabiner/karabiner.json" "$HOME/.config/karabiner/karabiner.json"
link "$MAC/karabiner/assets"         "$HOME/.config/karabiner/assets"

echo
echo "== shared configs =="
link "$SHARED/nvim"      "$HOME/.config/nvim"
link "$SHARED/opencode"  "$HOME/.config/opencode"
link "$SHARED/codex"     "$HOME/.codex"
link "$SHARED/gemini"    "$HOME/.gemini"
link "$SHARED/agents"    "$HOME/.agents"

echo
echo "note   kanata LaunchDaemon is per-user: edit macOS/launchdaemons/io.dreamsofcode.kanata.plist"
echo "       replace <USERNAME>, then: sudo cp ... /Library/LaunchDaemons/ && sudo launchctl load"
echo
echo "Done. Reload with: source ~/.bashrc"