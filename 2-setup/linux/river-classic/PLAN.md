# river-classic — System Menu, Wi-Fi/Bluetooth flows, live sliders, 4-finger brightness

**Status:** **implemented** (see §10 for what landed and where it deviates)
**Date:** 2026-07-22 (plan) · implemented 2026-07-22
**Scope:** `config/river/system-panel.py`, `config/river/wifi-connect.sh`, `config/river/wifi-pick.sh`,
`config/river/gestures.py`, `config/waybar/brightness.sh`, docs
**Related:** [README.md](README.md) (design contract, file table), [PROGRESS.md](PROGRESS.md) (master log)

This document is the reviewed version of the plan agreed in the session of 2026-07-22.
Section 0 records what changed during the review and which claims were re-verified on this
machine, so the implementation does not have to rediscover them.

---

## 0. Review notes

### 0.1 Corrections to the draft diagnosis

| Draft claim | Reviewed reality |
|---|---|
| "the panel is slow because every state read is a blocking subprocess" | **Partly wrong.** The tile refresh commands are cheap: `nmcli` cached queries 0.02 s, `bluetoothctl show` 0.01 s, `dunstctl` 0.00 s, `gsettings` 0.00 s, `wpctl get-volume` 0.02 s, `powerprofilesctl get` 0.20 s. |
| "the menu lags" | The real freezes are two specific calls on the GTK main thread: (1) `nmcli device wifi rescan` in `_fill_wifi_list(rescan=True)` — auto-triggered **500 ms after the Wi-Fi page opens** whenever the cached list has ≤ 2 networks; (2) `nmcli device wifi connect` attempted synchronously in `_connect_wifi` with an 8 s `subprocess.run` timeout. Everything else is fast but still blocks the loop, so the async rework is still required — it is just not the whole story. |
| "bluetoothctl info per device is slow" | With one paired device it is 0.01 s. It is O(devices) and serial, so it *will* degrade; it is not the current bottleneck. Replacing it with one D-Bus `GetManagedObjects` call is still the right move. |

### 0.2 Verified on this machine (do not re-verify, just use)

Tooling and libraries present:

- `nm-connection-editor`, `blueman-manager`, `foot`, `bluetoothctl` (BlueZ **5.85**), `busctl`,
  `gdbus`, `nmcli` (**1.54.3**), `wpctl`, `powerprofilesctl`, `dunstctl`, `gsettings` — all installed.
- Python: `gi` (PyGObject), `dbus` (python-dbus) available; `pydbus` absent.
- PyGObject surface confirmed present:
  `Gio.Subprocess.new`, `communicate_utf8_async`, `communicate_utf8_finish`, `force_exit`;
  `Gio.SubprocessFlags.{STDIN_PIPE,STDOUT_PIPE,STDERR_PIPE}`;
  `Gio.DBusConnection.register_object`, `signal_subscribe`; `Gio.DBusNodeInfo.new_for_xml`;
  `Gio.bus_get_sync`; `GLib.Variant.unpack`.

BlueZ D-Bus surface confirmed by introspection (`busctl --system introspect org.bluez …`):

- `org.freedesktop.DBus.ObjectManager` on `/` of `org.bluez`: `GetManagedObjects() → a{oa{sa{sv}}}`,
  plus the `InterfacesAdded` signal.
- `org.bluez.Device1`: `Pair()`, `Connect()`, `Disconnect()`, `ConnectProfile(s)`;
  properties `Address`, `Name`, `Paired`, `Connected`, `Trusted` (writable), `RSSI`.
  Object path example: `/org/bluez/hci0/dev_F4_B6_2D_E3_21_65`.
- `org.bluez.Adapter1`: `StartDiscovery()`, `StopDiscovery()`; properties `Powered` (writable),
  `Pairable` (writable), `PairableTimeout`.
- `org.bluez.AgentManager1`: `RegisterAgent(os)`, `RequestDefaultAgent(o)`, `UnregisterAgent(o)`.
- `org.bluez.Agent1` is **not** exported by BlueZ — the *client* (our panel) must export it.

Open item that must be tested with a real secured network:

