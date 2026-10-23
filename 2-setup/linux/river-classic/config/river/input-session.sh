#!/bin/sh
# Manage river-classic's two evdev grabbers: kanata + gestures.py.
#
# Why this exists:
#
#   * Switch User on the gtklock powerbar must *release* the keyboard and
#     touchpad grabs before GDM takes the seat, or the greeter (or the next
#     user's session) gets dead input.  Both daemons hold a global grab for
#     as long as they run: kanata EVIOCGRABs the physical keyboard, and
#     gestures.py mirrors the touchpad.  init used to own both as inline
#     `while river_alive` loops that could not be paused without killing the
#     respawn bookkeeping together with the child.
#   * The pause has to be *reversible*: the same session must come back with
#     its own daemons when the user unlocks.  So the managed supervisor keeps
#     running while paused, gated by a flag file.
#
# Subcommands:
#
#   start [river_pid]  idempotent — spawn the managers/grabbers that are not
#                      already running and return 0 when they are alive.
#   pause              release the grabs and mark the session as paused.
#                      Idempotent; never kills the managed supervisor.
#   resume             undo pause and re-spawn anything that is missing.
#   status             print the current state (for docs / debugging).
#
# State, all in $STATE_DIR (= ~/.local/state/river-classic):
#
#   input-paused                exists exactly while the grabs stay released
#   input-kanata-gave-up        kanata failed to start earlier this session
#   input-gestures-gave-up      gestures.py exited 3 (no permission/uinput)
#   input-kanata.pid            pid of the running kanata
#   input-supervisor.pid        pid of the managed gesture supervisor
#   input-session.lock          flock inode serialising spawn/pause decisions
#   input-session.log           this script's own log
#
# Race safety: spawn decisions and the pause critical section share one flock,
# and every decision re-checks the pause flag *inside* its critical section.
# A supervisor that just decided to spawn a grabber cannot resurrect a process
# that `pause` is killing: pause takes the same lock first.
set -u

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
PAUSE_FLAG="$STATE_DIR/input-paused"
KANATA_GAVE_UP="$STATE_DIR/input-kanata-gave-up"
GESTURES_GAVE_UP="$STATE_DIR/input-gestures-gave-up"
KANATA_PIDFILE="$STATE_DIR/input-kanata.pid"
SUPERVISOR_PIDFILE="$STATE_DIR/input-supervisor.pid"
LOCK="$STATE_DIR/input-session.lock"

KANATA_CFG="$HOME/.config/kanata/kanata.kbd"
GESTURES="$HOME/.config/river/gestures.py"
LOG="$STATE_DIR/input-session.log"
KANATA_LOG="$STATE_DIR/kanata.log"
GESTURES_LOG="$STATE_DIR/gestures.log"

cmd="" river_pid_arg=""

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >>"$LOG" 2>/dev/null || true; }

# river-alive.  A supplied pid (init always passes $RIVER_PID) wins; otherwise
# fall back to "any live river process", which is what the old init loop did.
river_alive() {
    if [ -n "$river_pid_arg" ] && [ -d "/proc/$river_pid_arg" ]; then
        return 0
    fi
    [ -n "$(pgrep -n -x river 2>/dev/null)" ]
}

pid_of_file() {
    p=$(cat "$1" 2>/dev/null || true)
    case "$p" in *[!0-9]*|"") return 1 ;; esac
    [ -d "/proc/$p" ] || return 1
    printf '%s\n' "$p"
}

