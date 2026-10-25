#!/bin/sh
# Quick clipboard popup: the last N CopyQ items at the mouse cursor, with
# type-to-search.  Selecting an item copies it and closes the menu; paste with
# Ctrl+V in the target app (CopyQ cannot inject the paste itself under
# river/Wayland - it cannot identify the target window).
#
# Use Super+Shift+V for the full CopyQ window (images, pins, editing, tabs).
#
# ONE copyq round-trip: the eval hides the main window a fresh server start
# restores, then opens the menu.  --start-server self-heals a dead server
# (the CopyQ server has been observed to exit silently in this session);
# that cold path costs a second or two, the warm path ~0.15 s.
# RIVER_CLIPBOARD_ITEMS overrides the number of entries shown (default 12).
set -u

COUNT="${RIVER_CLIPBOARD_ITEMS:-12}"
COPYQ="$HOME/.local/bin/copyq"

if [ ! -x "$COPYQ" ]; then
    echo "clipboard-menu: $COPYQ missing" >&2
    exit 0
fi

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

exec "$COPYQ" --start-server eval "if (visible()) hide(); menu(\"&clipboard\", $COUNT)"
