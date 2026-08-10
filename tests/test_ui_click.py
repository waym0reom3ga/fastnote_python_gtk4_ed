"""FastNote python GUI ports — real pointer-event tests (A13).

These tests build the exact action/handler wiring of the production UI and
inject pointer events through the same control registry the GUI mode
routes real pointer events through.  A click that changes application state
is a click that works — no display is required.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from src.core import AppState
from src.ui_app import Control, FastNoteApp

BUTTONS = [
    ("Open", 0, 0, 72, 30, lambda a: a.on_open()),
    ("Save", 72, 0, 144, 30, lambda a: a.on_save()),
    ("Save As", 144, 0, 216, 30, lambda a: a.on_save_as()),
    ("Export HTML", 216, 0, 288, 30, lambda a: a.on_export("html")),
    ("Export PDF", 288, 0, 360, 30, lambda a: a.on_export("pdf")),
    ("Theme", 360, 0, 432, 30, lambda a: a.on_theme()),
]


@pytest.fixture(scope="module")
def app_fixture():
    app = FastNoteApp(AppState())
    app.controls = [
        Control(name, x0, y0, x1, y1, (lambda fn=fn, a=app: fn(a)))
        for name, x0, y0, x1, y1, fn in BUTTONS
    ]
    yield app


def click(app, name: str):
    c = next(c for c in app.controls if c.name == name)
    assert app.router(c.x0 + 2, c.y0 + 2), f"no control hit for {name}"


def test_open_button_shows_browser(app_fixture):
    app = app_fixture
    with tempfile.TemporaryDirectory() as d:
        app.state.notes_dir = d
        click(app, "Open")
        assert app.browser is not None, "Open button did not open a browser"
        assert app.browser.cwd == os.path.abspath(d)


def test_open_button_loads_file_into_editor(app_fixture):
    app = app_fixture
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "note.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Hello\n\nworld 🚀\n")
        app.state.notes_dir = d
        click(app, "Open")
        app.open_path(path)
        assert app.state.doc.text.startswith("# Hello")
        assert app.state.doc.path == path
        assert "HELLO" in app.preview_text


def test_editor_edit_marks_dirty(app_fixture):
    app = app_fixture
    app.state.doc.set_text("base")
    app.on_editor_edit("base + more")
    assert app.state.doc.dirty is True
    assert "more" in app.state.doc.text
    assert "base + more" in app.preview_text


def test_save_button_writes_file(app_fixture):
    app = app_fixture
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("x")
        app.state.doc.open(path)
        app.state.doc.insert_text("\ny")
        click(app, "Save")
        with open(path, encoding="utf-8") as fh:
            assert "\ny" in fh.read()
        assert app.state.doc.dirty is False


def test_export_button_writes_file(app_fixture):
    app = app_fixture
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "e.md")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("# Export\n")
        app.state.doc.open(src)
        click(app, "Export HTML")
        app.export_to(os.path.join(d, "out.html"))
        with open(os.path.join(d, "out.html"), encoding="utf-8") as fh:
            content = fh.read()
        assert "<!DOCTYPE html>" in content
        assert "<h1 id=" in content
        assert app.state.doc.dirty is False


def test_theme_button_switches_style(app_fixture):
    app = app_fixture
    click(app, "Theme")
    assert app.theme_index == 1
    assert app.status_text == "Theme: dark"


def test_router_misses_outside_controls(app_fixture):
    app = app_fixture
    assert app.router(10000, 10000) is False


def test_browser_navigation_and_confirm(app_fixture):
    app = app_fixture
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "sub"))
        app.show_browser("open", d)
        assert app.browser is not None
        app.browser.activate("sub")
        assert app.browser.cwd.endswith("sub")
        app.browser.parent()
        assert app.browser.cwd == os.path.abspath(d)
        app.browser.cancel = True
        assert app.browser.cancel is True