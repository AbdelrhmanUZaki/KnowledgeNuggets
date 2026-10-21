#!/bin/sh
# Brightness control for the waybar bar via logind SetBrightness (GNOME's mechanism).
# Authoritative in-order: caller's own session ("self"); if refused (non-foreground
# scope), fall back to the active seat0 session of this user.
dev=intel_backlight
sysp=/sys/class/backlight/$dev
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$state_dir" 2>/dev/null || state_dir=/tmp
err="$state_dir/brightness.err"
last="$state_dir/brightness-last"

cur=$(cat "$sysp/brightness" 2>/dev/null) || exit 1
mx=$(cat "$sysp/max_brightness" 2>/dev/null) || exit 1
step=$((mx / 50))           # ~2% per notch
min=$((mx / 40))            # ~2.5% floor (panel never fully dies)
case "$1" in
    up)   n=$((cur + step)) ;;
    down) n=$((cur - step)) ;;
    set)  [ -n "$2" ] && n=$((mx * $2 / 100)) || n=$cur ;;
    *)    n=$cur ;;
esac
[ "$n" -lt "$min" ] && n=$min
[ "$n" -gt "$mx" ] && n=$mx
echo "$n" > "$last"

write() {
    busctl call --system org.freedesktop.login1 \
        /org/freedesktop/login1/session/"$1" \
        org.freedesktop.login1.Session SetBrightness \
        ssu backlight "$dev" "$n" 2>>"$err"
}

if ! write self; then
    for s in $(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1}'); do
        [ "$(loginctl show-session "$s" -p Active -p Seat -p User --value | tr '\n' ' ')" = "yes seat0 1000" ] || continue
        write "$s" && break
    done
fi
( echo "$n" > "$sysp/brightness" ) 2>/dev/null   # native fallback (usually refused)
