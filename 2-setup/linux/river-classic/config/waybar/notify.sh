#!/bin/sh
# waybar custom/notify — GNOME-style DND indicator:
# the bell only exists in the bar while Do Not Disturb is ON.
if dunstctl is-paused 2>/dev/null | grep -q true; then
    glyph=$(printf '\357\207\266')        # FontAwesome bell-slash (U+F1F6)
    printf '{"text":"<span font_family=%s size=%s>%s</span>","class":"dnd-on","tooltip":"Do Not Disturb is ON — click to disable"}\n' \
        "'FontAwesome'" "'115%'" "$glyph"
else
    printf '{"text":"","class":"dnd-off","tooltip":"Notifications are on"}\n'
fi
