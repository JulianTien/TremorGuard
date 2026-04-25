from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


def _pdf_escape_hex(text: str) -> str:
    return text.encode("utf-16-be").hex().upper()


def _wrap_text(text: str, limit: int = 28) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        current += char
        if len(current) >= limit:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines or [""]


def _build_pdf_bytes(title: str, lines: list[str]) -> bytes:
    content_lines = ["BT", "/F1 16 Tf", "48 792 Td", "20 TL"]
    first = True
    for line in lines:
        safe_line = line or " "
        if first:
            content_lines.append(f"<{_pdf_escape_hex(safe_line)}> Tj")
            first = False
        else:
            content_lines.append("T*")
            content_lines.append(f"<{_pdf_escape_hex(safe_line)}> Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content_stream)} >>\nstream\n".encode("latin-1") + content_stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [6 0 R] >>",
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 >>",
    ]

    chunks = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in chunks))
        chunks.append(f"{index} 0 obj\n".encode("latin-1"))
        chunks.append(obj)
        chunks.append(b"\nendobj\n")

    xref_offset = sum(len(part) for part in chunks)
    xref = [f"xref\n0 {len(objects) + 1}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode("latin-1"))
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode(
            "latin-1"
        )
    )
    return b"".join(chunks + xref + [trailer])


class MarkdownPdfRenderer:
    def render(self, title: str, markdown: str, metadata: Mapping[str, object] | None = None) -> bytes:
        raise NotImplementedError


@dataclass(slots=True)
class BuiltinMarkdownPdfRenderer(MarkdownPdfRenderer):
    disclaimer_text: str

    def render(self, title: str, markdown: str, metadata: Mapping[str, object] | None = None) -> bytes:
        del metadata
        lines = [title, self.disclaimer_text, ""]
        for raw_line in markdown.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                lines.append("")
                continue
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
                if heading:
                    lines.append(heading)
                continue
            if stripped.startswith("|"):
                table_line = " | ".join(part.strip() for part in stripped.strip("|").split("|"))
                lines.extend(_wrap_text(table_line))
                continue
            if stripped.startswith(("- ", "* ")):
                lines.extend(_wrap_text(f"• {stripped[2:].strip()}"))
                continue
            lines.extend(_wrap_text(stripped))
        return _build_pdf_bytes(title, lines)
