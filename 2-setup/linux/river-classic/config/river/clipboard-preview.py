#!/usr/bin/env python3
"""Clipboard picker with image previews (GTK4, for river-classic).

Super+V popup over the cliphist history:
- left pane  - searchable list; text entries show their first line, image
  entries show a thumbnail and a "WxH PNG" label;
- right pane - large preview of the SELECTED entry: the image itself, or
  the full text (wrapped, selectable).

Type to filter, Up/Down to move (the preview follows the selection),
Enter (or click) to copy the entry back to the clipboard via wl-copy
(which then holds the selection), Esc or losing focus closes.

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
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402
from PIL import Image  # noqa: E402

APP_ID = "org.riverclassic.Clippick"
THUMB = 52            # list thumbnail size in px (rendered 2x for hidpi)
PREVIEW_MAX = (400, 540)  # large preview fits inside this box
MAX_ENTRIES = 200     # render at most this many rows

BG = "#1e1e2e"        # catppuccin-ish dark palette
BG_ALT = "#313244"
BG_SEL = "#45475a"
FG = "#cdd6f4"
FG_BRIGHT = "#ffffff"

CSS = f"""
window, window.background {{
    background-color: {BG};
    border-radius: 14px;
}}
entry, entry.search {{
    background-color: {BG_ALT};
    color: {FG};
    caret-color: {FG};
    border-radius: 10px;
    font-size: 15px;
    padding: 10px 12px;
}}
list {{
    background-color: transparent;
}}
row {{
    background-color: transparent;
    color: {FG};
    border-radius: 10px;
}}
row:hover {{ background-color: #3b3d52; }}
row:selected {{ background-color: {BG_SEL}; }}
row:selected label {{ color: {FG_BRIGHT}; }}
label {{ color: {FG}; }}
.preview-meta {{ color: #8f9ac2; font-size: 13px; }}
.preview-text {{ color: {FG}; font-size: 14px; }}
"""

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
            return f"\U0001f5bc {dims.replace('x', '×')} PNG · {size} {unit}"
        except (IndexError, ValueError):
            return "\U0001f5bc PNG image"
    return body.replace("\n", " ")[:110]


def cliphist_lines():
    out = subprocess.run(["cliphist", "list"], capture_output=True)
    lines = out.stdout.decode("utf-8", "replace").splitlines()
    return [l for l in lines if l.strip()][:MAX_ENTRIES]


def decode(line: str) -> bytes:
    return subprocess.run(
        ["cliphist", "decode"], input=line.encode() + b"\n", capture_output=True
    ).stdout


def png_bytes(data: bytes, box=None) -> bytes:
    """Decode image data and re-encode downscaled to fit `box` (w, h)."""
    img = Image.open(io.BytesIO(data))
    if box:
        img.thumbnail(box)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class Picker(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.win = None
        self.rows = []            # [(listbox_row, line), ...]
        self.was_active = False
        self.preview_cache = {}   # line -> PNG bytes (large preview)

    # ---- skeleton --------------------------------------------------------
    def do_activate(self):  # noqa: N802
        Gtk.Settings.get_default().props.gtk_application_prefer_dark_theme = True

        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_default_size(1020, 600)
        self.win.set_decorated(False)
        self.win.connect("notify::is-active", self.on_active_changed)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(10)
        outer.set_margin_end(10)

        # --- left: search + list ---
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left.set_size_request(560, -1)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Type to search the clipboard…")
        self.search.connect("changed", self.on_search_changed)
        self.search.connect("activate", self.on_search_activate)
        left.append(self.search)

        self.listbox = Gtk.ListBox()
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", self.on_row_activated)
        self.listbox.connect("notify::selected-row", self.on_selection_changed)
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.listbox)
        scroll.set_vexpand(True)
        left.append(scroll)
        outer.append(left)

        # --- right: large preview of the selected entry ---
        self.preview_area = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True
        )
        self.preview_area.set_size_request(400, -1)
        outer.append(self.preview_area)

        self.win.set_child(outer)

        for line in cliphist_lines():
            self.add_row(line)

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
        self.search.grab_focus()
        self.select_first_visible()

    # ---- list rows -------------------------------------------------------
    def add_row(self, line):
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image()
        icon.set_pixel_size(THUMB)
        icon.set_from_icon_name(
            "image-x-generic-symbolic" if is_image(line) else "text-x-generic-symbolic"
        )
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
        """Small thumbnail for the list, decoded off the UI thread."""
        try:
            data = png_bytes(decode(line), box=(THUMB * 2, THUMB * 2))
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
            GLib.idle_add(
                lambda t=texture, icon=icon: icon.set_from_paintable(t) or False
            )
        except Exception:
            pass

    # ---- preview pane ----------------------------------------------------
    def on_selection_changed(self, *_args):
        row = self.listbox.get_selected_row()
        if row is None:
            return
        line = next(l for r, l in self.rows if r == row)
        self.show_preview(line)

    def clear_preview(self):
        while True:
            child = self.preview_area.get_first_child()
            if child is None:
                return
            self.preview_area.remove(child)

    def show_preview(self, line):
        self.clear_preview()
        meta = Gtk.Label(label=row_label(line), halign=Gtk.Align.START)
        meta.add_css_class("preview-meta")
        self.preview_area.append(meta)

        if is_image(line):
            holder = Gtk.Image(hexpand=True, vexpand=True)
            self.preview_area.append(holder)
            threading.Thread(
                target=self.preview_worker, args=(holder, line), daemon=True
            ).start()
        else:
            text = Gtk.Label(label=line.split("\t", 1)[-1])
            text.add_css_class("preview-text")
            text.set_wrap(True)
            text.set_valign(Gtk.Align.START)
            text.set_halign(Gtk.Align.START)
            text.set_selectable(True)
            scroll = Gtk.ScrolledWindow()
            scroll.set_child(text)
            scroll.set_vexpand(True)
            self.preview_area.append(scroll)

    def preview_worker(self, holder, line):
        """Large preview image, cached per entry."""
        try:
            data = self.preview_cache.get(line)
            if data is None:
                data = png_bytes(decode(line), box=PREVIEW_MAX)
                self.preview_cache[line] = data
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
            GLib.idle_add(
                lambda t=texture, h=holder: h.set_from_paintable(t) or False
            )
        except Exception:
            pass

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
        if keyval in (Gdk.KEY_Down, Gdk.KEY_Up):
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
