#!/bin/sh
# GNOME-style power menu for river-classic (fuzzel dmenu mode)
export PATH="$HOME/.local/bin:$PATH"

choice=$(printf 'Settings\nLogout\nLock\nSwitch user\nReboot\nPoweroff\nSuspend\n' \
    | fuzzel --dmenu --prompt='⏻  ' --cache=/dev/null)

case "$choice" in
    Settings) gnome-control-center ;;
    Logout)   riverctl exit ;;
    Lock)     "$HOME/.config/river/lock-session.sh" ;;
    "Switch user") "$HOME/.config/river/switch-user.sh" ;;
    Reboot)   systemctl reboot ;;
    Poweroff) systemctl poweroff ;;
    Suspend)  systemctl suspend ;;
esac
