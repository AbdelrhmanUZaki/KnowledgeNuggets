#!/bin/sh
# Clipboard history + persistence for river-classic (cliphist + wl-copy).
#
#   pick        — choose a recent entry (text or image) and put it back
#   store KIND  — recorder target; KIND is "text" or "image"
#   clear       — wipe the history and the current selection
#
# The session init runs two recorders:
#   wl-paste --type text  --watch clipboard.sh store text
#   wl-paste --type image --watch clipboard.sh store image
#
# Wayland drops a selection when its source client exits.  To keep it alive the
# store path re-copies each new item through wl-copy, which takes ownership.  The
# re-copy triggers the watcher again, so the content hash is remembered and
# identical data is ignored — cliphist 0.5 does not dedupe its own re-copies and
# without the hash this loops forever.  Only the watched MIME is kept: rich text
# becomes plain text, images keep their type (wl-copy auto-detects it).
set -u

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"

store() {
    kind="${1:-data}"
    state="$STATE_DIR/cliphist-last-$kind"
    mkdir -p "$STATE_DIR"

    # text and image watchers can fire at the same time — serialize them
    exec 9>"$STATE_DIR/cliphist.lock"
    flock 9

    # clipboard cleared externally: forget the last item so the same content
    # copied again is recorded and re-owned
    if [ "${CLIPBOARD_STATE:-data}" = "clear" ]; then
        rm -f "$state"
        exit 0
    fi

    tmp=$(mktemp) || exit 1
    trap 'rm -f "$tmp"' EXIT
    cat > "$tmp"
    [ -s "$tmp" ] || exit 0

    h=$(sha256sum "$tmp" | cut -d' ' -f1)
    [ "$h" = "$(cat "$state" 2>/dev/null || true)" ] && exit 0
    printf '%s\n' "$h" > "$state"

    cliphist -max-items 200 store < "$tmp" || exit 1
    wl-copy < "$tmp" || exit 1
}

pick() {
    # newest first; cap the menu so a long history stays fast
    sel=$(cliphist list | head -n 200 | fuzzel --dmenu --prompt "clipboard  ") || exit 0
    [ -n "$sel" ] || exit 0
    printf '%s\n' "$sel" | cliphist decode | wl-copy
}

case "${1:-pick}" in
    pick) pick ;;
    store) store "${2:-data}" ;;
    clear)
        cliphist wipe
        rm -f "$STATE_DIR"/cliphist-last-*
        wl-copy --clear 2>/dev/null || true
        ;;
    *)
        echo "usage: clipboard.sh [pick|store text|store image|clear]" >&2
        exit 2
        ;;
esac
