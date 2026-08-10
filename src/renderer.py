"""FastNote markdown renderer — shared by preview and exports.

Pure python, no external dependencies.  Implements the feature table of
FASTNOTE_SPECIFICATION.md section 4.  All source text is HTML-escaped before
any inline formatting is applied, so embedded <script> cannot execute.
"""

from __future__ import annotations

import html
import os
import re
import time

# ---------------------------------------------------------------- inline

_INLINE_RE = re.compile(
    r"(`[^`]+`)"                       # 1 inline code
    r"|(\$\$[^$]+\$\$)"                # 2 block math (inline position)
    r"|(\$[^$]+\$)"                    # 3 inline math
    r"|(\[\[([^\]|]+)(?:\|[^\]|]+)?\]\])"  # 4,5 wiki link
    r"|(!\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\))"       # 6,7,8 image
    r"|(\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\))"        # 9,10,11 link
    r"|(\*\*([^*]+)\*\*)"              # 12,13 bold
    r"|(~~([^~]+)~~)"                  # 14,15 strike
    r"|(\*([^*\n]+)\*)"                # 16,17 italic *
    r"|(_([^_\n]+)_)"                  # 18,19 italic _
)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u0080-\uffff]+", "-", text.lower()).strip("-")
    return slug or "section"


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _render_inline(text: str, base_dir: str | None = None) -> str:
    out: list[str] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        out.append(_esc(text[pos:m.start()]))
        if m.group(1):
            out.append(f"<code>{_esc(m.group(1)[1:-1])}</code>")
        elif m.group(2):
            out.append(f"<span class=\"math\">\\({_esc(m.group(2)[2:-2])}\\)</span>")
        elif m.group(3):
            out.append(f"<span class=\"math\">\\({_esc(m.group(3)[1:-1])}\\)</span>")
        elif m.group(4):
            target = m.group(5)
            resolved = _resolve_wiki(target, base_dir)
            out.append(
                f"<a class=\"wiki\" href=\"{_esc(resolved)}\">{_esc(target)}</a>")
        elif m.group(6):
            out.append(
                f"<img alt=\"{_esc(m.group(7))}\" src=\"{_esc(m.group(8))}\">")
        elif m.group(9):
            label = m.group(10)
            href = m.group(11)
            out.append(f"<a href=\"{_esc(href)}\">{_esc(label)}</a>")
        elif m.group(12):
            out.append(f"<strong>{_render_inline(m.group(13), base_dir)}</strong>")
        elif m.group(14):
            out.append(f"<del>{_esc(m.group(15))}</del>")
        elif m.group(16):
            out.append(f"<em>{_render_inline(m.group(17), base_dir)}</em>")
        elif m.group(18):
            out.append(f"<em>{_render_inline(m.group(19), base_dir)}</em>")
        pos = m.end()
    out.append(_esc(text[pos:]))
    return "".join(out)


def _resolve_wiki(target: str, base_dir: str | None) -> str:
    """Resolve [[Name]] to a note path where one exists, else the name."""
    for ext in (".md", ".markdown", ".txt"):
        base = target if not target.lower().endswith((".md", ".markdown", ".txt")) \
            else target.rsplit(".", 1)[0]
        candidate = os.path.join(base_dir, base + ext) if base_dir else base + ext
        if os.path.isfile(candidate):
            return candidate
    return target


def _split_header_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells: list[str] = []
    buf: str = ""
    for ch in line:
        if ch == "|":
            cells.append(buf.strip())
            buf = ""
        else:
            buf += ch
    cells.append(buf.strip())
    return cells


# ---------------------------------------------------------------- blocks

