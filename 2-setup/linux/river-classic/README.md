# river-classic — a dynamic-tiling Wayland session for Ubuntu

A **lightweight, dwm-style Wayland desktop** that keeps GNOME fully intact as the
fallback session. Chosen over Hyprland/sway/i3 because it is:

- **dynamic** tiling (dwm tags model: master + stack, new windows steal the master slot)
- **lightweight** — no giant toolkit, no 100 MB of dependencies
- **runtime-editable** — every keybind, the bar and the panel are plain config/scripts
  (no recompiling to change anything)
- **always-current** — built from source, not from a stale distro package

Compositor: [river-classic](https://codeberg.org/river/river-classic) v0.3.17 (a maintained
fork of river 0.3), built with Zig 0.16 against wlroots 0.20.2.

---

## Install

```bash
cd 2-setup/linux/river-classic
./install.sh          # deps (sudo) → build wlroots + river → GDM entry → config
```

Then **log out** of GNOME and pick **river-classic** in the gear menu.

Phases can be run separately: `./install.sh deps | build | session | rules | config`.

Re-apply the config at any time (this is what `2-setup/linux/restore.sh` calls):

```bash
./restore.sh          # symlinks ~/.config/{river,waybar} -> this repo, with backups
```

Because the config is symlinked, **edits in this repo are live immediately** — change
`config/waybar/style.css`, save, and the bar reloads it (`reload_style_on_change`).

---

## The design contract

> **The bar shows state. The panel holds actions.**

Modelled on GNOME's top bar: status indicators on the right, one grouped surface
(Quick Settings) for everything you can *change*, clock in the middle, workspaces on
the left. Nothing is duplicated, and nothing is a one-off scattered menu.
The Wi-Fi and Bluetooth tiles each carry a small **corner chevron** that expands the
panel into a list page — available networks / paired devices — exactly like GNOME's
Quick Settings; the back button sits in the header.

```
┌ 1 2 3 4 5 6 7 8 9   window title          Wed 21 Oct  16:29      🔊 ☀ ⇅ ᛒ 🔋 ⏻
└────────────────────────── workspaces ───────────┘           └─ state only ─┘
                                                            ↓ click any of them
                                      ┌───────────── System Menu ─────────────┐
                                      │ 🔋 79% · on charger        [⚙] [📸]  │
                                      │ ┌────────┬────────┬────────┐         │
                                      │ │  Wi-Fi │Bluetooth│ Power │         │  ← toggle tiles
                                      │ ├────────┼────────┼────────┤         │
                                      │ │🌙 Dark  │🔕 DND   │📸 Shot │         │
                                      │ └────────┴────────┴────────┘         │
                                      │ 🔊 ──────●──────   volume             │  ← live sliders
                                      │ ☀  ─────●───────   brightness         │
                                      │ [🔒][⇥][↺][☾][⏻]                    │  ← session row
                                      └────────────────────────────────────────┘
```

| File | Role |
|---|---|
| `config/river/init` | session bootstrap: paths, dbus env, keybinds, bar/dunst/swaybg, rivertile |
| `config/river/system-panel.py` | the System Menu (GTK3, PyGObject) — tiles, sliders, session row |
| `config/river/quick-settings.sh` | entry point for the panel (falls back to the dmenu) |
| `config/river/quick-settings-dmenu.sh` | keyboard-only fallback menu |
| `config/river/wifi-pick.sh` / `wifi-connect.sh` | network picker + password prompt |
| `config/river/media-key.sh` | MPRIS play/pause/next via dbus (no playerctl needed) |
| `config/river/gestures.py` | multi-finger gestures: 3-tap back, 4-tap forward, 3-swipe volume, physical press 1 = left / 2–3 = right |
| `config/river/scroll-speed.sh` | touchpad scroll speed: live apply + persist in `init` |
| `config/river/screenshot.sh` | grim + slurp region/full capture, auto clipboard |
| `config/river/power-menu.sh` | session actions (also available in the panel) |
| `config/waybar/config.jsonc` | bar layout, module formats, click actions |
| `config/waybar/style.css` | the solarized dark theme (GNOME-style flat surface) |
| `config/waybar/brightness.sh` | brightness via **logind** `SetBrightness` (±2% / absolute) |
| `config/waybar/notify.sh` | DND indicator (visible only while DND is on) |
| `config/waybar/bt-toggle.sh` | Bluetooth adapter power (also `status` mode) |

---

## Keybindings

Tags are on **Alt** (dwm muscle memory), not Super.

