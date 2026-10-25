#!/usr/bin/env python3
"""Notification center (GTK4, for river-classic).

Super+N popup over dunst's history (``dunstctl history``): every
notification that already disappeared, browsable - app icon, bold
summary, full wrapped body, "app · 3 min ago", one-click dismiss per
row (``dunstctl history-rm``), Clear all and a Do-Not-Disturb toggle.

Stateless like the clipboard picker: reads history on open, refreshes
every 10 s while open, exits on Esc or focus loss.  dunst remains the
only daemon; nothing here runs in the background.

Launched by notify-center.sh; floats via the river rule
`rule-add -app-id org.riverclassic.NotifyCenter float`.
"""

import html
import json
import os
import re
import subprocess
import threading
import time

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

APP_ID = "org.riverclassic.NotifyCenter"
REFRESH_SECS = 3
LOG = os.path.expanduser("~/.local/state/river-classic/notify-center.log")

BG = "#1e1e2e"             # same palette as clipboard-preview.py
BG_ALT = "#313244"
BG_SEL = "#45475a"
FG = "#cdd6f4"
FG_BRIGHT = "#ffffff"
FG_DIM = "#8f9ac2"
ACCENT = "#89b4fa"

CSS = f"""
window, window.background {{
    background-color: {BG};
    border-radius: 14px;
}}
label {{ color: {FG}; }}
label.nc-title {{ font-size: 16px; font-weight: 700; }}
label.nc-meta {{ color: {FG_DIM}; font-size: 12px; }}
label.nc-summary {{ font-weight: 700; font-size: 15px; }}
label.nc-body {{ font-size: 13px; }}
label.nc-empty {{ color: {FG_DIM}; font-size: 15px; }}
list {{ background-color: transparent; }}
row {{ background-color: transparent; border-radius: 10px; padding: 4px; }}
row:hover {{ background-color: #3b3d52; }}
button {{
    background-color: {BG_ALT}; color: {FG};
    border-radius: 8px; padding: 6px 12px; font-size: 13px;
}}
button:hover {{ background-color: #3b3d52; }}
button.nc-x {{ padding: 2px 9px; color: {FG_DIM}; }}
button.nc-x:hover {{ color: {FG_BRIGHT}; }}
button.nc-dnd-on {{ color: {ACCENT}; }}
"""

def log_error(where, exc):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as fh:
            fh.write(f"{where}: {exc!r}\n")
    except OSError:
        pass

def run(*cmd):
    return subprocess.run(cmd, capture_output=True).stdout

def getv(n, key, default=""):
    v = n.get(key)
    if isinstance(v, dict):
        return v.get("data", default)
    return default

def load_history():
    """dunstctl history -> plain list of dicts, newest first."""
    try:
        h = json.loads(run("dunstctl", "history").decode("utf-8", "replace"))
        notifs = h.get("data", [[]])[0] or []
        # dunst already returns newest-first, but sort by timestamp (us)
        # explicitly so the order can never depend on dunst internals.
        notifs.sort(key=lambda n: getv(n, "timestamp", 0), reverse=True)
        return notifs
    except Exception as e:
        log_error("history", e)
        return []

def is_paused():
    return b"true" in run("dunstctl", "is-paused")

def time_ago(ts_us):
    # dunst timestamps are CLOCK_MONOTONIC MICROSECONDS (since boot), not
    # epoch - comparing them to time.time() shows "20751 days ago".
    try:
        mono_now_us = time.clock_gettime(time.CLOCK_MONOTONIC) * 1e6
        secs = max(0, (mono_now_us - int(ts_us)) / 1e6)
    except (TypeError, ValueError, OSError):
        return ""
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return f"{int(secs // 86400)} d ago"

def body_text(n):
    """Plain, tag-free body (notifications may carry Pango markup)."""
    body = getv(n, "body", "")
    if not body:
        body = getv(n, "message", "")
    return html.unescape(re.sub(r"<[^>]+>", "", body)).strip()

def clickable(widget, fn):
    """Attach a click handler via an explicit GestureClick.

    Gtk.Button's built-in "clicked" is not triggered by this session's
    synthetic uinput pointer (a GestureClick is - verified on the picker
    and standalone tests); real mice fire both paths, so use the one that
    works everywhere.
    """
    gesture = Gtk.GestureClick()
    # CAPTURE phase: Gtk.Button's internal (bubble) gesture claims the
    # pointer sequence, so a bubble-phase controller never sees "released".
    gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    gesture.connect("released", lambda *_a: fn())
    widget.add_controller(gesture)
    return widget