# ------------------------------------------------------------------ kanata --
# The old init's `if ! pgrep -x kanata; then kanata ... &` block, plus:
#   * pause-gated spawn,
#   * a once-per-session probe so a kanata that dies instantly (broken udev
#     rule, bad config) does not get respawned in a tight loop.
kanata_once() {
    (
        flock -x 9 2>/dev/null
        if [ -e "$PAUSE_FLAG" ] || [ -e "$KANATA_GAVE_UP" ] || ! river_alive; then
            exit 0
        fi
        if pid_of_file "$KANATA_PIDFILE" >/dev/null 2>&1; then
            exit 0
        fi
        if pgrep -x kanata >/dev/null 2>&1; then
            pgrep -x kanata >"$KANATA_PIDFILE"
            exit 0 # running; spawned before this script owned it
        fi
        if ! command -v kanata >/dev/null 2>&1 || [ ! -f "$KANATA_CFG" ]; then
            touch "$KANATA_GAVE_UP"
            log "kanata unavailable (binary/$KANATA_CFG missing); no respawn"
            exit 0
        fi
        kanata --cfg "$KANATA_CFG" >>"$KANATA_LOG" 2>&1 9>&- &
        kp=$!
        echo "$kp" >"$KANATA_PIDFILE"
        sleep 1
        if [ -d "/proc/$kp" ]; then
            log "started kanata (pid $kp)"
        else
            touch "$KANATA_GAVE_UP"
            rm -f "$KANATA_PIDFILE"
            log "kanata exited immediately (pid $kp); gave up until relogin"
        fi
    ) >>"$LOG" 2>&1 9>>"$LOCK"
}

# ---------------------------------------------------------------- gestures --
# The old init's `while river_alive` respawn loop, kept in shape but now:
#   * pause-gated via the flag at the top of every pass,
#   * tracked in $SUPERVISOR_PIDFILE so pause/resume can find it,
#   * `exit 3` (no permission/uinput) sets a gave-up file instead of just
#     stopping the loop — same outcome, but `status` can say why.
# The rc-driven semantics come from running gestures.py as a foreground child
# of the supervisor, exactly like the inline version did.
gestures_loop() {
    (
        trap 'rm -f "$SUPERVISOR_PIDFILE"; exit 0' INT TERM HUP
        while river_alive; do
            if [ -e "$PAUSE_FLAG" ] || [ -e "$GESTURES_GAVE_UP" ]; then
                sleep 2
                continue
            fi
            # Run gestures.py for as long as it lives; rc drives the retry.
            rp=$(pgrep -n -x river 2>/dev/null)
            if [ -z "$rp" ]; then
                sleep 2
                continue
            fi
            "$GESTURES" --parent "$rp" >>"$GESTURES_LOG" 2>&1
            rc=$?
            river_alive || break
            case "$rc" in
                0|130|141|143)            # clean exit, ^C, SIGPIPE, SIGTERM
                    sleep 2 ;;
                3)
                    touch "$GESTURES_GAVE_UP"
                    log "gestures.py rc=3 (no permission/uinput); no respawn"
                    sleep 2 ;;
                4)
                    sleep 5 ;;
                *)
                    sleep 2 ;;
            esac
        done
        rm -f "$SUPERVISOR_PIDFILE"
        log "river exited; gesture supervisor stopped"
    ) >>"$LOG" 2>&1 9>&- &
}

# ------------------------------------------------------------------- verbs --

do_start() {
    # Verify river is actually alive; otherwise there is nothing to manage.
    if ! river_alive; then
        log "start: no live river process"
        return 1
    fi

    (
        flock -x 9 2>/dev/null
        if pid_of_file "$SUPERVISOR_PIDFILE" >/dev/null 2>&1; then
            exit 0 # supervisor already running
        fi
        # A managed supervisor has never run for this river session (or died).
        # Fresh state: no pause flag, no gave-up markers.  Old orphan files
        # from any previous session of this user are stale and go away.
        rm -f "$PAUSE_FLAG" "$KANATA_GAVE_UP" "$GESTURES_GAVE_UP" \
              "$KANATA_PIDFILE" "$SUPERVISOR_PIDFILE"
            gestures_loop
        echo "$!" >"$SUPERVISOR_PIDFILE"
        log "started gesture supervisor (pid $!, river $river_pid_arg)"
    ) 9>>"$LOCK"
    # kanata is spawned by this run (the supervisor only manages gestures.py
    # so the pause response stays immediate).
    kanata_once
    return 0
}

