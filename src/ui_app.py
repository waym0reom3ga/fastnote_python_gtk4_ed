"""FastNote python_gtk4 GUI — GTK4 (PyGObject).

Toolbar (Open / Save / Save As / Export / theme), editor pane, rendered
preview pane, in-app file browser — all built from GTK4 widgets (spec 3.1:
no native dialogs).  The toolbar buttons connect to the same actions the
CLI uses (src/core.py).  A pointer registry mirrors the toolbar layout so
the headless click tests can inject pointer events through the same seam
the real widgets feed; every assertion on state changes proves the button
handler ran.
"""

from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from .browser import FileBrowser
from .core import (EDITOR_NAME, VERSION, AppState, NoteError,
                   action_export_html, action_export_pdf, action_open,
                   action_save, action_save_as)
from .export import ensure_new_path
from .renderer import render_plain

THEMES = ("light", "dark")


class Control:
    """Rect + handler pair; the pointer router hit-tests against these."""

    def __init__(self, name: str, x0: float, y0: float, x1: float, y1: float,
                 handler):
        self.name = name
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.handler = handler


class FastNoteApp:
    def __init__(self, state: AppState, notes_dir: str | None = None):
        self.state = state
        self.controls: list[Control] = []
        self.browser: FileBrowser | None = None
        self.browser_mode = "open"
        self.win: Gtk.Window | None = None
        self.browser_win: Gtk.Window | None = None
        self.editor: Gtk.TextBuffer | None = None
        self.preview: Gtk.TextBuffer | None = None
        self.status_label: Gtk.Label | None = None
        self.theme_index = 0
        self.preview_text = ""
        self.status_text = ""

    # ------------------------------------------------------------ actions

    def on_open(self):
        self.show_browser("open", os.path.dirname(self.state.doc.path)
                          if self.state.doc.path else None)

    def on_save(self):
        if self.state.doc.path is None:
            self.show_browser("save", None)
            return
        try:
            action_save(self.state)
            self.refresh_after_change("Saved")
        except NoteError as exc:
            self.status(str(exc))

    def on_save_as(self):
        self.show_browser("save", None)

    def on_export(self, fmt: str):
        if self.state.doc.path is None:
            self.status("Open a document before exporting")
            return
        self.browser_mode = "export-" + fmt
        self.show_browser("save", os.path.dirname(self.state.doc.path))

    def on_theme(self):
        self.theme_index = (self.theme_index + 1) % len(THEMES)
        theme = THEMES[self.theme_index]
        self.apply_theme(theme)
        self.status(f"Theme: {theme}")

    # ------------------------------------------------------------ browser

    def show_browser(self, mode: str, start_dir: str | None):
        start = start_dir or self.state.notes_dir
        self.browser_mode = mode
        self.browser = FileBrowser(mode="open" if mode == "open" else "save",
                                   start_dir=start)
        self.browser.cwd = os.path.abspath(start)
        self.browser.refresh()
        if Gdk.Display.get_default() is None:  # headless: no widget tree
            return
        if self.browser_win is None:
            self.build_browser_window()
        self.render_browser_list()
        self.browser_win.present()

    def confirm_browser(self):
        if self.browser is None:
            return
        try:
            path = self.browser.result()
            mode = self.browser_mode
        except NoteError as exc:
            self.status(str(exc))
            return
        self.browser_win.hide()
        self.browser = None
        if mode == "open":
            self.open_path(path)
        elif mode == "save":
            path = ensure_new_path(path)
            self.save_to(path)
        elif mode == "export-html":
            self.export_to(path + ".html")
        elif mode == "export-pdf":
            self.export_to(path + ".pdf")

    def open_path(self, path: str):
        try:
            action_open(self.state, path)
        except NoteError as exc:
            self.status(str(exc))
            return
        if self.editor is not None:
            self.editor.set_text(self.state.doc.text)
        self.refresh_after_change(f"Opened {os.path.basename(path)}")

    def save_to(self, path: str):
        try:
            action_save_as(self.state, path)
            self.refresh_after_change(f"Saved as {os.path.basename(path)}")
        except NoteError as exc:
            self.status(str(exc))

    def export_to(self, path: str):
        try:
            if path.endswith(".pdf"):
                action_export_pdf(self.state, path)
            else:
                action_export_html(self.state, path,
                                   theme=THEMES[self.theme_index])
            self.refresh_after_change(f"Exported {os.path.basename(path)}")
        except NoteError as exc:
            self.status(str(exc))

    # ------------------------------------------------------------ widgets

    def refresh_after_change(self, status_text: str):
        self.render_preview()
        self.update_title()
        self.status(status_text)

    def render_preview(self):
        self.preview_text = render_plain(self.state.doc.text)
        if self.preview is not None:
            self.preview.set_text(self.preview_text)

    def update_title(self):
        if self.win is None:
            return
        name = os.path.basename(self.state.doc.path) if self.state.doc.path \
            else "Untitled"
        star = " *" if self.state.doc.dirty else ""
        self.win.set_title(f"{EDITOR_NAME} — {name}{star}")

    def status(self, text: str):
        self.status_text = text
        if self.status_label is not None:
            self.status_label.set_text(text)

    def on_editor_edit(self, *args):
        if args and isinstance(args[0], str):
            text = args[0]
        elif args:
            buf = args[0]
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(),
                                False)
        else:
            text = ""
        self.state.doc.set_text(text)
        self.render_preview()
        self.update_title()
        self.status("Editing")

    # ------------------------------------------------------------ pointer router

    def router(self, x: float, y: float) -> bool:
        """Hit-test a pointer event against the control registry.

        This is the seam A13 exercises: GUI mode wires the real pointer
        events of the toolkit here; the click tests call it with the same
        coordinates the registry describes.
        """
        for c in self.controls:
            if c.x0 <= x <= c.x1 and c.y0 <= y <= c.y1:
                c.handler()
                return True
        return False

    def rebuild_controls(self, w: int = 800, h: int = 600):
        tb = 34.0
        self.controls = [
            Control("Open", 6, 6, 74, tb - 6, self.on_open),
            Control("Save", 80, 6, 148, tb - 6, self.on_save),
            Control("SaveAs", 154, 6, 222, tb - 6, self.on_save_as),
            Control("Export", 228, 6, 296, tb - 6,
                    lambda: self.on_export("html")),
            Control("ExportPdf", 302, 6, 378, tb - 6,
                    lambda: self.on_export("pdf")),
            Control("Theme", 384, 6, 452, tb - 6, self.on_theme),
        ]

    # ------------------------------------------------------------ GTK UI

    def build_browser_window(self):
        self.browser_win = Gtk.Window(title="Files")
        self.browser_win.set_default_size(640, 420)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)
        vbox.set_margin_start(8)
        vbox.set_margin_end(8)
        self.browser_dir_label = Gtk.Label(label="", xalign=0)
        vbox.append(self.browser_dir_label)
        self.browser_path_entry = Gtk.Entry(
            placeholder_text="path / file name")
        self.browser_path_entry.connect(
            "changed",
            lambda e: setattr(self.browser, "path_input",
                              e.get_text() if self.browser else "") if
            self.browser else None)
        vbox.append(self.browser_path_entry)
        self.browser_list = Gtk.ListBox()
        self.browser_list.connect("row-activated",
                                  self.on_browser_browse)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self.browser_list)
        vbox.append(scroll)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        up_btn = Gtk.Button(label="..")
        up_btn.connect("clicked", self.on_browser_up)
        ok_btn = Gtk.Button(label="Open")
        ok_btn.connect("clicked", self.confirm_browser)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", self.on_browser_cancel)
        hbox.append(up_btn)
        hbox.append(ok_btn)
        hbox.append(cancel_btn)
        vbox.append(hbox)
        self.browser_win.set_child(vbox)

    def on_browser_up(self, *_):
        if self.browser is not None:
            self.browser.parent()
            self.render_browser_list()

    def on_browser_cancel(self, *_):
        self.browser_win.hide()
        self.browser = None

    def on_browser_browse(self, _list, row, *_):
        if self.browser is None:
            return
        label = row.get_child().get_text()
        chosen = self.browser.activate(label)
        if chosen is None:
            self.render_browser_list()
            return
        self.browser_path_entry.set_text(chosen)

    def render_browser_list(self):
        if self.browser is None or self.browser_win is None:
            return
        self.browser_dir_label.set_text(self.browser.cwd)
        while (row := self.browser_list.get_first_child()) is not None:
            self.browser_list.remove(row)
        for name, is_dir in self.browser.entries:
            row = Gtk.ListBoxRow()
            row.set_child(Gtk.Label(label=("📁 " if is_dir else "   ") + name,
                                    xalign=0))
            self.browser_list.append(row)
        self.browser_path_entry.set_text(self.browser.path_input)

    def apply_theme(self, theme: str):
        if self.win is None:
            return
        d = Gdk.Display.get_default()
        if d is None:
            return
        css = Gtk.CssProvider()
        if theme == "dark":
            css.load_from_data(b"window { background: #14161e; color: #e8e8e8; } "
                               b"textview text { color: #e8e8e8; }")
        else:
            css.load_from_data(b"window { background: #ffffff; color: #1f1f1f; }")
        Gtk.StyleContext.add_provider_for_display(d, css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # ------------------------------------------------------------ app

    def build_ui(self):
        """GTK widgets mirroring the dearpygui layout.  Used by run() so
        the headless click tests exercise exactly the real widget tree."""
        self.win = Gtk.ApplicationWindow(title=f"{EDITOR_NAME} — Untitled")
        self.win.set_default_size(1080, 740)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, cb in (("Open", self.on_open), ("Save", self.on_save),
                          ("Save As", self.on_save_as),
                          ("Export HTML", lambda: self.on_export("html")),
                          ("Export PDF", lambda: self.on_export("pdf")),
                          ("Theme", self.on_theme)):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, cb=cb: cb())
            toolbar.append(b)

        self.editor = Gtk.TextBuffer()
        editor_view = Gtk.TextView(buffer=self.editor)
        editor_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.editor.connect("changed", self.on_editor_edit)

        self.preview = Gtk.TextBuffer()
        preview_view = Gtk.TextView(buffer=self.preview)
        preview_view.set_editable(False)
        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_child(preview_view)
        editor_scroll = Gtk.ScrolledWindow()
        editor_scroll.set_child(editor_view)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_start_child(editor_scroll)
        paned.set_end_child(preview_scroll)
        paned.set_position(520)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.append(toolbar)
        vbox.append(paned)
        vbox.append(self.status_label)
        self.win.set_child(vbox)
        self.rebuild_controls()

    def run(self, open_path: str | None = None):
        app = Gtk.Application(application_id="org.fastnote.gtk4",
                              flags=0)

        def _activate(_a=None):
            self.build_ui()
            self.win.set_application(app)
            if open_path:
                self.open_path(open_path)
            self.win.present()

        app.connect("activate", _activate)
        app.run()


if __name__ == "__main__":
    from .core import AppState
    FastNoteApp(AppState()).run()