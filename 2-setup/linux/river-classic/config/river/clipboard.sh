#!/bin/sh
# Clipboard history for river-classic (cliphist + fuzzel).
#
#   pick   — choose from the recent text entries, put it back on the clipboard
#   clear  — wipe the history and the current selection
#
# The session init starts the recorder:
#   wl-paste --type text --watch cliphist store
# Text only on purpose: screenshots are already saved in ~/Pictures and would
# otherwise fill the database with binary blobs.
set -eu

pick() {
    # newest first; cap the menu so a long history stays fast
    sel=$(cliphist list | head -n 200 | fuzzel --dmenu --prompt "clipboard  ") || exit 0
    [ -n "$sel" ] || exit 0
    printf '%s\n' "$sel" | cliphist decode | wl-copy
}

case "${1:-pick}" in
    pick) pick ;;
    clear)
        cliphist wipe
        wl-copy --clear 2>/dev/null || true
        ;;
    *)
        echo "usage: clipboard.sh [pick|clear]" >&2
        exit 2
        ;;
esac