- `nmcli --ask` reading a password from a **pipe** is unproven (a probe with a non-existent SSID
  fails with "No network with SSID" before any prompt). Plan for the argv fallback
  (`nmcli device wifi connect "<ssid>" password "<pw>"`), which briefly exposes the secret in
  `ps` on a local machine only.

### 0.3 Design decisions taken during the review

1. **Async everywhere, no threads.** Use `Gio.Subprocess` + `communicate_utf8_async`, callbacks on
   the GTK main loop. Avoid `ThreadPoolExecutor`: its non-daemon threads keep the panel process
   alive after `Gtk.main_quit()`, which would make `quick-settings.sh` (which waits for the panel
   process) hang until the last command finishes.
2. **In-panel modal overlay** for password/passkey/confirm dialogs instead of a separate toplevel:
   the panel is a wlr-layer-shell surface with `KEYBOARD_MODE_ON_DEMAND`, and a foreign toplevel
   would both steal focus (panel closes on focus-out) and fight the layer-shell keyboard mode.
3. **Bluetooth via D-Bus, not `bluetoothctl`.** One `GetManagedObjects` call replaces N
   `bluetoothctl info` calls, gives live `PropertiesChanged` updates, and is the only clean way to
   implement a pairing agent in-process.
4. **Keep the terminal fallbacks** (`foot -e wifi-connect.sh`, `blueman-manager`) but fix them —
   they are the escape hatch when the layer-shell keyboard or the D-Bus agent misbehaves.
5. **Do not touch the working gesture mapping.** 1-tap left, 2-tap right, 3-tap back, 4-tap forward,
   physical press 1 = left / 2+ = right, 3-finger swipe = volume, pointer speed 0.2, scroll factor 0.3.

---

## 1. Goals and non-goals

### Goals

1. The system menu opens and stays responsive; no external command runs on the GTK main thread.
2. Volume and brightness sliders change the real hardware **while dragging**, not after release.
3. Wi-Fi: connect with the right flow per network state, asking for a password only when required.
4. Bluetooth: pair and connect from the menu, prompting only when the device asks for it.
5. Add the missing **4-finger vertical swipe = brightness** gesture.

### Non-goals (explicitly out of scope)

- Enterprise (802.1X) Wi-Fi setup beyond handing off to `nm-connection-editor`.
- Persisting the panel between openings (a process per opening stays).
- A Bluetooth audio profile picker (`ConnectProfile` is not needed; `Connect()` suffices).
- Re-implementing libinput taps, palm rejection or DWT — the uinput clone design stays.

---

## 2. Current implementation: what is where

| Area | File / function | Current behaviour | Problem |
|---|---|---|---|
| Command execution | `system-panel.py: sh()` | `subprocess.run(..., capture_output=True, timeout=8)` on the GTK thread | blocks the UI; no cancellation; process lingers |
| Tile refresh | `system-panel.py: refresh()` | calls `wifi()`, `bt()`, `profile()`, `dark_mode()`, `dnd()` serially; `bt()` is called twice | blocking, duplicated work, slow first paint |
| Wi-Fi list | `system-panel.py: _fill_wifi_list()` | cached `nmcli list --rescan no`; if ≤ 2 networks, schedules `_fill_wifi_list(rescan=True)` after 500 ms, which runs `nmcli device wifi rescan` **synchronously** | multi-second freeze right after opening the Wi-Fi page |
| Wi-Fi connect | `system-panel.py: _connect_wifi()` | `nmcli device wifi connect <ssid>` with no password (8 s timeout), and on failure writes `wifi-chosen` and opens `foot -e wifi-connect.sh` | no password is ever requested; `wifi-connect.sh` also calls `nmcli` without `--ask`, so it fails too |
| Saved networks | — | not detected | the panel cannot tell "saved" from "unknown", so it always tries to connect first |
| Bluetooth list | `system-panel.py: bt_devices()` | `bluetoothctl devices` + one `bluetoothctl info <mac>` per device | O(n) serial calls, no discovery, no live updates |
| Bluetooth action | `system-panel.py: _bt_device()` | `bluetoothctl connect/disconnect` only | unpaired devices cannot be paired from the menu; no passkey/PIN handling |
| Sliders | `system-panel.py: _on_vol()`, `_on_bri()` | `GLib.timeout_add(120, apply)` restarted on every `value-changed` | one-shot **debounce**: only the final value is applied, after the drag ends |
| Slider sync | `system-panel.py: _sliders()` | values read once at construction; never refreshed | media keys / gestures are not reflected while the panel is open |
| Gestures | `gestures.py: _swipe_steps()` | requires exactly 3 fingers → volume; `TAP_ACTIONS = {3: back, 4: forward}` | a 4-finger vertical swipe does nothing |
| Brightness helper | `waybar/brightness.sh` | `up` / `down` / `set` via logind `SetBrightness` | no batched relative mode for gestures |
| Panel dismissal | `system-panel.py: _on_focus_out()`, `_dismiss_watch()` | close on focus-out / pointer leave | a modal dialog would trigger focus-out and close the panel |
| Launcher | `quick-settings.sh` | spawns a new panel process per click | a double click can open two panels |

