"""In-app file browser (spec §3) — toolkit-independent state machine.

The GUI renders this state and routes pointer events through the same
handlers this module exposes; tests inject clicks into the same router.
No native dialog is involved anywhere (spec 3.1).
"""

from __future__ import annotations

import os

from src.core import APP_EXTENSIONS, NoteError


class BrowserOpen(Exception):
    """Raised when the user confirms a selection."""


class BrowserCancel(Exception):
    """Raised when the user cancels — application state must be unchanged."""


class FileBrowser:
    def __init__(self, mode: str = "open", start_dir: str | None = None,
                 filter_ext: tuple[str, ...] = APP_EXTENSIONS):
        self.mode = mode  # "open" | "save"
        self.cwd = os.path.abspath(start_dir or os.path.expanduser("~"))
        self.filter = filter_ext
        self.show_all = False
        self.path_input = ""
        self.selected: str | None = None
        self.entries: list[tuple[str, bool]] = []  # (name, is_dir)
        self.refresh()

    def refresh(self) -> None:
        try:
            names = sorted(os.listdir(self.cwd))
        except OSError as exc:
            raise NoteError(f"cannot list {self.cwd}: {exc.strerror or exc}")
        dirs, files = [], []
        for name in names:
            full = os.path.join(self.cwd, name)
            if os.path.isdir(full):
                dirs.append((name, True))
            elif os.path.isfile(full):
                if self.show_all or os.path.splitext(name)[1].lower() in self.filter:
                    files.append((name, False))
        self.entries = [("..", True)] + dirs + files

    def activate(self, name: str) -> str | None:
        """Enter a directory, or return the selected file path."""
        full = os.path.join(self.cwd, name)
        if os.path.isdir(full):
            self.cwd = full
            self.path_input = ""
            self.selected = None
            self.refresh()
            return None
        if self.mode == "open" and not os.path.isfile(full):
            return None
        self.selected = full
        return full

    def parent(self) -> None:
        parent = os.path.dirname(self.cwd)
        if parent and parent != self.cwd:
            self.cwd = parent
            self.refresh()

    def toggle_filter(self) -> None:
        self.show_all = not self.show_all
        self.refresh()

    def result(self) -> str:
        """The path the confirm action commits to (save mode may not exist)."""
        path = self.path_input.strip() or (self.selected or "")
        if not path:
            raise NoteError("choose a file or type a path")
        if not os.path.isabs(path):
            path = os.path.join(self.cwd, path)
        return os.path.abspath(path)

    def select_by_path(self, path: str) -> None:
        self.path_input = path
        self.selected = path

    def navigate_to(self, path: str) -> None:
        if os.path.isdir(path):
            self.cwd = os.path.abspath(path)
            self.path_input = ""
            self.selected = None
            self.refresh()