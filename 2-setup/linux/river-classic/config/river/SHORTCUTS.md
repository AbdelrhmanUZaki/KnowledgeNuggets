# river-classic shortcuts

**Open this file:** `Super+F1` or `Super+Shift+/` (the `?` key).
The same file lives at `~/.config/river/SHORTCUTS.md`; the live bindings are
defined in `~/.config/river/init`.

`Super` is the Windows key. The menu key is mapped to `Super` too.
Tags are on **Alt**, matching the old dwm setup.

---

## Windows and tags

| Keys | Action |
|---|---|
| `Alt+1` … `Alt+9` | view tag 1–9 |
| `Alt+0` | view all tags |
| `Alt+Tab` | toggle current ↔ previous tag set (dwm `view(0)`) |
| `Alt+1…9` / `Super+1…9`, `Alt+0` / `Super+0` | view tag / all tags (instant river binds) |
| `Alt+Shift+1…9` / `Super+Shift+1…9` | move the focused window to that tag |
| `Alt+Shift+0` | put the focused window on every tag |
| `Alt+Ctrl+1` … `Alt+Ctrl+9` | also show tag n (multi-view) |
| `Alt+Shift+Ctrl+1` … `Alt+Shift+Ctrl+9` | toggle that tag on the focused window |
| `Super+J` / `Super+K` (or `Alt+J/K`) | focus next / previous window |
| `Super+Shift+J` / `Super+Shift+K` (or `Alt+Shift+J/K`) | swap focused window next / previous |
| `Super+Z` (or `Alt+Return`) | zoom (promote focused window to master) |
| `Super+H` / `Super+L` (or `Alt+H/L`) | shrink / grow the master area |
| `Super+Shift+H` / `Super+Shift+L` | fewer / more master windows |
| `Super+Up/Down/Left/Right` (or `Alt+Shift+arrows`) | move the master area |
| `Super+Alt+Shift+H` / `L` | resize window horizontally (− / + 100 px) |
| `Super+Alt+Shift+J` / `K` | resize window vertically (+ / − 100 px) |
| `Super+Q` (or `Alt+Q`) | close the focused window |
| `Super+Shift+Space` / `Alt+Shift+Space` | toggle floating |
| `Super+F` / `Alt+Shift+F` | toggle fullscreen |
| `Super+Period` / `Super+Comma` (or `Alt+Period/Comma`) | focus next / previous monitor |
| `Super+Shift+Period` / `Super+Shift+Comma` (or `Alt+Shift+Period/Comma`) | send window to next / previous monitor |
| `Super+Left` drag | move a view |
| `Super+Right` drag | resize a view |
| `Super+Middle` click | toggle floating |

## Launchers, panels and session

| Keys | Action |
|---|---|
| `Super+P` / `Alt+P` | app launcher (fuzzel) |
| `Super+Return` | terminal (foot) |
| `Alt+I` | Brave browser |
| `Alt+T` | new tab in Brave |
| `Super+Shift+Return` | terminal (foot, dwm-style) |
| `Super+V` | clipboard manager (CopyQ 17: text, images, search, pins) |
| `Super+F1` or `Super+Shift+/` | show this cheat sheet |
| `Alt+Escape` / `Super+Escape` / `Super+Alt+L` | lock the session |
| `Super+Shift+E` | log out of river (returns to GDM) |
| `Alt+B` | show / hide the bar |
| `Super+Space` | switch keyboard layout (US ↔ Arabic) |
| `Caps` | tap = Esc; hold = scroll layer (kanata) |
| `Menu` | acts as `Super` |

The System Menu is the GTK panel opened by clicking the battery, network,
Bluetooth or power area of the bar. It holds Wi-Fi, Bluetooth, power profile,
dark mode, DND, screenshots, volume, brightness and the session buttons.

## Screenshots, media and brightness

