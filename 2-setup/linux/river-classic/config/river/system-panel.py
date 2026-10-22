#!/usr/bin/env python3
"""GNOME-class system panel for river-classic.

A borderless Wayland popup (xdg-shell) styled like GNOME's Quick Settings:
toggle tiles, live sliders, session actions. Opened from any system indicator
in the bar (network / bluetooth / battery / power) — the bar shows state, this
panel holds the actions.

Design rules (see PLAN.md):

  * no external command may run on the GTK main thread -> Gio.Subprocess
  * the panel paints instantly; every state read arrives later, asynchronously
  * sliders apply while dragging (throttled), not after release
  * Wi-Fi asks for a password only when a network really needs one
  * Bluetooth pairs through an in-panel BlueZ agent
"""

import ctypes
import os
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

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
_KB_NONE, _KB_EXCLUSIVE, _KB_ON_DEMAND = 0, 1, 2
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

PROFILES = ["performance", "balanced", "power-saver"]
PROFILE_ICON = {"performance": "\uf0e7", "balanced": "\uf013", "power-saver": "\uf186"}


# ── pure (synchronous, fast) readers ────────────────────────────────────────
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


def battery():
    base = "/sys/class/power_supply"
    try:
        for d in sorted(os.listdir(base)):
            if d.startswith("BAT"):
                cap = int(open("%s/%s/capacity" % (base, d)).read().strip())
                st = open("%s/%s/status" % (base, d)).read().strip().lower()
                return cap, st
    except Exception:
        pass
    return None, "unknown"


def brightness():
    try:
        cur = int(open("/sys/class/backlight/intel_backlight/brightness").read())
        mx = int(open("/sys/class/backlight/intel_backlight/max_brightness").read())
        return int(cur * 100 / mx) if mx else 0
    except Exception:
        return 0


def parse_volume(out):
    """'Volume: 0.62 [MUTED]' -> 62"""
    for tok in out.replace(":", " ").replace("[", " ").replace("]", " ").split():
        try:
            val = float(tok)
        except ValueError:
            continue
        if 0.0 <= val <= 1.0:
            return int(val * 100)
    return None


def parse_wifi_list(out):
    """nmcli terse IN-USE,SSID,SIGNAL,SECURITY -> [{ssid,signal,in_use,security}]"""
    nets = {}
    for line in out.splitlines():
        p = _split_terse(line)
        if len(p) < 3 or not p[1]:
            continue
        ssid = p[1]
        try:
            signal = int(p[2])
        except ValueError:
            signal = 0
        security = p[3] if len(p) > 3 else ""
        if ssid in nets:                      # same AP on 2.4 + 5 GHz
            nets[ssid]["signal"] = max(nets[ssid]["signal"], signal)
            nets[ssid]["in_use"] = nets[ssid]["in_use"] or p[0] == "*"
        else:
            nets[ssid] = {"ssid": ssid, "signal": signal, "in_use": p[0] == "*",
                          "security": security}
    out_list = list(nets.values())
    out_list.sort(key=lambda n: (not n["in_use"], -n["signal"]))
    return out_list


def is_enterprise(security):
    return "802.1X" in security or "EAP" in security


def is_secured(security):
    security = (security or "").strip()
    if not security or security == "--":
        return False
    if security == "OWE":                    # enhanced open: no secret
        return False
    return True


# ── async command runner ────────────────────────────────────────────────────
class Runner:
    """Run external commands without ever blocking the GTK main loop.

    Every callback is delivered on the GTK main loop, so widgets may be
    touched directly.  Commands are killed when the panel closes, so a
    long running `nmcli device wifi rescan` cannot keep the process alive.
    """

    def __init__(self):
        self._live = {}
        self.alive = True

    def run(self, argv, cb, timeout=10.0, stdin=None):
        """cb(stdout, stderr, rc) — rc is -1 when the command was killed."""
        if not self.alive:
            return
        flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
        if stdin is not None:
            flags |= Gio.SubprocessFlags.STDIN_PIPE
        try:
            proc = Gio.Subprocess.new(argv, flags)
        except GLib.Error as exc:
            GLib.idle_add(cb, "", exc.message, 127)
            return
        self._live[proc] = proc
        state = {"timer": None}

        def kill():
            try:
                proc.force_exit()
            except Exception:
                pass
            return False

        if timeout:
            state["timer"] = GLib.timeout_add(int(max(0.2, timeout) * 1000), kill)

        def done(_proc, result):
            out, err = "", ""
            try:
                _ok, out, err = proc.communicate_utf8_finish(result)
            except GLib.Error as exc:
                err = exc.message
            if state["timer"]:
                GLib.source_remove(state["timer"])
            self._live.pop(proc, None)
            rc = proc.get_exit_status() if proc.get_if_exited() else -1
            if self.alive:
                GLib.idle_add(cb, out or "", err or "", rc)

        # communicate_utf8_async takes the stdin data as a *string*
        proc.communicate_utf8_async(
            stdin if isinstance(stdin, str) else None, None, done)

    def spawn(self, argv):
        """start a process and do not wait for it"""
        if not self.alive:
            return
        try:
            proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE)
            self._live[proc] = proc
        except GLib.Error:
            pass

    def close(self):
        self.alive = False
        for proc in list(self._live.values()):
            try:
                proc.force_exit()
            except Exception:
                pass
        self._live.clear()


# ── BlueZ over D-Bus ────────────────────────────────────────────────────────
BT_AGENT_XML = """
<node>
  <interface name="org.bluez.Agent1">
    <method name="Release"/>
    <method name="RequestPinCode">
      <arg type="o" direction="in"/>
      <arg type="s" direction="out"/>
    </method>
    <method name="DisplayPinCode">
      <arg type="o" direction="in"/>
      <arg type="s" direction="in"/>
    </method>
    <method name="RequestPasskey">
      <arg type="o" direction="in"/>
      <arg type="u" direction="out"/>
    </method>
    <method name="DisplayPasskey">
      <arg type="o" direction="in"/>
      <arg type="u" direction="in"/>
      <arg type="u" direction="in"/>
    </method>
    <method name="RequestConfirmation">
      <arg type="o" direction="in"/>
      <arg type="u" direction="in"/>
    </method>
    <method name="RequestAuthorization">
      <arg type="o" direction="in"/>
    </method>
    <method name="AuthorizeService">
      <arg type="o" direction="in"/>
      <arg type="s" direction="in"/>
    </method>
    <method name="Cancel"/>
  </interface>
</node>
"""


