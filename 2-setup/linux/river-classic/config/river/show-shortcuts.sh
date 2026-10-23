#!/bin/sh
# Open the complete river-classic cheat sheet in a terminal.
# Bound to Super+F1 and Super+Shift+Slash in init.
#
# `show-shortcuts.sh --print` prints the same content to stdout (used by the
# tests and by anyone who wants the list in their current shell).
export PATH="$HOME/.local/bin:$PATH"

self=$(readlink -f "$0" 2>/dev/null || printf '%s\n' "$0")
here=$(dirname "$self")
file="$here/SHORTCUTS.md"
[ -f "$file" ] || file="$HOME/.config/river/SHORTCUTS.md"

if [ ! -f "$file" ]; then
    printf 'shortcuts: missing %s\n' "$file" >&2
    notify-send -u critical "Shortcuts" "Missing $file" 2>/dev/null || true
    exit 1
fi

if [ "${1:-}" = "--print" ]; then
    exec cat "$file"
fi

if command -v foot >/dev/null 2>&1; then
    if command -v less >/dev/null 2>&1; then
        exec foot -e less -R "$file"
    fi
    exec foot -e cat "$file"
fi

if command -v less >/dev/null 2>&1; then
    exec less -R "$file"
fi
exec cat "$file"
