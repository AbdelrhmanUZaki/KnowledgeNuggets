#!/bin/sh
# GNU-style screenshots: no args = select region, arg "full" = whole screen
mkdir -p "$HOME/Pictures/Screenshots"
f="$HOME/Pictures/Screenshots/shot-$(date +%Y%m%d-%H%M%S).png"
case "$1" in
    full) grim "$f" ;;
    *)    region=$(slurp 2>/dev/null) || exit 0
          [ -n "$region" ] || exit 0
          grim -g "$region" "$f" ;;
esac
[ -f "$f" ] || exit 0
command -v wl-copy >/dev/null 2>&1 && wl-copy < "$f" 2>/dev/null