---

## 3. Target behaviour

### 3.1 Wi-Fi (row click on the Wi-Fi sub-button page)

| Network state | Prompt? | Command | Feedback |
|---|---|---|---|
| already connected | no | none (offer Disconnect) | row shows "connected" |
| saved profile exists | no | `nmcli connection up id "<profile>"` | row shows "connecting…" → "connected" |
| open, no profile | no | `nmcli device wifi connect "<ssid>"` | as above |
| secured (WPA/WPA2/WPA3/WEP), no profile | **yes — password dialog** | `nmcli device wifi connect "<ssid>" password "<pw>"` | inline error on failure, retry allowed |
| enterprise / 802.1X | no single password | open `nm-connection-editor` | note in the page |

Password dialog: SSID + security shown, masked entry, show/hide toggle, Connect/Cancel,
Enter = Connect, Escape = Cancel, inline error text, spinner while connecting.

### 3.2 Bluetooth (row click on the Bluetooth sub-button page)

| Device state | Prompt? | Action |
|---|---|---|
| connected | no | `Device1.Disconnect()` |
| paired, not connected | no | `Device1.Connect()` |
| unpaired (discovered) | **only if the device asks** | `Device1.Pair()` → agent prompt if required → `Trusted = true` → `Device1.Connect()` |

Agent prompts: confirmation code (6 digits), passkey (host enters), legacy PIN, service
authorization. Adapter `Pairable: no` is fine for host-initiated pairing; the adapter is never
made discoverable automatically.

### 3.3 Sliders

- Apply continuously while dragging (throttled), flush the final value on release.
- Show a live percentage next to each slider.
- Reflect external changes (media keys, gestures) while the panel is open.
- Never fight the user's drag.

### 3.4 Gestures (addition only)

| Gesture | Action | Status |
|---|---|---|
| 1-finger tap | left click | libinput, unchanged |
| 2-finger tap | right click | libinput, unchanged |
| 3-finger tap | back | working, confirmed by the user |
| 4-finger tap | forward | working |
| 3-finger vertical swipe | volume | working |
| physical press 1 / 2+ fingers | left / right | working |
| **4-finger vertical swipe** | **brightness up/down** | **to be added** |

---

## 4. Implementation

### Phase 1 — async panel core, live sliders, fast first paint  *(done)*

**Files:** `config/river/system-panel.py`

#### 1.1 `CommandRunner` (new)

```python
class Command:
    """one async external command; callbacks run on the GTK main loop"""
    def __init__(self, runner, argv, cb, timeout=10, stdin=None): ...
    # Gio.Subprocess.new(argv, STDIN_PIPE|STDOUT_PIPE|STDERR_PIPE)
    # communicate_utf8_async(stdin_bytes, None, cb)
    # cb(stdout, stderr, rc, timed_out)
```

- `Gio.Subprocess.new` spawns synchronously but costs ~1 ms — acceptable.
- Timeout via `GLib.timeout_add_seconds` → `proc.force_exit()` → callback with `timed_out=True`.
- The runner keeps a set of live processes; `close()` force-exits them all.
- Every call site replaces a `sh()` invocation. `sh()` is removed from the GUI path; only direct
  sysfs/`os.path` reads stay on the main thread.

#### 1.2 State split

