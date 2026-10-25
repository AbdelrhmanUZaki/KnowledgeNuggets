#!/bin/sh
# Quick clipboard popup: the last N CopyQ items at the mouse cursor, with
# type-to-search.  Selecting an item copies it and closes the menu; paste with
# Ctrl+V in the target app (CopyQ cannot inject the paste itself under
# river/Wayland - it cannot identify the target window).
#
# Use Super+Shift+V for the full CopyQ window (images, pins, editing, tabs).
#
# Warm path (server up): one round-trip, ~0.2 s, popup only.
# Cold path (the server dies silently now and then): a fresh start restores
# the main window LATE (well after the server answers), so hiding it before
# the menu races and loses.  Instead: open the menu first (instant), then
# hide the window server-side after it settles - sleep()/hide() run while
# the popup is already up; this client just lingers a little longer.
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
    setsid -f "$COPYQ" --start-server >/dev/null 2>&1
    i=0
    until "$COPYQ" count >/dev/null 2>&1; do
        i=$((i + 1))
        [ "$i" -ge 40 ] && exit 0
        sleep 0.25
    done
    # Menu first, then keep hiding the restored window as it shows up:
    # repeat hides every ~300 ms for the first ~1.8 s (each is a no-op when
    # the window is already hidden) so the flash is a brief flicker at most.
    exec "$COPYQ" eval "menu(\"&clipboard\", $COUNT); hide(); sleep(300); hide(); sleep(300); hide(); sleep(400); hide(); sleep(500); hide(); sleep(300); hide()"
fi

exec "$COPYQ" eval "menu(\"&clipboard\", $COUNT)"