class Bt:
    """BlueZ state, discovery, pairing and a pairing agent for prompts."""

    def __init__(self, panel):
        self.panel = panel
        self.conn = None
        self.agent_path = "/org/riverclassic/agent"
        self.devices = {}          # address -> dict(path, name, paired, connected, rssi)
        self.adapter_path = None
        self.adapter_on = None     # None = not known yet
        self.agent_ready = False
        self.scanning = False
        self.on_update = None      # set by the panel
        self._scan_timer = None
        self._starting = False
        self._pending_power = None

    # -- bus plumbing ----------------------------------------------------
    def start(self):
        if self.conn is not None or self._starting:
            return
        self._starting = True
        try:
            # PyGObject cannot finish an async g_bus_get (call_finish needs
            # an instance, but g_bus_get hands the connection over through
            # the result), so connect synchronously: it is a local socket
            # connect (~7 ms) and it only happens when the page is opened.
            self.conn = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except GLib.Error as exc:
            self._starting = False
            self.panel.note("Bluetooth: no system bus (%s)" % exc.message)
            return
        self._register_agent()
        self._load()
        self._watch()
        if self._pending_power is not None:
            want = self._pending_power
            self._pending_power = None
            self.set_power(want)

    def _register_agent(self):
        try:
            node = Gio.DBusNodeInfo.new_for_xml(BT_AGENT_XML)
            self.conn.register_object_with_closures2(
                self.agent_path, node.interfaces[0], self._agent_call,
                None, None)
        except Exception as exc:
            self.panel.note("Bluetooth: agent export failed (%s)" % exc)
            return
        self._call("org.bluez.AgentManager1", "RegisterAgent",
                   GLib.Variant("(os)", (self.agent_path, "KeyboardDisplay")),
                   self._on_agent_registered, path="/org/bluez")

    def _on_agent_registered(self, conn, res):
        try:
            conn.call_finish(res)
        except GLib.Error as exc:
            self.panel.note("Bluetooth: pairing prompts unavailable (%s)"
                            % exc.message)
            return
        self.agent_ready = True
        self._call("org.bluez.AgentManager1", "RequestDefaultAgent",
                   GLib.Variant("(o)", (self.agent_path,)),
                   lambda c, r: c.call_finish(r), path="/org/bluez")

    def _call(self, iface, method, params, cb, path=None, timeout=-1):
        if self.conn is None:
            return
        self.conn.call("org.bluez", path or self.adapter_path or "/org/bluez",
                       iface, method, params, None, Gio.DBusCallFlags.NONE,
                       timeout, None, cb)

    def _watch(self):
        # the *service* is org.bluez; its signals carry the interfaces
        # org.freedesktop.DBus.ObjectManager / .Properties, so the interface
        # filter must stay empty -- filtering on "org.bluez" matches nothing
        self.conn.signal_subscribe("org.bluez", None, None, None, None,
                                   Gio.DBusSignalFlags.NONE, self._on_signal)

    def _on_signal(self, _conn, _sender, _path, _iface, _signal, params,
                   *_extra):
        try:
            unpacked = params.unpack()
        except Exception:
            return
        if _signal == "InterfacesAdded":
            _path, ifaces = unpacked[0], unpacked[1]
            for iface, props in ifaces.items():
                if iface == "org.bluez.Device1":
                    self._put_device(_path, props)
        elif _signal == "PropertiesChanged":
            path, changed = unpacked[0], unpacked[1]
            for addr, dev in self.devices.items():
                if dev["path"] == path:
                    for key, variant in changed.items():
                        value = variant.unpack()
                        if key in dev:
                            dev[key] = value
                    if "Name" in changed:
                        dev["name"] = changed["Name"].unpack()
        if self.on_update:
            self.on_update()

    # -- state ------------------------------------------------------------
    def _load(self):
        # the object manager is exported on the root path of the service
        self._call("org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
                   None, self._on_objects, path="/")

    def _on_objects(self, conn, res):
        try:
            result = conn.call_finish(res)
        except GLib.Error as exc:
            self.panel.note("Bluetooth: cannot read devices (%s)" % exc.message)
            return
        objects = result.unpack()
        # the reply is a one-tuple around the a{oa{sa{sv}}} dictionary
        if isinstance(objects, tuple):
            objects = objects[0] if objects else {}
        for path, ifaces in objects.items():
            for iface, props in ifaces.items():
                if iface == "org.bluez.Adapter1":
                    self.adapter_path = path
                    self.adapter_on = bool(_unpack(props, "Powered", False))
                elif iface == "org.bluez.Device1":
                    self._put_device(path, props)
        if self.on_update:
            self.on_update()

    def _put_device(self, path, props):
        addr = _unpack(props, "Address", None)
        if not addr:
            return
        dev = self.devices.setdefault(addr, {"path": path, "address": addr})
        dev["path"] = path
        name = _unpack(props, "Name", None) or _unpack(props, "Alias", None)
        dev["name"] = name or _pretty_mac(addr)
        dev["paired"] = bool(_unpack(props, "Paired", False))
        dev["connected"] = bool(_unpack(props, "Connected", False))
        dev["trusted"] = bool(_unpack(props, "Trusted", False))
        rssi = _unpack(props, "RSSI", None)
        dev["rssi"] = int(rssi) if isinstance(rssi, int) else None

    def ordered_devices(self):
        def key(dev):
            return (0 if dev["connected"] else 1 if dev["paired"] else 2,
                    -(dev["rssi"] if dev["rssi"] is not None else -100))
        return sorted(self.devices.values(), key=key)

    # -- actions ----------------------------------------------------------
    def set_power(self, on, cb=None):
        if self.conn is None:
            # the bus is not up yet: remember the wish and apply it later
            self._pending_power = bool(on)
            if cb:
                cb(False, "bluetooth bus not ready")
            return
        if self.adapter_path is None:
            if cb:
                cb(False, "no adapter")
            return

        def done(conn, res):
            try:
                conn.call_finish(res)
                ok, err = True, ""
            except GLib.Error as exc:
                ok, err = False, exc.message
            self.adapter_on = bool(on) if ok else self.adapter_on
            if self.on_update:
                self.on_update()
            if cb:
                cb(ok, err)

        self._call("org.freedesktop.DBus.Properties", "Set",
                   GLib.Variant("(ssv)", ("org.bluez.Adapter1", "Powered",
                                           GLib.Variant("b", bool(on)))),
                   done, path=self.adapter_path)

    def start_discovery(self, cb=None):
        if self.adapter_path is None or self.scanning:
            return
        self.scanning = True

        def done(conn, res):
            try:
                conn.call_finish(res)
                self.panel.note("Bluetooth: scanning for devices…")
            except GLib.Error as exc:
                if "InProgress" in exc.message:
                    self.panel.note("Bluetooth: scanning…")
                else:
                    self.scanning = False
                    self.panel.note("Bluetooth: scan failed (%s)" % exc.message)
            if self._scan_timer:
                GLib.source_remove(self._scan_timer)
            self._scan_timer = GLib.timeout_add_seconds(20, self._stop_discovery)
            if cb:
                cb()

        self._call("org.bluez.Adapter1", "StartDiscovery", None, done,
                   path=self.adapter_path)

    def _stop_discovery(self):
        self._scan_timer = None
        self.stop_discovery()
        return False

    def stop_discovery(self):
        if not self.scanning or self.adapter_path is None:
            return
        self.scanning = False
        self._call("org.bluez.Adapter1", "StopDiscovery", None,
                   lambda c, r: c.call_finish(r), path=self.adapter_path)

    def device_call(self, addr, method, cb):
        dev = self.devices.get(addr)
        if dev is None:
            if cb:
                cb(False, "unknown device")
            return
        self._call("org.bluez.Device1", method, None,
                   lambda c, r: _finish(c, r, cb), path=dev["path"])

    def trust(self, addr, cb):
        dev = self.devices.get(addr)
        if dev is None:
            if cb:
                cb(False, "unknown device")
            return
        self._call("org.freedesktop.DBus.Properties", "Set",
                   GLib.Variant("(ssv)", ("org.bluez.Device1", "Trusted",
                                           GLib.Variant("b", True))),
                   lambda c, r: _finish(c, r, cb), path=dev["path"])

    # -- pairing agent ----------------------------------------------------
    def _agent_call(self, _conn, _sender, _path, _iface, method, params,
                    invocation):
        if method == "Release":
            invocation.return_value(None)
        elif method == "Cancel":
            self.panel.bt_cancel_pending()
            invocation.return_value(None)
        elif method == "RequestPinCode":
            addr = params.unpack()[0]
            self.panel.bt_prompt_entry(addr, "PIN code", False,
                                       lambda ok, text: _reply_text(invocation, ok, text))
        elif method == "DisplayPinCode":
            addr, code = params.unpack()
            self.panel.bt_show_code(addr, code)
            invocation.return_value(None)
        elif method == "RequestPasskey":
            addr = params.unpack()[0]
            self.panel.bt_prompt_entry(addr, "Passkey", True,
                                       lambda ok, text: _reply_uint(invocation, ok, text))
        elif method == "DisplayPasskey":
            addr, passkey, _entered = params.unpack()
            self.panel.bt_show_code(addr, str(passkey))
            invocation.return_value(None)
        elif method in ("RequestConfirmation", "RequestAuthorization",
                        "AuthorizeService"):
            args = params.unpack()
            addr = args[0]
            code = args[1] if method == "RequestConfirmation" else None
            self.panel.bt_prompt_confirm(addr, code,
                                         lambda ok: _reply_void(invocation, ok))
        else:
            invocation.return_dbus_error("org.bluez.Error.Failed",
                                         "unsupported agent method %s" % method)


