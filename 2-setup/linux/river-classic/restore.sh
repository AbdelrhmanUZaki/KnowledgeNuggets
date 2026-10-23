#!/usr/bin/env bash
# Apply the river-classic config into $HOME.
# Safe to re-run; existing files are backed up to ~/.dotfiles-backup-<timestamp>/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$HOME/.dotfiles-backup-$(date +%Y%m%d-%H%M%S)"

link() {
  local src="$1" dst="$2" dst_dir rel

  if [ -L "$dst" ] && [ -e "$dst" ]; then
    printf 'skip   %-42s (already a symlink)\n' "$dst"
    return
  elif [ -e "$dst" ]; then
    mkdir -p "$BACKUP_DIR"
    mv "$dst" "$BACKUP_DIR/"
    printf 'backup %-42s -> %s\n' "$dst" "$BACKUP_DIR/"
  fi

  dst_dir="$(dirname "$dst")"
  mkdir -p "$dst_dir"
  if command -v realpath >/dev/null 2>&1; then
    rel="$(realpath --relative-to="$dst_dir" "$src")"
    ln -s "$rel" "$dst"
    printf 'linked %-42s [rel] -> %s\n' "$dst" "$rel"
  else
    ln -s "$src" "$dst"
    printf 'linked %-42s -> %s\n' "$dst" "$src"
  fi
}

echo "== river-classic config =="
link "$HERE/config/river" "$HOME/.config/river"
link "$HERE/config/waybar" "$HOME/.config/waybar"
link "$HERE/config/foot" "$HOME/.config/foot"
link "$HERE/config/dunst" "$HOME/.config/dunst"
link "$HERE/config/gtklock" "$HOME/.config/gtklock"

# shared kanata config (the same file the other Linux machines use)
if command -v kanata >/dev/null 2>&1 && [ -f "$HERE/../kanata.kbd" ]; then
  link "$HERE/../kanata.kbd" "$HOME/.config/kanata/kanata.kbd"
else
  echo "note   kanata not installed or ../kanata.kbd missing; skipping keyboard remap config"
fi

# wallpaper: keep a copy in a stable location (the init looks there first)
mkdir -p "$HOME/.local/share/wallpapers"
if [ ! -f "$HOME/.local/share/wallpapers/river-classic.jpg" ]; then
  cp "$HERE/assets/wallpaper.jpg" "$HOME/.local/share/wallpapers/river-classic.jpg"
  echo "copy   wallpaper -> ~/.local/share/wallpapers/river-classic.jpg"
fi

# the init is executed by river and the gesture daemon is spawned from it
chmod +x "$HERE/config/river/init" "$HERE/config/river/"*.sh "$HERE/config/river/"*.py 2>/dev/null || true

echo
echo "Done. Log out and pick 'river-classic' in the GDM gear menu."
