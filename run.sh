#!/usr/bin/env python3
"""FastNote python_gtk4 launcher.  Single-file artifact for the harness."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from src.cli import run  # noqa: E402

if __name__ == "__main__":
    run()