#!/bin/sh
# Leave the *logical* session in place and hand the seat to a fresh GDM greeter
# so the user can log in as someone else without closing their apps.
#
# Used by the gtklock powerbar's Switch User button via
# `[powerbar] userswitch-command` in ~/.config/gtklock/config.ini.
#
# The invasive part is not GDM — the greeter is fine.  The invasive part is
# that river-classic's kanata and gestures.py hold a *global* evdev grab; if
# they stay alive while we leave the session, the greeter (or the session
# behind it) gets a dead keyboard/touchpad.  So the switch pauses them first
# and only asks GDM to take the seat when we actually own clean input.
#
# The reverse direction is symmetric and needs nothing here: when the user
# returns to this river session, river shows the same gtklock form, and on
# *unlock* gtklock runs "input-session.sh resume" (unpatched: the
# `[main] unlock-command` in that config uses the same $HOME pattern).
#
# Usage: switch-user.sh
# (called with no arguments — the powerbar spawns it)
set -u

STATE_DIR="${RIVER_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/river-classic}"
INPUT_SESSION="${RIVER_INPUT_SESSION:-$HOME/.config/river/input-session.sh}"
GDBUS="${RIVER_GDBUS:-gdbus}"
NOTIFY="${RIVER_NOTIFY:-notify-send}"
GDM_DEST="org.gnome.DisplayManager"
GDM_OBJ=/org/gnome/DisplayManager/LocalDisplayFactory
GDM_IFACE=org.gnome.DisplayManager.LocalDisplayFactory
GDM_METHOD=CreateTransientDisplay

LOG="$STATE_DIR/switch-user.log"
mkdir -p "$STATE_DIR" 2>/dev/null

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >>"$LOG" 2>/dev/null || true; }

fail() {
    log "$*"
    "$NOTIFY" -u critical "Switch user failed" "$*" 2>/dev/null || true
    return 0
}

# One shot guard so a double-click on the powerbar cannot run the switch
# against itself.
LOCK="$STATE_DIR/switch-user.lock"
(
    flock -n 9 2>/dev/null || exit 1

    if [ ! -x "$INPUT_SESSION" ]; then
        fail "input-session.sh is not executable at $INPUT_SESSION"
        exit 1
    fi

    log "switch: releasing input grabs (kanata + gestures.py)"
    if ! "$INPUT_SESSION" pause; then
        log "switch: input pause failed; not calling GDM"
        "$NOTIFY" -u critical "Switch user failed" \
            "Could not release keyboard/touchpad grabs; session left locked." \
            2>/dev/null || true
        exit 1
    fi

    log "switch: calling GDM $GDM_METHOD"
    out=$("$GDBUS" call --system \
        --dest "$GDM_DEST" \
        --object-path "$GDM_OBJ" \
        --method "$GDM_IFACE.$GDM_METHOD" 2>&1)
    rc=$?
    if [ "$rc" -ne 0 ]; then
        log "switch: GDM call failed (rc=$rc): $out"
        "$NOTIFY" -u critical "Switch user failed" \
            "GDM did not take the seat; input restored, session still locked." \
            2>/dev/null || true
        "$INPUT_SESSION" resume || true
        exit 1
    fi
    log "switch: GDM accepted the switch ($out); input stays paused until unlock"
    exit 0
) 9>>"$LOCK"
