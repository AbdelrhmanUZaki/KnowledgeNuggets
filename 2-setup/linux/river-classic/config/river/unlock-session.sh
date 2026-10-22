#!/bin/sh
# Release a river session that a dead locker left locked.
#
# river's LockManager does not unlock when the lock client is destroyed
# (river/LockManager.zig, handleDestroy), so killing a locker while the
# screen is locked leaves a black screen with only the cursor and no way
# out -- a VT switch does not help either.  This helper asks the compositor
# for the lock, waits for the "locked" event and releases it again, which
# is the only request that makes river leave the locked state.
#
# usage: ~/.config/river/unlock-session.sh
#
# needs: gcc, wayland-scanner, libwayland-dev and the wayland-protocols
# package (the ext-session-lock-v1 protocol XML).
set -e

SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$STATE_DIR" 2>/dev/null || STATE_DIR=/tmp

XML=""
for candidate in \
    /usr/share/wayland-protocols/staging/ext-session-lock/ext-session-lock-v1.xml \
    /usr/share/wayland-protocols/unstable/ext-session-lock/ext-session-lock-v1.xml
do
    [ -f "$candidate" ] && XML="$candidate" && break
done

if [ -z "$XML" ]; then
    echo "ext-session-lock-v1.xml not found -- install the wayland-protocols package" >&2
    exit 1
fi

if ! command -v gcc >/dev/null 2>&1 || ! command -v wayland-scanner >/dev/null 2>&1; then
    echo "gcc and wayland-scanner are needed (build-essential + wayland-protocols)" >&2
    exit 1
fi

BUILD="$STATE_DIR/unlock-session"
if [ ! -x "$BUILD" ] || [ "$SRC_DIR/unlock-session.c" -nt "$BUILD" ]; then
    cd "$STATE_DIR" || exit 1
    wayland-scanner client-header "$XML" ext-session-lock-v1-client-protocol.h
    wayland-scanner private-code "$XML" ext-session-lock-v1-protocol.c
    gcc -o "$BUILD" "$SRC_DIR/unlock-session.c" ext-session-lock-v1-protocol.c \
        -I"$STATE_DIR" $(pkg-config --cflags --libs wayland-client) || exit 1
    chmod +x "$BUILD"
fi

exec "$BUILD"
