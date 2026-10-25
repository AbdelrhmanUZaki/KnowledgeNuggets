#!/bin/sh
# Super+V clipboard popup: cliphist history, fuzzy/substring search.
#
# Prefers the GTK4 picker (config/river/clipboard-preview.py), which shows a
# real thumbnail for image entries; falls back to the plain fuzzel text
# picker if GTK4/PyGObject is unavailable.  Both copy the picked entry back
# to the clipboard with wl-copy (which forks and holds the selection).
# Paste with Ctrl+V - Wayland compositors cannot inject the paste for us.
#
# The full CopyQ manager stays available on Super+Shift+V (pins, editing);
# nothing CopyQ runs in the background.
set -u

DIR=${0%/*}

if command -v python3 >/dev/null 2>&1 && [ -r "$DIR/clipboard-preview.py" ]; then
    python3 "$DIR/clipboard-preview.py" && exit 0
    # GTK4 missing or the picker crashed: fall through to fuzzel.
fi

SEL=$(cliphist list 2>/dev/null | fuzzel --dmenu -p ' 📋 ' -l 14)
[ -n "$SEL" ] || exit 0

# Image entries carry "binary data ... png" in their list line; decode
# yields raw PNG bytes, so tell wl-copy the type (it cannot sniff stdin).
case "$SEL" in
    *'binary data'*)
        printf '%s\n' "$SEL" | cliphist decode | wl-copy -t image/png
        ;;
    *)
        printf '%s\n' "$SEL" | cliphist decode | wl-copy
        ;;
esac
