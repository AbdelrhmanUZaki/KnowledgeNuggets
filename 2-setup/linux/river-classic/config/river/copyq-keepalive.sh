#!/bin/sh
# Keep the CopyQ server alive in the background.
#
# Why: the CopyQ server has been observed to exit silently mid-session (no
# crash log, no OOM).  Without this loop, only the next Super+V restarts it -
# a "cold" popup: slower, and a fresh server restores its main window late
# (clipboard-menu.sh hides it, but at best a flicker).  With the keepalive,
# the server is back within ~15 s of dying and the popup stays warm.
#
# The server starts HIDDEN (no window).  A fresh start restores the main
# window late, so after every restart the window is hidden repeatedly while
# the server settles (same trick clipboard-menu.sh uses).
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
    setsid -f "$COPYQ" --start-server >/dev/null 2>&1
    i=0
    until probe; do
        i=$((i + 1))
        [ "$i" -ge 40 ] && return 1
        sleep 0.25
    done
    # A fresh start restores the main window late; keep hiding it while the
    # server settles (each hide is a no-op when already hidden).
    "$COPYQ" eval "hide(); sleep(300); hide(); sleep(300); hide(); sleep(400); hide(); sleep(500); hide(); sleep(300); hide()" >/dev/null 2>&1
    echo "$(date '+%F %T') keepalive: restarted CopyQ server"
}

while :; do
    probe || restart_server
    sleep "$INTERVAL" &
    wait $!
done
