"""Headless CLI seam (spec §5).  Shared-path rule: every action funnels
through the same action functions the GUI uses (src/core.py)."""

from __future__ import annotations

import argparse
import sys

from .core import (PORT_ID, VERSION, AppState, NoteError,
                   run_cli_actions)


class Parser(argparse.ArgumentParser):
    def error(self, message):  # unknown flags must exit non-zero
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def build_parser() -> Parser:
    p = Parser(prog="fastnote", add_help=False,
               description="FastNote markdown editor")
    p.add_argument("--open", metavar="PATH")
    p.add_argument("--insert", metavar="TEXT")
    p.add_argument("--save", action="store_true")
    p.add_argument("--export", metavar="PATH")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--notes-dir", metavar="PATH")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--version", action="store_true")
    p.add_argument("--help", action="store_true")
    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"FastNote {PORT_ID} v{VERSION}")
        return 0
    if args.help:
        parser.print_help()
        return 0
    if args.selftest:
        from .selftest import run_selftest
        return 0 if run_selftest() else 1

    state = AppState(notes_dir=args.notes_dir)
    try:
        run_cli_actions(state, args.open, args.insert, args.save, args.export)
    except NoteError as exc:
        print(f"fastnote: {exc}", file=sys.stderr)
        return 1

    if args.headless:
        return 0

    from .ui_app import FastNoteApp
    app = FastNoteApp(state, notes_dir=args.notes_dir)
    app.run(open_path=args.open)
    return 0


def run() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    run()