#!/bin/sh
# GNOME-style wifi picker for river-classic (fuzzel dmenu + nmcli)
export PATH="$HOME/.local/bin:$PATH"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$STATE_DIR" 2>/dev/null
CHOOSE_FILE="$STATE_DIR/wifi-chosen"

dev=$(nmcli -t -f DEVICE,TYPE device status 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}')
[ -n "$dev" ] || exit 0

menu() {
    nmcli radio wifi | grep -q enabled || { nmcli radio wifi on 2>/dev/null; sleep 2; }
    list=$(nmcli -t -f IN-USE,SSID,SIGNAL device wifi list ifname $dev 2>/dev/null)
    [ -n "$list" ] || list=$(nmcli -t -f IN-USE,SSID,SIGNAL device wifi list ifname $dev 2>/dev/null)
    printf '🔗  manage connections…\n'
    printf '%s\n' "$list" | awk -F: '$2!="" {
        mark = ($1=="*") ? "✓ " : "  "
        printf "%3d%%\t%s%s\n", $3, mark, $2
    }' | sort -rn
}

choice=$(menu | fuzzel --dmenu --prompt='wifi> ' --cache=/dev/null) || exit 0
[ -n "$choice" ] || exit 0

case "$choice" in
    🔗*|*manage*)
        nm-connection-editor &
        ;;
    *)
        ssid=$(printf '%s' "$choice" | cut -f2 | sed 's/^✓ *//')
        if nmcli device wifi connect "$ssid" >/dev/null 2>&1; then
            notify-send "WiFi ✅" "connected: $ssid" 2>/dev/null
        else
            echo "$ssid" > "$CHOOSE_FILE"
            foot -e "$HOME/.config/river/wifi-connect.sh" &
        fi
        ;;
esac
