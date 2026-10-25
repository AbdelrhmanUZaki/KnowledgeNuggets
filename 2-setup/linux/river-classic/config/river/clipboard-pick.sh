#!/bin/sh
# Super+V clipboard popup: cliphist history, fuzzy-searched with fuzzel.
#
# Text and images.  Picking an item copies it back to the clipboard
# (wl-copy then holds the selection in the background, so it also survives
# this script and the source app exiting).  Paste in the target app with
# Ctrl+V - Wayland compositors cannot inject the paste for us.
#
# The full CopyQ manager stays available on Super+Shift+V (pins, editing,
# image previews); nothing CopyQ runs in the background anymore.
set -u

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
