#!/bin/sh
# Quick clipboard popup: the last N CopyQ items at the mouse cursor, with
# type-to-search.  Selecting an item copies it and closes the menu; paste with
# Ctrl+V in the target app (CopyQ cannot inject the paste itself under
# river/Wayland - it cannot identify the target window).
#
# Use Super+Shift+V for the full CopyQ window (images, pins, editing, tabs).
#
# The CopyQ server occasionally dies silently in this session; --start-server
# below makes every invocation self-healing.  A fresh server start restores
# the main window, so it is hidden again before the menu opens.
# RIVER_CLIPBOARD_ITEMS overrides the number of entries shown (default 12).
set -u

COUNT="${RIVER_CLIPBOARD_ITEMS:-12}"
COPYQ="$HOME/.local/bin/copyq"

if [ ! -x "$COPYQ" ]; then
    echo "clipboard-menu: $COPYQ missing" >&2
    exit 0
fi

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

# Start the server if it is down.  Detach with setsid so the server survives
# even when this wrapper is started from a short-lived shell.
if ! "$COPYQ" count >/dev/null 2>&1; then
    setsid -f "$COPYQ" --start-server >/dev/null 2>&1
    i=0
    until "$COPYQ" count >/dev/null 2>&1; do
        i=$((i + 1))
        [ "$i" -ge 40 ] && exit 0
        sleep 0.25
    done
    # A freshly started server restores the main window - hide it again.
    "$COPYQ" hide >/dev/null 2>&1
fi

exec "$COPYQ" eval "menu(\"&clipboard\", $COUNT)"