class Center(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.win = None
        self.was_active = False
        self.paused = False
        self.monitored = None      # dbus-monitor child
        self._last_signal = 0.0    # refresh coalescing
        self.live = []             # notifications seen on D-Bus, popup still up

    def do_activate(self):  # noqa: N802
        Gtk.Settings.get_default().props.gtk_application_prefer_dark_theme = True

        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_default_size(780, 640)
        self.win.set_decorated(False)
        self.win.connect("notify::is-active", self.on_active_changed)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.title = Gtk.Label(label="Notifications", halign=Gtk.Align.START)
        self.title.add_css_class("nc-title")
        self.title.set_hexpand(True)
        header.append(self.title)

        self.dnd_btn = Gtk.Button(label="DND")
        clickable(self.dnd_btn, self.on_dnd_clicked)
        header.append(self.dnd_btn)

        clear = Gtk.Button(label="Clear all")
        clickable(clear, self.on_clear_clicked)
        header.append(clear)
        outer.append(header)

        self.listbox = Gtk.ListBox()
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.listbox)
        scroll.set_vexpand(True)
        outer.append(scroll)
        self.win.set_child(outer)

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(keys)

        self.win.present()
        self.refresh_async()
        self.watch_notifications()
        GLib.timeout_add_seconds(REFRESH_SECS, self.on_tick)

    def watch_notifications(self):
        """Track notifications the INSTANT they are sent.

        dunst moves a notification into its history only when the popup
        CLOSES (~5-10 s), so polling `dunstctl history` alone always lags.
        dbus-monitor sees every org.freedesktop.Notifications.Notify call
        WITH its arguments - those go into a live list that is merged with
        the history at render time (deduped on app+summary+body once the
        history copy lands). The 3 s tick stays as a safety net.
        """
        def reader():
            try:
                self.monitored = subprocess.Popen(
                    ["dbus-monitor", "--session",
                     "type='method_call',"
                     "interface='org.freedesktop.Notifications',member='Notify'"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                in_call = False
                args = []
                for line in self.monitored.stdout:
                    if "member=Notify" in line:
                        in_call, args = True, []
                        continue
                    if not in_call:
                        continue
                    if line[:1] not in (" ", "\t"):
                        # next header: flush what we collected
                        in_call = False
                        self._add_live(args)
                        continue
                    args.append(line.strip())
                # EOF: flush a trailing call
                if in_call and args:
                    self._add_live(args)
            except Exception as e:
                log_error("dbus-monitor", e)

        threading.Thread(target=reader, daemon=True).start()

    def _add_live(self, args):
        """Parse Notify args (app_name, replaces_id, icon, summary, body)."""
        strings = []
        for a in args:
            if a.startswith("string "):
                strings.append(a[8 - 1 :].strip('"')[:300])
            elif a.startswith("uint32 "):
                strings.append(a[7:])
        if len(strings) < 5:
            return
        app, _repl, _icon, summary, body = strings[0], strings[1], strings[2], strings[3], strings[4]
        info = {
            "appname": {"data": app},
            "summary": {"data": summary},
            "body": {"data": body},
            "timestamp": {"data": int(time.clock_gettime(time.CLOCK_MONOTONIC) * 1e6)},
            "urgency": {"data": "NORMAL"},
            "id": {"data": -1},
            "icon_path": {"data": ""},
            "_live": True,
        }
        GLib.idle_add(lambda: self.on_live(info) or False)

    def on_live(self, info):
        self.live = [n for n in self.live if not self._same(n, info)] + [info]
        self.live = self.live[-30:]
        self.refresh_async()
        return False

    @staticmethod
    def _same(a, b):
        return (
            getv(a, "appname") == getv(b, "appname")
            and getv(a, "summary") == getv(b, "summary")
            and getv(a, "body") == getv(b, "body")
        )

    def do_shutdown(self):  # noqa: N802
        if self.monitored is not None:
            try:
                self.monitored.kill()
            except Exception:
                pass
        Gtk.Application.do_shutdown(self)

    # ---- data ------------------------------------------------------------
    def on_tick(self):
        self.refresh_async()
        return GLib.Source.CONTINUE

    def refresh_async(self):
        threading.Thread(target=self.load, daemon=True).start()

    def load(self):
        notifs, paused = load_history(), is_paused()
        # Merge live (sent but popup still showing) entries with the
        # history; drop live copies whose history twin has landed.
        live = []
        for l in self.live:
            if not any(self._same(l, h) for h in notifs):
                live.append(l)
        self.live = live
        combined = notifs + live
        combined.sort(key=lambda n: getv(n, "timestamp", 0), reverse=True)
        GLib.idle_add(lambda: self.render(combined, paused) or False)

    def render(self, notifs, paused):
        while True:
            child = self.listbox.get_first_child()
            if child is None:
                break
            self.listbox.remove(child)

        self.paused = paused
        self.title.set_label(
            f"\U0001f514 {len(notifs)} notification"
            f"{'s' if len(notifs) != 1 else ''}"
        )
        self.dnd_btn.set_label(f"DND: {'ON' if paused else 'off'}")
        if paused:
            self.dnd_btn.add_css_class("nc-dnd-on")
        else:
            self.dnd_btn.remove_css_class("nc-dnd-on")

        if not notifs:
            empty = Gtk.Label(label="No notifications")
            empty.add_css_class("nc-empty")
            self.listbox.append(empty)
            return

        for n in notifs:
            self.listbox.append(self.make_row(n))

    def make_row(self, n):
        row = Gtk.ListBoxRow()
        row.props.activatable = False
        row.props.selectable = False
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        icon = Gtk.Image()
        icon.set_pixel_size(36)
        icon.set_valign(Gtk.Align.START)
        ipath = getv(n, "icon_path", "")
        app = getv(n, "appname", "") or "notification"
        if ipath and os.path.isfile(ipath):
            icon.set_from_file(ipath)
        else:
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            name = ipath or app.lower().replace(" ", "-")
            if not ipath and not theme.has_icon(name):
                name = "dialog-information-symbolic"
            icon.set_from_icon_name(name)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vbox.set_hexpand(True)

        summ = Gtk.Label(
            label=GLib.markup_escape_text(getv(n, "summary", "") or app),
            halign=Gtk.Align.START,
        )
        summ.set_xalign(0.0)
        summ.add_css_class("nc-summary")
        vbox.append(summ)

        body = body_text(n)
        if body:
            blab = Gtk.Label(label=body, halign=Gtk.Align.START)
            blab.set_xalign(0.0)
            blab.set_wrap(True)
            blab.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            blab.add_css_class("nc-body")
            vbox.append(blab)

        meta_bits = [app]
        ago = time_ago(getv(n, "timestamp", 0))
        if ago:
            meta_bits.append(ago)
        urg = getv(n, "urgency", "")
        if urg and urg != "NORMAL":
            meta_bits.append(urg.lower())
        meta = Gtk.Label(label=" · ".join(meta_bits), halign=Gtk.Align.START)
        meta.set_xalign(0.0)
        meta.add_css_class("nc-meta")
        vbox.append(meta)

        xbtn = Gtk.Button(label="\u2715")
        xbtn.add_css_class("nc-x")
        xbtn.set_valign(Gtk.Align.CENTER)
        if n.get("_live"):
            # not in dunst history yet (popup still up) - drop locally
            clickable(xbtn, lambda info=n: self.drop_live(info))
        else:
            nid = getv(n, "id", -1)
            clickable(xbtn, lambda i=nid: self.dismiss(i))

        hbox.append(icon)
        hbox.append(vbox)
        hbox.append(xbtn)
        row.set_child(hbox)
        return row

    # ---- actions ---------------------------------------------------------
    def drop_live(self, info):
        self.live = [x for x in self.live if x is not info]
        self.refresh_async()

    def dismiss(self, nid):
        def work():
            run("dunstctl", "history-rm", str(nid))
            GLib.idle_add(lambda: self.refresh_async() or False)

        threading.Thread(target=work, daemon=True).start()

    def on_clear_clicked(self):
        def work():
            run("dunstctl", "history-clear")
            GLib.idle_add(lambda: self.refresh_async() or False)

        threading.Thread(target=work, daemon=True).start()

    def on_dnd_clicked(self):
        def work():
            run("dunstctl", "set-paused", "toggle")
            GLib.idle_add(lambda: self.refresh_async() or False)

        threading.Thread(target=work, daemon=True).start()

    # ---- window behaviour --------------------------------------------------
    def on_key_pressed(self, _ctl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        return False

    def on_active_changed(self, win, _pspec):
        if win.props.is_active:
            self.was_active = True
            self.refresh_async()  # returning to the window = fresh list
        elif self.was_active:
            # Debounce: a new dunst popup briefly deactivates the window -
            # that must NOT close it. Only a focus change that sticks for
            # ~1 s (the user really clicked elsewhere) quits.
            def check(_win=win):
                try:
                    if not _win.props.is_active:
                        self.quit()
                except AttributeError:
                    pass  # window already gone
                return GLib.SOURCE_REMOVE

            GLib.timeout_add(1000, check)


if __name__ == "__main__":
    if not os.environ.get("WAYLAND_DISPLAY"):
        raise SystemExit("no WAYLAND_DISPLAY")
    Center().run([])
