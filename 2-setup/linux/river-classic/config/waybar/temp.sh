#!/bin/sh
# CPU package temperature for the bar.
#
# waybar's own temperature module wants a fixed hwmon/thermal path, but the
# hwmonN and thermal_zoneN numbers move around between boots, so we look the
# sensor up by name instead: the coretemp "Package id 0" first, then the
# x86_pkg_temp thermal zone.
value=""

for h in /sys/class/hwmon/hwmon*; do
    [ -r "$h/name" ] || continue
    [ "$(cat "$h/name" 2>/dev/null)" = "coretemp" ] || continue
    for label in "$h"/temp*_label; do
        [ -r "$label" ] || continue
        case "$(cat "$label" 2>/dev/null)" in
            "Package id 0")
                input="${label%_label}_input"
                [ -r "$input" ] && value=$(cat "$input" 2>/dev/null)
                break
                ;;
        esac
    done
    [ -n "$value" ] && break
done

if [ -z "$value" ]; then
    for z in /sys/class/thermal/thermal_zone*; do
        [ -r "$z/type" ] || continue
        [ "$(cat "$z/type" 2>/dev/null)" = "x86_pkg_temp" ] || continue
        value=$(cat "$z/temp" 2>/dev/null)
        [ -n "$value" ] && break
    done
fi

if [ -z "$value" ]; then
    echo "--°C"
    exit 0
fi

# the kernel reports millidegrees
awk -v v="$value" 'BEGIN { printf "%d°C\n", v / 1000 }'