```python
self.state = {"wifi_on": None, "ssid": "", "bt_on": None, "profile": "balanced",
              "dark": False, "dnd": False, "volume": 0, "brightness": 0}
```

- `refresh_fast()` — battery, brightness sysfs, current tile state; no subprocess.
- `refresh_async()` — starts independent async reads; each callback patches one tile.
- `_on_show()` → `refresh_fast()` then `refresh_async()`; the panel paints immediately.
- Generation counters guard list fills; a `_alive` flag guards callbacks after close.

#### 1.3 Actions

Each tile/action becomes: optimistic UI update → async command → targeted refresh → revert on error.
`refresh()` loses the duplicated `bt()` call. `shell=True` launches are replaced by argv +
`Gio.Subprocess` without waiting (header buttons, session actions, `gnome-control-center`,
`nm-connection-editor`, `blueman-manager`, `swaylock`, `systemctl`).

#### 1.4 Sliders

```python
def _on_vol(self, scale):
    self._vol_target = int(scale.get_value())
    self._vol_label.set_text(f"{self._vol_target}%")
    if self._vol_timer is None:
        self._vol_timer = GLib.timeout_add(50, self._pump_vol)   # repeating, not one-shot

def _pump_vol(self):
    if self._vol_target == self._vol_applied:
        return True                       # idle, keep polling cheaply
    set_volume_async(self._vol_target)
    self._vol_applied = self._vol_target
    return True
```

- 50 ms throttle for volume, 80 ms for brightness (logind is slower).
- `button-release-event` / `drag-end` → flush the pending value and stop the timer.
- `set_volume` / `set_brightness` become async.
- Percentage labels added to the slider row.
- On show: read the real values and set the scales (`_updating` guard to avoid re-triggering).
- While visible: poll brightness sysfs every 500 ms and volume every 1 s; update the scale and the
  label **only when the user is not dragging** (`_dragging` flag) — otherwise the thumb fights the
  pointer.

#### 1.5 Tests

- Panel opens with no visible stall; a `nmcli`/`bluetoothctl` call in flight must not block the UI.
- Dragging volume changes `wpctl get-volume` continuously; same for brightness via sysfs.
- Media key / gesture changes are reflected in the open panel.
- No slider feedback loop.

**Commit:** `river-classic: async panel core + live volume/brightness sliders`

### Phase 2 — Wi-Fi flow  *(done)*

**Files:** `config/river/system-panel.py`, `config/river/wifi-connect.sh`, `config/river/wifi-pick.sh`

#### 2.1 List

- Open the page → show the cached list at once (async `nmcli … list --rescan no`).
- Remove the automatic blocking rescan. The explicit "rescan" row starts an **async**
  `nmcli device wifi rescan` (20 s timeout), shows a "Scanning…" row, and refreshes the list when
  it returns. No fixed 6 s `GLib.timeout_add` guesswork.
- Rows show: SSID, signal %, secured marker, and (once known) "saved" / "connected".

#### 2.2 Saved profiles and security classification

- `nmcli -t -f NAME,TYPE connection show` → for each `802-11-wireless` profile,
  `nmcli -g 802-11-wireless.ssid connection show "<profile>"` (quote properly; the draft's
  `for` loop broke on SSIDs containing spaces).
- Build `saved = {ssid: profile_name}`.
- Security from `nmcli -t -f …,SECURITY …`: empty/`--` → open; `WPA*`/`WEP` → personal;
  `802.1X` (nmcli renders it as e.g. `WPA2 802.1X`) → enterprise.

#### 2.3 Connect flow

Implement the decision table from §3.1. All `nmcli` calls are async with `--wait 30` and a 35 s
process timeout. Errors are surfaced from nmcli's stderr (strip the `Error: ` prefix) in the
dialog or as a row subtitle.

#### 2.4 Password dialog (in-panel)

- `Gtk.Overlay` around the panel root; a scrim + a dialog box (rounded, matching the panel CSS).
- `Gtk.Entry` (masked, `Gtk.InputPurpose.PASSWORD`), show/hide checkbox, Connect/Cancel,
  error label, spinner.
