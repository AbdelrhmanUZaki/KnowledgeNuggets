#!/bin/sh
# The interactive password path for the wifi picker (runs inside foot)
export PATH="$HOME/.local/bin:$PATH"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$STATE_DIR" 2>/dev/null
ssid=$(cat "$STATE_DIR/wifi-chosen" 2>/dev/null)

printf 'Connecting to: %s\n' "$ssid"
if nmcli device wifi connect "$ssid"; then
    printf '\n✅ connected'
    notify-send "WiFi ✅" "$ssid" 2>/dev/null
else
    printf '\n❌ failed'
    notify-send "WiFi ❌" "could not connect to $ssid" 2>/dev/null
fi

printf '\n\npress any key to close… '
read -r _unused 2>/dev/null