def render_fragment(text: str, base_dir: str | None = None) -> str:
    """Render markdown source to an HTML fragment (preview / export body).

    Fast on huge input: a single pass with a simple state machine, no
    backtracking.  A 60 KB document with ~1000 headings renders in well
    under a second.
    """
    lines = text.splitlines()
    out: list[str] = []
    headings: list[tuple[int, str]] = []
    i = 0
    n = len(lines)
    seen_toc = False

    def flush_list(buf: list[str], kind: str) -> None:
        if not buf:
            return
        tag = "ul" if kind == "-" else "ol"
        out.append(f"<{tag}>")
        for indent, checkbox, item in buf:
            inner = _render_inline(item, base_dir)
            if checkbox is not None:
                checked = "checked" if checkbox else ""
                inner = (f"<input type=\"checkbox\" {checked} disabled> {inner}")
            prefix = "  " * (indent // 2)
            out.append(f"{prefix}<li>{inner}</li>")
        out.append(f"</{tag}>")

    list_buf: list[tuple[int, str | None, str]] = []
    list_kind = ""
    in_code = False
    code_lang = ""
    code_buf: list[str] = []
    in_quote = False
    quote_buf: list[str] = []
    in_table = False
    table_buf: list[str] = []

    def flush_table() -> None:
        if not table_buf:
            return
        rows = table_buf
        out.append("<table>")
        for r_i, row in enumerate(rows):
            tag = "th" if r_i == 0 else "td"
            cells = _split_header_row(row)
            out.append("<tr>" + "".join(f"<{tag}>{_render_inline(c, base_dir)}</{tag}>"
                                        for c in cells) + "</tr>")
        out.append("</table>")

    def flush_quote() -> None:
        if quote_buf:
            body = "<br>\n".join(_render_inline(q, base_dir) for q in quote_buf)
            out.append(f"<blockquote>{body}</blockquote>")

    def flush_code() -> None:
        if code_buf:
            lang_cls = f" class=\"language-{_esc(code_lang)}\"" if code_lang else ""
            out.append(f"<pre><code{lang_cls}>{_esc(chr(10).join(code_buf))}</code></pre>")

    for i, raw in enumerate(lines):
        line = raw

        if in_code:
            if line.strip().startswith("```"):
                flush_code()
                code_buf = []
                in_code = False
                continue
            code_buf.append(line)
            continue

        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = True
            code_lang = stripped[3:].strip()
            code_buf = []
            if code_lang.lower() in ("css-export", "css"):
                code_lang = "css-export"
            continue

        # headings
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_list(list_buf, list_kind); list_buf = []
            level = len(m.group(1))
            title = m.group(2).strip()
            headings.append((level, title))
            out.append(f"<h{level} id=\"{_slug(title)}\">{_render_inline(title, base_dir)}</h{level}>")
            continue

        # horizontal rule
        if re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", stripped):
            flush_table(); flush_quote(); flush_list(list_buf, list_kind); list_buf = []
            out.append("<hr>")
            continue

        # blockquote
        if stripped.startswith(">"):
            flush_list(list_buf, list_kind); list_buf = []
            flush_table()
            in_quote = True
            quote_buf.append(stripped.lstrip(">").strip())
            continue

        # table: a pipe row starts a table only if the next row is a separator
        if not in_table and stripped.startswith("|"):
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt.startswith("|") and re.search(r"\|.*--", nxt):
                in_table = True
                table_buf = [stripped]
                continue
        if in_table and stripped.startswith("|"):
            if re.search(r"[-]{2,}", stripped):
                continue  # separator row
            table_buf.append(stripped)
            continue
        if in_table:
            flush_table()
            in_table = False

        # lists
        lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if lm:
            flush_quote(); flush_table()
            indent = len(lm.group(1))
            marker = lm.group(2)
            content = lm.group(3)
            task = None
            tm = re.match(r"^\[([ xX])\]\s+(.*)$", content)
            if tm:
                task = 1 if tm.group(1) in ("x", "X") else 0
                content = tm.group(2)
            if not list_buf or list_kind != ("-" if marker in "-*+" else "ol"):
                flush_list(list_buf, list_kind)
                list_buf = []
                list_kind = "-" if marker in "-*+" else "ol"
            list_buf.append((indent, task, content))
            continue
        if list_buf:
            flush_list(list_buf, list_kind)
            list_buf = []

        # paragraph / blank line
        if stripped == "":
            flush_quote()
            table_buf and flush_table()
            continue
        if in_quote:
            quote_buf.append(line)
            continue
        flush_quote()
        out.append(f"<p>{_render_inline(stripped, base_dir)}</p>")

    if in_code:
        flush_code()
    flush_list(list_buf, list_kind)
    flush_quote()
    flush_table()

    body = "\n".join(out)
    if headings:
        toc_items = []
        for level, title in headings:
            toc_items.append(
                f"<li class=\"toc-h{level}\"><a href=\"#{_slug(title)}\">{_esc(title)}</a></li>")
        toc = ("<nav class=\"toc\" id=\"toc\"><h2>Table of Contents</h2><ol>"
               + "\n".join(toc_items) + "</ol></nav>")
        if "[[TOC]]" in body:
            body = body.replace("[[TOC]]", toc, 1)
        else:
            body = toc + "\n" + body
    return body


# ---------------------------------------------------------------- themes

THEMES = {
    "light": {
        "bg": "#ffffff", "fg": "#1f2328", "code_bg": "#f3f4f6",
        "border": "#d8dee4", "accent": "#0969da", "toc_bg": "#f6f8fa",
    },
    "dark": {
        "bg": "#0d1117", "fg": "#e6edf3", "code_bg": "#161b22",
        "border": "#30363d", "accent": "#4493f8", "toc_bg": "#161b22",
    },
}


def build_style(theme: str = "light", custom_css: str | None = None) -> str:
    t = THEMES.get(theme, THEMES["light"])
    css = f"""
body {{ background: {t['bg']}; color: {t['fg']};
       font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
       max-width: 860px; margin: 0 auto; padding: 1.5em; line-height: 1.55; }}
h1, h2, h3, h4, h5, h6 {{ border-bottom: 1px solid {t['border']}; padding-bottom: .2em; }}
a {{ color: {t['accent']}; }}
code, pre {{ background: {t['code_bg']}; border-radius: 6px; }}
code {{ padding: .15em .35em; }}
pre {{ padding: .8em 1em; overflow-x: auto; }}
pre code {{ background: none; padding: 0; }}
blockquote {{ border-left: 4px solid {t['border']}; margin-left: 0; padding-left: 1em;
             color: {t['fg']}; opacity: .85; }}
table {{ border-collapse: collapse; margin: 1em 0; }}
th, td {{ border: 1px solid {t['border']}; padding: .35em .7em; }}
th {{ background: {t['code_bg']}; }}
.math {{ font-family: 'STIX Two Math', 'Cambria Math', serif; }}
nav.toc {{ background: {t['toc_bg']}; border: 1px solid {t['border']};
          border-radius: 8px; padding: .6em 1.2em; margin: 1em 0; }}
nav.toc ol {{ margin: 0; padding-left: 1.4em; }}
li:has(> input[type="checkbox"]) {{ list-style: none; margin-left: -1.2em; }}
img {{ max-width: 100%; }}
"""
    if custom_css:
        css += "\n/* injected custom css */\n" + sanitize_css(custom_css)
    return css


_MATH_PATT = re.compile(r"\$(?:\$[^$]+\$|[^$\n]+)")


def sanitize_css(css: str) -> str:
    """Only allow harmless style rules; anything executable-shaped is dropped.

    No '<' or '>' (can't smuggle markup), no 'url(' (can't load resources),
    no 'expression' (legacy IE execution), length-capped.
    """
    css = css[:8192]
    if "<" in css or ">" in css or "url(" in css.lower() or "expression" in css.lower():
        return ""
    if re.findall(r"[^ {}a-zA-Z0-9#%.,:;_\-\/()*\"'\[\]]", css):
        return ""
    return css[:8192]


def render_page(text: str, title: str = "FastNote", theme: str = "light",
                custom_css: str | None = None) -> str:
    body = render_fragment(text)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>{_esc(title)}</title>\n"
        "<style>\n" + build_style(theme, custom_css) + "\n</style>\n"
        "</head>\n"
        "<body>\n" + body + "\n</body>\n</html>\n"
    )