do_pause() {
    (
        flock -x 9 2>/dev/null
        # 1) Flag FIRST, so a managed supervisor cannot respawn behind us.
        touch "$PAUSE_FLAG"
        # 2) A legacy inline supervisor (the pre-input-session.sh init) does
        #    not know about the flag: if it owns a live gestures.py it would
        #    instantly respawn the one we're about to kill.  Its subshell's
        #    argv contains river/init AND is the direct parent of that
        #    gesture — narrow enough never to touch the init shell itself.
        for g in $(pgrep -u "$(id -u)" -f "$GESTURES" 2>/dev/null); do
            pp=$(awk '/^PPid:/{print $2}' "/proc/$g/status" 2>/dev/null)
            if [ -n "$pp" ] &&
               tr '\0' ' ' <"/proc/$pp/cmdline" 2>/dev/null | grep -q 'river/init'; then
                kill "$pp" 2>/dev/null || true
                log "killed legacy gesture supervisor (pid $pp)"
            fi
        done
        # 3) The grabbers themselves.  TERM first.
        pkill -u "$(id -u)" -f "$GESTURES" 2>/dev/null || true
        pkill -x kanata 2>/dev/null || true
        rm -f "$KANATA_PIDFILE"
    ) 9>>"$LOCK"
    # Give the grabs a moment to be released; fail loudly if they aren't.
    i=0
    while [ "$i" -lt 25 ]; do
        if ! pgrep -u "$(id -u)" -f "$GESTURES" >/dev/null 2>&1 &&
           ! pgrep -x kanata >/dev/null 2>&1; then
            log "pause: grabs released"
            return 0
        fi
        sleep 0.2
        i=$((i + 1))
    done
    log "pause: grabber survived the TERM pass; forcing"
    pkill -9 -u "$(id -u)" -f "$GESTURES" 2>/dev/null || true
    pkill -9 -x kanata 2>/dev/null || true
    sleep 0.2
    if pgrep -u "$(id -u)" -f "$GESTURES" >/dev/null 2>&1 ||
       pgrep -x kanata >/dev/null 2>&1; then
        log "pause: FAILED — a grabber is still running"
        return 1
    fi
    log "pause: grabs released (forced)"
    return 0
}

do_resume() {
    (
        flock -x 9 2>/dev/null
        if [ -e "$PAUSE_FLAG" ]; then
            rm -f "$PAUSE_FLAG"
            log "pause flag removed"
        fi
    ) 9>>"$LOCK"
    do_start "$river_pid_arg"
}

do_status() {
    s=$(pid_of_file "$SUPERVISOR_PIDFILE" 2>/dev/null)
    if [ -n "$s" ]; then
        printf 'gestures supervisor running (pid %s)\n' "$s"
    else
        echo 'gestures supervisor stopped'
    fi
    if k=$(pid_of_file "$KANATA_PIDFILE" 2>/dev/null) && pgrep -x kanata >/dev/null 2>&1; then
        printf 'kanata             running (pid %s)\n' "$k"
    elif pgrep -x kanata >/dev/null 2>&1; then
        printf 'kanata             running (pid %s, unmanaged)\n' "$(pgrep -n -x kanata)"
    else
        echo 'kanata             stopped'
    fi
    if pgrep -u "$(id -u)" -f "$GESTURES" >/dev/null 2>&1; then
        printf 'gestures.py        running (%s)\n' "$(pgrep -u "$(id -u)" -f "$GESTURES" 2>/dev/null)"
    else
        echo 'gestures.py        stopped'
    fi
    [ -e "$PAUSE_FLAG" ] && echo 'paused             YES' || echo 'paused             no'
    [ -e "$KANATA_GAVE_UP" ] && echo 'kanata gave up     YES' || echo 'kanata gave up     no'
    [ -e "$GESTURES_GAVE_UP" ] && echo 'gestures gave up   YES' || echo 'gestures gave up   no'
    return 0
}

# -------------------------------------------------------------------- main --

cmd="${1:-status}"
river_pid_arg="${2:-}"

case "$cmd" in
    start)   do_start ;;
    pause)   do_pause ;;
    resume)  do_resume ;;
    status)  do_status ;;
    *)
        printf 'usage: %s {start [river_pid] | pause | resume | status}\n' "$0" >&2
        exit 2 ;;
esac
