#!/bin/sh
# Compile (once) and run view-watcher: single-view = edge-to-edge with no
# border, multi-view = 12 px gaps and a 2 px border. See view-watcher.c.
set -u
export PATH="$HOME/.local/bin:$PATH"

here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
state="${XDG_STATE_HOME:-$HOME/.local/state}/river-classic"
mkdir -p "$state" 2>/dev/null || exit 0

bin="$state/view-watcher"
src="$here/view-watcher.c"
xml="$here/river-status-unstable-v1.xml"

if [ -x "$bin" ] && [ "$bin" -nt "$src" ] && [ "$bin" -nt "$xml" ]; then
    exec "$bin" >>"$state/view-watcher.log" 2>&1
fi

if ! command -v wayland-scanner >/dev/null 2>&1 ||
   ! command -v cc >/dev/null 2>&1 ||
   ! command -v pkg-config >/dev/null 2>&1; then
    echo "view-watcher: wayland-scanner/cc/pkg-config missing; not running"
    exit 0
fi

tmp=$(mktemp -d "${TMPDIR:-/tmp}/view-watcher.XXXXXX") || exit 0
trap 'rm -rf "$tmp"' EXIT INT TERM HUP

if ! wayland-scanner client-header "$xml" "$tmp/river-status-unstable-v1-client-protocol.h" ||
   ! wayland-scanner private-code "$xml" "$tmp/river-status-protocol.c"; then
    echo "view-watcher: wayland-scanner failed"
    exit 0
fi

if ! cc -O2 -Wall -Wextra -o "$bin.tmp" "$src" "$tmp/river-status-protocol.c" -I"$tmp" \
        $(pkg-config --cflags --libs wayland-client); then
    echo "view-watcher: compile failed"
    exit 0
fi

mv "$bin.tmp" "$bin" || exit 0
exec "$bin" >>"$state/view-watcher.log" 2>&1
