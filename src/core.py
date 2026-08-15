"""FastNote python_gtk4 — document model and shared action layer.

The actions in this module are the ONLY place the application's behaviour is
implemented.  The GUI callbacks call these same functions (specification 5.2,
shared-path rule).
"""

from __future__ import annotations

import os
import sys

EDITOR_NAME = "FastNote"
VERSION = "1.0.0"
PORT_ID = "python_gtk4"

APP_EXTENSIONS = (".md", ".markdown", ".txt")


class NoteError(Exception):
    """A user-visible failure (open/save/export)."""


class Document:
    """In-memory markdown document with dirty tracking."""

    def __init__(self, path: str | None = None, text: str = ""):
        self.path: str | None = path
        self.text: str = text
        self.dirty: bool = False

    def set_text(self, text: str) -> None:
        if text != self.text:
            self.text = text
            self.dirty = True

    def open(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            raise NoteError(f"cannot open {path}: {exc.strerror or exc}") from exc
        self.path = path
        self.text = text
        self.dirty = False

    def insert_text(self, text: str) -> None:
        """Append text to the document."""
        self.text += text
        self.dirty = True

    def save(self) -> str:
        if self.path is None:
            raise NoteError("no file name: use save-as (FR-6)")
        self._write(self.path)
        return self.path

    def save_as(self, path: str) -> str:
        self._write(path)
        self.path = path
        return path

    def _write(self, path: str) -> None:
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(self.text)
        except OSError as exc:
            raise NoteError(f"cannot save {path}: {exc.strerror or exc}") from exc
        self.dirty = False


class AppState:
    """Application state shared between GUI and CLI."""

    def __init__(self, notes_dir: str | None = None):
        self.doc = Document()
        self.notes_dir = os.path.abspath(notes_dir) if notes_dir else os.path.expanduser("~")
        self.saved_once = False
        self.failed: list[str] = []
        self.event_file: str | None = None


def fn_event(state: AppState, marker: str) -> None:
    """Append a phase marker to the event file (spec 5.1).

    A reporting outlet only — never drives or simulates an operation.
    """
    if state is None or state.event_file is None:
        return
    try:
        with open(state.event_file, "a", encoding="utf-8") as f:
            f.write(marker + "\n")
    except OSError:
        pass


def action_open(state: AppState, path: str) -> None:
    state.doc.open(path)
    fn_event(state, "open")


def action_insert(state: AppState, text: str) -> None:
    state.doc.insert_text(text)


def action_save(state: AppState) -> str:
    path = state.doc.save()
    state.saved_once = True
    fn_event(state, "save")
    return path


def action_save_as(state: AppState, path: str) -> str:
    path = state.doc.save_as(path)
    state.saved_once = True
    fn_event(state, "save-as")
    return path


def action_export_html(state: AppState, path: str, theme: str = "light",
                       custom_css: str | None = None) -> str:
    from src.export import write_html_export
    write_html_export(state.doc.text, path, theme=theme, custom_css=custom_css)
    fn_event(state, "export-html")
    return path


def action_export_pdf(state: AppState, path: str) -> str:
    from src.export import write_pdf_export
    write_pdf_export(state.doc.text, path)
    fn_event(state, "export-pdf")
    return path


def run_cli_actions(state: AppState, open_path: str | None, insert: str | None,
                    do_save: bool, export: str | None) -> None:
    """Execute the headless seam in the mandated order (spec 5.1)."""
    if open_path is not None:
        action_open(state, open_path)
    if insert is not None:
        action_insert(state, insert)
    if do_save:
        action_save(state)
    if export:
        ext = os.path.splitext(export)[1].lower()
        if ext == ".pdf":
            action_export_pdf(state, export)
        else:
            action_export_html(state, export)


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)