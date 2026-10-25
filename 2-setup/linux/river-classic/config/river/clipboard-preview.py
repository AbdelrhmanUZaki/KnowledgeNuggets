#!/usr/bin/env python3
"""Clipboard picker with image previews (GTK4, for river-classic).

Super+V popup over the cliphist history.  Text entries show their first
line; image entries show a real thumbnail decoded from the stored PNG.
Type to filter, Up/Down to move, Enter (or click) to copy the entry back
to the clipboard via wl-copy (which then holds the selection), Esc or
losing focus closes the window.

History comes from `cliphist list` (plain file ~/.cache/cliphist/db) -
this process is stateless and exits right after a pick.

Launched by clipboard-pick.sh; floats via the river rule
`rule-add -app-id org.riverclassic.Clippick float`.
"""

import io
import os
import subprocess
import threading

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402
from PIL import Image  # noqa: E402

APP_ID = "org.riverclassic.Clippick"
THUMB = 40            # thumbnail size in px (rendered 2x for hidpi)
MAX_ENTRIES = 200     # render at most this many rows

def is_image(line: str) -> bool:
    return "[[ binary data" in line and "png" in line


def row_label(line: str) -> str:
    """Human label for a cliphist list line (id + tab prefix stripped)."""
    body = line.split("\t", 1)[1] if "\t" in line else line
    if is_image(line):
        # [[ binary data 2 KiB png 200x100 ]] -> 🖼 200×100 PNG (2 KiB)
        parts = body.strip("[] ").split()
        try:
            size, unit, _, dims = parts[2], parts[3], parts[4], parts[5]
            return f"\U0001f5bc  {dims.replace('x', '×')} PNG · {size} {unit}"
        except (IndexError, ValueError):
            return "\U0001f5bc PNG image"
    return body.replace("\n", " ")[:120]


def cliphist_lines():
    out = subprocess.run(["cliphist", "list"], capture_output=True)
    lines = out.stdout.decode("utf-8", "replace").splitlines()
    return [l for l in lines if l.strip()][:MAX_ENTRIES]


def decode(line: str) -> bytes:
    return subprocess.run(
        ["cliphist", "decode"], input=line.encode() + b"\n", capture_output=True
    ).stdout


class Picker(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.win = None
        self.rows = []          # (listbox_row, line, is_img)
        self.was_active = False

    def do_activate(self):  # noqa: N802
        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_default_size(660, 560)
        self.win.set_decorated(False)
        self.win.connect("notify::is-active", self.on_active_changed)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Type to search the clipboard…")
        self.search.props.hexpand = True
        self.search.connect("changed", self.on_search_changed)
        self.search.connect("activate", self.on_search_activate)
        box.append(self.search)

        self.listbox = Gtk.ListBox()
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", self.on_row_activated)
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.listbox)
        scroll.set_vexpand(True)
        box.append(scroll)
        self.win.set_child(box)

        for line in cliphist_lines():
            self.add_row(line)

        self.apply_css()

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self.on_key_pressed)
        self.win.add_controller(keys)

        self.win.present()
        self.search.grab_focus()
        self.select_first_visible()

    # ---- UI helpers ------------------------------------------------------
    def add_row(self, line):
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image()
        icon.set_pixel_size(THUMB)
        if is_image(line):
            icon.set_from_icon_name("image-x-generic-symbolic")
        else:
            icon.set_from_icon_name("text-x-generic-symbolic")
        label = Gtk.Label(label=row_label(line), halign=Gtk.Align.START)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_single_line_mode(True)
        hbox.append(icon)
        hbox.append(label)
        row.set_child(hbox)
        self.listbox.append(row)
        self.rows.append((row, line))
        if is_image(line):
            threading.Thread(
                target=self.thumb_worker, args=(icon, line), daemon=True
            ).start()

    def thumb_worker(self, icon, line):
        """Decode + downscale an image entry off the UI thread."""
        try:
            img = Image.open(io.BytesIO(decode(line)))
            img.thumbnail((THUMB * 2, THUMB * 2))
            buf = io.BytesIO()
            img.save(buf, "PNG")
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))
            GLib.idle_add(lambda t=texture, icon=icon: icon.set_from_paintable(t) or False)
        except Exception:
            pass

    def apply_css(self):
        css = b"""
        window { background: rgba(30, 30, 46, 0.97); border-radius: 14px; }
        entry { background: #313244; color: #cdd6f4; border-radius: 10px;
                padding: 10px 12px; font-size: 15px; border: none; }
        row { padding: 7px 10px; border-radius: 10px; }
        row:selected { background: #45475a; }
        label { color: #cdd6f4; font-size: 15px; }
        """
        prov = Gtk.CssProvider()
        prov.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ---- behaviour -------------------------------------------------------
    def on_active_changed(self, win, _pspec):
        if win.props.is_active:
            self.was_active = True
        elif self.was_active:  # clicked outside -> close, like fuzzel
            self.quit()

    def visible_rows(self):
        return [r for r in self.rows if r[0].props.visible]

    def select_first_visible(self):
        vis = self.visible_rows()
        if vis:
            self.listbox.select_row(vis[0][0])

    def on_search_changed(self, _entry):
        needle = self.search.get_text().casefold()
        for row, line in self.rows:
            row.props.visible = needle in row_label(line).casefold()
        self.select_first_visible()

    def on_search_activate(self, _entry):
        row = self.listbox.get_selected_row()
        if row is not None:
            self.pick(row)

    def on_key_pressed(self, _ctl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Down or keyval == Gdk.KEY_Up:
            vis = self.visible_rows()
            if not vis:
                return True
            cur = self.listbox.get_selected_row()
            idx = next((i for i, (r, _) in enumerate(vis) if r == cur), 0)
            idx = max(0, min(len(vis) - 1, idx + (1 if keyval == Gdk.KEY_Down else -1)))
            self.listbox.select_row(vis[idx][0])
            return True
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        return False

    def on_row_activated(self, _box, row):
        self.pick(row)

    def pick(self, row):
        line = next(l for r, l in self.rows if r == row)
        data = decode(line)
        cmd = ["wl-copy", "-t", "image/png"] if is_image(line) else ["wl-copy"]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        proc.communicate(data)  # wl-copy forks and keeps holding the selection
        self.quit()


if __name__ == "__main__":
    if not os.environ.get("WAYLAND_DISPLAY"):
        raise SystemExit("no WAYLAND_DISPLAY")
    Picker().run([])
