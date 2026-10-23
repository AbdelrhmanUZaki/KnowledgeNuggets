#!/bin/sh
# Stop river-classic-only processes after the compositor exits.
#
# Started by init twice: once through `systemd-run --user` (outside the
# session-*.scope cgroup) and once as a session-scope copy.  logind runs with
# KillUserProcesses=false here, so a session child (kanata, gestures.py,
# waybar, ...) is not guaranteed to die at logout.  In particular, a surviving
# kanata/gesture process would keep an evdev/uinput grab into GDM or GNOME,
# which is exactly the failure this script exists to prevent.
#
# It also stops the user portals.  river does not run graphical-session.target,
# so the portal units are not stopped by river's logout; left alone, a later
# GNOME login can inherit river's XDG_CURRENT_DESKTOP/GTK or WLR backend.  Once
# stopped, GNOME activates the portal chain again with its own environment.
#
# Usage: session-cleanup.sh RIVER_PID
set -u

# The session-scope copy is a background job of init.  Logging out can send
# SIGHUP through the old terminal/session; ignoring it lets the watcher reach
# the compositor-exit cleanup instead of dying first.  The systemd-run copy is
# unaffected.  (TERM from an actual user-manager stop is handled by the other
# copy if the session scope is still alive.)
trap '' HUP

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

RIVER_PID="${1:-}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
LOG="$STATE_DIR/session-cleanup.log"
mkdir -p "$STATE_DIR"

log() {
    printf '%s %s\n' "$(date '+%F %T')" "$*" >>"$LOG"
}

if [ -z "$RIVER_PID" ]; then
    log "no river PID supplied; refusing to run cleanup"
    exit 1
fi

if [ "$(cat "/proc/$RIVER_PID/comm" 2>/dev/null || true)" != "river" ]; then
    log "PID $RIVER_PID is not river; refusing to run cleanup"
    exit 1
fi

log "watching river pid $RIVER_PID"

# A zombie is not a live compositor.  This also protects against the historic
# $PPID-is-a-shell-wrapper bug.
while [ -r "/proc/$RIVER_PID/stat" ]; do
    state=$(awk '{ print $3 }' "/proc/$RIVER_PID/stat" 2>/dev/null || true)
    case "$state" in
        Z|X) break ;;
    esac
    sleep 1
done

# Give Wayland clients a moment to notice that the compositor disappeared and
# exit on their own before we force the stragglers.
sleep 1

# Do not touch a newly-started river session (for example if a user logs back
# in immediately).  A new compositor will have started its own components.
new_river=$(pgrep -n -x river 2>/dev/null || true)
if [ -n "$new_river" ] && [ "$new_river" != "$RIVER_PID" ]; then
    log "new river pid $new_river is running; leaving new session alone"
    exit 0
fi

log "compositor exited; cleaning river-classic processes"

# Kill the launcher loops first so they cannot restart their children.
pkill -f "$HOME/.config/river/init" 2>/dev/null || true
pkill -f "$HOME/.config/river/gestures.py" 2>/dev/null || true

# Input grabs and session daemons.  These are river-specific; GNOME does not
# use any of them.
pkill -x kanata 2>/dev/null || true
pkill -x waybar 2>/dev/null || true
pkill -x swaybg 2>/dev/null || true
pkill -x dunst 2>/dev/null || true
pkill -x rivertile 2>/dev/null || true
# A locker is an ext-session-lock client; it must not survive into GDM/GNOME.
pkill -x swaylock 2>/dev/null || true
pkill -x gtklock 2>/dev/null || true

# CopyQ's server can be detached from init.  Ask it to exit first (so it can
# flush history), then make sure the server is gone.
if [ -x "$HOME/.local/bin/copyq" ] &&
   { pgrep -x copyq >/dev/null 2>&1 || pgrep -x CopyQ >/dev/null 2>&1; }; then
    timeout 2 "$HOME/.local/bin/copyq" exit >/dev/null 2>&1 || true
fi
pkill -x copyq 2>/dev/null || true
pkill -x CopyQ 2>/dev/null || true

# Second pass: an input grab must never survive into GDM/GNOME.  TERM is enough
# for the normal case, but a stuck kanata/gesture process is exactly the failure
# this script exists to prevent, so make sure they are really gone.  Re-check
# for a new river first; a fast relogin owns its own processes.
sleep 1
new_river=$(pgrep -n -x river 2>/dev/null || true)
if [ -n "$new_river" ] && [ "$new_river" != "$RIVER_PID" ]; then
    log "new river pid $new_river is running; skipping force-kill pass"
    exit 0
fi
pkill -9 -f "$HOME/.config/river/init" 2>/dev/null || true
pkill -9 -f "$HOME/.config/river/gestures.py" 2>/dev/null || true
for name in kanata waybar swaybg dunst rivertile swaylock gtklock; do
    pkill -9 -x "$name" 2>/dev/null || true
done
pkill -9 -x copyq 2>/dev/null || true
pkill -9 -x CopyQ 2>/dev/null || true

# Portals are user services, so river's session teardown does not stop them.
# Stop the frontend and every installed backend; the next graphical session
# activates what it needs with its own environment.  Do not unset the user
# manager environment here: a fast GDM login could race and remove GNOME's
# fresh values before gnome-session imports them.
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user stop \
        xdg-desktop-portal.service \
        xdg-desktop-portal-gtk.service \
        xdg-desktop-portal-wlr.service \
        xdg-desktop-portal-gnome.service \
        >/dev/null 2>&1 || true
fi

log "cleanup complete"