| Keys | Action |
|---|---|
| `Print` | full-screen screenshot → clipboard |
| `Super+Shift+Print` | region screenshot → clipboard |
| `XF86AudioPlay` / `Pause` | play / pause |
| `XF86AudioNext` / `Prev` | next / previous track |
| `XF86AudioRaiseVolume` / `LowerVolume` | volume ±5 % |
| `XF86AudioMute` | mute / unmute |
| `XF86MonBrightnessUp` / `Down` | brightness ±2 % |

Volume and brightness keys also work while the session is locked.

## Touchpad

| Gesture | Action |
|---|---|
| 1-finger tap / press | left click |
| 2-finger tap / press | right click |
| 3-finger tap | back (`BTN_SIDE`) |
| 4-finger tap | forward (`BTN_EXTRA`) |
| 3-finger swipe up / down | volume + / − |
| 4-finger swipe up / down | brightness + / − |
| 2-finger drag | natural scroll (touchpad only; a mouse wheel is unchanged) |

The gesture daemon mirrors the pad through a non-clickpad uinput clone, so
libinput keeps acceleration, palm rejection and tap-to-click (disable-while-typing is off, see README)
and tap-and-drag. libinput's own middle click on a 3-finger tap is suppressed
by injecting a phantom 4th touch during the gesture (libinput's tap state
machine goes DEAD), so a 3-finger tap only ever goes back.
`python3 ~/.config/river/gestures.py --selftest` runs the engine + phantom
tests; `--off` restores stock clickfinger.

## Kanata keyboard layer

| Keys | Action |
|---|---|
| `Space` held + `H/J/K/L` | arrow keys |
| `Space` tapped | normal space |
| `Caps` tapped | Esc |
| `Caps` held + `H/J/K/L` | scroll left / down / up / right |
| `Caps` held + `D/E` | scroll down / up (normal step) |
| `Caps` held + `C/S` | fast scroll down / up (3× step) |
| `Caps` held + `F/W` | scroll right / left |
| `Caps` held + `U` | fast scroll up |
| `Caps` held + `G` | top; double-tap `G` = bottom |
| `Lctl` + `Space` + `Esc` | emergency: exit kanata |

The config is `~/.config/kanata/kanata.kbd`, linked from the repo. Kanata reads
the keyboard directly, so the input udev rule must be installed
(`sudo ./install.sh rules`).

## Locking and recovery

- Lock from the System Menu, with `Super+Escape`, or from the keyboard-only
  fallback menu. All of them call the same `lock-session.sh`.
- The lock screen is **gtklock** (GTK/PAM, live clock + date) over a blurred,
  darkened copy of the wallpaper, with an icon-only power bar (Switch user /
  power / reboot). Force the old **swaylock inside foot** path with
  `RIVER_LOCKER=swaylock` — that one gets a *static* clock baked into the
  image. GDM is the login manager, not an in-session locker: it can only start
  or end a session.
- **Switch user** (non-destructive, nothing in-app is closed) is in the
  System Menu / keyboard-only menu / power menu, and calls
  `config/river/switch-user.sh`: it releases the keyboard (kanata) and
  touchpad (gestures.py) grabs, then asks GDM for a fresh greeter. Returning
  to the session — by unlock or GDM's own re-auth — brings both grabbers back
  automatically (`input-session.sh` watches logind's Active state).
- `input-session.sh status` shows whether the grabbers are running or paused.
- If a locker ever leaves the screen black or solid and you cannot unlock,
  switch to a text VT (`Ctrl+Alt+F3`), log in, and run:

  ```sh
  ~/.config/river/unlock-session.sh
  ```

  This sends `unlock_and_destroy` through a new lock client; it only works while
  river believes the session is locked. Then switch back to the graphical VT.
- Logging out with `Super+Shift+E` runs the session cleanup and returns to GDM.
  Switch User (lock screen power bar) keeps this session alive on its own VT
  instead: it pauses the input grabs before asking GDM for a greeter, so the
  greeter isn't blocked by them.