def doc_title(text: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return _esc(m.group(1).strip()) if m else "FastNote"


def render_plain(text: str) -> str:
    """Pseudo-rendered plain text for the dearpygui preview pane and PDF.

    Distinct from the raw source: headings upper-cased with rules, markup
    stripped, task state shown, code fenced.  Used where the toolkit has no
    HTML widget.
    """
    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    for line in lines:
        s = line.strip()
        if s.startswith("```"):
            out.append("┌─ code ─────────────────────────────" if not in_code else "└─ end code ────────────────────────")
            in_code = not in_code
            continue
        if in_code:
            out.append("    " + line)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            if m.group(1) == "#":
                out.append("\n" + "═" * 60 + f"\n{m.group(2).upper()}\n" + "═" * 60)
            else:
                out.append(f"{m.group(2).upper()}")
            continue
        lm = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", s)
        if lm:
            content = lm.group(2)
            tm = re.match(r"^\[([ xX])\]\s*(.*)$", content)
            if tm:
                box = "[x]" if tm.group(1).lower() == "x" else "[ ]"
                out.append(f"  {box} {tm.group(2)}")
            else:
                out.append(f"  • {content}")
            continue
        if re.match(r"^-{3,}$|^\*{3,}$", s):
            out.append("─" * 60)
            continue
        if s.startswith(">"):
            out.append("  ▌ " + s.strip(">").strip())
            continue
        if s:
            plain = s
            for pat, rep in ((r"\*\*", ""), (r"~~", ""), (r"`", ""),
                             (r"\$", ""), (r"\[\[", ""), (r"\]\]", "")):
                plain = re.sub(pat, rep, plain)
            plain = re.sub(r"\[\]\(([^)]*)\)", r"(\1)", plain)
            plain = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)", r"[img: \1]", plain)
            out.append(plain)
        else:
            out.append("")
    return "\n".join(out)


def measure_large_document() -> float:
    """Synthesize the spec's worst case (60 KB, ~1000 headings) and time it."""
    parts = []
    for i in range(1000):
        parts.append(f"# Heading {i}")
        parts.append(f"Some **body** text with *italics* and `code` and $x^2$.\n")
    text = "\n".join(parts)
    start = time.monotonic()
    render_fragment(text)
    return time.monotonic() - start