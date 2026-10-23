#!/bin/sh
# The System Menu — GNOME Quick-Settings parity hub for river-classic (keyboard-only).
# Used as the fallback when the GTK panel (system-panel.py) cannot start.
export PATH="$HOME/.local/bin:$PATH"

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$STATE_DIR" 2>/dev/null

wifi_state()  { nmcli radio wifi 2>/dev/null | sed 's/^ *//;s/ *$//' | tail -1; }
bt_state()    { "$HOME/.config/waybar/bt-toggle.sh" status 2>/dev/null || echo absent; }
profile_now() { powerprofilesctl get 2>/dev/null || echo unknown; }
dark_state()  { gsettings get org.gnome.desktop.interface color-scheme 2>/dev/null | grep -q dark && echo dark || echo light; }
dnd_state()   { dunstctl is-paused 2>/dev/null | grep -q true && echo on || echo off; }

W=$(wifi_state); B=$(bt_state); P=$(profile_now); T=$(dark_state); D=$(dnd_state)

# --- groups mirror the GNOME panel: toggles ▸ submenus ▸ session rows ---
pick=$(printf '%s\n' \
"⚡  profile: $P" \
"◐  theme: dark mode $T" \
"✈  wifi: $W" \
"▸  choose network…" \
"◉  bluetooth: $B" \
"▸  bluetooth devices…" \
"🔕  do not disturb: $D" \
"📸  screenshot (region)" \
"🖥  screenshot (full screen)" \
"─── sessions ───" \
"⚙  settings" \
"🔒  lock" \
"⇥  logout" \
"↺  reboot" \
"☾  suspend" \
"⏻  power off" \
| fuzzel --dmenu --prompt='⌘ ' --cache=/dev/null) || exit 0

case "$pick" in
    ⚡*)
        case "$P" in
            performance) powerprofilesctl set balanced ;;
            power-saver) powerprofilesctl set performance ;;
            *)           powerprofilesctl set power-saver ;;
        esac
        ;;
    ◐*)
        if [ "$T" = dark ]; then
            gsettings set org.gnome.desktop.interface color-scheme prefer-light
        else
            gsettings set org.gnome.desktop.interface color-scheme prefer-dark
        fi
        ;;
    ✈*)
        case "$W" in
            enabled) nmcli radio wifi off ;;
            *)       nmcli radio wifi on ;;
        esac
        ;;
    *bluetooth*)
        blueman-manager >/dev/null 2>&1 &
        exit 0
        ;;
    ▸*)
        exec "$HOME/.config/river/wifi-pick.sh"
        ;;
    ◉*)
        "$HOME/.config/waybar/bt-toggle.sh" >/dev/null 2>&1
        ;;
    🔕*)
        dunstctl set-paused toggle >/dev/null 2>&1
        ;;
    📸*)
        "$HOME/.config/river/screenshot.sh" >/dev/null 2>&1 &
        exit 0
        ;;
    🖥*)
        "$HOME/.config/river/screenshot.sh" full >/dev/null 2>&1 &
        exit 0
        ;;
    ⚙*)
        gnome-control-center >/dev/null 2>&1 &
        exit 0
        ;;
    🔒*)
        "$HOME/.config/river/lock-session.sh"
        exit 0
        ;;
    ⇥*)
        riverctl exit
        ;;
    ↺*)
        systemctl reboot
        ;;
    ☾*)
        systemctl suspend
        ;;
    ⏻*)
        systemctl poweroff
        ;;
    *)
        exit 0
        ;;
esac

exec "$0"
