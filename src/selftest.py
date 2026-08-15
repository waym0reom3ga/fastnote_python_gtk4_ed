"""FastNote selftest — internal consistency checks (--selftest seam).

Spec 6.1 prohibits vacuous tests: every check here exercises real behaviour
and asserts on the outcome.
"""

from __future__ import annotations

import os
import tempfile

from src.browser import FileBrowser
from src.core import AppState, action_open, action_save, run_cli_actions
from src.export import write_html_export, write_pdf_export
from src.renderer import (render_fragment, render_plain, sanitize_css,
                       measure_large_document)

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"ok   {name}")
    else:
        FAILURES.append(name)
        print(f"FAIL {name} {detail}")


def run_selftest() -> bool:
    md = ("# Title\n\n**bold** *italic* ~~gone~~ `code`\n\n"
          "## Sub\n\n- a\n- [x] done\n- [ ] todo\n\n"
          "```py\nprint(1)\n```\n\n> quote\n\n"
          "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
          "[[Wiki]] $x^2$ and $$x+1$$ end.\n")
    frag = render_fragment(md)
    check("render.headings", "<h1" in frag and "<h2" in frag)
    check("render.inline", "<strong>bold</strong>" in frag
          and "<em>italic</em>" in frag and "<del>gone</del>" in frag)
    check("render.code", "<pre><code" in frag and "language-py" in frag)
    check("render.task", "checkbox" in frag and "checked" in frag)
    check("render.quote", "<blockquote>quote</blockquote>" in frag)
    check("render.table", "<table>" in frag and "<th>a</th>" in frag)
    check("render.wiki", '<a class="wiki"' in frag)
    check("render.math", "class=\"math\"" in frag and "\\(" in frag)
    check("render.toc", "Table of Contents" in frag)

    evil = "<script>alert(1)</script>\n\n# Hi\n"
    out = render_fragment(evil)
    check("render.html-escaped", "<script>" not in out
          and "&lt;script&gt;" in out)
    check("render.css-sanitized", sanitize_css("p{color:red}") == "p{color:red}"
          and sanitize_css("p{background:url(x)}") == ""
          and sanitize_css("x<script>") == "")

    td = measure_large_document()
    check("render.large-doc-fast", td < 5.0, f"{td:.2f}s")

    with tempfile.TemporaryDirectory() as td_dir:
        doc = os.path.join(td_dir, "n.md")
        with open(doc, "w", encoding="utf-8") as fh:
            fh.write("原始 内容 — 你好, Привет 🚀\n")
        state = AppState(notes_dir=td_dir)
        action_open(state, doc)
        check("doc.open", state.doc.text.startswith("原始"))
        state.doc.insert_text("\n尾")
        check("doc.dirty", state.doc.dirty is True)
        action_save(state)
        check("doc.saved-not-dirty", state.doc.dirty is False)
        with open(doc, encoding="utf-8") as fh:
            check("doc.roundtrip", "尾" in fh.read())

        html = os.path.join(td_dir, "out.html")
        write_html_export(state.doc.text, html)
        with open(html, encoding="utf-8") as fh:
            content = fh.read()
        check("export.html-complete", "<!DOCTYPE html>" in content
              and "<html" in content and "<style>" in content
              and "<title>" in content and "原始" in content)

        pdf = os.path.join(td_dir, "out.pdf")
        write_pdf_export(state.doc.text, pdf)
        with open(pdf, "rb") as fh:
            head = fh.read(8)
            check("export.pdf-valid", head.startswith(b"%PDF-1.4")
                  and os.path.getsize(pdf) > 500)

    fb = FileBrowser(mode="open", start_dir="/usr/bin")
    check("browser.lists", len(fb.entries) > 5
          and any(e[0] == ".." for e in fb.entries))
    fb.show_all = True
    fb.refresh()
    check("browser.filter-toggle", fb.show_all and len(fb.entries) > 3)
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "sub"))
        open(os.path.join(d, "a.md"), "w").write("x")
        b2 = FileBrowser(mode="open", start_dir=d)
        check("browser.open-lists-md",
              any(e[0] == "a.md" for e in b2.entries))
        picked = b2.activate("sub")
        check("browser.enter-dir", picked is None and b2.cwd.endswith("sub"))
        b2.parent()
        check("browser.parent", b2.cwd == os.path.abspath(d))
        picked2 = b2.activate("a.md")
        check("browser.open-returns-path", picked2 and picked2.endswith("a.md"))

    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "s.md")
        open(src, "w", encoding="utf-8").write("# CLI")
        st = AppState(notes_dir=d)
        run_cli_actions(st, src, "\ninserted", True, os.path.join(d, "o.html"))
        check("cli.e2e", st.doc.dirty is False
              and os.path.exists(os.path.join(d, "o.html")))

    print(f"\nselftest: {0 if FAILURES else 'all checks'} "
          f"{'passed' if not FAILURES else f'failed: {FAILURES}'}")
    return not FAILURES


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_selftest() else 1)