- While open: layer-shell keyboard mode → `EXCLUSIVE`; `_on_focus_out` and `_dismiss_watch` are
  suppressed by a `_modal` counter; restored on close. Escape closes the dialog first, the panel
  second.
- Secret handling: try `nmcli --ask --wait 30 device wifi connect "<ssid>"` with the password
  written to stdin (not yet proven — see §0.2); otherwise fall back to the `password` argument.

#### 2.5 Fallback scripts

`wifi-connect.sh` (currently broken — it claims to be interactive but has no `--ask`):

```sh
nmcli --ask --wait 30 device wifi connect "$ssid"
```

- accept the SSID as `$1`, keep the state file as a fallback;
- keep the notify + "press any key to close" behaviour.

`wifi-pick.sh` (fuzzel fallback): on a failed/unsaved selection, launch the fixed
`wifi-connect.sh` instead of silently failing.

#### 2.6 Optional

"Join hidden network…" row (SSID + security + password). Only after the core flow works.

**Commit:** `river-classic: correct Wi-Fi connect flow with in-panel password prompt`

### Phase 3 — Bluetooth via BlueZ D-Bus  *(done)*

**File:** `config/river/system-panel.py` (optionally a helper module next to it)

#### 3.1 Backend

- System bus connection (`Gio.bus_get_sync(Gio.BusType.SYSTEM, None)`).
- One `GetManagedObjects` call on `/` of `org.bluez`; filter `org.bluez.Device1`:
  `Address`, `Name`/`Alias`, `Paired`, `Connected`, `Trusted`, `Adapter`, `RSSI`, `UUIDs`.
- Subscribe to `InterfacesAdded` (discovery) and `PropertiesChanged` (connect/disconnect/pair
  state) with `signal_subscribe`; unsubscribe on close.
- Adapter: `/org/bluez/hci0` → `Powered`, `Pairable`, `StartDiscovery()`, `StopDiscovery()`.
- Device path convention: `/org/bluez/hci0/dev_<MAC with _ >`.

#### 3.2 Pairing agent

- Export `org.bluez.Agent1` on the system bus at e.g. `/org/riverclassic/agent` using
  `Gio.DBusConnection.register_object` + `Gio.DBusNodeInfo.new_for_xml`.
- `AgentManager1.RegisterAgent(path, "KeyboardDisplay")` then `RequestDefaultAgent(path)`.
- Methods and their dialogs:
  | Method | Dialog | Return |
  |---|---|---|
  | `RequestConfirmation(o)` | "Confirm code 123456 on <device>" — Confirm/Cancel | void / `org.bluez.Error.Rejected` |
  | `RequestPasskey(o)` | numeric entry (0–999999) | `u` |
  | `RequestPinCode(o)` | text entry | `s` |
  | `DisplayPasskey(o,u,u)` | show the code, "Pairing…" | void |
  | `RequestAuthorization(o)` | confirm | void |
  | `AuthorizeService(o,s)` | confirm | void |
  | `Cancel()` | dismiss any open prompt | void |
  | `Release()` | — | void |
- Prompts are **asynchronous**: store the `Gio.DBusMethodInvocation` and reply when the user
  answers. Cancelling the dialog returns `org.bluez.Error.Canceled`.
- If the panel closes mid-pairing, reply with `Canceled` so BlueZ does not hang.
- If registration or `RequestDefaultAgent` fails, fall back to `blueman-manager` for unpaired
  devices and say so in the page.

#### 3.3 Page UI

- Adapter off → row "Bluetooth is off" + "Turn on" (`Adapter1.Powered = true`).
- Sections: Connected / Paired / Available (during discovery).
- Rows: name, subtitle (`connected · click to disconnect`, `paired · click to connect`,
  `available · click to pair`), RSSI for discovered devices.
- "Scan for devices" / "Stop scanning" row; discovery auto-stops after ~20 s and always stops
  when the page or panel closes.
- "Open Bluetooth manager" row (blueman-manager) kept as the advanced fallback.

#### 3.4 Actions

- Connected → `Device1.Disconnect()`.
- Paired → `Device1.Connect()`.
- Unpaired → `Device1.Pair()` → on success `Trusted = true` → `Device1.Connect()`.
- All via async D-Bus calls; errors shown inline.

