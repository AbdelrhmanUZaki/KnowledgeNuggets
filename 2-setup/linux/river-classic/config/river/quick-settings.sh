#!/bin/sh
# The System Menu entry point (GNOME parity).
# Primary surface = the GTK quick-settings panel (system-panel.py):
# toggle tiles, live sliders, session actions — a real popover, not a dmenu.
# If the panel cannot start, fall back to the dmenu version.
export PATH="$HOME/.local/bin:$PATH"

PANEL="$HOME/.config/river/system-panel.py"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$STATE_DIR" 2>/dev/null
ERR="$STATE_DIR/panel-err.log"

if command -v python3 >/dev/null 2>&1 && [ -f "$PANEL" ]; then
    MARKER="$STATE_DIR/panel-started"
    rm -f "$MARKER"
    python3 "$PANEL" 2>"$ERR"
    # The panel writes the marker once it is mapped, so a non-zero exit after
    # that is a close/kill, not a startup failure — falling back then would
    # pop a dmenu every time the panel is dismissed.
    [ -f "$MARKER" ] && exit 0
fi

exec "$HOME/.config/river/quick-settings-dmenu.sh"
