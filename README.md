# FastNote — Python (python_gtk4) port

Reimplementation of the FastNote specification using python_gtk4.

## Running

```sh
./run.sh                          # GUI (needs a display)
./run.sh --headless --version     # CLI seam
./run.sh --headless --notes-dir /tmp/n --selftest   # built-in self-test
```

## Tests

- `make selftest` — in-app self-test suite (render pipeline, document actions, HTML export, E2E).
- `make clicks` — real pointer-event tests (A13): pointer events injected through the same control registry the GUI routes real events through; no display required.

## Layout

- `src/main.py`, `src/cli.py` — entry point, CLI seams, headless mode
- `src/ui_app.py` — GUI, pointer router, in-app file browser
- `src/core.py` — document state and actions (shared by CLI and GUI)
- `src/renderer.py`, `src/export.py`, `src/pdfwriter.py`, `src/browser.py`, `src/selftest.py`
- `tests/test_ui_click.py` — A13 pointer-event tests
