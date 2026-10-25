#!/bin/sh
# Super+N notification center: dunst's history in a GTK4 window
# (config/river/notify-center.py).  Falls back to popping the latest
# notification from history if GTK4 is unavailable.
set -u

DIR=${0%/*}

if command -v python3 >/dev/null 2>&1 && [ -r "$DIR/notify-center.py" ]; then
    exec python3 "$DIR/notify-center.py"
fi

exec dunstctl history-pop
