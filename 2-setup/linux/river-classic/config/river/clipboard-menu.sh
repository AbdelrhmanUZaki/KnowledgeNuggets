#!/bin/sh
# Quick clipboard popup: the last N CopyQ items at the mouse cursor, with
# type-to-search.  Selecting an item copies it and closes the menu; paste with
# Ctrl+V in the target app (CopyQ cannot inject the paste itself under
# river/Wayland - it cannot identify the target window).
#
# Use Super+Shift+V for the full CopyQ window (images, pins, editing, tabs).
#
# Warm path (server up): one round-trip, ~0.2 s, popup only.
# Cold path (the server dies silently now and then): restart it WITHOUT a
# window - a bare `--start-server` (no command) launches the app with its
# main window visible, which is how the "popup also shows the CopyQ window"
# bug happened; `--start-server count` starts the same server headless.
# RIVER_CLIPBOARD_ITEMS overrides the number of entries shown (default 12).
set -u

COUNT="${RIVER_CLIPBOARD_ITEMS:-12}"
COPYQ="$HOME/.local/bin/copyq"

if [ ! -x "$COPYQ" ]; then
    echo "clipboard-menu: $COPYQ missing" >&2
    exit 0
fi

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

if ! "$COPYQ" count >/dev/null 2>&1; then
    setsid -f "$COPYQ" --start-server count >/dev/null 2>&1
    i=0
    until "$COPYQ" count >/dev/null 2>&1; do
        i=$((i + 1))
        [ "$i" -ge 40 ] && exit 0
        sleep 0.25
    done
fi

exec "$COPYQ" eval "menu(\"&clipboard\", $COUNT)"
