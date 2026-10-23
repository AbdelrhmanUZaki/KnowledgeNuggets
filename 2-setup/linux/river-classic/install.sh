#!/usr/bin/env bash
# Install the river-classic Wayland session: compositor, bar, system panel.
#
#   ./install.sh            # everything (deps -> build -> session -> config)
#   ./install.sh deps       # packages only            (needs sudo)
#   ./install.sh build      # wlroots + river-classic -> ~/.local
#   ./install.sh session    # GDM entry + mask Ubuntu's waybar.service
#   ./install.sh config     # symlink the config into ~/.config
#
# Safe to re-run. Nothing outside ~/.local, ~/.config and the two files listed
# under "session" is touched.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$HOME/.local"

WLROOTS_VERSION="0.20.2"     # C library the zig bindings link against
RIVER_TAG="v0.3.17"          # river-classic (river 0.3 fork) — dwm-style tags
ZIG_VERSION="0.16.0"         # compiler river-classic is built with

log()  { printf '\033[1;34m[river]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[river]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[river]\033[0m %s\n' "$*" >&2; exit 1; }

APT_PACKAGES=(
  # session + bar
  waybar foot fuzzel dunst swaylock
  # screen capture + clipboard
  grim slurp wl-clipboard
  # system panel / desktop integration
  pavucontrol network-manager-gnome blueman
  gnome-calendar gnome-control-center
  pipewire-utils                 # wpctl — the audio CLI (this is PipeWire, not PulseAudio)
  python3-gi gir1.2-gtk-3.0      # the GTK3 system panel (PyGObject)
  libgtk-layer-shell0            # wlr-layer-shell — docks the panel under the bar
  fonts-font-awesome             # monochrome icon font used by the bar and the panel
  kanata                         # keyboard remap: space-hold arrows / caps-hold scroll
)

BUILD_PACKAGES=(
  meson ninja-build build-essential pkg-config git wget xz-utils
  libwayland-dev wayland-protocols libxkbcommon-dev libseat-dev libinput-dev
  libpixman-1-dev libegl-dev libgles-dev libdrm-dev libgbm-dev libudev-dev
  libvulkan-dev libdisplay-info-dev hwdata gperf
  libxcb1-dev libxcb-randr0-dev libxcb-shm0-dev libxcb-xfixes0-dev
  libxcb-composite0-dev libxcb-dri3-dev libxcb-present-dev libxcb-sync-dev
  libxcb-xinput-dev libxcb-glx0-dev libxcb-icccm4-dev libxcb-image0-dev
  libxcb-keysyms1-dev libxcb-render-util0-dev libxcb-shape0-dev
  libxcb-util-dev libxcb-xtest0-dev libxcb-render0-dev
)

