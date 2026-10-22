#!/bin/sh
# Interactive password path for the wifi picker (runs inside foot).
#
# nmcli only asks for the missing secret when it is told to (--ask) and it can
# read it from a pipe, so the password never has to appear on the command
# line.  Without --ask the connect fails with "Secrets were required, but not
# provided" -- that was the old behaviour of this script.
export PATH="$HOME/.local/bin:$PATH"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$STATE_DIR" 2>/dev/null

# the SSID may be given as an argument, otherwise take it from the state file
ssid="$1"
[ -n "$ssid" ] || ssid=$(cat "$STATE_DIR/wifi-chosen" 2>/dev/null)

if [ -z "$ssid" ]; then
    printf 'No network selected.\n'
    exit 1
fi

printf 'Connecting to: %s\n' "$ssid"
printf 'Password (empty for an open network): '
read -r -s password 2>/dev/null
printf '\n\n'

if [ -n "$password" ]; then
    # --ask reads the secret from stdin, so it stays out of the process list
    printf '%s\n' "$password" | nmcli --ask --wait 30 device wifi connect "$ssid"
else
    nmcli --wait 30 device wifi connect "$ssid"
fi
rc=$?

if [ "$rc" -eq 0 ]; then
    printf '\nconnected'
    notify-send "WiFi" "$ssid connected" 2>/dev/null
else
    printf '\nfailed'
    notify-send "WiFi" "could not connect to $ssid" 2>/dev/null
fi

printf '\n\npress any key to close… '
read -r _unused 2>/dev/null
exit "$rc"
