"""Minimal PDF writer used by the grounding tests.

The fixture writes a valid PDF with one text line per page using the standard
Helvetica font, so the tests do not need a PDF library to build an input. The
implementation is deliberately small: it covers exactly what the tests need
(a text layer that pypdf can extract) and nothing else.
"""

from __future__ import annotations


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content(lines: list[str]) -> bytes:
    body = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            body.append("0 -18 Td")
        body.append(f"({_escape(line)}) Tj")
    body.append("ET")
    return "\n".join(body).encode("latin-1")


def build_pdf(pages: list[list[str]]) -> bytes:
    """Return a PDF with one page per entry; each entry is a list of text lines."""
    count = len(pages)
    page_ids = [4 + 2 * index for index in range(count)]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode("latin-1"),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for index, lines in enumerate(pages):
        page_id = 4 + 2 * index
        content_id = page_id + 1
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("latin-1")
        content = _content(lines)
        objects[content_id] = (
            b"<< /Length " + str(len(content)).encode("latin-1") + b" >>\nstream\n" + content + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for object_id in sorted(objects):
        offsets[object_id] = len(out)
        out += f"{object_id} 0 obj\n".encode("latin-1") + objects[object_id] + b"\nendobj\n"

    xref = len(out)
    total = max(objects) + 1
    out += f"xref\n0 {total}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for object_id in range(1, total):
        out += f"{offsets[object_id]:010d} 00000 n \n".encode("latin-1")
    out += f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("latin-1")
    return bytes(out)