| Keys | Action |
|---|---|
| `Alt+1..9` | switch to tag · `Alt+0` = all tags |
| `Alt+Shift+1..9` | **move the focused window to that tag** · `Alt+Shift+0` = on every tag |
| `Alt+Ctrl+n` | also show tag n (multi-view) |
| `Super+Shift+Return` | terminal (foot) |
| `Super+P` | launcher (fuzzel) |
| `Super+Return` | zoom / `Super+H` `Super+L` master ratio · `Super+Shift+H/L` master count |
| `Super+Q` | close · `Super+Shift+E` exit river |
| `Super+Period` / `Super+Comma` | switch monitor |
| `Alt+B` | show/hide the bar (waybar's SIGUSR1 toggle) |
| `Print` / `Super+Shift+Print` | screenshot full / region |
| `XF86AudioPlay/Pause/Next/Prev` | media keys |

> Browser caveat: Firefox/Chromium also use `Alt+<number>` for tab switching — the
> compositor wins the race.

---

## Gotchas worth knowing (all hit during the build)

- **Audio is PipeWire, not PulseAudio.** `pactl` does not exist here; use `wpctl`
  (`wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.5`, `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle`).
- **Brightness must go through logind.** `brightnessctl` direct writes are denied
  (not in the `video` group); `SetBrightness` on the session object works — and the
  caller must live in the *compositor's* session cgroup.
- **Wayland clients cannot position their own toplevels.** The panel is docked with
  **wlr-layer-shell** (river speaks v4). `libgtk-layer-shell0` is installed but its GI
  typelib is not, so the C API is called through `ctypes`; the GObject pointer is
  `hash(widget)` (PyGObject's `__gpointer__` is a PyCapsule and cannot be cast).
- **GTK3 CSS has no `::after`/content** — waybar exits instantly on an invalid
  selector. Themed buttons and sliders also paint their own background over your CSS:
  add `background-image: none` (and `relief NONE` for buttons).
- **`show_all()` is a no-op on a widget with `no_show_all`** — widgets kept out of the
  initial reveal (the panel's back button) and rows added *after* `show_all()` need an
  explicit `show()`. `Gtk.ListBoxRow` also has no `activated` signal: listen to
  `row-activated` on the `Gtk.ListBox`.
- **Never use a bare `nmcli device wifi list` in UI code** — it implicitly rescans and
  blocks ~8 s (the panel looked frozen). Read the cache with `--rescan no` and kick
  `nmcli device wifi rescan` in the background.
- **libinput preferences can't be set from udev** (those `LIBINPUT_*` properties are
  hardware quirks). Use `riverctl input` — see the touchpad block in `config/river/init`.
- **`click-method none` does not stop physical buttons.** libinput still forwards
  the clickpad's BTN_LEFT, so a daemon that "replaces" clicks would double every
  press. `gestures.py` mirrors the pad through a non-clickpad uinput clone instead;
  libinput ignores non-left buttons only on *clickpads*, so the clone can carry the
  translated left/right button.
- **`/dev/uinput` is not covered by logind's uaccess ACL** (it is `misc`, not
  `input`). The gesture daemon needs the udev rule in `udev/`; without it it exits
  cleanly after logging the fix, leaving the stock touchpad untouched.
- **A grabbed evdev fd is released by the kernel when the process dies.** That is
  why `gestures.py` can never leave a dead touchpad: worst case river goes back to
  the physical pad with stock clickfinger.
- **A GtkBox has no "box" style class** — `.box.panel` never matches; use `.panel`.
- **dash needs `; }`** to close a one-line function body (`f() { echo hi }` is a
  syntax error that swallows the rest of the file).
- **Ubuntu ships a `waybar.service`** that restart-storms at every login transition
  (no layer-shell compositor to attach to) — it is masked by `install.sh`.
- **Never `pkill -f` a pattern that appears in your own command line** — it matches
  the shell running it.

Full troubleshooting history: [PROGRESS.md](PROGRESS.md).

---

## Notes

- The bar renders on **every** output; the panel docks to the monitor under the pointer.
- **Touchpad = GNOME parity** (`config/river/init`): tap-to-click (2-finger tap =
  right click), clickfinger, natural scrolling, palm rejection, tap-and-drag,
  pointer speed `pointer-accel 0.2` (libinput's 0.0 default felt too slow; touchpad
  only), and a scroll factor of your choice — the touchpad only, so any external
  mouse keeps its normal wheel direction and rate. Tune the scroll speed live with
  `~/.config/river/scroll-speed.sh <factor>` (1.0 = stock, 0.3 = current).
- **Touchpad gestures** (`config/river/gestures.py`):
  3-finger tap = back, 4-finger tap = forward, 3-finger swipe up/down = volume,
  and physical clicks map 1 finger = left, 2 or 3 fingers = right. The daemon
  mirrors the pad through uinput so libinput keeps doing acceleration, palm
  rejection, DWT, tap-to-click, 2-finger scrolling and tap-and-drag.
  One documented side effect: libinput still emits its own **middle click on a
  3-finger tap** (plus the back action); 1/2-finger taps are untouched.
  Install the udev rule once (the daemon is already spawned by `init`):
  ```sh
  sudo install -m 0644 udev/70-river-classic-input.rules /etc/udev/rules.d/
  echo uinput | sudo tee /etc/modules-load.d/river-classic-uinput.conf
  sudo modprobe uinput
  sudo udevadm control --reload
  sudo udevadm trigger --subsystem-match=input
  sudo udevadm trigger --sysname-match=uinput
  ```
  Then log out/in so `init` starts the daemon (if it previously exited with
  code 3, waiting alone will not restart it). Check
  `~/.local/state/river-classic/gestures.log` and `riverctl list-inputs`
  (a second `...Touchpad` device appears while the mirror is active).
  `python3 ~/.config/river/gestures.py --selftest` runs the engine tests without
  hardware; `--off` restores stock clickfinger if an old daemon was interrupted.
- The `Z`-icon in the tray is the ZCode editor registering a tray item.
- Everything is hot-editable: `riverctl map ...` for keybinds, the CSS for the bar,
  the Python for the panel — no recompile, no relogin.
