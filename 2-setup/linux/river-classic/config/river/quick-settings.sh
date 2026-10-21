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
    python3 "$PANEL" 2>"$ERR" && exit 0
    # panel failed → fall through to the dmenu
fi

exec "$HOME/.config/river/quick-settings-dmenu.sh"