def _pretty_mac(address):
    """BlueZ calls unnamed devices F4-B6-2D-55-7E-6D -- show a real MAC"""
    if not address:
        return "unknown device"
    text = str(address)
    if "-" in text and ":" not in text:
        return text.replace("-", ":")
    return text


def _unpack(props, key, default=None):
    """read a property from a D-Bus dict.

    GetManagedObjects hands the values over already unpacked, while
    PropertiesChanged delivers them as GLib.Variant — accept both.
    """
    value = props.get(key)
    if value is None:
        return default
    if hasattr(value, "unpack"):
        try:
            return value.unpack()
        except Exception:
            return default
    return value


def _finish(conn, res, cb):
    try:
        conn.call_finish(res)
        ok, err = True, ""
    except GLib.Error as exc:
        ok, err = False, exc.message
    if cb:
        cb(ok, err)
    return ok


def _reply_void(invocation, ok):
    if ok:
        invocation.return_value(None)
    else:
        invocation.return_dbus_error("org.bluez.Error.Canceled",
                                     "cancelled by the user")


def _reply_text(invocation, ok, text):
    if ok:
        invocation.return_value(GLib.Variant("(s)", (text or "",)))
    else:
        invocation.return_dbus_error("org.bluez.Error.Canceled",
                                     "cancelled by the user")


def _reply_uint(invocation, ok, text):
    if ok:
        try:
            value = int((text or "0").strip())
        except ValueError:
            value = 0
        invocation.return_value(GLib.Variant("(u)", (value,)))
    else:
        invocation.return_dbus_error("org.bluez.Error.Canceled",
                                     "cancelled by the user")