**Commit:** `river-classic: Bluetooth over BlueZ D-Bus with an in-panel pairing agent`

### Phase 4 — 4-finger brightness gesture  *(done)*

**Files:** `config/river/gestures.py`, `config/waybar/brightness.sh`

#### 4.1 `brightness.sh bump <signed-steps>`

```sh
bump) n=$((cur + step * $2)) ;;      # step = mx/50 ≈ 2 %
```

- One logind `SetBrightness` call per bump (no process per 2 %).
- `up` / `down` / `set` keep their current meaning — the waybar `backlight` module's
  `on-scroll` uses `up`/`down`, and the panel uses `set`.

#### 4.2 Engine changes (`gestures.py`)

- `SWIPE_FINGERS = {3: "volume", 4: "brightness"}`.
- `Engine.reset()` gains `swipe_kind = None`, `swipe_fingers = 0`.
- `feed_abs()`: a swipe may start with 3 **or** 4 fingers; the swipe reference point is reset
  whenever the finger count leaves {3, 4} or changes mid-gesture.
- `_swipe_steps()`:
  - vertical-dominant check with `SWIPE_LOCK` (1.6) as today;
  - `want = |dy| / (STEP_FRAC * y_range)`;
  - throttle: 40 ms for volume, 80 ms for brightness;
  - per-frame cap: 4 volume steps, 3 brightness steps;
  - returns **one** action with a magnitude: `[("brightness", step * n)]` so the dispatcher can
    batch it into a single `brightness.sh bump` call.
- `_finish()`: `swiping` already suppresses the tap → a 4-finger swipe never becomes "forward",
  and a 4-finger **tap** still becomes "forward".
- `dispatch()`: new `("brightness", ±n)` branch → `brightness.sh bump ±n`, spawned with
  `Popen` (non-blocking) so the gesture event loop is never stalled by logind; log the action.
- Direction: 4 fingers up → brighter, down → dimmer.

#### 4.3 Selftest additions (`python3 gestures.py --selftest`)

- 4-finger vertical swipe up → brightness +, no tap.
- 4-finger vertical swipe down → brightness −, no tap.
- 4-finger tap → forward (still).
- 3-finger swipe → volume (still), 3-finger tap → back (still).
- 4-finger swipe does **not** produce a forward tap.
- partial X-before-Y frame does not crash (existing regression case stays).

#### 4.4 Tuning

- Start at ~2 % brightness per 8 % of pad travel (`BRIGHT_STEP_FRAC = 0.08`).
- After physical testing, adjust `BRIGHT_STEP_FRAC` / `BRIGHT_HOLD_S`.

**Commit:** `river-classic: 4-finger vertical swipe controls brightness`

### Phase 5 — verification, docs, cleanup  *(in progress)*

- Re-verify the whole matrix in §5.
- README: new Wi-Fi/Bluetooth behaviour, 4-finger brightness, corrected note about the
  3-finger tap (confirm it is back-only and remove the stale "middle click" warning if confirmed).
- PROGRESS: entry 18 with the latency root causes, the async design, the D-Bus agent notes and
  the gesture tuning.
- Optional polish: single-instance panel (PID/lock) so a double bar click cannot open two panels.

**Commit:** `river-classic: document the new menu flows and gestures`

---

## 5. Acceptance checklist

**Panel**
- [ ] No `subprocess.run` / `sh()` left on the GTK main thread.
- [ ] Panel paints immediately; tiles fill in asynchronously.
- [ ] Opening the Wi-Fi page never blocks; a background scan shows "Scanning…".
- [ ] A second bar click does not open a duplicate panel (optional polish).

**Wi-Fi**
- [ ] Saved network → connects with no prompt.
- [ ] Open network → connects with no prompt.
- [ ] Secured, unsaved network → password dialog before any connection attempt.
- [ ] Wrong password → inline error, dialog stays open, retry works.
- [ ] Enterprise network → hands off to `nm-connection-editor`.
- [ ] `foot -e wifi-connect.sh` prompts for a password (fallback path fixed).
- [ ] Secret is not visible in `ps` if the stdin path works; otherwise it is accepted locally.

