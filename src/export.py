"""FastNote export writers — HTML (FR-7) and PDF (FR-8)."""

from __future__ import annotations

import os

from .pdfwriter import pdf_from_lines
from .renderer import doc_title, render_page, render_plain


def write_html_export(text: str, path: str, theme: str = "light",
                      custom_css: str | None = None) -> None:
    page = render_page(text, title=doc_title(text), theme=theme,
                       custom_css=custom_css)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(page)


def write_pdf_export(text: str, path: str) -> None:
    plain = render_plain(text)
    data = pdf_from_lines(plain)
    with open(path, "wb") as fh:
        fh.write(data)


def ensure_new_path(path: str) -> str:
    """Enforce an extension when the user typed a bare save/export path."""
    if os.path.splitext(path)[1] == "":
        return path + ".md"
    return path