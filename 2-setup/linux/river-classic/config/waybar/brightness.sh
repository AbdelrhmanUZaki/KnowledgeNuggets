#!/bin/sh
# Brightness control for the waybar bar via logind SetBrightness (GNOME's mechanism).
# Authoritative in-order: caller's own session ($XDG_SESSION_ID); if refused, fall
# back to the active seat0 session of this user. logind has NO /session/self
# object, and `loginctl show-session -p A -p B --value` does NOT preserve the
# property order (it prints User, Seat, Active), so query each property alone.
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
    # bump <signed steps>: move by n * step (~2% each) in ONE logind call.
    # The gesture daemon uses this so a swipe does not spawn one busctl per 2%.
    bump) n=$((cur + step * ${2:-1})) ;;
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

ok=0
if [ -n "$XDG_SESSION_ID" ] && write "$XDG_SESSION_ID"; then
    ok=1
else
    for s in $(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1}'); do
        [ "$(loginctl show-session "$s" -p Active --value 2>/dev/null)" = yes ] || continue
        [ "$(loginctl show-session "$s" -p Seat --value 2>/dev/null)" = seat0 ] || continue
        [ "$(loginctl show-session "$s" -p User --value 2>/dev/null)" = "$(id -u)" ] || continue
        if write "$s"; then ok=1; break; fi
    done
fi

if [ "$ok" -eq 0 ]; then
    # native fallback (usually refused on a default Ubuntu install)
    if ! ( echo "$n" > "$sysp/brightness" ) 2>/dev/null; then
        echo "brightness: logind and sysfs both refused" >&2
        exit 1
    fi
fi
exit 0
