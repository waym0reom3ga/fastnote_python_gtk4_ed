"""Entry point (spec §5.1).

Exactly two permitted flags: --version and --event-file.
Unknown flags exit non-zero.
"""

from __future__ import annotations

import argparse
import sys

from src.core import PORT_ID, VERSION, AppState


class Parser(argparse.ArgumentParser):
    def error(self, message):  # unknown flags must exit non-zero
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def build_parser() -> Parser:
    p = Parser(prog="fastnote", add_help=False,
               description="FastNote markdown editor")
    p.add_argument("--version", action="store_true")
    p.add_argument("--event-file", metavar="PATH")
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

    state = AppState()
    if args.event_file:
        state.event_file = args.event_file

    from src.ui_app import FastNoteApp
    app = FastNoteApp(state)
    app.run()
    return 0


def run() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    run()
