#!/bin/sh
# Keep the CopyQ server alive in the background - HIDDEN.
#
# Why: the CopyQ server has been observed to exit silently mid-session (no
# crash log, no OOM).  Without this loop, only the next Super+V restarts it
# (a "cold" popup).  With the keepalive, the server is back within ~15 s of
# dying and the popup stays warm.
#
# IMPORTANT: a bare `copyq --start-server` (no command) LAUNCHES THE APP WITH
# ITS MAIN WINDOW VISIBLE - restarting that way made the window pop up every
# keepalive cycle.  `--start-server count` starts the exact same server
# headless (count is a no-op that prints the item count).
#
# Idempotent: exits if another instance already runs.  Started from init,
# killed by session-cleanup.sh; PID file in $STATE_DIR.
# RIVER_COPYQ_KEEPALIVE_SECS overrides the check interval (default 15 s).
set -u

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
PIDFILE="$STATE_DIR/copyq-keepalive.pid"
COPYQ="$HOME/.local/bin/copyq"
INTERVAL="${RIVER_COPYQ_KEEPALIVE_SECS:-15}"

[ -x "$COPYQ" ] || exit 0
mkdir -p "$STATE_DIR"

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

# Single instance.
if [ -f "$PIDFILE" ]; then
    OLD=$(cat "$PIDFILE" 2>/dev/null)
    [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null && exit 0
fi
echo $$ >"$PIDFILE"
trap 'rm -f "$PIDFILE"; exit 0' TERM INT HUP

probe() { "$COPYQ" count >/dev/null 2>&1; }

restart_server() {
    # count = headless start; a bare --start-server would show the window.
    setsid -f "$COPYQ" --start-server count >/dev/null 2>&1
    i=0
    until probe; do
        i=$((i + 1))
        [ "$i" -ge 40 ] && return 1
        sleep 0.25
    done
    echo "$(date '+%F %T') keepalive: restarted CopyQ server (headless)"
}

while :; do
    probe || restart_server
    sleep "$INTERVAL" &
    wait $!
done
