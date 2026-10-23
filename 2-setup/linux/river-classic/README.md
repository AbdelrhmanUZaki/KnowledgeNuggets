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
./install.sh          # deps (sudo) → CopyQ 17 → build wlroots + river → GDM entry → config
```

Then **log out** of GNOME and pick **river-classic** in the gear menu.

Phases can be run separately: `./install.sh deps | copyq | build | session | rules | config`.

`deps` installs the runtime packages used by the keybinds and panel (bar,
terminal, launcher, notifications, wallpaper, screen capture, portals, fonts,
power profiles, audio) plus the build toolchain.

`./install.sh copyq` downloads the CopyQ 17.0.0 AppImage (44 MB, SHA-512
pinned) to `~/.local/opt` and creates `~/.local/bin/copyq`. It is deliberately
not the APT package: Ubuntu 26.04 ships 13.0.0, which crashes when restoring
large images under Qt 6.10/Wayland.

Re-apply the river config at any time:

```bash
./restore.sh          # links ~/.config/{river,waybar,foot,dunst}; links ../kanata.kbd; copies the wallpaper
```

This is separate from `2-setup/linux/restore.sh`, which restores the shared
shell, git, tmux and editor configs.

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

The two network indicators name what they are connected to, so the bar alone
answers "am I online, and on what?":

| state | Wi-Fi | Bluetooth |
|---|---|---|
| connected | `📶 OrangeDSL-batekh` | `ᛒ soundcore R50i VI` |
| radio on, nothing connected | `📶 offline` | `ᛒ no device` |
| radio off | `📶 off` (grey) | `ᛒ off` (grey) |

`{essid}` and `{device_alias}` are waybar's own placeholders, so this costs
nothing to maintain; the tooltips keep the details (signal strength, IP).
`kill -USR2 $(pgrep -x waybar)` reloads the bar config without a restart.

Next to them the bar carries the **system numbers**: CPU load, RAM use, the CPU
package temperature and, right after the Wi-Fi name, the **network speed**
(`↓`/`↑`). The speed is a custom module (`config/waybar/netspeed.sh`) rather
than the network module's own placeholders because its output is a fixed
15-character string in a monospace font: the numbers change every 2 s, and a
label whose width changed would drag the whole right-hand cluster of the bar
with it. The temperature is the same story in reverse — a small custom module
(`config/waybar/temp.sh`) because the kernel renumbers `hwmonN`/`thermal_zoneN`
between boots, and the script looks the sensor up by name. waybar's own `cpu`
and `memory` modules do the rest.

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
| `config/river/init` | session bootstrap: paths, dbus env, keybinds, kanata autostart, CopyQ setup, bar/dunst/swaybg, rivertile |
| `install-copyq17.sh` | downloads CopyQ 17.0.0 AppImage to `~/.local/opt`, verifies SHA-512, creates `~/.local/bin/copyq` |
| `config/foot/foot.ini` | terminal font size (14 pt default; `ctrl+=` / `ctrl+-` zoom live) |
| `config/dunst/dunstrc` | notifications — Noto Sans 14, white cards, gold 3px frame (ported from the dwm setup) |
| `config/river/system-panel.py` | the System Menu (GTK3, PyGObject) — tiles, live sliders, session row; **fully async** (no blocking shell calls) |
| `config/river/quick-settings.sh` | entry point for the panel (falls back to the dmenu) |
| `config/river/quick-settings-dmenu.sh` | keyboard-only fallback menu |
| `config/river/wifi-pick.sh` / `wifi-connect.sh` | network picker + password prompt (the secret goes in over stdin, never on the command line) |
| `config/river/media-key.sh` | MPRIS play/pause/next via dbus (no playerctl needed) |
| `config/river/gestures.py` | multi-finger gestures: 3-tap back, 4-tap forward, 3-swipe volume, 4-swipe brightness, physical press 1 = left / 2–3 = right |
| `config/river/tag-switch.sh` | tag switching + **Alt+Tab history** (dwm's `view(0)` two-slot toggle between the current and previous tag set) |
| `config/river/scroll-speed.sh` | touchpad scroll speed: live apply + persist in `init` |
| `config/river/unlock-session.sh` | releases a session that river left locked (black screen recovery) |
| `config/river/screenshot.sh` | grim + slurp region/full capture, auto clipboard |
| `config/river/copyq-setup.sh` | CopyQ preferences + the automatic re-own command (idempotent; run by `init`) |
| `config/river/copyq-keep.js` | CopyQ script: re-own each selection so text/images survive the source app closing |
| `config/river/power-menu.sh` | session actions (also available in the panel) |
| `config/waybar/config.jsonc` | bar layout, module formats, click actions |
| `config/waybar/style.css` | the solarized dark theme (GNOME-style flat surface) |
| `config/waybar/brightness.sh` | brightness via **logind** `SetBrightness` (±2% / absolute, `bump` for gestures) |
| `config/waybar/notify.sh` | DND indicator (visible only while DND is on) |
| `config/waybar/temp.sh` | CPU package temperature for the bar (finds the sensor by name) |
| `config/waybar/netspeed.sh` | ↓/↑ throughput for the bar, fixed width so nothing moves |
| `config/waybar/bt-toggle.sh` | Bluetooth adapter power (also `status` mode) |
| `PLAN.md` | reviewed plan for the menu rework (async panel, Wi-Fi/Bluetooth flows, live sliders, 4-finger brightness) |

---

## Keybindings

Tags are on **Alt** (dwm muscle memory), not Super.

| Keys | Action |
|---|---|
| `Alt+1..9` | switch to tag · `Alt+0` = all tags |
| `Alt+Shift+1..9` | **move the focused window to that tag** · `Alt+Shift+0` = on every tag |
| `Alt+Ctrl+n` | also show tag n (multi-view) |
| `Alt+Tab` | toggle current ↔ previous tag set (dwm `view(0)`) |
| `Alt+T` | terminal (foot) |
| `Super+Shift+Return` | terminal (foot, dwm-style) |
| `Super+P` | launcher (fuzzel) |
| `Super+V` | clipboard manager (CopyQ 17: text, images, search, pins) |
| `Super+Space` | switch keyboard layout (US ↔ Arabic; `Caps` = Esc, `Menu` = Super) |
| `Super+Shift+Space` | toggle floating |
| `Super+F` | toggle fullscreen |
| `Super+Return` | zoom / `Super+H` `Super+L` master ratio · `Super+Shift+H/L` master count |
| `Super+Q` | close · `Super+Shift+E` exit river |
| `Super+Period` / `Super+Comma` | switch monitor |
| `Alt+B` | show/hide the bar (waybar's SIGUSR1 toggle) |
| `Print` / `Super+Shift+Print` | screenshot full / region |
| `XF86AudioPlay/Pause/Next/Prev` | media keys |

> Browser caveat: Firefox/Chromium also use `Alt+<number>` for tab switching — the
> compositor wins the race.

### Keyboard remap (kanata)

`space` held = arrows (`h/j/k/l`), `space` tapped = a normal space. `caps` tapped =
Esc; `caps` held = vim scroll (`j/k` scroll, `d/e` page, `c/s` fast, `g` top,
double-tap `g` bottom). The config is `../kanata.kbd` (shared with the other Linux
machines), linked to `~/.config/kanata/kanata.kbd`; `init` starts kanata when it
is installed. It reads the keyboard directly, so the keyboard half of the udev
rule is required (`sudo ./install.sh rules`). Emergency exit: hold
`lctl`+`spc`+`esc`.

### Clipboard

`Super+V` toggles the **CopyQ 17** window: searchable history (newest first),
text, images, pinned items and tags. Select an item with Enter or double-click;
CopyQ copies it, closes the window and returns focus to the previous app, where
you paste with `Ctrl+V`. There is no tray icon and no notification; the panel's
clipboard button opens the same window.

CopyQ is a Qt app using Qt's light default style, and river 0.3 has no
per-window rules, so it opens as a normal tiled window rather than a popup.
`Super+Shift+Space` toggles floating if you prefer a separate window; the
clipboard behavior is unaffected.

**Persistence:** Wayland normally drops a selection when the app that owns it
exits. CopyQ's monitor stores the history, but storing alone does not keep the
selection alive. `copyq-keep.js` installs a CopyQ automatic command that re-owns
every new selection through `copy(item)`; CopyQ then owns it until the next
copy, so text and images survive the source closing. The re-copy marks the item
`application/x-copyq-owner` and the command aborts on that marker, so it cannot
loop. It keeps all non-image MIME types plus one image type, avoiding Qt's
synthetic image-conversion explosion. Verified with text and several 1920×1200
PNGs: source killed → `wl-paste` / `wl-paste --type image` still return the
content, and restoring the image from history does not crash the server.

Use **CopyQ 17** (`~/.local/bin/copyq`), not Ubuntu's 13.0.0: 13 reads the
Wayland clipboard and stores images, but crashes when restoring large images
after the first one (Qt 6.10/river). `./install.sh copyq` installs the 17.0.0
AppImage with a pinned SHA-512 (`install-copyq17.sh`). CopyQ keeps its data in
`~/.local/share/copyq`; v17 migrated the old v13 profile on first run. The
window/paste settings are applied at login by `copyq-setup.sh`. Images are
re-encoded by Qt on restore (the 1×1 test PNG went 70 → 91 bytes; screenshots
keep their dimensions), so the visual content is preserved, not necessarily the
original bytes.

Everything copied is in the history, **passwords included**. Delete sensitive
items in the CopyQ window (select + Delete); clearing all:
`copyq eval 'for (var i=count()-1;i>=0;--i) remove(i)'`.

## Switching back to GNOME safely

GNOME stays the fallback session.  Most of what this setup changes is
session-scoped, but there are two cross-session traps:

- **`KillUserProcesses=false`** is set by logind here.  A river child is not
  guaranteed to die when the session ends.  In particular, a surviving
  `kanata` or `gestures.py` keeps an evdev/uinput grab and can make GDM or
  GNOME's keyboard/touchpad unusable.  `init` launches `session-cleanup.sh`
  twice: once through `systemd-run --user` (in `user@1000.service`,
  **outside** `session-*.scope`) and once as a session-scope copy.  The
  session copy is important because logind *abandons* the session scope when
  `KillUserProcesses=false`; it survives a user-manager stop that would take
  the `systemd-run` copy with it.  Running both is idempotent.  When river
  exits either copy stops the gesture loop, kanata, waybar, swaybg, dunst,
  rivertile and a detached CopyQ, then stops the `xdg-desktop-portal*` user
  services.  That releases the input grabs and lets GNOME activate its own
  portal backend.
- **The packaged `kanata.service` is system-wide.**  It expects
  `/etc/kanata/config.kbd` and the `_kanata` user; it must stay disabled.
  `install.sh` now disables and resets it automatically.  Only the
  per-session instance started by river's `init` should run.

The preceding `init` had a real bug here: `$PPID` points at a short-lived
`sh -c` wrapper, not river, and that wrapper can be a zombie.  A zombie still
answers `kill(pid, 0)`, so the old gesture/kanata watchers never fired.  The
compositor PID is now resolved by walking to the real `river` process, and
`gestures.py` treats a zombie parent as gone.

Shared user state is intentionally persistent: GNOME color-scheme, power
profile, Wi-Fi/Bluetooth radio state, saved network/Bluetooth profiles and
CopyQ history.  These are not failures, but GNOME may start in the state you
last selected in river; change them in GNOME if you want the previous state.

Use GDM's **Log Out** (or `Super+Shift+E` in river), not **Switch User**, when
going back to GNOME.  The cleanup runs when river exits; an evdev grab is
global, so a river session left logged in on another VT can still affect the
new session.

### Verify the handoff

Run this in a GNOME terminal after logging in:

```sh
echo "desktop=$XDG_CURRENT_DESKTOP session=$XDG_SESSION_TYPE display=$WAYLAND_DISPLAY"
systemctl --user show-environment | grep -E '^(XDG_CURRENT_DESKTOP|XDG_SESSION_TYPE|WAYLAND_DISPLAY)='
pgrep -a -x kanata || true
pgrep -af '[g]estures.py' || true
pgrep -a -x copyq || true
pgrep -a -x CopyQ || true
pgrep -a -x waybar || true
pgrep -a -x swaybg || true
pgrep -a -x rivertile || true
pgrep -a -x dunst || true
systemctl --user list-units 'xdg-desktop-portal*' --all --no-pager
systemctl is-enabled kanata.service
systemctl is-active kanata.service
```

Expected: `XDG_CURRENT_DESKTOP` contains `GNOME`, the user-manager environment
shows the same GNOME values (not `river-classic`), the `pgrep` commands produce
no river processes, `kanata.service` is `disabled`/`inactive`, and the portal
chain is active for GNOME (`xdg-desktop-portal-gnome.service` may stay
inactive until the first portal request; `-wlr` must not be serving GNOME).
Then test the things a stale river session would break: GDM/GNOME login,
keyboard and touchpad, a file chooser, screenshot/screen sharing, clipboard,
audio, notifications, lock and suspend.

If `systemctl --user show-environment` still says `river-classic`, import the
GNOME values from the GNOME terminal and restart the portal chain:

```sh
systemctl --user import-environment XDG_CURRENT_DESKTOP XDG_SESSION_TYPE WAYLAND_DISPLAY
systemctl --user stop xdg-desktop-portal.service xdg-desktop-portal-gtk.service \
  xdg-desktop-portal-wlr.service xdg-desktop-portal-gnome.service
