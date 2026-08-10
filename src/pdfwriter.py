"""Minimal, self-contained PDF writer.

Produces a valid single- or multi-page PDF/1.4 with Helvetica text, enough
for FastNote's export requirement (FR-8): a file on disk that is a valid PDF.
No external library, so no missing-tool failure mode; the bytes are written
by this port and only this port.
"""

from __future__ import annotations

import zlib


def _esc_pdf(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_from_lines(text: str, font_pt: int = 11) -> bytes:
    """Build a PDF document from a plain-text rendering (no layout engine)."""
    lines = text.split("\n") or [""]
    lines = [line[:96] or " " for line in lines]

    page_height = 842.0
    page_width = 595.0
    line_h = font_pt * 1.32
    margin = 56.0
    usable = page_height - 2 * margin
    pages: list[list[str]] = []
    current: list[str] = []
    used = 0.0
    for line in lines:
        if used + line_h > usable:
            pages.append(current)
            current = []
            used = 0.0
        current.append(line)
        used += line_h
    pages.append(current)

    objects: list[bytes] = []
    for page in pages:
        stream_lines = []
        y = page_height - margin
        for line in page:
            stream_lines.append(
                f"BT /F1 {font_pt} Tf {margin:.1f} {y:.1f} Td "
                f"({_esc_pdf(line)}) Tj ET")
            y -= line_h
        content = "\n".join(stream_lines).encode("latin-1", "replace")
        objects.append(b"stream\n" + content + b"\nendstream")

    out: list[bytes] = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets: list[int] = []
    # catalog 1
    offsets.append(_tell(out))
    out.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # pages tree 2
    kids = "".join(f"{3 + i} 0 R " for i in range(len(pages)))
    offsets.append(_tell(out))
    out.append(b"2 0 obj\n<< /Type /Pages /Kids [" + kids.encode()
               + b"] /Count " + str(len(pages)).encode() + b" >>\nendobj\n")
    font_obj = 3 + len(pages)
    # each page 3.., and its content stream right after it
    for i, page in enumerate(pages):
        obj = 3 + i
        offsets.append(_tell(out))
        out.append(f"{obj} 0 obj\n<< /Type /Page /Parent 2 0 R "
                   f"/MediaBox [0 0 {page_width:.0f} {page_height:.0f}] "
                   f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
                   f"/Contents {obj + len(pages)} 0 R >>\nendobj\n".encode())
        offsets.append(_tell(out))
        out.append((f"{obj + len(pages)} 0 obj\n<< /Length {len(objects[i]):d} >>\n"
            ).encode() + objects[i] + b"\nendobj\n")
    offsets.append(_tell(out))
    out.append((f"{font_obj} 0 obj\n<< /Type /Font /Subtype /Type1 "
                "/BaseFont /Helvetica >>\nendobj\n").encode())
    xref = _tell(out)
    out.append(f"xref\n0 {font_obj + 1}\n".encode())
    out.append(b"0000000000 65535 f \n")
    for off in offsets:
        out.append(f"{off:010d} 00000 n \n".encode())
    out.append(b"trailer\n<< /Size " + str(font_obj + 1).encode()
               + b" /Root 1 0 R >>\nstartxref\n" + str(xref).encode()
               + b"\n%%EOF\n")
    return b"".join(out)


def _tell(out: list[bytes]) -> int:
    return sum(len(x) for x in out)


if __name__ == "__main__":
    import sys
    data = pdf_from_lines(sys.stdin.read())
    sys.stdout.buffer.write(data)