**Bluetooth**
- [ ] Paired device connects and disconnects.
- [ ] Unpaired device appears during a scan and can be paired.
- [ ] Confirmation-code, passkey and legacy-PIN prompts work; cancel is clean.
- [ ] Adapter off/on behaves; discovery always stops when the page/panel closes.
- [ ] If the agent cannot register, the page says so and offers `blueman-manager`.

**Sliders**
- [ ] Dragging volume changes the real volume continuously.
- [ ] Dragging brightness changes the real backlight continuously.
- [ ] Percentages update live; media keys and gestures are reflected while open.
- [ ] No jump-back while dragging.

**Gestures**
- [ ] 3-finger swipe = volume; 4-finger swipe = brightness.
- [ ] 4-finger tap = forward; 3-finger tap = back (back only, no middle click).
- [ ] 1/2-finger taps and physical clicks unchanged.
- [ ] `--selftest` passes, including the partial-MT-frame case.

**Regressions**
- [ ] Bar modules, tags, panel dismiss/escape, pointer speed 0.2, scroll factor 0.3 unchanged.
- [ ] `quick-settings.sh` still falls back to the dmenu if the panel cannot start.

---

## 6. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Layer-shell keyboard focus refuses the password entry | cannot type a password | in-panel overlay + `EXCLUSIVE` keyboard mode + dismiss suppression; `foot` fallback; test early in Phase 2 |
| `nmcli --ask` cannot read a password from a pipe | secret ends up in `ps` | argv fallback, local machine only; revisit with NetworkManager D-Bus `AddAndActivateConnection` if it matters |
| BlueZ agent prompts race the panel lifecycle | BlueZ waits forever | always reply to the invocation (including `Canceled` on close); unregister the agent on close |
| `RequestDefaultAgent` displaces another agent (blueman) | other tools lose pairing | register only while the Bluetooth page is open, unregister after |
| Async callbacks after the panel closed | crashes / use-after-free | `_alive` flag + generation counters + `close()` force-exits all processes |
| Discovery left running | battery/radio drain | stop discovery on page close, panel close and a 20 s timer |
| Too many brightness calls from the gesture | logind churn, input lag | 80 ms throttle, 3 steps/frame cap, one `bump` call per frame |
| D-Bus/Variant parsing bugs | wrong device states | read `GetManagedObjects` once at startup and log the parsed summary; compare against `bluetoothctl devices Paired/Connected` |
| Panel still feels slow because the process is spawned per click | first-open latency | measure after Phase 1; if needed, add a persistent panel with a socket toggle (deferred) |

---

## 7. Open decisions (defaults chosen so work can start)

| Decision | Default if unanswered | Notes |
|---|---|---|
| Wi-Fi prompt surface | in-panel dialog | terminal kept as fallback |
| Bluetooth pairing surface | in-panel D-Bus agent | `blueman-manager` fallback |
| 4-finger brightness gesture | vertical swipe up/down, 2 % per 8 % pad travel | tune after testing |
| Slider percentage labels | yes | small change, big clarity win |
| Save Wi-Fi profiles after a successful connect | yes (nmcli default) | matches GNOME behaviour |
| Auto-connect on join | nmcli default (`yes`) | |
| 3-finger tap middle click | keep back-only | user confirmed; README warning to be corrected after re-verification |
| Enterprise Wi-Fi | `nm-connection-editor` | |
| 4-finger horizontal swipe | unbound | avoid accidental actions |

---

## 8. Do not change

- Gesture mapping for taps and physical clicks; the uinput clone design and its udev rule.
- `pointer-accel 0.2`, `scroll-factor 0.3`, natural scroll, clickfinger, tap-button-map.
- The bar shows state only; actions live in the GTK system menu.
- `quick-settings.sh` → `system-panel.py` → dmenu fallback chain.
- No passwordless sudo; system changes stay in the documented `sudo` blocks.

---

## 9. Manual verification commands

