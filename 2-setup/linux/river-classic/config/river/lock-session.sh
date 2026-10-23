#!/bin/sh
# The one and only way to lock a river-classic session.
#
# Why a wrapper instead of a bare `swaylock`:
#
#   * swaylock reads the password from its controlling terminal.  Started from
#     a GUI keybinding, the panel or a dmenu it has no tty, so it either exits
#     immediately (river then unlocks) or sits on its default solid background
#     with no way to type the password.  `foot -e` gives it a real pty; the
#     foot window is covered by the lock surface.
#   * The old `swaylock -f` calls in power-menu.sh / quick-settings-dmenu.sh
#     were exactly that broken path.  `-f` detaches from the terminal, which is
#     the opposite of what we need.
#   * The default swaylock background is a solid colour.  We pass the same
#     wallpaper as the session so the lock screen looks intentional.
#   * gtklock (if installed) is the nicer option: a GTK/PAM unlock form, no tty
#     required.  This wrapper picks it automatically.  Force the old locker with
#     RIVER_LOCKER=swaylock.
#
# River has a matching patch (patches/river-session-lock-release-on-client-death.patch)
# that releases the session if the locker dies, so a crash cannot leave the
# compositor stuck in the locked state.
export PATH="$HOME/.local/bin:$PATH"

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$STATE_DIR" 2>/dev/null

log() {
    printf '%s %s\n' "$(date '+%F %T')" "$*" >>"$STATE_DIR/lock.log" 2>/dev/null || true
}

wallpaper() {
    w="${RIVER_WALLPAPER:-}"
    [ -n "$w" ] || w="$HOME/.local/share/wallpapers/river-classic.jpg"
    [ -f "$w" ] || w="$HOME/Github/KnowledgeNuggets/2-setup/linux/river-classic/assets/wallpaper.jpg"
    [ -f "$w" ] && printf '%s\n' "$w"
}

# Keep the previous lock attempt discoverable: a future "it broke again" can be
# matched to the panel, a dmenu or the keybinding instead of guessing.
caller=$(tr '\0' ' ' <"/proc/$PPID/cmdline" 2>/dev/null || true)
log "lock requested by ${caller:-pid $PPID}"

# A locker is already up: never stack two ext-session-lock clients.  The second
# one would be denied by river, or (worse) fight the first for the surface.
if pgrep -x gtklock >/dev/null 2>&1 || pgrep -x swaylock >/dev/null 2>&1; then
    log "a locker is already running; not stacking another"
    exit 0
fi

LOCKER="${RIVER_LOCKER:-auto}"
if [ "$LOCKER" = auto ] && command -v gtklock >/dev/null 2>&1; then
    LOCKER=gtklock
fi

if [ "$LOCKER" = gtklock ]; then
    if command -v gtklock >/dev/null 2>&1; then
        set -- gtklock
        w=$(wallpaper)
        [ -n "$w" ] && set -- "$@" --background "$w"
        # Adwaita-dark is part of GTK3 on Ubuntu; gtklock ignores an unknown
        # theme rather than failing, so this is safe everywhere.
        set -- "$@" --gtk-theme Adwaita-dark
        log "locking with gtklock (background: ${w:-none})"
        exec "$@"
    fi
    log "RIVER_LOCKER=gtklock but gtklock is not installed; falling back to swaylock"
fi

if ! command -v swaylock >/dev/null 2>&1; then
    log "no locker installed (need gtklock or swaylock)"
    notify-send -u critical "Lock failed" "Install gtklock or swaylock." 2>/dev/null || true
    exit 1
fi

set -- swaylock
w=$(wallpaper)
if [ -n "$w" ]; then
    set -- "$@" -i "$w" -s fill
else
    # No wallpaper installed: use the session's dark surface instead of
    # swaylock's default light grey.
    set -- "$@" -c 1e1e2e
fi

# foot gives swaylock the pty it needs for PAM.  The window is behind the lock
# surface and is closed when swaylock exits.
if command -v foot >/dev/null 2>&1; then
    log "locking with swaylock via foot (image: ${w:-solid colour})"
    exec foot -e "$@"
fi

# Last resort for a session without foot: `script` also allocates a pty, but it
# has no visible terminal window.  Quote the wallpaper path; it normally has no
# spaces, but the repo path is user-controlled.
if command -v script >/dev/null 2>&1; then
    log "locking with swaylock via script pty (foot not installed)"
    if [ -n "$w" ]; then
        exec script -qec "swaylock -i '$w' -s fill" /dev/null
    fi
    exec script -qec "swaylock -c 1e1e2e" /dev/null
fi

# No pty helper at all.  Bare swaylock can lock, but cannot read a password;
# river's patch will release the session if it exits.  Do not pretend this is
# supported: log it so the next debugging session has the evidence.
log "no foot or script available; starting swaylock without a pty"
exec "$@"
