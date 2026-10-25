#!/bin/sh
# Apply the river-classic CopyQ preferences and the clipboard persistence
# command.  Idempotent: init runs this at login, and it is safe to re-run after
# editing copyq-keep.js.
#
# CopyQ 17.x is installed as ~/.local/bin/copyq by install-copyq17.sh.  Do not
# substitute Ubuntu's 13.0.0 package: it crashes when restoring large images
# under Qt 6.10/Wayland (see PROGRESS.md, entry 25).
set -u

COPYQ="$HOME/.local/bin/copyq"
if [ ! -x "$COPYQ" ]; then
    echo "copyq-setup: $COPYQ missing; run install-copyq17.sh" >&2
    exit 0
fi

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"

# Start the server and wait until it answers. --start-server alone can return
# before the server is ready, so the first config command is also the probe.
i=0
until "$COPYQ" config autostart false >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 20 ]; then
        echo "copyq-setup: server did not start" >&2
        exit 0
    fi
    # Bare `--start-server` (no command) LAUNCHES THE APP WITH ITS WINDOW
    # VISIBLE - that is how a CopyQ window appeared at login.  `count` is a
    # no-op command that starts the exact same server headless.
    "$COPYQ" --start-server count >/dev/null 2>&1
    sleep 0.25
done

# Select an item -> copy it, close the window, refocus the previous app.  The
# user pastes with Ctrl+V: Wayland has no reliable global paste injection.
# No tray icon (the bar/panel has the entry), no notification spam, no X11
# primary-selection history.
for setting in \
    "activate_pastes false" \
    "activate_closes true" \
    "activate_focuses true" \
    "disable_tray true" \
    "close_on_unfocus true" \
    "clipboard_notification_lines 0" \
    "check_clipboard true" \
    "check_selection false" \
    "autostart false" \
    "confirm_exit false"
do
    # shellcheck disable=SC2086
    set -- $setting
    "$COPYQ" config "$1" "$2" >/dev/null 2>&1 || true
done

# Install/update the automatic command that re-owns every new selection (so it
# survives the source client exiting) while preserving the useful MIME types.
if ! "$COPYQ" eval - < "$HOME/.config/river/copyq-keep.js" >/dev/null 2>&1; then
    echo "copyq-setup: failed to install copyq-keep.js" >&2
    exit 0
fi
