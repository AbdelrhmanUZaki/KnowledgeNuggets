#!/usr/bin/env python3
"""GNOME-class system panel for river-classic.

A borderless Wayland popup (xdg-shell) styled like GNOME's Quick Settings:
toggle tiles, live sliders, session actions. Opened from any system indicator
in the bar (network / bluetooth / battery / power) — the bar shows state, this
panel holds the actions.
"""

import os
import subprocess
import ctypes
import time
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango  # noqa: E402

HOME = os.path.expanduser("~")
FA = "FontAwesome"
# durable state (not /tmp — that is wiped at every boot)
STATE = os.path.join(os.environ.get("XDG_STATE_HOME",
                                    os.path.expanduser("~/.local/state")),
                     "river-classic")

# the panel is spawned by waybar, whose PATH may not include the system bins
os.environ["PATH"] = "/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")

# ── wlr-layer-shell via ctypes ───────────────────────────────────────────────
# The GI typelib is not installed, but libgtk-layer-shell0 is — calling the C
# API directly lets the panel dock under the bar's right corner exactly like
# GNOME's quick-settings popover (Wayland clients cannot position toplevels).
_EDGE_LEFT, _EDGE_RIGHT, _EDGE_TOP, _EDGE_BOTTOM = 0, 1, 2, 3
_LAYER_OVERLAY = 3
_KB_ON_DEMAND = 2   # never steal the keyboard from the focused app
_ls = None
try:
    _ls = ctypes.CDLL("libgtk-layer-shell.so.0")
    _ls.gtk_layer_init_for_window.argtypes = [ctypes.c_void_p]
    _ls.gtk_layer_set_anchor.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    _ls.gtk_layer_set_margin.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    _ls.gtk_layer_set_layer.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _ls.gtk_layer_set_keyboard_mode.argtypes = [ctypes.c_void_p, ctypes.c_int]
except OSError:
    _ls = None

# ── state helpers ────────────────────────────────────────────────────────────
def sh(cmd, *args):
    try:
        r = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=8)
        return r.stdout.strip()
    except Exception:
        return ""


def battery():
    base = "/sys/class/power_supply"
    try:
        for d in sorted(os.listdir(base)):
            if d.startswith("BAT"):
                cap = int(open(f"{base}/{d}/capacity").read().strip())
                st = open(f"{base}/{d}/status").read().strip().lower()
                return cap, st
    except Exception:
        pass
    return None, "unknown"


def _split_terse(line):
    """split nmcli terse output, honouring backslash-escaped ':'"""
    parts, cur, i = [], "", 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            cur += line[i + 1]
            i += 2
            continue
        if ch == ":":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    parts.append(cur)
    return parts


def wifi():
    on = "enabled" in sh("nmcli", "radio", "wifi")
    ssid = ""
    # --rescan no: use the cache, a fresh scan blocks for several seconds
    for line in sh("nmcli", "-t", "-f", "IN-USE,SSID", "device", "wifi",
                   "list", "--rescan", "no").splitlines():
        p = _split_terse(line)
        if len(p) > 1 and p[0] == "*":
            ssid = p[1]
            break
    return on, ssid


def bt():
    return "Powered: yes" in sh("bluetoothctl", "show")


def profile():
    return sh("powerprofilesctl", "get") or "balanced"


def dark_mode():
    return "dark" in sh("gsettings", "get", "org.gnome.desktop.interface", "color-scheme")


def dnd():
    return sh("dunstctl", "is-paused") == "true"


