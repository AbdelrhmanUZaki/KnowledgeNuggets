#!/bin/sh
# Clipboard history recorder for river-classic.
#
# Two tiny `wl-paste --watch` loops feed cliphist's plain-file database
# (~/.cache/cliphist/db): one for text, one for PNG images.  There is no
# server, no window and no state beyond that file - a watcher can be killed
# and restarted freely, and editing the picker (clipboard-pick.sh) never
# affects recording.
#
# This script is a small supervisor: it starts the watchers, re-starts any
# that die (checked every 15 s), and is idempotent itself (PID file in
# $STATE_DIR).  Started from init, killed by session-cleanup.sh.
set -u

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
PIDFILE="$STATE_DIR/clipboard-store.pid"
INTERVAL="${RIVER_CLIPBOARD_STORE_SECS:-15}"

mkdir -p "$STATE_DIR"

# Single instance.
if [ -f "$PIDFILE" ]; then
    OLD=$(cat "$PIDFILE" 2>/dev/null)
    [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null && exit 0
fi
echo $$ >"$PIDFILE"
trap 'rm -f "$PIDFILE"; exit 0' TERM INT HUP

TEXT_PID=
IMAGE_PID=

start_watcher() {
    case "$1" in
        text)  wl-paste --type text/plain --watch cliphist store >/dev/null 2>&1 & TEXT_PID=$! ;;
        image) wl-paste --type image/png   --watch cliphist store >/dev/null 2>&1 & IMAGE_PID=$! ;;
    esac
}

start_watcher text
start_watcher image

while :; do
    sleep "$INTERVAL" &
    wait $!
    [ -n "$TEXT_PID" ]  && ! kill -0 "$TEXT_PID" 2>/dev/null  && start_watcher text
    [ -n "$IMAGE_PID" ] && ! kill -0 "$IMAGE_PID" 2>/dev/null && start_watcher image
done
