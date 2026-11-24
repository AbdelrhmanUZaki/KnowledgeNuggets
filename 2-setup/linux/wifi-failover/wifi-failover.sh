#!/usr/bin/env bash
# Watch internet on the home router WiFi and fail over to the personal hotspot
# the moment it dies, then switch back when the router's internet returns.
#
# Detection is a continuous ping stream (default: 2 probes/second). The OS has
# no event for "internet behind the router is gone" (the WiFi link stays up),
# so we probe continuously — cost is one 64-byte packet per probe. After
# MISS_THRESHOLD missed replies, a confirmation round against all targets runs
# before switching, to avoid false positives.
#
# All settings can be overridden with environment variables (FAILOVER_*),
# which makes testing easy without editing the file.

set -u

ROUTER_SSID="${FAILOVER_ROUTER_SSID:-}"
HOTSPOT_SSID="${FAILOVER_HOTSPOT_SSID:-}"
PROBE_INTERVAL="${FAILOVER_PROBE_INTERVAL:-0.5}"      # seconds between stream pings
MISS_THRESHOLD="${FAILOVER_MISS_THRESHOLD:-3}"        # missed replies before confirming
CONFIRM_TIMEOUT="${FAILOVER_CONFIRM_TIMEOUT:-1}"      # per-target timeout for confirm round
SWITCH_BACK_EVERY="${FAILOVER_SWITCH_BACK_EVERY:-90}" # seconds between router retries on hotspot
SWITCH_BACK_STABLE="${FAILOVER_SWITCH_BACK_STABLE:-45}" # seconds router internet must hold before committing back
STABLE_CHECK_STEP="${FAILOVER_STABLE_CHECK_STEP:-5}"   # seconds between stability checks in the window
STABLE_ALLOWED_MISS="${FAILOVER_STABLE_ALLOWED_MISS:-1}" # tolerated failed checks in the window
MIN_GOOD_DWELL="${FAILOVER_MIN_GOOD_DWELL:-120}"      # dying sooner after a commit counts as a failed return
MAX_RETRY_INTERVAL="${FAILOVER_MAX_RETRY_INTERVAL:-600}" # cap for the escalating router-retry interval
POST_SWITCH_WAIT="${FAILOVER_POST_SWITCH_WAIT:-8}"    # seconds to settle after a connect
RETRY_AFTER_FAIL="${FAILOVER_RETRY_AFTER_FAIL:-60}"   # wait after a failed switch attempt
LOG="${FAILOVER_LOG:-$HOME/.local/state/wifi-failover.log}"
read -ra PING_TARGETS <<< "${FAILOVER_PING_TARGETS:-1.1.1.1 8.8.8.8 9.9.9.9}"

if [[ -z "$ROUTER_SSID" || -z "$HOTSPOT_SSID" ]]; then
    echo "wifi-failover: set FAILOVER_ROUTER_SSID and FAILOVER_HOTSPOT_SSID" >&2
    exit 2
fi

mkdir -p "$(dirname "$LOG")"

state="ROUTER"
last_retry=0
retry_interval="${SWITCH_BACK_EVERY}"
router_since=0
target_idx=0

