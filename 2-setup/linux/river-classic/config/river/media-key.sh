#!/bin/sh
# Sends media commands to the first active MPRIS player (no playerctl needed)
case "$1" in
    playpause|next|previous|stop) ;;
    *) exit 0 ;;
esac
player=$(dbus-send --session --print-reply --dest=org.freedesktop.DBus \
    /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>/dev/null \
    | grep -o 'org\.mpris\.MediaPlayer2\.[A-Za-z0-9_.-]*' | head -1)
[ -n "$player" ] || exit 0
dbus-send --session --print-reply --dest="$player" /org/mpris/MediaPlayer2 \
    "org.mpris.MediaPlayer2.Player.$1" >/dev/null 2>&1
