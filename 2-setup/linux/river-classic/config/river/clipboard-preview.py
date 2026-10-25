#!/usr/bin/env python3
"""Clipboard picker with image previews (GTK4, for river-classic).

Super+V popup over the cliphist history:
- left pane  - searchable list; text entries show their first line, image
  entries show a thumbnail and a "WxH PNG" label;
- right pane - LARGE preview of the selected entry: the image scaled by
  the widget to FILL the pane (Gtk.Picture with ContentFit.CONTAIN -
  any size source), or the full text (wrapped, selectable).

Type to filter, Up/Down to move (the preview follows the selection and
the list scrolls along), Enter (or click) to copy the entry back to the
clipboard via wl-copy (which then holds the selection), Esc or losing
focus closes.

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
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402
from gi.repository import Graphene  # noqa: E402
from PIL import Image  # noqa: E402

APP_ID = "org.riverclassic.Clippick"
THUMB = 52                 # list thumbnail size in px (rendered 2x for hidpi)
WINDOW = (1460, 920)       # popup size (fits a 1600x1000 screen)
LIST_WIDTH = 430           # fixed width of the list pane
MAX_ENTRIES = 200          # render at most this many rows

BG = "#1e1e2e"             # catppuccin-ish dark palette
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
.preview-meta {{ color: {FG_DIM}; font-size: 13px; }}
.preview-hint {{ color: {ACCENT}; font-size: 12px; }}
textview, textview text {{ background-color: transparent; }}
.preview-text, .preview-text text {{
    color: {FG};
    font-size: 14px;
    font-family: monospace;
}}
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
    """Decode image data and re-encode, scaled to FIT `box` (w, h).

    Unlike PIL's thumbnail() this also UPSCALES small images - Gtk.Image
    renders textures at native size and would show a small source image
    tiny no matter how big the preview pane is.
    """
    img = Image.open(io.BytesIO(data))
    if box and img.width and img.height:
        ratio = min(box[0] / img.width, box[1] / img.height)
        if abs(ratio - 1.0) > 0.01:
            img = img.resize(
                (max(1, round(img.width * ratio)), max(1, round(img.height * ratio))),
                Image.Resampling.LANCZOS,
            )
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class Picker(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.win = None
        self.rows = []            # [(listbox_row, line), ...]
        self.was_active = False
        self.fit_cache = {}       # line -> raw PNG bytes (decoded entry)

    # ---- skeleton --------------------------------------------------------
    def do_activate(self):  # noqa: N802
        Gtk.Settings.get_default().props.gtk_application_prefer_dark_theme = True

        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_default_size(*WINDOW)
        self.win.set_decorated(False)
        self.win.connect("notify::is-active", self.on_active_changed)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)
        outer.set_margin_start(10)
        outer.set_margin_end(10)

        # --- left: search + list ---
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left.set_size_request(LIST_WIDTH, -1)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Type to search the clipboard…")
        self.search.connect("changed", self.on_search_changed)
        self.search.connect("activate", self.on_search_activate)
        left.append(self.search)

        self.listbox = Gtk.ListBox()
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", self.on_row_activated)
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_child(self.listbox)
        self.scroll.set_vexpand(True)
        left.append(self.scroll)
        outer.append(left)

        # --- right: LARGE preview of the selected entry ---
        self.preview_area = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True
        )
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
        """Small thumbnail for the list (PNG bytes off-thread, texture on
        the UI thread - GDK objects are not safe to build off it)."""
        try:
            data = png_bytes(decode(line), box=(THUMB * 2, THUMB * 2))
            GLib.idle_add(
                lambda d=data, i=icon: i.set_from_paintable(
                    Gdk.Texture.new_from_bytes(GLib.Bytes.new(d))
                )
                or False
            )
        except Exception as e:
            self.log_error("thumb", e)

    # ---- preview pane ----------------------------------------------------
    def line_for(self, row):
        return next(l for r, l in self.rows if r == row)

    def select_row(self, row):
        """Select a row, refresh the preview and keep it scrolled into view.

        Called explicitly from startup/filter/keyboard so the preview never
        depends on property notifications firing.
        """
        self.listbox.select_row(row)
        self.show_preview(self.line_for(row))
        GLib.idle_add(self.scroll_row_into_view, row)

    def scroll_row_into_view(self, row):
        """Minimal-scroll the list so `row` is visible (GTK 4.22 has no
        ListBox scroll API, so the vadjustment is driven by hand)."""
        try:
            ok, pt = row.compute_point(self.listbox, Graphene.Point(x=0.0, y=0.0))
            if not ok:
                return False
            y, h = pt.y, max(row.get_allocation().height, 1)
            adj = self.scroll.get_vadjustment()
            top, page = adj.get_value(), adj.get_page_size()
            if y < top:
                adj.set_value(max(0.0, y - 8))
            elif y + h > top + page:
                adj.set_value(min(adj.get_upper() - page, y + h - page + 8))
        except Exception:
            pass
        return False

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
            # Gtk.Picture (not Gtk.Image): it scales the paintable to the
            # widget allocation in BOTH directions, so any image - tiny or
            # huge - fills the pane. Gtk.Image renders at native size and
            # showed small images as a small block.
            holder = Gtk.Picture()
            holder.set_content_fit(Gtk.ContentFit.CONTAIN)
            holder.set_can_shrink(True)
            holder.set_hexpand(True)
            holder.set_vexpand(True)
            scroll = Gtk.ScrolledWindow()
            scroll.set_child(holder)
            scroll.set_vexpand(True)
            scroll.set_hexpand(True)
            self.preview_area.append(scroll)
            threading.Thread(
                target=self.preview_worker, args=(holder, line), daemon=True
            ).start()
        else:
            # Full decoded text (cliphist list lines only carry the FIRST
            # line - decode returns the whole entry) in a read-only
            # TextView: labels inside ScrolledWindows refuse to wrap, a
            # TextView wraps, scrolls and stays selectable.
            view = Gtk.TextView()
            view.add_css_class("preview-text")
            view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            view.set_editable(False)
            view.set_cursor_visible(False)
            view.set_vexpand(True)
            scroll = Gtk.ScrolledWindow()
            scroll.set_child(view)
            scroll.set_vexpand(True)
            self.preview_area.append(scroll)
            threading.Thread(
                target=self.text_preview_worker, args=(view, meta, line), daemon=True
            ).start()

    def text_preview_worker(self, view, meta, line):
        """Fetch the full entry text off-thread and fill the TextView."""
        try:
            text = decode(line).decode("utf-8", "replace")
            nl = text.count("\n") + 1
            stats = f"{len(text)} chars · {nl} line{'s' if nl > 1 else ''}"

            def fill():
                view.get_buffer().set_text(text)
                meta.set_label(f"{stats} · {row_label(line)}")
                return False

            GLib.idle_add(fill)
        except Exception as e:
            self.log_error("text-preview", e)

    def preview_worker(self, holder, line):
        """Raw decoded image (texture built on the UI thread); the Picture
        widget itself scales it to fill the pane, so no PIL resizing here."""
        try:
            data = self.fit_cache.get(line)
            if data is None:
                data = decode(line)
                self.fit_cache[line] = data
                while len(self.fit_cache) > 12:
                    self.fit_cache.pop(next(iter(self.fit_cache)))
            GLib.idle_add(
                lambda d=data, h=holder: h.set_paintable(
                    Gdk.Texture.new_from_bytes(GLib.Bytes.new(d))
                )
                or False
            )
        except Exception as e:
            self.log_error("preview", e)
            msg = f"preview failed: {e}"
            GLib.idle_add(
                lambda m=msg, h=holder: h.set_from_icon_name(
                    "image-missing-symbolic"
                )
                or h.set_tooltip_text(m)
                or False
            )

    def log_error(self, where, exc):
        try:
            state = os.path.expanduser("~/.local/state/river-classic")
            os.makedirs(state, exist_ok=True)
            with open(os.path.join(state, "clipboard-preview.log"), "a") as fh:
                fh.write(f"{where}: {exc!r}\n")
        except OSError:
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
            self.select_row(vis[0][0])

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
            self.select_row(vis[idx][0])
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