log()  { printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$state" "$*" >> "$LOG"; }
note() {
    log "$*"
    command -v notify-send >/dev/null 2>&1 && \
        notify-send -a "WiFi failover" "WiFi failover" "$*"
}

active_wifi() {
    nmcli -t -f NAME,TYPE,STATE connection show --active 2>/dev/null \
        | awk -F: '$2 == "802-11-wireless" && $3 == "activated" {print $1; exit}'
}

# Try every target once; echo the first one that answers; exit 0 if any did.
internet_ok() {
    local t
    for t in "${PING_TARGETS[@]}"; do
        if ping -q -c 1 -W "$CONFIRM_TIMEOUT" "$t" >/dev/null 2>&1; then
            echo "$t"
            return 0
        fi
    done
    return 1
}

connect() { nmcli connection up id "$1" >/dev/null 2>&1; }

# Before committing back to the router, its internet must hold up for a whole
# window. The router's WAN sometimes recovers for only a few seconds, and a
# single lucky ping round would cause endless flapping router <-> hotspot.
stable_router() {
    local misses=0 i
    for (( i = 0; i < SWITCH_BACK_STABLE; i += STABLE_CHECK_STEP )); do
        sleep "$STABLE_CHECK_STEP"
        internet_ok >/dev/null || misses=$((misses + 1))
        if (( misses > STABLE_ALLOWED_MISS )); then
            log "router internet failed stability window ($misses misses)"
            return 1
        fi
    done
    return 0
}

# Stream-ping the current target and react to events as they arrive. Returns:
#   0 = internet confirmed down (stream target silent AND all targets silent)
#   1 = we are no longer on the router WiFi
#   2 = probe target went silent but internet is fine; probe target rotated
watch_router() {
    local misses=0 ev target ok i
    target="${PING_TARGETS[$target_idx]}"
    log "watching internet via stream-ping to $target (${PROBE_INTERVAL}s probes)"
    while IFS= read -r -u 3 ev; do
        if [[ "$ev" == "64 bytes from"* ]]; then
            misses=0
            continue
        fi
        misses=$((misses + 1))
        (( misses >= MISS_THRESHOLD )) || continue
        if ok="$(internet_ok)"; then
            log "probe target $target silent but $ok answers, rotating probe target"
            for i in "${!PING_TARGETS[@]}"; do
                [[ "${PING_TARGETS[$i]}" == "$ok" ]] && target_idx=$i
            done
            return 2
        fi
        return 0
    done 3< <(ping -n -O -i "$PROBE_INTERVAL" -W 1 "$target" 2>/dev/null)

    # ping exited: WiFi dropped, or the router stopped answering entirely
    if [[ "$(active_wifi)" != "$ROUTER_SSID" ]]; then
        return 1
    fi
    if ok="$(internet_ok)"; then
        log "ping stream ended but internet is fine via $ok"
        return 2
    fi
    return 0
}

log "started (router=$ROUTER_SSID hotspot=$HOTSPOT_SSID probes=${PROBE_INTERVAL}s miss-threshold=$MISS_THRESHOLD)"

while true; do
    conn="$(active_wifi)"

    if [[ "$conn" == "$HOTSPOT_SSID" ]]; then
        state="HOTSPOT"
        if (( $(date +%s) - last_retry >= retry_interval )); then
            last_retry=$(date +%s)
            log "trying router again"
            if connect "$ROUTER_SSID"; then
                sleep "$POST_SWITCH_WAIT"
                if stable_router; then
                    state="ROUTER"
                    retry_interval=$SWITCH_BACK_EVERY
                    router_since=$(date +%s)
                    note "Router internet is back and stable. Switched back to '$ROUTER_SSID'."
                    continue
                else
                    # unproven router: back off before trusting it again
                    (( retry_interval *= 2 ))
                    (( retry_interval > MAX_RETRY_INTERVAL )) && retry_interval=$MAX_RETRY_INTERVAL
                    log "back to hotspot, next router try in ${retry_interval}s"
                    connect "$HOTSPOT_SSID"
                fi
            else
                log "could not connect to router, will retry"
            fi
        fi
        sleep 5

    elif [[ "$conn" == "$ROUTER_SSID" ]]; then
        state="ROUTER"
        (( router_since == 0 )) && router_since=$(date +%s)
        watch_router
        rc=$?
        if [[ "$rc" -eq 0 ]]; then
            # A return to the router that dies soon afterwards counts as a
            # failed return: push the next try further away, so a flapping
            # WAN cannot make us bounce router <-> hotspot forever.
            dwell=$(( $(date +%s) - router_since ))
            if (( router_since > 0 && dwell < MIN_GOOD_DWELL )); then
                (( retry_interval *= 2 ))
                (( retry_interval > MAX_RETRY_INTERVAL )) && retry_interval=$MAX_RETRY_INTERVAL
                log "router held only ${dwell}s (< ${MIN_GOOD_DWELL}s), next try in ${retry_interval}s"
            else
                retry_interval=$SWITCH_BACK_EVERY
            fi
            router_since=0
            log "internet confirmed down, switching to hotspot '$HOTSPOT_SSID'"
            if connect "$HOTSPOT_SSID"; then
                last_retry=$(date +%s)
                note "Router internet is down. Switched to hotspot '$HOTSPOT_SSID'."
            else
                log "ERROR: could not connect to hotspot, retry in ${RETRY_AFTER_FAIL}s"
                note "Internet is down, and connecting to hotspot '$HOTSPOT_SSID' failed."
                sleep "$RETRY_AFTER_FAIL"
            fi
        fi
        sleep 1   # gentle on tight loops (stream restarts, NM churn)

    else
        sleep 5   # user picked another network by hand: leave it alone
    fi
done
