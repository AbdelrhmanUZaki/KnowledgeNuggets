#!/bin/sh
# Tag switching with a two-slot history — dwm's view(0) behaviour.
#
#   Alt+N         set tag N        (records the outgoing tag set)
#   Alt+Ctrl+N    toggle tag N     (records the outgoing tag set)
#   Alt+0         show all tags    (records the outgoing tag set)
#   Alt+Tab       flip between the current and the previous tag set
#
# dwm keeps two tagset[] slots and view(0) flips between them; river has no
# such buffer, so the masks live in $STATE_DIR/tags-{current,last}. The init
# resets them to tag 1 on every login (river always boots on tag 1).
#
# state dir override (tests): TAG_STATE_DIR=/tmp/x tag-switch.sh set 2

PATH="$HOME/.local/bin:$PATH"
RIVERCTL="${RIVERCTL:-riverctl}"
STATE_DIR="${TAG_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/river-classic}"
mkdir -p "$STATE_DIR"

cur_file="$STATE_DIR/tags-current"
last_file="$STATE_DIR/tags-last"
cur=$(cat "$cur_file" 2>/dev/null || echo 1)

save() { printf '%s\n' "$1" > "$cur_file"; }
remember() { printf '%s\n' "$1" > "$last_file"; }

case "${1:-}" in
    set)
        n=${2:?tag number}
        new=$((1 << (n - 1)))
        [ "$cur" -eq "$new" ] && exit 0
        remember "$cur"
        save "$new"
        "$RIVERCTL" set-focused-tags "$new"
        ;;
    toggle)
        n=${2:?tag number}
        mask=$((1 << (n - 1)))
        new=$((cur ^ mask))
        remember "$cur"
        save "$new"
        "$RIVERCTL" toggle-focused-tags "$mask"
        ;;
    all)
        new=$(((1 << 32) - 1))
        [ "$cur" -eq "$new" ] && exit 0
        remember "$cur"
        save "$new"
        "$RIVERCTL" set-focused-tags "$new"
        ;;
    back)
        last=$(cat "$last_file" 2>/dev/null) || exit 0
        [ -n "$last" ] || exit 0
        [ "$cur" -eq "$last" ] && exit 0
        remember "$cur"
        save "$last"
        "$RIVERCTL" set-focused-tags "$last"
        ;;
    *)
        echo "usage: tag-switch.sh set N | toggle N | all | back" >&2
        exit 2
        ;;
esac
