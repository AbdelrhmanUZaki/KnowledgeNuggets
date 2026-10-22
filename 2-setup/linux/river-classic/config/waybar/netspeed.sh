#!/bin/sh
# ↓/↑ throughput for the bar, shown right after the wifi name.
#
# The numbers change every couple of seconds, so this module must never change
# width -- otherwise the whole right-hand cluster of the bar dances.  The
# output is always the same 15 characters ("↓ 17.1K ↑  1.4K") and style.css
# gives the module a monospace font, so every update covers the same pixels.
set -eu

state="${XDG_RUNTIME_DIR:-/tmp}/waybar-netspeed-$(id -u).state"

iface=$(ip -4 route show default 2>/dev/null | awk '{print $5; exit}')
if [ -z "${iface:-}" ]; then
    iface=$(ip -6 route show default 2>/dev/null | awk '{print $5; exit}')
fi

rx=0
tx=0
if [ -n "${iface:-}" ] && [ -r "/sys/class/net/$iface/statistics/rx_bytes" ]; then
    rx=$(cat "/sys/class/net/$iface/statistics/rx_bytes")
    tx=$(cat "/sys/class/net/$iface/statistics/tx_bytes")
else
    iface=""
fi

now=$(date +%s%3N)
down=0
up=0

prev_iface=""
prev_rx=0
prev_tx=0
prev_now=0
if [ -r "$state" ]; then
    read -r prev_iface prev_rx prev_tx prev_now < "$state" || prev_iface=""
fi

# only compute a rate when it is the same interface as last time (otherwise a
# switch from wifi to ethernet would look like a giant burst) and enough time
# has passed for the delta to mean something
if [ -n "${prev_iface:-}" ] && [ -n "$iface" ] && [ "$prev_iface" = "$iface" ]; then
    ms=$((now - prev_now))
    if [ "$ms" -ge 200 ]; then
        down=$(( (rx - prev_rx) * 1000 / ms ))
        up=$(( (tx - prev_tx) * 1000 / ms ))
    fi
fi

[ "$down" -ge 0 ] || down=0
[ "$up" -ge 0 ] || up=0

printf '%s %s %s %s\n' "$iface" "$rx" "$tx" "$now" > "$state" 2>/dev/null || true

awk -v d="$down" -v u="$up" '
function human(v,   i, unit) {
    split("B K M G T", unit, " ")
    i = 1
    while (v >= 1000 && i < 5) { v /= 1000; i++ }
    if (v >= 999.95 && i < 5) { v /= 1000; i++ }
    return sprintf("%5.1f%s", v, unit[i])
}
BEGIN { printf "↓%s ↑%s\n", human(d), human(u) }
'