```sh
# panel state and logs
tail -40 ~/.local/state/river-classic/gestures.log
ls -l ~/.local/state/river-classic/

# touchpad clone / gesture daemon
~/.local/bin/riverctl list-inputs
~/.local/bin/riverctl list-input-configs
python3 ~/.config/river/gestures.py --selftest

# volume / brightness
wpctl get-volume @DEFAULT_AUDIO_SINK@
~/.config/waybar/brightness.sh up && cat /sys/class/backlight/intel_backlight/brightness
~/.config/waybar/brightness.sh bump +3      # new in Phase 4

# wifi / bluetooth
nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list --rescan no
nmcli -t -f NAME,TYPE connection show
bluetoothctl devices Paired
bluetoothctl devices Connected
busctl --system call org.bluez / org.freedesktop.DBus.ObjectManager GetManagedObjects
```

---

## 10. Implementation notes (what actually landed)

Commits: `ef14343` (panel), `5e2cd9c` (gesture + scripts), plus the documentation commits.

### Landed as planned

| Plan item | Where | Notes |
|---|---|---|
| Async command layer, no blocking on the GTK thread | `system-panel.py` (`Runner`) | `Gio.Subprocess` + `communicate_utf8_async`; per-command timeout; live processes force-exited on close |
| Split fast/slow refresh, tiles patched as answers arrive | `system-panel.py` (`_refresh_fast` / `_refresh_async`) | panel paints immediately |
| Live sliders with throttle + percentage labels + read-back | `system-panel.py` (`_on_vol`, `_on_bri`, `_poll_hardware`) | 50 ms volume / 80 ms brightness |
| Wi-Fi: saved/open/secured/enterprise decision tree | `system-panel.py` (`_connect_wifi`) | saved profiles resolved per SSID with proper quoting |
| In-panel password modal | `system-panel.py` (`_ask_password`, `_open_modal`) | mask, show/hide, inline error, retry; layer-shell keyboard mode + dismissal suppression |
| Secret over stdin, argv only as fallback | `system-panel.py` (`_connect_with_password`) | `nmcli --ask` reads the secret from the pipe |
| Async rescan with a "Scanning…" row, disk-cached list | `system-panel.py` (`_rescan_wifi`, `_read_wifi_cache`) | `$STATE/wifi-list` |
| BlueZ over D-Bus, live updates, in-panel pairing agent | `system-panel.py` (`Bt`) | `GetManagedObjects` + `PropertiesChanged` + `org.bluez.Agent1` |
| 4-finger swipe = brightness, batched | `gestures.py`, `brightness.sh bump` | 3 fingers = volume, 4-finger tap = forward |
| Terminal fallback really asks for a password | `wifi-connect.sh`, `wifi-pick.sh` | `read -s` + `nmcli --ask` |

### Deviations from the plan (and why)

1. **The system bus connection is opened synchronously** (`Gio.bus_get_sync`, ~7 ms)
   instead of asynchronously. PyGObject cannot finish an async `g_bus_get`:
   `call_finish` needs a connection instance, but `g_bus_get` delivers the
   connection through the result object. The call is lazy — it happens when the
   Bluetooth page is opened, not when the panel starts.
2. **The Wi-Fi list is cached on disk** (`$STATE/wifi-list`) in addition to the
   in-memory cache. `nmcli device wifi list --rescan no` can take 1.5 s+ while a
   scan is running, so the page shows the last known list immediately instead of
   a "Loading…" row.
3. **The Bluetooth list is throttled** to two rebuilds per second. A scan emits
   RSSI updates continuously, and rebuilding the rows on every signal was
   wasteful.
4. **A diagnostic hook was added**: `RIVER_PANEL_OPEN=wifi|bt` opens a page
   directly, and `--check` runs the parser self-test without a display. Both
   are used by the verification script.
5. **The plan's "one `nmcli` per SSID" for saved profiles** turned out to be the
   right call, but the first implementation broke on SSIDs containing spaces
   (shell word splitting); the profile names are now passed as a single argv
   element.

### Still to verify by hand (hardware / real devices)

- [ ] A secured Wi-Fi network without a saved profile → password dialog → connect.
- [ ] Wrong password → inline error, retry, no profile left behind.
- [ ] An unpaired Bluetooth device → scan → pair → passkey/confirm prompt → connect.
- [ ] 4-finger swipe up/down changes the brightness by a sensible amount.
- [ ] Slider drags feel smooth and the bar follows live.
