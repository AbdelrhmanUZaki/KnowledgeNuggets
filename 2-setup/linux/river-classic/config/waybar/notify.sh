#!/bin/sh
# waybar custom/notify — bell with the dunst history count.
#
# Left-click opens the notification center (notify-center.sh), middle-click
# toggles Do-Not-Disturb, right-click opens dunst's context menu.
# The count includes notifications still being displayed - dunst only moves
# them into history when their popup closes, which would lag by ~5-10 s.
H=$(dunstctl count history 2>/dev/null)
D=$(dunstctl count displayed 2>/dev/null)
case "$H" in ''|*[!0-9]*) H=0 ;; esac
case "$D" in ''|*[!0-9]*) D=0 ;; esac
COUNT=$((H + D))

if dunstctl is-paused 2>/dev/null | grep -q true; then
    glyph=$(printf '\357\207\266')        # FontAwesome bell-slash (U+F1F6)
    printf '{"text":"<span font_family=%s size=%s>%s</span> %s","class":"dnd-on","tooltip":"Do Not Disturb is ON — %s in history. Click: history · middle: DND · right: menu"}\n' \
        "'FontAwesome'" "'115%'" "$glyph" "$COUNT" "$COUNT"
else
    glyph=$(printf '\357\203\263')        # FontAwesome bell (U+F0F3)
    printf '{"text":"<span font_family=%s size=%s>%s</span> %s","class":"dnd-off","tooltip":"%s in history — Click: history · middle: DND · right: menu"}\n' \
        "'FontAwesome'" "'115%'" "$glyph" "$COUNT" "$COUNT"
fi
