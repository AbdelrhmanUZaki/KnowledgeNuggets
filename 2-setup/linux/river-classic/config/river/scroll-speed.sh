#!/bin/sh
# Touchpad scroll speed — live tuning without a relogin.
#
#   scroll-speed.sh          show the current factor
#   scroll-speed.sh 0.4      40% of the stock speed (also persisted in init)
#
# The factor multiplies the scroll delta in river, so 1.0 = stock, 0.5 = half
# speed, 2 = twice as fast. Touchpad only: a wheel mouse keeps its own rate.
RC="$HOME/.local/bin/riverctl"
[ -x "$RC" ] || RC="$(command -v riverctl)"
INIT="$HOME/.config/river/init"
GLOB='*Touchpad'

case "$1" in
    ''|--get)
        now=$("$RC" list-input-configs 2>/dev/null | awk -F': ' '/scroll-factor/{print $2; exit}')
        [ -n "$now" ] || now="1.0 (river default)"
        printf 'touchpad scroll factor: %s\n' "$now"
        printf 'set it with: %s <factor>   (0.4 = 40%%, 1.0 = stock)\n' "$(basename "$0")"
        exit 0
        ;;
    -h|--help)
        sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
esac

factor="$1"
case "$factor" in
    ''|*[!0-9.]*|.) echo "usage: $(basename "$0") <factor>   e.g. 0.4" >&2; exit 2 ;;
esac

"$RC" input "$GLOB" scroll-factor "$factor" || exit 1

# persist: keep the single scroll-factor line in init in sync (init is a
# symlink into the dotfiles repo, so this edits the source of truth too)
if [ -f "$INIT" ]; then
    if grep -q "scroll-factor" "$INIT"; then
        sed -i "s|^\(riverctl input '\*Touchpad' scroll-factor\).*|\1 $factor|" "$INIT"
    else
        printf "\nriverctl input '%s' scroll-factor %s\n" "$GLOB" "$factor" >> "$INIT"
    fi
fi

pct=$(awk "BEGIN{printf \"%d\", $factor * 100}" 2>/dev/null || echo "?")
command -v notify-send >/dev/null 2>&1 &&
    notify-send "Touchpad" "scroll speed ${pct}% (factor $factor)" 2>/dev/null
printf 'touchpad scroll factor set to %s (%s%% of stock)\n' "$factor" "$pct"