```

The next portal request starts the correct backend.  If a river process is
still present, the cleanup watcher did not run; make sure
`~/.config/river/session-cleanup.sh` is executable and that the next river
login logs `compositor exited; cleaning river-classic processes` in
`~/.local/state/river-classic/session-cleanup.log`.  A one-time system-unit
cleanup still needs sudo:

```sh
sudo systemctl reset-failed kanata.service
```

---

## Gotchas worth knowing (all hit during the build)

- **`riverctl map … spawn` takes one command string, not argv.** `spawn
  "/path/script arg"` works; `spawn "/path/script" arg` is accepted by `map` but
  fails on every keypress with `error(command): spawn: too many arguments` in
  river's log (the screenshot and CopyQ binds both pass one quoted string).
  River's own environment does **not** include `~/.local/bin` — the `PATH`
  export at the top of `init` only reaches its children — so the CopyQ bind
  uses the absolute `$HOME/.local/bin/copyq`.
- **Use CopyQ 17, not the APT 13.0.0.** 13.0.0 reads the Wayland clipboard and
  stores text/images, but restoring a large image after the first one crashes
  the server (`ERROR: Connection lost!`) and its own image restore can duplicate
  history items. 17.0.0 (AppImage, bundled Qt 6.11.1) survives repeated
  1920×1200 PNG restores with a stable item count.
- **A CopyQ re-own command must ignore CopyQ's own selections.** `copy(item)`
  adds `application/x-copyq-owner`; `copyq-keep.js` aborts when that MIME is
  already present, and copies only the useful formats (text/HTML/URI plus one
  image) instead of every Qt image conversion. Re-copying the full conversion
  set into CopyQ 13's own image selection was what killed the server.
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
  cleanly after logging the fix, leaving the stock touchpad untouched. Stock
  Ubuntu's `70-uaccess.rules` also tags only joysticks, so keyboards stay
  `root:input` — the same rule grants `plugdev` read access to
  `ID_INPUT_KEYBOARD` event nodes for **kanata** (space/caps layers).
- **A grabbed evdev fd is released by the kernel when the process dies.** That is
  why `gestures.py` can never leave a dead touchpad: worst case river goes back to
  the physical pad with stock clickfinger.
- **logind has no `/session/self`** for `SetBrightness`; call it on the real
  `$XDG_SESSION_ID`. Also, `loginctl show-session -p Active -p Seat -p User --value`
  prints properties in its own order (User, Seat, Active), not the `-p` order —
  query each property separately when matching a session.
- **PyGObject cannot finish an async `Gio.bus_get`** (`call_finish` needs an
  instance, but `g_bus_get` hands the connection over through the result) —
  use `Gio.bus_get_sync` (a local socket connect, ~7 ms) and keep it lazy.
- **`GetManagedObjects` delivers its values already unpacked**, while
  `PropertiesChanged` delivers them as `GLib.Variant` — accept both, or every
  property silently reads as "false".
- **The object manager lives on the root path** `/` of `org.bluez`, not on
  `/org/bluez`; the agent manager is the one on `/org/bluez`.
- **`Gio.DBusConnection.register_object` is deprecated**; the replacement
  `register_object_with_closures2` takes one argument more (the user data).
- **A GtkBox has no "box" style class** — `.box.panel` never matches; use `.panel`.
- **dash needs `; }`** to close a one-line function body (`f() { echo hi }` is a
  syntax error that swallows the rest of the file).
- **Ubuntu ships a `waybar.service`** that restart-storms at every login transition
  (no layer-shell compositor to attach to) — it is masked by `install.sh`.
- **Never `pkill -f` a pattern that appears in your own command line** — it matches
  the shell running it.
- **river's session lock can strand the session**: `LockManager.handleDestroy()` does not
  unlock when the lock client dies, so killing a locker (or a locker that has no tty to
  read the password from) leaves **a black screen with only the cursor**, and a VT switch
  does not help — the state lives in the compositor. The session button therefore starts
  `foot -e swaylock` (foot provides the tty) instead of a bare `swaylock`. If you ever
  land in the black state, `~/.config/river/unlock-session.sh` releases it: it asks the
  compositor for the lock, waits for the `locked` event (which river sends immediately to
  a new client when the session is already locked) and sends `unlock_and_destroy` — the
  only request that makes river leave the locked state. It needs `gcc`,
  `wayland-scanner`, `libwayland-dev` and `wayland-protocols`, and it only works **while
  the session is locked**.

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
  3-finger tap = back, 4-finger tap = forward, **3-finger swipe up/down = volume,
  4-finger swipe up/down = brightness**, and physical clicks map 1 finger = left,
  2 or 3 fingers = right. The daemon mirrors the pad through uinput so libinput
  keeps doing acceleration, palm rejection, DWT, tap-to-click, 2-finger scrolling
  and tap-and-drag. The swipe reference restarts whenever the finger count
  changes, so a palm landing mid-gesture cannot bend it, and the steps are
  batched into one `brightness.sh bump` / `wpctl` call per frame.
  One documented side effect: libinput still emits its own **middle click on a
  3-finger tap** (plus the back action); 1/2-finger taps are untouched.
  Install the udev rule once (it covers the gesture daemon **and** kanata; both
  are spawned by `init`):
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
- **System menu** (`config/river/system-panel.py`): every external command runs
  through `Gio.Subprocess`, so **nothing blocks the GTK thread** — the menu
  paints instantly and the tiles fill in as the answers arrive.
  - *Wi-Fi*: the list comes from the NetworkManager cache (kept on disk, so it
    shows up immediately) and is refreshed in the background; "rescan" runs
    asynchronously and shows a **Scanning…** row. Clicking a network connects
    it when it is **saved or open**; a **secured network without a saved
    profile** opens an in-panel password dialog (masked, show/hide, inline
    error, retry). The secret is handed to `nmcli` over stdin, so it does not
    appear in the process list. Enterprise networks open
    `nm-connection-editor`. A **saved** network carries a **forget** button:
    it asks for confirmation and then deletes the NetworkManager profile
    (password included) — you are asked for the password again next time.
  - *Bluetooth*: BlueZ over D-Bus — devices, discovery and pairing all live
    in the panel, and the panel exports an `org.bluez.Agent1`, so a device that
    asks for a **passkey, PIN or confirmation** gets an in-panel prompt
    instead of failing. Paired devices connect/disconnect, unpaired ones are
    paired first and then connected. A **paired** device carries an **unpair**
    button (with confirmation) that removes the device and its keys.
    `blueman-manager` stays available as the advanced fallback.
  - *The lists refresh themselves* (nothing runs when the panel is closed):
    opening the Wi-Fi page **scans immediately**, and then the page scans
    again every **15 s** while it is open — NetworkManager only learns about
    new APs after a real scan, so the cache alone is not enough. 15 s is the
    interval wpa_supplicant's own background scan uses, and it matters: a scan
    takes the radio off your AP's channel for a few seconds (measured here:
    ping to the gateway goes from 1.2 ms to ~42 ms, peak 109 ms, no loss), so
    scanning every 5 s would hurt games and calls. Bluetooth needs no polling
    (BlueZ pushes every change over D-Bus) and keeps **discovering
    continuously** while its page is open — BLE scanning is receive-only and
    does not touch the Wi-Fi link. The page title shows the state ("live
    (scan every 15s)" / "scanning…" / "live"), and the manual rows are still
    there for a one-off scan.
  - *Sliders*: volume and brightness apply **while you drag** (50 ms / 80 ms
    throttle, flushed on release) and show a live percentage; media keys and
    gestures are reflected while the panel is open.
  - Diagnostics: `~/.local/state/river-classic/panel.log`, and
    `RIVER_PANEL_OPEN=wifi|bt python3 ~/.config/river/system-panel.py` opens a
    page directly. `python3 ~/.config/river/system-panel.py --check` runs the
    parser self-test without a display.
- The `Z`-icon in the tray is the ZCode editor registering a tray item.
- Everything is hot-editable: `riverctl map ...` for keybinds, the CSS for the bar,
  the Python for the panel — no recompile, no relogin.