install_pkgs() {
  local -a missing=()
  for pkg in "$@"; do
    dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
  done
  if [ ${#missing[@]} -gt 0 ]; then
    log "installing: ${missing[*]}"
    sudo apt update
    sudo apt install -y "${missing[@]}"
  else
    log "all packages present"
  fi
}

build_compositor() {
  mkdir -p "$HOME/src"

  # --- zig -------------------------------------------------------------
  if [ ! -x "$PREFIX/zig-$ZIG_VERSION/zig" ]; then
    log "fetching zig $ZIG_VERSION"
    wget -q "https://ziglang.org/download/${ZIG_VERSION}/zig-x86_64-linux-${ZIG_VERSION}.tar.xz" \
      -O "/tmp/zig-${ZIG_VERSION}.tar.xz"
    tar -xf "/tmp/zig-${ZIG_VERSION}.tar.xz" -C "$PREFIX"
    rm -f "/tmp/zig-${ZIG_VERSION}.tar.xz"
  fi
  export PATH="$PREFIX/zig-$ZIG_VERSION:$PATH"
  log "zig: $(zig version)"

  # --- wlroots (C library) ---------------------------------------------
  if [ ! -f "$PREFIX/lib/x86_64-linux-gnu/libwlroots-0.20.so" ]; then
    cd "$HOME/src"
    [ -d wlroots ] || git clone --depth 1 -b "$WLROOTS_VERSION" \
      https://gitlab.freedesktop.org/wlroots/wlroots.git
    cd wlroots
    log "building wlroots $WLROOTS_VERSION"
    meson setup build --prefix="$PREFIX" --libdir=lib/x86_64-linux-gnu \
      -Dwerror=false -Dexamples=false -Dtests=false
    ninja -C build
    ninja -C build install
  else
    log "wlroots already built"
  fi

  # --- river-classic ----------------------------------------------------
  cd "$HOME/src"
  [ -d river-classic ] || git clone --depth 1 -b "$RIVER_TAG" \
    https://codeberg.org/river/river-classic.git
  cd river-classic
  git fetch --tags --quiet || true
  # our patches on top of upstream (session lock: release the session when
  # the lock client dies -- without it a killed locker leaves a black screen)
  for p in "$HERE"/patches/*.patch; do
      [ -f "$p" ] || continue
      if git apply --check "$p" 2>/dev/null; then
          log "applying $(basename "$p")"
          git apply "$p"
      elif git apply --reverse --check "$p" 2>/dev/null; then
          log "already applied: $(basename "$p")"
      else
          warn "patch does not apply: $(basename "$p") (upstream changed?)"
      fi
  done
  log "building river-classic $RIVER_TAG"
  PKG_CONFIG_PATH="$PREFIX/lib/x86_64-linux-gnu/pkgconfig:${PKG_CONFIG_PATH:-}" \
    zig build -Doptimize=ReleaseFast --prefix "$PREFIX"
  log "installed: $(ls "$PREFIX/bin" | tr '\n' ' ')"
}

install_session() {
  mkdir -p "$HOME/.local/share/wayland-sessions"
  cat > "$HOME/.local/share/wayland-sessions/river-classic.desktop" <<EOF
[Desktop Entry]
Name=river-classic
Comment=Dynamic tiling (dwm tags) Wayland compositor
Exec=env LD_LIBRARY_PATH=$PREFIX/lib/x86_64-linux-gnu $PREFIX/bin/river
Icon=wayland
Terminal=false
Type=Application
DesktopNames=river-classic
EOF

  # GDM only lists sessions from the system directory
  if [ -w /usr/share/wayland-sessions ] || [ ! -f /usr/share/wayland-sessions/river-classic.desktop ]; then
    log "registering the session with GDM (sudo)"
    sudo cp "$HOME/.local/share/wayland-sessions/river-classic.desktop" \
      /usr/share/wayland-sessions/river-classic.desktop
  else
    warn "/usr/share/wayland-sessions/river-classic.desktop exists — copy it manually if stale"
  fi

  # Ubuntu ships a waybar.service that restart-storms at every login
  # transition (it has no layer-shell compositor to attach to).
  log "masking Ubuntu's waybar.service (it fights our bar)"
  systemctl --user mask waybar.service >/dev/null 2>&1 || true
}

install_rules() {
  local rule="$HERE/udev/70-river-classic-input.rules"
  [ -f "$rule" ] || { warn "missing $rule"; return; }

  log "installing input udev rules (gestures + kanata)"
  sudo install -m 0644 "$rule" /etc/udev/rules.d/70-river-classic-input.rules
  echo uinput | sudo tee /etc/modules-load.d/river-classic-uinput.conf >/dev/null
  sudo modprobe uinput 2>/dev/null || true
  sudo udevadm control --reload
  sudo udevadm trigger --subsystem-match=input
  sudo udevadm trigger --sysname-match=uinput 2>/dev/null || true
  log "udev rule active — a reboot is the fallback if /dev/uinput is still root-only"
}

case "${1:-all}" in
  deps)    install_pkgs "${APT_PACKAGES[@]}" "${BUILD_PACKAGES[@]}" ;;
  build)   build_compositor ;;
  session) install_session ;;
  rules)   install_rules ;;
  config)  "$HERE/restore.sh" ;;
  all)
    install_pkgs "${APT_PACKAGES[@]}" "${BUILD_PACKAGES[@]}"
    build_compositor
    install_session
    install_rules
    "$HERE/restore.sh"
    cat <<EOF

$(log "done — now:")
  1. log out of the GNOME session
  2. pick "river-classic" in the GDM gear menu and log in
  3. the bar appears on every output; click any system icon for the panel

EOF
    ;;
  *) die "unknown phase: $1 (use deps|build|session|rules|config|all)" ;;
esac
