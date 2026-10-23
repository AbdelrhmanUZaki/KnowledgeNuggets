#!/bin/sh
# Install CopyQ 17.x as a user-level AppImage plus a ~/.local/bin/copyq wrapper.
#
# Why not the distro package: Ubuntu 26.04 ships CopyQ 13.0.0, which crashes
# when restoring large images under Qt 6.10/Wayland on river.  CopyQ 17.0.0
# (bundled Qt 6.11.1) was verified with repeated 1920x1200 PNG restore cycles.
#
# Run as the desktop user; no sudo.  Needs curl (or wget) and FUSE for the
# AppImage.  The published SHA-512 is pinned below.
set -eu

VERSION=17.0.0
SHA512=d684feaf867617e0052b1bc28928ea2d7f1300d45eac2fb1127fc7a9df1b30e49bfe7b6d08a44080e4e5d70097fab3e274c6990831b55a6b1e786248993304a7
URL="https://github.com/hluk/CopyQ/releases/download/v$VERSION/CopyQ-$VERSION-x86_64.AppImage"
APPIMAGE="$HOME/.local/opt/CopyQ-$VERSION-x86_64.AppImage"
WRAPPER="$HOME/.local/bin/copyq"

log() { printf '\033[1;34m[copyq]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[copyq]\033[0m %s\n' "$*" >&2; exit 1; }

mkdir -p "$(dirname "$APPIMAGE")" "$(dirname "$WRAPPER")"

if [ -x "$APPIMAGE" ] && "$APPIMAGE" --version 2>/dev/null | grep -q "CopyQ Clipboard Manager $VERSION"; then
    log "CopyQ $VERSION already installed"
else
    log "downloading CopyQ $VERSION (44 MB)…"
    tmp="$APPIMAGE.tmp"
    trap 'rm -f "$tmp"' EXIT HUP INT TERM
    if command -v curl >/dev/null 2>&1; then
        curl -fL --progress-bar -o "$tmp" "$URL"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$tmp" "$URL"
    else
        die "curl or wget is required to download CopyQ"
    fi
    echo "$SHA512  $tmp" | sha512sum -c - >/dev/null || die "checksum mismatch for $tmp"
    mv "$tmp" "$APPIMAGE"
    chmod +x "$APPIMAGE"
    trap - EXIT HUP INT TERM
fi

# The wrapper must win over /usr/bin/copyq (the broken 13.0.0 package) for
# interactive shells; river's keybind/panel use the absolute path explicitly.
printf '#!/bin/sh\nexec "%s" "$@"\n' "$APPIMAGE" > "$WRAPPER"
chmod +x "$WRAPPER"

"$WRAPPER" --version | head -n 1
log "installed: $WRAPPER"
log "next: ~/.config/river/copyq-setup.sh (init runs it at login)"