def volume():
    out = sh("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
    for tok in out.replace(":", " ").split():
        try:
            val = float(tok)
        except ValueError:
            continue
        if 0.0 <= val <= 1.0:
            return int(val * 100)
    return 0


def set_volume(pct):
    sh("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{pct / 100.0:.2f}")


def brightness():
    try:
        cur = int(open("/sys/class/backlight/intel_backlight/brightness").read())
        mx = int(open("/sys/class/backlight/intel_backlight/max_brightness").read())
        return int(cur * 100 / mx)
    except Exception:
        return 0


def set_brightness(pct):
    sh(f"{HOME}/.config/waybar/brightness.sh", "set", str(pct))


def bt_devices():
    """paired/known bluetooth devices -> [(mac, name, connected)]"""
    out = []
    for line in sh("bluetoothctl", "devices").splitlines():
        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue
        mac, name = parts[1], parts[2]
        connected = "Connected: yes" in sh("bluetoothctl", "info", mac)
        out.append((mac, name, connected))
    return out


def wifi_networks():
    """cached scan -> [(ssid, signal, in_use, secured)], strongest first"""
    found = {}
    # --rescan no: a live rescan takes ~8 s and freezes the panel; the list
    # page has an explicit "rescan" row for that
    for line in sh("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                   "device", "wifi", "list", "--rescan", "no").splitlines():
        p = _split_terse(line)
        if len(p) < 3 or not p[1]:
            continue
        ssid, signal = p[1], int(p[2]) if p[2].isdigit() else 0
        in_use = p[0] == "*"
        secured = bool(p[3]) if len(p) > 3 else False
        if ssid in found:                       # same AP on 2.4 + 5 GHz
            found[ssid][1] = max(found[ssid][1], signal)
            found[ssid][2] = found[ssid][2] or in_use
        else:
            found[ssid] = [ssid, signal, in_use, secured]
    nets = [tuple(n) for n in found.values()]
    nets.sort(key=lambda n: (not n[2], -n[1]))
    return nets


PROFILES = ["performance", "balanced", "power-saver"]
PROFILE_ICON = {"performance": "\uf0e7", "balanced": "\uf013", "power-saver": "\uf186"}


class Panel(Gtk.Window):
    def __init__(self):
        # TOPLEVEL (not POPUP): a parentless Gtk.WindowType.POPUP cannot be mapped
        # as an xdg_popup on Wayland and gets centred by the compositor. A
        # POPUP_MENU type hint keeps it undecorated and lets us place it.
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("System Menu")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.NONE)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)   # NORMAL honours move()
        self.get_style_context().add_class("panel-window")
        self._armed = False
        self._positioned = False
        self._vol_timer = None
        self._bri_timer = None
        self._docked = self._dock()

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.get_style_context().add_class("panel")
        root.set_border_width(0)
        self.add(root)

        root.pack_start(self._header(), False, False, 0)

        # pages: the overview (tiles + sliders + session row) and the
        # expandable network / device lists behind the tile corner buttons
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)
        root.pack_start(self.stack, True, True, 0)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main.pack_start(self._tiles(), False, False, 0)
        main.pack_start(self._sliders(), False, False, 0)
        main.pack_start(self._sessions(), False, False, 0)
        self.stack.add_named(main, "main")
        self.stack.add_named(self._wifi_page(), "wifi")
        self.stack.add_named(self._bt_page(), "bt")

        self.connect("key-press-event", self._on_key)
        self.connect("focus-out-event", self._on_focus_out)
        self.connect("focus-in-event", self._on_focus_in)
        self.connect("size-allocate", self._on_allocate)
        self.connect("show", self._on_show)

    # ── header: back button + battery state + shortcuts ─────────────────
    def _header(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.back_btn = Gtk.Button()
        self.back_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.back_btn.get_style_context().add_class("round")
        self.back_btn.set_tooltip_text("Back")
        bl = Gtk.Label()
        # plain text glyph: the FA back-arrow codepoint is missing from the
        # installed FontAwesome cut and renders as an empty box
        bl.set_markup("<span size='15pt'>‹</span>")
        self.back_label = bl
        self.back_btn.add(bl)
        self.back_btn.connect("clicked", lambda _b: self._show_page("main"))
        self.back_btn.set_no_show_all(True)
        box.pack_start(self.back_btn, False, False, 0)

        self.battery_label = Gtk.Label()
        self.battery_label.get_style_context().add_class("battery")
        box.pack_start(self.battery_label, True, True, 0)

        for icon, tip, action in (
            ("\uf013", "Settings", lambda: sh("gnome-control-center")),
            ("\uf030", "Screenshot", lambda: sh(f"{HOME}/.config/river/screenshot.sh")),
        ):
            b = Gtk.Button()
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.get_style_context().add_class("round")
            b.set_tooltip_text(tip)
            lbl = Gtk.Label()
            lbl.set_markup(f"<span font_family='{FA}' size='13pt'>{icon}</span>")
            b.add(lbl)
            b.connect("clicked", lambda _b, a=action: (a(), self.close()))
            box.pack_start(b, False, False, 0)
        return box

    # ── toggle tiles ─────────────────────────────────────────────────────
    def _tile(self, icon, label, active=False, on_click=None, sub=None):
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class("tile")
        btn.set_size_request(96, 62)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_halign(Gtk.Align.CENTER)
        ico = Gtk.Label()
        ico.set_markup(f"<span font_family='{FA}' size='15pt'>{icon}</span>")
        ico.get_style_context().add_class("tile-icon")
        txt = Gtk.Label(label=label)
        txt.get_style_context().add_class("tile-label")
        btn._tile_label = txt
        box.pack_start(ico, False, False, 0)
        box.pack_start(txt, False, False, 0)
        btn.add(box)
        if active:
            btn.get_style_context().add_class("active")
        btn.connect("clicked", on_click)
        if not sub:
            return btn

        # small corner button → expands the tile into a list page
        overlay = Gtk.Overlay()
        overlay.add(btn)
        sb = Gtk.Button()
        sb.set_relief(Gtk.ReliefStyle.NONE)
        sb.get_style_context().add_class("sub")
        sb.set_tooltip_text(sub[0])
        sl = Gtk.Label()
        sl.set_markup(f"<span font_family='{FA}' size='9pt'>\uf105</span>")
        sb.add(sl)
        sb.set_halign(Gtk.Align.END)
        sb.set_valign(Gtk.Align.START)
        sb.set_margin_top(3)
        sb.set_margin_end(3)
        sb.connect("clicked", sub[1])
        overlay.add_overlay(sb)
        overlay._tile_button = btn
        return overlay

    def _tiles(self):
        grid = Gtk.Grid(row_spacing=8, column_spacing=8)
        grid.set_column_homogeneous(True)
        self.t_wifi = self._tile("\uf0eb", "Wi-Fi", on_click=self._act_wifi,
                                 sub=("available networks",
                                      lambda _b: self._show_page("wifi")))
        self.t_bt = self._tile("\uf293", "Bluetooth", on_click=self._act_bt,
                               sub=("paired devices",
                                    lambda _b: self._show_page("bt")))
        self.t_prof = self._tile("\uf0e7", "Power", on_click=self._act_profile)
        self.t_dark = self._tile("\uf186", "Dark mode", on_click=self._act_dark)
        self.t_dnd = self._tile("\uf0f3", "Do not disturb", on_click=self._act_dnd)
        self.t_shot = self._tile("\uf030", "Screenshot", on_click=self._act_shot)
        for i, t in enumerate((self.t_wifi, self.t_bt, self.t_prof,
                                self.t_dark, self.t_dnd, self.t_shot)):
            grid.attach(t, i % 3, i // 3, 1, 1)
        return grid

    # ── sliders ──────────────────────────────────────────────────────────
    def _slider(self, icon, value, on_change):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ico = Gtk.Label()
        ico.set_markup(f"<span font_family='{FA}' size='12pt'>{icon}</span>")
        ico.set_valign(Gtk.Align.CENTER)
        box.pack_start(ico, False, False, 0)
        adj = Gtk.Adjustment(value=value, lower=0, upper=100, step_increment=2, page_increment=10)
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_valign(Gtk.Align.CENTER)
        scale.get_style_context().add_class("slider")
        scale.connect("value-changed", on_change)
        box.pack_start(scale, True, True, 0)
        return box, scale

    def _sliders(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox, self.s_vol = self._slider("\uf028", volume(), self._on_vol)
        bbox, self.s_bri = self._slider("\uf185", brightness(), self._on_bri)
        box.pack_start(vbox, False, False, 0)
        box.pack_start(bbox, False, False, 0)
        return box

    # ── session actions ──────────────────────────────────────────────────
    def _sessions(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_homogeneous(True)
        actions = (
            ("\uf023", "Lock", lambda: sh("swaylock", "-f")),
            ("\uf08b", "Log out", lambda: sh(f"{HOME}/.local/bin/riverctl", "exit")),
            ("\uf021", "Reboot", lambda: sh("systemctl", "reboot")),
            ("\uf186", "Suspend", lambda: sh("systemctl", "suspend")),
            ("\uf011", "Power off", lambda: sh("systemctl", "poweroff")),
        )
        for icon, tip, action in actions:
            b = Gtk.Button()
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.get_style_context().add_class("session")
            b.set_tooltip_text(tip)
            lbl = Gtk.Label()
            lbl.set_markup(f"<span font_family='{FA}' size='12pt'>{icon}</span>")
            b.add(lbl)
            b.connect("clicked", lambda _b, a=action: (a(), self.close()))
            row.pack_start(b, True, True, 0)
        return row

    # ── expandable pages: networks / devices ─────────────────────────────
    def _page_box(self, title):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        head = Gtk.Label(label=title)
        head.get_style_context().add_class("page-title")
        head.set_xalign(0)
        box.pack_start(head, False, False, 0)
        lst = Gtk.ListBox()
        lst.set_selection_mode(Gtk.SelectionMode.NONE)
        lst.get_style_context().add_class("list")
        lst.connect("row-activated", self._on_row_activated)
        # cap the height: a dense 5 GHz area can list 20+ networks, which
        # would otherwise stretch the panel to the bottom of the screen
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_max_content_height(300)
        sw.set_propagate_natural_height(True)
        sw.get_style_context().add_class("list-scroll")
        sw.add(lst)
        box.pack_start(sw, True, True, 0)
        return box, lst

    def _on_row_activated(self, _list, row):
        action = getattr(row, "_action", None)
        if action:
            action(row)

    def _row(self, label, sublabel="", on_click=None, icon=None):
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if icon:
            il = Gtk.Label()
            il.set_markup(f"<span font_family='{FA}' size='11pt'>{icon}</span>")
            il.set_valign(Gtk.Align.CENTER)
            hbox.pack_start(il, False, False, 0)
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        l1 = Gtk.Label(label=label)
        l1.set_xalign(0)
        l1.get_style_context().add_class("row-label")
        v.pack_start(l1, False, False, 0)
        if sublabel:
            l2 = Gtk.Label(label=sublabel)
            l2.set_xalign(0)
            l2.get_style_context().add_class("row-sub")
            v.pack_start(l2, False, False, 0)
        hbox.pack_start(v, True, True, 0)
        row.add(hbox)
        if on_click:
            row.set_activatable(True)
            row._action = on_click
        # rows are added after the initial show_all() -> show them explicitly
        row.show_all()
        return row

    def _wifi_page(self):
        box, lst = self._page_box("Available networks")
        self.wifi_list = lst
        return box

    def _bt_page(self):
        box, lst = self._page_box("Paired devices")
        self.bt_list = lst
        return box

    def _show_page(self, name):
        self.stack.set_visible_child_name(name)
        self.back_btn.set_visible(name != "main")
        if name != "main":
            # show_all() is a no-op on a no_show_all widget, so reveal the
            # label explicitly or the button renders as an empty box
            self.back_label.show()
        if name == "wifi":
            self._auto_scanned = False
            self._fill_wifi_list()
        elif name == "bt":
            self._fill_bt_list()
        else:
            self.refresh()

    def _fill_wifi_list(self, rescan=False):
        if rescan:
            # a scan takes several seconds and blocks; paint the cached list
            # now and repaint once NetworkManager has fresh results
            sh("nmcli", "device", "wifi", "rescan")
            GLib.timeout_add(6000, lambda: (self._fill_wifi_list(), False)[1])
        for c in list(self.wifi_list.get_children()):
            self.wifi_list.remove(c)
        nets = wifi_networks()
        if not rescan and len(nets) <= 2 and not getattr(self, "_auto_scanned", False):
            # cache looks stale (right after login) -> one background refresh
            self._auto_scanned = True
            GLib.timeout_add(500, lambda: (self._fill_wifi_list(rescan=True), False)[1])
        if not nets:
            self.wifi_list.add(self._row("No networks found",
                                         "is the radio off?"))
        for ssid, signal, active, secured in nets:
            label = ("✓ " + ssid) if active else ssid
            sub = f"{signal}%" + ("  · secured" if secured else "")
            self.wifi_list.add(self._row(label, sub, icon="\uf0eb",
                                         on_click=lambda _r, s=ssid: self._connect_wifi(s)))
        self.wifi_list.add(self._row("manage connections…",
                                     "nm-connection-editor",
                                     on_click=lambda _r: self._launch("nm-connection-editor")))
        self.wifi_list.add(self._row("rescan", "search for networks again",
                                     on_click=lambda _r: self._rescan_wifi()))

    def _rescan_wifi(self):
        self._fill_wifi_list(rescan=True)

    def _fill_bt_list(self):
        for c in list(self.bt_list.get_children()):
            self.bt_list.remove(c)
        devs = bt_devices()
        if not devs:
            self.bt_list.add(self._row("No paired devices",
                                       "pair one from the manager"))
        for mac, name, connected in devs:
            sub = "connected · click to disconnect" if connected else "click to connect"
            self.bt_list.add(self._row(name, sub, icon="\uf293",
                                       on_click=lambda _r, m=mac, c=connected: self._bt_device(m, c)))
        self.bt_list.add(self._row("pair a new device…", "blueman-manager",
                                   on_click=lambda _r: self._launch("blueman-manager")))

    # ── actions ──────────────────────────────────────────────────────────
    def _launch(self, cmd):
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        self.close()

    def _connect_wifi(self, ssid):
        if sh("nmcli", "device", "wifi", "connect", ssid):
            self.refresh()
            self._fill_wifi_list()
            return
        # unknown network -> needs a password, use the foot prompt
        try:
            os.makedirs(STATE, exist_ok=True)
            with open(os.path.join(STATE, "wifi-chosen"), "w") as f:
                f.write(ssid)
        except OSError:
            pass
        subprocess.Popen(["foot", "-e", f"{HOME}/.config/river/wifi-connect.sh"])

    def _bt_device(self, mac, connected):
        sh("bluetoothctl", "disconnect" if connected else "connect", mac)
        self._fill_bt_list()

    def _act_wifi(self, _b):
        on, _ = wifi()
        sh("nmcli", "radio", "wifi", "off" if on else "on")
        self.refresh()

    def _act_bt(self, _b):
        sh("bluetoothctl", "power", "off" if bt() else "on")
        self.refresh()

    def _act_profile(self, _b):
        p = profile()
        nxt = PROFILES[(PROFILES.index(p) + 1) % len(PROFILES)] if p in PROFILES else "balanced"
        sh("powerprofilesctl", "set", nxt)
        self.refresh()

    def _act_dark(self, _b):
        sh("gsettings", "set", "org.gnome.desktop.interface", "color-scheme",
           "prefer-light" if dark_mode() else "prefer-dark")
        self.refresh()

    def _act_dnd(self, _b):
        sh("dunstctl", "set-paused", "toggle")
        self.refresh()

    def _act_shot(self, _b):
        sh(f"{HOME}/.config/river/screenshot.sh")
        self.close()

    def _on_vol(self, scale):
        val = int(scale.get_value())

        def apply():
            set_volume(val)
            return False

        if self._vol_timer:
            GLib.source_remove(self._vol_timer)
        self._vol_timer = GLib.timeout_add(120, apply)

    def _on_bri(self, scale):
        val = int(scale.get_value())

        def apply():
            set_brightness(val)
            return False

        if self._bri_timer:
            GLib.source_remove(self._bri_timer)
        self._bri_timer = GLib.timeout_add(120, apply)

    # ── lifecycle ────────────────────────────────────────────────────────
    def _dock(self):
        """anchor the panel under the bar's right corner (wlr-layer-shell)"""
        if _ls is None:
            return False
        try:
            # PyGObject exposes the GObject address as the widget's hash;
            # __gpointer__ is a PyCapsule and cannot be cast directly
            ptr = ctypes.c_void_p(hash(self))
            _ls.gtk_layer_init_for_window(ptr)
            _ls.gtk_layer_set_layer(ptr, _LAYER_OVERLAY)
            _ls.gtk_layer_set_anchor(ptr, _EDGE_TOP, 1)
            _ls.gtk_layer_set_anchor(ptr, _EDGE_RIGHT, 1)
            _ls.gtk_layer_set_margin(ptr, _EDGE_TOP, 40)   # clear the 30px bar
            _ls.gtk_layer_set_margin(ptr, _EDGE_RIGHT, 16)
            _ls.gtk_layer_set_keyboard_mode(ptr, _KB_ON_DEMAND)
            return True
        except Exception:
            return False

    def refresh(self):
        cap, st = battery()
        if cap is None:
            self.battery_label.set_text("No battery")
        else:
            glyph = {"charging": "\uf0e7", "full": "\uf240"}.get(st, "\uf240")
            extra = " · charging" if st == "charging" else (" · on charger" if st == "not charging" else "")
            self.battery_label.set_markup(
                f"<span font_family='{FA}' size='12pt'>{glyph}</span>  {cap}%<span size='small'>{extra}</span>")

        on, ssid = wifi()
        self._set_tile(self.t_wifi, ssid or ("Wi-Fi" if on else "Wi-Fi off"), "\uf0eb", on)
        self.t_wifi.set_tooltip_text(f"Wi-Fi: {ssid}" if on else "Wi-Fi is off")

        self._set_tile(self.t_bt, "Bluetooth" if bt() else "Bluetooth off", "\uf293", bt())

        p = profile()
        self._set_tile(self.t_prof, p.capitalize(), PROFILE_ICON.get(p, "\uf013"), p != "balanced")

        self._set_tile(self.t_dark, "Dark mode", "\uf186", dark_mode())
        self._set_tile(self.t_dnd, "Do not disturb", "\uf0f3", dnd())
        self._set_tile(self.t_shot, "Screenshot", "\uf030", False)

    def _set_tile(self, widget, text, icon, active):
        btn = getattr(widget, "_tile_button", widget)
        lbl = btn._tile_label
        lbl.set_text(text)
        ctx = btn.get_style_context()
        if active:
            ctx.add_class("active")
        else:
            ctx.remove_class("active")

    def _on_show(self, _w):
        self.refresh()
        self._mapped_at = time.monotonic()
        self._had_focus = False
        # tell quick-settings.sh we are really up: it only falls back to the
        # dmenu when the panel never started (a later kill is not a failure)
        try:
            os.makedirs(STATE, exist_ok=True)
            with open(os.path.join(STATE, "panel-started"), "w") as f:
                f.write(str(os.getpid()))
        except OSError:
            pass
        GLib.timeout_add(400, self._arm)
        self._watch = GLib.timeout_add(600, self._dismiss_watch)

    def _dismiss_watch(self):
        """GNOME-like dismiss: if the pointer leaves the panel, close it"""
        if not self.get_mapped():
            return False
        try:
            display = Gdk.Display.get_default()
            pointer = display.get_default_seat().get_pointer()
            px, py = pointer.get_position()
            gx, gy = self.get_position()
            w, h = self.get_size()
            inside = gx <= px < gx + w and gy <= py < gy + h
        except Exception:
            return True
        if inside:
            self._seen_inside = True
            self._away = 0
            return True
        if not getattr(self, "_seen_inside", False):
            return True          # opened from the bar: pointer is outside — stay open
        self._away = getattr(self, "_away", 0) + 1
        if self._away >= 2:      # ~1.2 s grace after the pointer leaves the panel
            self.close()
            return False
        return True

    def _arm(self):
        self._armed = True
        return False

    def _on_allocate(self, _w, _alloc):
        if self._positioned or self._docked:
            return
        self._positioned = True
        GLib.idle_add(self._place)

    def _place(self):
        """dock to the top-right corner of the monitor under the pointer"""
        w = self.get_allocated_width() or 360
        h = self.get_allocated_height() or 420
        try:
            display = Gdk.Display.get_default()
            seat = display.get_default_seat()
            pointer = seat.get_pointer()
            px, py = pointer.get_position()
            monitor = display.get_monitor_at_point(px, py) or display.get_primary_monitor()
            geo = monitor.get_geometry()
            self.move(geo.x() + geo.width() - w - 14, geo.y() + 38)
        except Exception:
            self.move(600, 40)
        return False

    def _on_key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_focus_in(self, _w, _e):
        self._had_focus = True
        return False

    def _on_focus_out(self, _w, _e):
        # only dismiss if the panel actually held the keyboard focus, and never
        # within the first moment after mapping (layer surfaces can get a
        # spurious focus-out right after they appear, which would close the
        # panel instantly)
        age = time.monotonic() - getattr(self, "_mapped_at", 0.0)
        if getattr(self, "_had_focus", False) and age > 0.8:
            self.close()
        self._had_focus = False
        return False

    def close(self):
        self.hide()
        self.destroy()
        Gtk.main_quit()


CSS = """
window.panel-window { background-color: transparent; }
.panel {
    background-color: #002b36;
    background-image: none;
    border: 1px solid #073642;
    border-radius: 12px;
    padding: 12px;
    box-shadow: 0 6px 22px rgba(0, 0, 0, 0.55);
}
label { color: #93a1a1; font-family: "Ubuntu Sans"; }
label.battery { color: #fdf6e3; font-size: 13px; }

button.tile, button.round, button.session {
    background-color: #073642;
    background-image: none;              /* kill the theme's own button face */
    border: 1px solid #0b4a58;
    border-radius: 9px;
    padding: 6px;
    color: #93a1a1;
    transition: background-color 120ms ease;
}
button.tile:hover, button.round:hover, button.session:hover {
    background-color: #0b4a58;
    border-color: #268bd2;
}
button.tile.active {
    background-color: #12697a;
    border-color: #2aa198;
}
label.tile-icon { color: #fdf6e3; }
button.tile.active label.tile-icon { color: #2aa198; }
label.tile-label { color: #93a1a1; font-size: 11px; }
button.session { border-radius: 7px; padding: 5px; }

/* small corner button on a tile → expands into the list page */
button.sub {
    background-color: transparent;
    background-image: none;
    border: none;
    border-radius: 6px;
    padding: 0;
    min-width: 17px;
    min-height: 17px;
    color: #586e75;
}
button.sub:hover { background-color: #0b4a58; color: #2aa198; }

/* list pages (networks / devices) */
label.page-title { color: #93a1a1; font-size: 11px; }
scrolledwindow.list-scroll, scrolledwindow.list-scroll viewport { background-color: transparent; }
scrolledwindow.list-scroll { border: none; }
scrolledwindow.list-scroll scrollbar slider { background-color: #0b4a58; border-radius: 4px; min-width: 5px; }
list.list { background-color: transparent; }
list.list row { padding: 4px 6px; border-radius: 6px; }
list.list row:hover { background-color: #073642; }
label.row-label { color: #fdf6e3; font-size: 12px; }
label.row-sub { color: #586e75; font-size: 10px; }

scale.slider { min-height: 20px; }
scale.slider trough {
    min-height: 6px;
    background-color: #073642;
    background-image: none;
    border: none;
    border-radius: 3px;
}
scale.slider trough highlight,
scale.slider highlight {
    min-height: 6px;
    background-color: #2aa198;
    background-image: none;
    border-radius: 3px;
}
scale.slider slider {
    min-width: 14px;
    min-height: 14px;
    background-color: #2aa198;
    background-image: none;
    border: none;
    border-radius: 7px;
}
"""


def apply_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def main():
    panel = Panel()
    apply_css()
    panel.show_all()
    panel.refresh()
    Gtk.main()


if __name__ == "__main__":
    main()
