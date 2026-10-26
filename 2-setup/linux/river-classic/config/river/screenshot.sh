#!/bin/sh
# GNU-style screenshots: no args = select region, arg "full" = whole screen
mkdir -p "$HOME/Pictures/Screenshots"
f="$HOME/Pictures/Screenshots/shot-$(date +%Y%m%d-%H%M%S).png"
say() { # $1 = title, $2 = body
    if command -v dunstify >/dev/null 2>&1; then
        dunstify -i "$f" "$1" "$2" 2>/dev/null
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send -i "$f" "$1" "$2" 2>/dev/null
    fi
}
case "$1" in
    full) grim "$f" ;;
    *)    region=$(slurp 2>/dev/null) || exit 0
          [ -n "$region" ] || exit 0
          grim -g "$region" "$f" ;;
esac
if [ ! -f "$f" ]; then
    say "Screenshot failed" "grim could not capture the screen"
    exit 0
fi
copied=""
if command -v wl-copy >/dev/null 2>&1 && wl-copy < "$f" 2>/dev/null; then
    copied=" — copied to clipboard"
fi
say "Screenshot saved" "$(basename "$f")$copied"