# ── the panel ───────────────────────────────────────────────────────────────
class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("System Menu")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.NONE)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
        self.get_style_context().add_class("panel-window")

        self.runner = Runner()
        self.state = {
            "wifi_on": None, "ssid": "", "bt_on": None,
            "profile": "balanced", "dark": False, "dnd": False,
            "volume": 0, "brightness": brightness(),
        }
        self.wifi_nets = []
        self.wifi_saved = {}
        self._wifi_cache = None
        self._wifi_epoch = 0
        self._bt_started = False
        self._bt_built_at = 0
        self._bt_timer = None
        self._modal_open = False
        self._modal_on_ok = None
        self._dragging = False
        self._updating = False
        self._vol_timer = None
        self._vol_target = 0
        self._vol_applied = -1
        self._bri_timer = None
        self._bri_target = 0
        self._bri_applied = -1
        self._poller = None
        self._armed = False
        self._positioned = False
        self._docked = self._dock()

        self.overlay = Gtk.Overlay()
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.get_style_context().add_class("panel")
        root.set_border_width(0)
        self.overlay.add(root)
        self.add(self.overlay)

        root.pack_start(self._header(), False, False, 0)

        # status line for actions that run in the background
        self.banner = Gtk.Label()
        self.banner.get_style_context().add_class("banner")
        self.banner.set_xalign(0)
        self.banner.set_ellipsize(Pango.EllipsizeMode.END)
        self.banner.set_no_show_all(True)
        root.pack_start(self.banner, False, False, 0)

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

        self._make_modal()

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
            ("\uf013", "Settings", ["gnome-control-center"]),
            ("\uf030", "Screenshot", ["%s/.config/river/screenshot.sh" % HOME]),
        ):
            b = Gtk.Button()
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.get_style_context().add_class("round")
            b.set_tooltip_text(tip)
            lbl = Gtk.Label()
            lbl.set_markup("<span font_family='%s' size='13pt'>%s</span>" % (FA, icon))
            b.add(lbl)
            b.connect("clicked", lambda _b, a=action: (self.runner.spawn(a), self.close()))
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
        ico.set_markup("<span font_family='%s' size='15pt'>%s</span>" % (FA, icon))
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
        sl.set_markup("<span font_family='%s' size='9pt'>\uf105</span>" % FA)
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
        ico.set_markup("<span font_family='%s' size='12pt'>%s</span>" % (FA, icon))
        ico.set_valign(Gtk.Align.CENTER)
        box.pack_start(ico, False, False, 0)
        adj = Gtk.Adjustment(value=value, lower=0, upper=100,
                             step_increment=2, page_increment=10)
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_valign(Gtk.Align.CENTER)
        scale.get_style_context().add_class("slider")
        scale.connect("value-changed", on_change)
        scale.connect("button-press-event", self._on_drag_start)
        scale.connect("button-release-event", self._on_drag_end)
        box.pack_start(scale, True, True, 0)
        lbl = Gtk.Label(label="%d%%" % value)
        lbl.get_style_context().add_class("slider-value")
        lbl.set_valign(Gtk.Align.CENTER)
        box.pack_start(lbl, False, False, 0)
        return box, scale, lbl

    def _sliders(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox, self.s_vol, self.s_vol_label = self._slider(
            "\uf028", self.state["volume"], self._on_vol)
        bbox, self.s_bri, self.s_bri_label = self._slider(
            "\uf185", self.state["brightness"], self._on_bri)
        box.pack_start(vbox, False, False, 0)
        box.pack_start(bbox, False, False, 0)
        return box

    def _on_drag_start(self, _scale, _event):
        self._dragging = True
        return False

    def _on_drag_end(self, _scale, _event):
        self._dragging = False
        return False

    # ── session actions ──────────────────────────────────────────────────
    def _sessions(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_homogeneous(True)
        actions = (
            ("\uf023", "Lock", ["swaylock", "-f"]),
            ("\uf08b", "Log out", ["%s/.local/bin/riverctl" % HOME, "exit"]),
            ("\uf021", "Reboot", ["systemctl", "reboot"]),
            ("\uf186", "Suspend", ["systemctl", "suspend"]),
            ("\uf011", "Power off", ["systemctl", "poweroff"]),
        )
        for icon, tip, action in actions:
            b = Gtk.Button()
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.get_style_context().add_class("session")
            b.set_tooltip_text(tip)
            lbl = Gtk.Label()
            lbl.set_markup("<span font_family='%s' size='12pt'>%s</span>" % (FA, icon))
            b.add(lbl)
            b.connect("clicked", lambda _b, a=action: (self.runner.spawn(a), self.close()))
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
            il.set_markup("<span font_family='%s' size='11pt'>%s</span>" % (FA, icon))
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

    def _clear(self, lst):
        for child in list(lst.get_children()):
            lst.remove(child)

    def _wifi_page(self):
        box, lst = self._page_box("Available networks")
        self.wifi_list = lst
        return box

    def _bt_page(self):
        box, lst = self._page_box("Bluetooth devices")
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
            self._fill_wifi_list()
        elif name == "bt":
            self._fill_bt_list()
        else:
            self._refresh_async()

    # ── Wi-Fi ────────────────────────────────────────────────────────────
    def _fill_wifi_list(self):
        """cached list first, never a blocking rescan"""
        self._wifi_epoch += 1
        epoch = self._wifi_epoch
        self._clear(self.wifi_list)
        # nmcli can take seconds while a scan is running, so show the last
        # known list from disk right away and refresh it in the background
        cached = self._read_wifi_cache()
        if cached:
            self._wifi_list_ready(cached, "", 0, epoch)
        else:
            self.wifi_list.add(self._row("Loading networks…", "reading the cache"))
        self.runner.run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                         "device", "wifi", "list", "--rescan", "no"],
                        lambda out, err, rc: self._wifi_list_ready(out, err, rc, epoch))
        self._load_saved_wifi()

    def _read_wifi_cache(self):
        try:
            with open(os.path.join(STATE, "wifi-list")) as fh:
                return fh.read()
        except OSError:
            return ""

    def _write_wifi_cache(self, text):
        try:
            os.makedirs(STATE, exist_ok=True)
            with open(os.path.join(STATE, "wifi-list"), "w") as fh:
                fh.write(text)
        except OSError:
            pass

    def _wifi_list_ready(self, out, err, rc, epoch):
        if epoch != self._wifi_epoch:
            return
        self._wifi_cache = out if rc == 0 else ""
        if rc == 0:
            self._write_wifi_cache(self._wifi_cache)
        nets = parse_wifi_list(self._wifi_cache)
        self.wifi_nets = nets
        self._clear(self.wifi_list)
        if not nets:
            self.wifi_list.add(self._row("No networks found",
                                         "the radio may be off"))
            if self.state["wifi_on"]:
                self.wifi_list.add(self._row("scan for networks…", "takes a few seconds",
                                             on_click=lambda _r: self._rescan_wifi()))
        for net in nets:
            ssid = net["ssid"]
            saved = ssid in self.wifi_saved
            if net["in_use"]:
                label = "✓ " + ssid
                sub = "connected" + (" · saved" if saved else "")
                action = None
            else:
                label = ssid
                bits = ["%d%%" % net["signal"]]
                if is_enterprise(net["security"]):
                    bits.append("enterprise")
                elif is_secured(net["security"]):
                    bits.append("secured" + (" · saved" if saved else " · password needed"))
                else:
                    bits.append("open")
                sub = " · ".join(bits)
                action = (lambda _r, s=ssid: self._connect_wifi(s))
            self.wifi_list.add(self._row(label, sub, icon="\uf0eb", on_click=action))
        self.wifi_list.add(self._row("manage connections…", "nm-connection-editor",
                                     on_click=lambda _r: self._launch(["nm-connection-editor"])))
        self.wifi_list.add(self._row("rescan", "search for networks again",
                                     on_click=lambda _r: self._rescan_wifi()))

    def _load_saved_wifi(self):
        """map SSID -> saved NetworkManager profile (async, chained)"""
        def got_profiles(out, err, rc):
            if rc != 0:
                return
            profiles = []
            for line in out.splitlines():
                parts = _split_terse(line)
                if len(parts) >= 2 and parts[1] == "802-11-wireless":
                    profiles.append(parts[0])
            saved = {}

            def step(index):
                if index >= len(profiles):
                    self.wifi_saved = saved
                    # re-render so the rows can show "saved" / "password needed"
                    if self._wifi_cache is not None:
                        self._wifi_list_ready(self._wifi_cache, "", 0, self._wifi_epoch)
                    return
                name = profiles[index]

                def got_ssid(out2, _err2, rc2):
                    ssid = ""
                    if rc2 == 0 and out2.strip():
                        ssid = out2.strip().splitlines()[0]
                    if ssid:
                        saved[ssid] = name
                    step(index + 1)

                self.runner.run(["nmcli", "-g", "802-11-wireless.ssid",
                                 "connection", "show", name], got_ssid, timeout=8)
            step(0)

        self.runner.run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
                        got_profiles, timeout=8)

    def _rescan_wifi(self):
        self._wifi_epoch += 1
        epoch = self._wifi_epoch
        self._clear(self.wifi_list)
        self.wifi_list.add(self._row("Scanning…", "this takes a few seconds"))

        def done(out, err, rc):
            if epoch != self._wifi_epoch:
                return
            self.runner.run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                             "device", "wifi", "list", "--rescan", "no"],
                            lambda o, e, r: self._wifi_list_ready(o, e, r, epoch))

        self.runner.run(["nmcli", "device", "wifi", "rescan"], done, timeout=25)

    def _connect_wifi(self, ssid):
        net = next((n for n in self.wifi_nets if n["ssid"] == ssid), None)
        security = net["security"] if net else ""
        saved = self.wifi_saved.get(ssid)
        if is_enterprise(security):
            self.note("%s needs enterprise setup — opening the editor" % ssid)
            self._launch(["nm-connection-editor"])
            return
        if saved:
            self._nmcli(["nmcli", "--wait", "30", "connection", "up", "id", saved],
                        "connecting to %s" % ssid)
            return
        if not is_secured(security):
            self._nmcli(["nmcli", "--wait", "30", "device", "wifi", "connect", ssid],
                        "connecting to %s" % ssid)
            return
        self._ask_password(ssid)

    def _ask_password(self, ssid):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        info = Gtk.Label(label="Password for %s" % ssid)
        info.set_xalign(0)
        info.get_style_context().add_class("row-sub")
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        entry.set_activates_default(True)
        show = Gtk.CheckButton(label="Show password")
        show.connect("toggled", lambda b: entry.set_visibility(b.get_active()))
        content.pack_start(info, False, False, 0)
        content.pack_start(entry, False, False, 0)
        content.pack_start(show, False, False, 0)

        def submit():
            password = entry.get_text()
            if not password:
                self._modal_error("The password is required.")
                return
            self._modal_busy(True)
            self._connect_with_password(ssid, password)

        entry.connect("activate", lambda _e: submit())
        self._open_modal("Wi-Fi", content, "Connect", submit)
        entry.grab_focus()

    def _connect_with_password(self, ssid, password):
        """try the secret on stdin first, fall back to the command line"""

        def failed(_out, err, _rc):
            self.runner.run(["nmcli", "--wait", "30", "device", "wifi", "connect",
                             ssid, "password", password],
                            lambda o, e, r: self._wifi_connected(ssid, r, e or o),
                            timeout=40)

        self.runner.run(["nmcli", "--ask", "--wait", "30", "device", "wifi",
                         "connect", ssid],
                        lambda o, e, r: (self._wifi_connected(ssid, r, e or o)
                                         if r == 0 else failed(o, e, r)),
                        timeout=40, stdin=password + "\n")

    def _wifi_connected(self, ssid, rc, err):
        if rc == 0:
            self._modal_close()
            self.note("Wi-Fi: connected to %s" % ssid)
            self._refresh_async()
            self._fill_wifi_list()
            return
        message = (err or "connection failed").strip()
        if message.startswith("Error:"):
            message = message[len("Error:"):].strip()
        self._modal_error(message or "connection failed")
        self._modal_busy(False)

    def _nmcli(self, argv, what):
        self.note(what + "…")

        def done(_out, err, rc):
            if rc == 0:
                self.note(what.replace("connecting to", "connected to"))
                self._refresh_async()
                self._fill_wifi_list()
            else:
                self.note((err or "failed").strip())

        self.runner.run(argv, done, timeout=40)

    # ── Bluetooth ────────────────────────────────────────────────────────
    def _bt(self):
        if not hasattr(self, "bt_backend"):
            self.bt_backend = Bt(self)
            self.bt_backend.on_update = self._bt_updated
        return self.bt_backend

    def _fill_bt_list(self):
        bt = self._bt()
        if not self._bt_started:
            self._bt_started = True
            bt.start()
        self._bt_updated()

    def _bt_updated(self):
        bt = self._bt()
        if getattr(self, "bt_list", None) is None:
            return
        # a scan produces a stream of RSSI updates -> rebuild at most twice
        # a second instead of on every signal
        now = time.monotonic()
        if now - getattr(self, "_bt_built_at", 0) < 0.5:
            if self._bt_timer is None:
                self._bt_timer = GLib.timeout_add(500, self._bt_rebuild)
            return
        self._bt_built_at = now
        self._bt_render()

    def _bt_rebuild(self):
        self._bt_timer = None
        self._bt_built_at = 0
        self._bt_render()
        return False

    def _bt_render(self):
        bt = self._bt()
        on = bt.adapter_on
        self.state["bt_on"] = on
        if on is None:
            label, active = "Bluetooth…", False
        elif on:
            label, active = "Bluetooth", True
        else:
            label, active = "Bluetooth off", False
        self._set_tile(self.t_bt, label, "\uf293", active)
        self._clear(self.bt_list)
        if on is None:
            self.bt_list.add(self._row("Reading the adapter state…", ""))
            return
        if not on:
            self.bt_list.add(self._row("Bluetooth is off", "tap to turn it on",
                                       icon="\uf293",
                                       on_click=lambda _r: self._act_bt(None)))
            return
        devices = bt.ordered_devices()
        if not devices:
            self.bt_list.add(self._row("No devices yet", "scan for devices",
                                       icon="\uf293"))
        for dev in devices:
            if dev["connected"]:
                sub = "connected · click to disconnect"
                action = (lambda _r, d=dev: self._bt_device(d, "Disconnect"))
            elif dev["paired"]:
                sub = "paired · click to connect"
                action = (lambda _r, d=dev: self._bt_device(d, "Connect"))
            else:
                bits = ["click to pair"]
                if dev["rssi"] is not None and dev["rssi"] > -120:
                    bits.append("%d%%" % max(0, min(100, (dev["rssi"] + 100) * 2)))
                sub = " · ".join(bits)
                action = (lambda _r, d=dev: self._bt_device(d, "Pair"))
            self.bt_list.add(self._row(dev["name"], sub, icon="\uf293",
                                       on_click=action))
        self.bt_list.add(self._row("scan for devices" if not bt.scanning
                                   else "stop scanning",
                                   "discovery runs for 20 seconds",
                                   on_click=lambda _r: self._bt_scan()))
        self.bt_list.add(self._row("open bluetooth manager", "blueman-manager",
                                   on_click=lambda _r: self._launch(["blueman-manager"])))

    def _bt_scan(self):
        bt = self._bt()
        if bt.scanning:
            bt.stop_discovery()
        else:
            bt.start_discovery()
        self._bt_updated()

    def _bt_device(self, dev, action):
        bt = self._bt()
        addr = dev["address"]
        if action == "Disconnect":
            bt.device_call(addr, "Disconnect", lambda ok, err: self._bt_result(addr, ok, err))
        elif action == "Connect":
            bt.device_call(addr, "Connect", lambda ok, err: self._bt_result(addr, ok, err))
        else:
            self.note("Bluetooth: pairing %s…" % dev["name"])
            bt.device_call(addr, "Pair",
                           lambda ok, err: self._bt_paired(addr, ok, err))

    def _bt_paired(self, addr, ok, err):
        if not ok:
            self.note("Bluetooth: pairing failed (%s)" % err)
            return
        bt = self._bt()
        bt.trust(addr, lambda _ok, _err: bt.device_call(
            addr, "Connect", lambda o, e: self._bt_result(addr, o, e)))

    def _bt_result(self, addr, ok, err):
        if ok:
            self.note("Bluetooth: %s" % addr)
        else:
            self.note("Bluetooth: %s" % (err or "failed"))
        self._bt_updated()

    # -- pairing prompts --------------------------------------------------
    def bt_prompt_confirm(self, addr, code, cb):
        dev = self._bt().devices.get(addr, {})
        name = dev.get("name", addr)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        text = "Confirm the request from %s?" % name
        if code:
            text = "Does %s show the code %06d?" % (name, code)
        lbl = Gtk.Label(label=text)
        lbl.set_line_wrap(True)
        lbl.set_xalign(0)
        content.pack_start(lbl, False, False, 0)

        def submit():
            self._modal_close()
            cb(True)

        self._open_modal("Bluetooth", content, "Confirm", submit)

    def bt_prompt_entry(self, addr, what, numeric, cb):
        dev = self._bt().devices.get(addr, {})
        name = dev.get("name", addr)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        lbl = Gtk.Label(label="Enter the %s for %s" % (what.lower(), name))
        lbl.set_xalign(0)
        entry = Gtk.Entry()
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        entry.set_activates_default(True)
        if numeric:
            entry.set_max_length(6)
        content.pack_start(lbl, False, False, 0)
        content.pack_start(entry, False, False, 0)

        def submit():
            text = entry.get_text().strip()
            if not text:
                self._modal_error("A value is required.")
                return
            self._modal_close()
            cb(True, text)

        entry.connect("activate", lambda _e: submit())
        self._open_modal("Bluetooth", content, "OK", submit)
        entry.grab_focus()

    def bt_show_code(self, addr, code):
        dev = self._bt().devices.get(addr, {})
        self.note("Bluetooth: enter the code %s on %s" % (code, dev.get("name", addr)))

    def bt_cancel_pending(self):
        self._modal_close()

    # ── modal overlay ────────────────────────────────────────────────────
    def _make_modal(self):
        self._modal_scrim = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._modal_scrim.get_style_context().add_class("modal-scrim")
        # show_all() would reveal the scrim and dim the whole panel, so it
        # must opt out of it and only appear while a modal is open
        self._modal_scrim.set_no_show_all(True)
        self._modal_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._modal_card.get_style_context().add_class("modal-card")
        self._modal_card.set_halign(Gtk.Align.CENTER)
        self._modal_card.set_valign(Gtk.Align.CENTER)
        # pack with expand so the card is centred in the scrim
        self._modal_scrim.pack_start(self._modal_card, True, True, 0)
        self.overlay.add_overlay(self._modal_scrim)
        self._modal_scrim.set_visible(False)

    def _open_modal(self, title, content, ok_label, on_ok):
        self._modal_on_ok = on_ok
        for child in list(self._modal_card.get_children()):
            self._modal_card.remove(child)
        head = Gtk.Label(label=title)
        head.get_style_context().add_class("page-title")
        head.set_xalign(0)
        self._modal_card.pack_start(head, False, False, 0)
        self._modal_card.pack_start(content, False, False, 0)
        self._modal_error_label = Gtk.Label()
        self._modal_error_label.get_style_context().add_class("modal-error")
        self._modal_error_label.set_line_wrap(True)
        self._modal_error_label.set_xalign(0)
        self._modal_card.pack_start(self._modal_error_label, False, False, 0)
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        cancel.get_style_context().add_class("session")
        cancel.connect("clicked", lambda _b: self._modal_close())
        ok = Gtk.Button(label=ok_label)
        ok.get_style_context().add_class("session")
        ok.connect("clicked", lambda _b: self._modal_on_ok and self._modal_on_ok())
        self._modal_ok_btn = ok
        buttons.pack_start(cancel, False, False, 0)
        buttons.pack_start(ok, False, False, 0)
        self._modal_card.pack_start(buttons, False, False, 0)
        self._modal_error_label.set_text("")
        self._modal_card.show_all()
        self._modal_scrim.set_visible(True)
        self._modal_open = True
        self._set_keyboard_mode(_KB_EXCLUSIVE)

    def _modal_error(self, text):
        if getattr(self, "_modal_error_label", None) is not None:
            self._modal_error_label.set_text(text)

    def _modal_busy(self, busy, message="Working…"):
        """disable the confirm button while a command is running"""
        if getattr(self, "_modal_ok_btn", None) is None:
            return
        self._modal_ok_btn.set_sensitive(not busy)
        if busy:
            self._modal_error(message)

    def _modal_close(self):
        if getattr(self, "_modal_scrim", None) is not None:
            self._modal_scrim.set_visible(False)
        self._modal_open = False
        self._modal_on_ok = None
        self._set_keyboard_mode(_KB_ON_DEMAND)

    def note(self, text):
        """status line in the panel + a log line for debugging"""
        if getattr(self, "banner", None) is not None:
            self.banner.set_text(text)
            self.banner.show()
        try:
            os.makedirs(STATE, exist_ok=True)
            with open(os.path.join(STATE, "panel.log"), "a") as fh:
                fh.write("%s %s\n" % (time.strftime("%H:%M:%S"), text))
        except OSError:
            pass

    # ── actions ──────────────────────────────────────────────────────────
    def _launch(self, argv):
        self.runner.spawn(argv)
        self.close()

    def _act_wifi(self, _b):
        on = bool(self.state["wifi_on"])
        self.state["wifi_on"] = not on
        self._set_tile(self.t_wifi, "Wi-Fi…" if not on else "Wi-Fi off",
                       "\uf0eb", not on)
        self.runner.run(["nmcli", "radio", "wifi", "off" if on else "on"],
                        lambda _o, _e, _rc: self._refresh_async(), timeout=10)

    def _act_bt(self, _b):
        bt = self._bt()
        if not self._bt_started:
            self._bt_started = True
            bt.start()
        if bt.adapter_on is None:
            self.note("Bluetooth: reading the adapter state…")
            return
        want = not bt.adapter_on
        self.state["bt_on"] = want
        self._set_tile(self.t_bt, "Bluetooth…" if want else "Bluetooth off",
                       "\uf293", want)
        bt.set_power(want, lambda _ok, _err: self._bt_updated())

    def _act_profile(self, _b):
        p = self.state["profile"]
        nxt = PROFILES[(PROFILES.index(p) + 1) % len(PROFILES)] if p in PROFILES else "balanced"
        self.state["profile"] = nxt
        self._set_tile(self.t_prof, nxt.capitalize(), PROFILE_ICON.get(nxt, "\uf013"),
                       nxt != "balanced")
        self.runner.run(["powerprofilesctl", "set", nxt],
                        lambda _o, _e, _rc: self._refresh_async(), timeout=10)

    def _act_dark(self, _b):
        want_dark = not self.state["dark"]
        self.state["dark"] = want_dark
        self._set_tile(self.t_dark, "Dark mode", "\uf186", want_dark)
        self.runner.run(["gsettings", "set", "org.gnome.desktop.interface",
                         "color-scheme", "prefer-light" if want_dark else "prefer-dark"],
                        lambda _o, _e, _rc: self._refresh_async(), timeout=10)

    def _act_dnd(self, _b):
        self.runner.run(["dunstctl", "set-paused", "toggle"],
                        lambda _o, _e, _rc: self._refresh_async(), timeout=10)

    def _act_shot(self, _b):
        self.runner.spawn(["%s/.config/river/screenshot.sh" % HOME])
        self.close()

    # ── sliders: throttled, live ─────────────────────────────────────────
    def _on_vol(self, scale):
        if self._updating:
            return
        value = int(scale.get_value())
        self._vol_target = value
        self.s_vol_label.set_text("%d%%" % value)
        if self._vol_timer is None:
            self._vol_timer = GLib.timeout_add(50, self._pump_vol)

    def _pump_vol(self):
        if self._vol_target == self._vol_applied:
            self._vol_timer = None
            return False
        value = self._vol_target
        self._vol_applied = value
        self.runner.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@",
                         "%.2f" % (value / 100.0)],
                        lambda _o, _e, _rc: None, timeout=5)
        return True

    def _on_bri(self, scale):
        if self._updating:
            return
        value = int(scale.get_value())
        self._bri_target = value
        self.s_bri_label.set_text("%d%%" % value)
        if self._bri_timer is None:
            self._bri_timer = GLib.timeout_add(80, self._pump_bri)

    def _pump_bri(self):
        if self._bri_target == self._bri_applied:
            self._bri_timer = None
            return False
        value = self._bri_target
        self._bri_applied = value
        self.runner.run(["%s/.config/waybar/brightness.sh" % HOME, "set", str(value)],
                        lambda _o, _e, _rc: None, timeout=6)
        return True

    def _set_scale(self, scale, label, value):
        self._updating = True
        scale.set_value(value)
        label.set_text("%d%%" % value)
        self._updating = False

    def _poll_hardware(self):
        """keep the sliders in sync with the outside world"""
        if self._dragging:
            return True
        value = brightness()
        if value != self.state["brightness"]:
            self.state["brightness"] = value
            self._set_scale(self.s_bri, self.s_bri_label, value)
        self.runner.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                        lambda out, _e, rc: self._volume_poll(out, rc), timeout=5)
        return True

    def _volume_poll(self, out, rc):
        if rc != 0 or self._dragging:
            return
        value = parse_volume(out)
        if value is None or value == self.state["volume"]:
            return
        self.state["volume"] = value
        self._set_scale(self.s_vol, self.s_vol_label, value)
        self._vol_applied = value

    # ── state refresh ────────────────────────────────────────────────────
    def _refresh_fast(self):
        cap, st = battery()
        if cap is None:
            self.battery_label.set_text("No battery")
        else:
            glyph = {"charging": "\uf0e7", "full": "\uf240"}.get(st, "\uf240")
            extra = (" · charging" if st == "charging"
                     else " · on charger" if st == "not charging" else "")
            self.battery_label.set_markup(
                "<span font_family='%s' size='12pt'>%s</span>  %d%%"
                "<span size='small'>%s</span>" % (FA, glyph, cap, extra))
        self.state["brightness"] = brightness()
        self._set_scale(self.s_bri, self.s_bri_label, self.state["brightness"])

    def _refresh_async(self):
        self._refresh_fast()
        self.runner.run(["nmcli", "radio", "wifi"],
                        lambda out, _e, rc: self._wifi_state(out, rc), timeout=8)
        self.runner.run(["powerprofilesctl", "get"],
                        lambda out, _e, rc: self._profile_state(out, rc), timeout=8)
        self.runner.run(["gsettings", "get", "org.gnome.desktop.interface",
                         "color-scheme"],
                        lambda out, _e, _rc: self._dark_state(out), timeout=8)
        self.runner.run(["dunstctl", "is-paused"],
                        lambda out, _e, _rc: self._dnd_state(out), timeout=8)
        self.runner.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                        lambda out, _e, rc: self._volume_poll(out, rc), timeout=8)

    def _wifi_state(self, out, rc):
        on = rc == 0 and "enabled" in out
        self.state["wifi_on"] = on
        self.runner.run(["nmcli", "-t", "-f", "IN-USE,SSID", "device", "wifi",
                         "list", "--rescan", "no"],
                        lambda o, _e, r: self._ssid_state(o, r), timeout=8)

    def _ssid_state(self, out, rc):
        ssid = ""
        for line in out.splitlines():
            parts = _split_terse(line)
            if len(parts) > 1 and parts[0] == "*":
                ssid = parts[1]
                break
        self.state["ssid"] = ssid
        self._set_tile(self.t_wifi, ssid or ("Wi-Fi" if self.state["wifi_on"]
                                             else "Wi-Fi off"),
                       "\uf0eb", bool(self.state["wifi_on"]))
        self.t_wifi.set_tooltip_text("Wi-Fi: %s" % ssid if ssid
                                      else ("Wi-Fi is off" if not self.state["wifi_on"]
                                            else "Wi-Fi"))

    def _profile_state(self, out, rc):
        p = out.strip() or "balanced"
        self.state["profile"] = p
        self._set_tile(self.t_prof, p.capitalize(), PROFILE_ICON.get(p, "\uf013"),
                       p != "balanced")

    def _dark_state(self, out):
        dark = "dark" in out
        self.state["dark"] = dark
        self._set_tile(self.t_dark, "Dark mode", "\uf186", dark)

    def _dnd_state(self, out):
        dnd = out.strip() == "true"
        self.state["dnd"] = dnd
        self._set_tile(self.t_dnd, "Do not disturb", "\uf0f3", dnd)

    def _set_tile(self, widget, text, icon, active):
        btn = getattr(widget, "_tile_button", widget)
        lbl = btn._tile_label
        lbl.set_text(text)
        ctx = btn.get_style_context()
        if active:
            ctx.add_class("active")
        else:
            ctx.remove_class("active")

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

    def _set_keyboard_mode(self, mode):
        if _ls is None:
            return
        try:
            _ls.gtk_layer_set_keyboard_mode(ctypes.c_void_p(hash(self)), mode)
        except Exception:
            pass

    def _on_show(self, _w):
        self._refresh_fast()
        self._refresh_async()
        self._mapped_at = time.monotonic()
        self._had_focus = False
        self._poller = GLib.timeout_add(1000, self._poll_hardware)
        # diagnostic hook: RIVER_PANEL_OPEN=wifi|bt opens that page directly
        page = os.environ.get("RIVER_PANEL_OPEN", "")
        if page in ("wifi", "bt"):
            GLib.timeout_add(500, lambda: (self._show_page(page), False)[1])
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

    def _arm(self):
        self._armed = True
        return False

    def _dismiss_watch(self):
        """GNOME-like dismiss: if the pointer leaves the panel, close it"""
        if not self.get_mapped() or self._modal_open:
            return True
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
            if self._modal_open:
                self._modal_close()
            else:
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
        # panel instantly).  A modal dialog also takes the focus away on
        # purpose — do not close the panel while one is open.
        if self._modal_open:
            return False
        age = time.monotonic() - getattr(self, "_mapped_at", 0.0)
        if getattr(self, "_had_focus", False) and age > 0.8:
            self.close()
        self._had_focus = False
        return False

    def close(self):
        self.runner.close()
        try:
            if getattr(self, "bt_backend", None) is not None:
                self.bt_backend.stop_discovery()
        except Exception:
            pass
        if self._poller:
            GLib.source_remove(self._poller)
            self._poller = None
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
label.banner { color: #2aa198; font-size: 11px; }
label.slider-value { color: #93a1a1; font-size: 11px; min-width: 34px; }

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

/* modal card (wifi password, bluetooth passkey) */
.modal-scrim {
    background-color: rgba(0, 43, 54, 0.92);
    border-radius: 12px;
}
.modal-card {
    background-color: #073642;
    border: 1px solid #0b4a58;
    border-radius: 10px;
    padding: 12px;
    min-width: 260px;
}
label.modal-error { color: #dc322f; font-size: 11px; }
entry { background-color: #002b36; color: #fdf6e3; border: 1px solid #0b4a58; border-radius: 6px; padding: 5px; }

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


def self_check():
    """parse-level checks that do not need a display"""
    nets = parse_wifi_list("*:Home:88:WPA2\n:OpenNet:55:\n*:Home:70:WPA2\n")
    ok = True
    ok &= any(n["ssid"] == "Home" and n["in_use"] and n["signal"] == 88
              for n in nets)
    ok &= any(n["ssid"] == "OpenNet" and not n["in_use"] for n in nets)
    ok &= len(nets) == 2
    ok &= is_secured("WPA2") and not is_secured("") and not is_secured("--")
    ok &= is_enterprise("WPA2 802.1X") and not is_enterprise("WPA2")
    ok &= parse_volume("Volume: 0.62 [MUTED]") == 62
    ok &= parse_volume("Volume: 1.00") == 100
    print("self-check:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main():
    if "--check" in sys.argv:
        sys.exit(self_check())
    panel = Panel()
    apply_css()
    panel.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
