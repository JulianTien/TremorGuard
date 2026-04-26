from __future__ import annotations

from collections.abc import Mapping
import ctypes.util
from dataclasses import dataclass
from html import escape
from io import BytesIO
import re
from threading import Lock

from app.core.config import get_settings

_WEASYPRINT_LOCK = Lock()


def _pdf_escape_hex(text: str) -> str:
    return text.encode("utf-16-be").hex().upper()


def _wrap_text(text: str, limit: int = 30) -> list[str]:
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


def _build_minimal_pdf_bytes(title: str, markdown: str, disclaimer_text: str) -> bytes:
    lines = [title, disclaimer_text, ""]
    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            lines.append("")
        elif stripped.startswith("#"):
            lines.append(stripped.lstrip("#").strip())
        elif stripped.startswith("|"):
            lines.extend(_wrap_text(" | ".join(part.strip() for part in stripped.strip("|").split("|"))))
        elif stripped.startswith(("- ", "* ")):
            lines.extend(_wrap_text(f"• {stripped[2:].strip()}"))
        else:
            lines.extend(_wrap_text(stripped))

    content_lines = ["BT", "/F1 14 Tf", "48 792 Td", "18 TL"]
    first = True
    for line in lines:
        if first:
            content_lines.append(f"<{_pdf_escape_hex(line or ' ')}> Tj")
            first = False
        else:
            content_lines.append("T*")
            content_lines.append(f"<{_pdf_escape_hex(line or ' ')}> Tj")
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


def _can_load_weasyprint_native_libs() -> bool:
    return bool(
        ctypes.util.find_library("pango-1.0")
        or ctypes.util.find_library("pango-1.0-0")
        or ctypes.util.find_library("libpango-1.0-0")
    )


def _inline(text: object) -> str:
    rendered = escape(str(text or ""))
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"`(.+?)`", r"<code>\1</code>", rendered)
    return rendered


def _slug(value: str) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
    return normalized or "section"


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html: list[str] = []
    list_stack: list[str] = []
    in_table = False
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            html.append(f"<p>{'<br/>'.join(_inline(item) for item in paragraph)}</p>")
            paragraph.clear()

    def close_lists() -> None:
        while list_stack:
            html.append(f"</{list_stack.pop()}>")

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            html.append("</tbody></table></div>")
            in_table = False

    def table_cells(raw: str) -> list[str]:
        return [part.strip() for part in raw.strip().strip("|").split("|")]

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            close_lists()
            close_table()
            index += 1
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            flush_paragraph()
            close_lists()
            close_table()
            level = min(len(heading_match.group(1)), 4)
            text = heading_match.group(2).strip()
            html.append(f'<h{level} id="{_slug(text)}">{_inline(text)}</h{level}>')
            index += 1
            continue

        if line.startswith(">"):
            flush_paragraph()
            close_lists()
            close_table()
            html.append(f"<blockquote>{_inline(line.lstrip('>').strip())}</blockquote>")
            index += 1
            continue

        if line.startswith("|") and "|" in line[1:]:
            flush_paragraph()
            close_lists()
            cells = table_cells(line)
            next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if not in_table:
                html.append('<div class="table-wrap"><table>')
                if next_line.startswith("|") and re.fullmatch(r"[\|\s:\-]+", next_line):
                    html.append("<thead><tr>" + "".join(f"<th>{_inline(cell)}</th>" for cell in cells) + "</tr></thead><tbody>")
                    in_table = True
                    index += 2
                    continue
                html.append("<tbody>")
                in_table = True
            html.append("<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in cells) + "</tr>")
            index += 1
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", line)
        ordered_match = re.match(r"^\d+[\.)]\s+(.+)$", line)
        if bullet_match or ordered_match:
            flush_paragraph()
            close_table()
            tag = "ol" if ordered_match else "ul"
            if not list_stack or list_stack[-1] != tag:
                close_lists()
                html.append(f"<{tag}>")
                list_stack.append(tag)
            text = (ordered_match or bullet_match).group(1)
            html.append(f"<li>{_inline(text)}</li>")
            index += 1
            continue

        if line == "---":
            flush_paragraph()
            close_lists()
            close_table()
            html.append("<hr/>")
            index += 1
            continue

        close_table()
        paragraph.append(line)
        index += 1

    flush_paragraph()
    close_lists()
    close_table()
    return "\n".join(html)


def _metadata_dict(metadata: Mapping[str, object] | None) -> dict[str, object]:
    return dict(metadata or {})


def _safe_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _patient_card(context: dict[str, object], metadata: dict[str, object]) -> str:
    patient = _safe_dict(context.get("display_patient_profile") or context.get("patient_profile"))
    report_meta = _safe_dict(context.get("report_metadata"))
    rows = [
        ("姓名", patient.get("name") or "当前用户"),
        ("年龄", patient.get("age") or "待补充"),
        ("性别", patient.get("gender") or "待补充"),
        ("报告编号", report_meta.get("report_id") or metadata.get("report_id") or "待生成"),
        ("生成日期", str(report_meta.get("generated_at") or metadata.get("created_at") or "")[:10] or "待生成"),
    ]
    return "".join(
        f'<div class="patient-field"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>'
        for label, value in rows
    )


def _kpi_cards(payload: dict[str, object], context: dict[str, object]) -> str:
    cards = _safe_list(payload.get("kpi_cards") or context.get("kpi_cards"))
    if not cards:
        return ""
    return '<section class="kpi-grid">' + "".join(
        (
            '<div class="kpi-card">'
            f'<span>{escape(str(_safe_dict(card).get("label") or ""))}</span>'
            f'<strong>{escape(str(_safe_dict(card).get("value") or ""))}</strong>'
            f'<small>{escape(str(_safe_dict(card).get("hint") or ""))}</small>'
            "</div>"
        )
        for card in cards
    ) + "</section>"


def _polyline(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _hourly_chart(data: list[object]) -> str:
    rows = [_safe_dict(item) for item in data]
    if not rows:
        return ""
    max_count = max(int(item.get("count") or 0) for item in rows) or 1
    width, height = 520, 180
    points = []
    bars = []
    for item in rows:
        hour = int(item.get("hour") or 0)
        count = int(item.get("count") or 0)
        x = 28 + hour * 20
        y = height - 30 - (count / max_count) * 115
        points.append((x + 5, y))
        bars.append(f'<rect x="{x}" y="{y:.1f}" width="10" height="{height - 30 - y:.1f}" rx="2"></rect>')
    return f"""
    <div class="chart-card">
      <h3>震颤事件频率分布</h3>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="震颤事件频率图">
        <line x1="24" y1="{height - 30}" x2="{width - 24}" y2="{height - 30}" class="axis"/>
        <line x1="24" y1="20" x2="24" y2="{height - 30}" class="axis"/>
        <g class="bars">{''.join(bars)}</g>
        <polyline points="{_polyline(points)}" class="line"/>
        <text x="24" y="{height - 8}">00:00</text><text x="{width - 70}" y="{height - 8}">23:00</text>
      </svg>
    </div>
    """


def _histogram_chart(data: list[object]) -> str:
    rows = [_safe_dict(item) for item in data]
    if not rows:
        return ""
    max_count = max(int(item.get("count") or 0) for item in rows) or 1
    bars = []
    for index, item in enumerate(rows):
        count = int(item.get("count") or 0)
        bar_height = (count / max_count) * 95
        x = 70 + index * 120
        y = 140 - bar_height
        label = escape(str(item.get("label") or ""))
        bars.append(
            f'<rect x="{x}" y="{y:.1f}" width="58" height="{bar_height:.1f}" rx="4"></rect>'
            f'<text x="{x + 29}" y="160" text-anchor="middle">{label}</text>'
            f'<text x="{x + 29}" y="{y - 8:.1f}" text-anchor="middle">{count}</text>'
        )
    return f"""
    <div class="chart-card">
      <h3>震颤幅度分布</h3>
      <svg viewBox="0 0 430 180" role="img" aria-label="震颤幅度分布图">
        <line x1="42" y1="140" x2="390" y2="140" class="axis"/>
        <g class="bars">{''.join(bars)}</g>
      </svg>
    </div>
    """


def _timeline_chart(data: list[object]) -> str:
    rows = [_safe_dict(item) for item in data]
    if not rows:
        return ""
    items = []
    for index, item in enumerate(rows):
        y = 34 + index * 34
        status = str(item.get("status") or "")
        color_class = "taken" if status == "taken" else "pending"
        label = escape(f"{item.get('time') or ''} {item.get('name') or ''} {item.get('dose') or ''} ({status})")
        items.append(f'<circle cx="34" cy="{y}" r="6" class="{color_class}"/><text x="54" y="{y + 5}">{label}</text>')
    height = max(120, 48 + len(rows) * 34)
    return f"""
    <div class="chart-card">
      <h3>用药执行时间轴</h3>
      <svg viewBox="0 0 520 {height}" role="img" aria-label="用药时间轴">
        <line x1="34" y1="24" x2="34" y2="{height - 22}" class="axis"/>
        {''.join(items)}
      </svg>
    </div>
    """


def _scatter_chart(data: list[object]) -> str:
    rows = [_safe_dict(item) for item in data]
    if not rows:
        return ""
    xs = [float(item.get("minutes_from_first_dose") or 0) for item in rows]
    ys = [float(item.get("amplitude") or 0) for item in rows]
    min_x, max_x = min(xs), max(xs)
    max_y = max(max(ys), 1)
    dots = []
    for x_value, y_value in zip(xs, ys, strict=False):
        x = 38 + ((x_value - min_x) / ((max_x - min_x) or 1)) * 430
        y = 136 - (y_value / max_y) * 95
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4"></circle>')
    return f"""
    <div class="chart-card">
      <h3>症状-用药时间关联散点</h3>
      <svg viewBox="0 0 520 170" role="img" aria-label="症状用药关联散点图">
        <line x1="34" y1="140" x2="485" y2="140" class="axis"/>
        <line x1="34" y1="24" x2="34" y2="140" class="axis"/>
        <g class="dots">{''.join(dots)}</g>
        <text x="34" y="162">首剂相对时间</text><text x="390" y="162">震颤幅度</text>
      </svg>
    </div>
    """


def _visualizations(payload: dict[str, object], context: dict[str, object]) -> str:
    data = _safe_dict(payload.get("visualization_data") or context.get("visualization_data"))
    charts = [
        _hourly_chart(_safe_list(data.get("hourly_event_counts"))),
        _histogram_chart(_safe_list(data.get("amplitude_histogram"))),
        _timeline_chart(_safe_list(data.get("medication_timeline"))),
        _scatter_chart(_safe_list(data.get("medication_scatter"))),
    ]
    rendered = "".join(chart for chart in charts if chart)
    if not rendered:
        return ""
    return f'<section class="visualizations"><h2>数据可视化概览</h2><div class="chart-grid">{rendered}</div></section>'


def _toc(sections: list[dict[str, str]]) -> str:
    if not sections:
        return ""
    links = []
    for section in sections:
        title = str(section.get("title") or "")
        section_id = _slug(title)
        links.append(f'<li><a href="#{section_id}">{escape(title)}</a></li>')
    return '<section class="toc page-break"><h1>目录</h1><ol>' + "".join(links) + "</ol></section>"


def _sections_from_metadata(markdown: str, metadata: dict[str, object]) -> list[dict[str, str]]:
    raw_sections = _safe_list(metadata.get("sections"))
    if raw_sections:
        sections = []
        for item in raw_sections:
            section = _safe_dict(item)
            title = str(section.get("title") or "")
            body = str(section.get("body") or "")
            if title:
                sections.append({"title": title, "body": body})
        return sections

    sections: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    body_lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current:
                current["body"] = "\n".join(body_lines).strip()
                sections.append(current)
            current = {"title": stripped[3:].strip(), "body": ""}
            body_lines = []
        elif current:
            body_lines.append(line)
    if current:
        current["body"] = "\n".join(body_lines).strip()
        sections.append(current)
    return sections


def _body_sections(sections: list[dict[str, str]], markdown: str) -> str:
    if not sections:
        return f'<section class="report-body">{_markdown_to_html(markdown)}</section>'
    blocks = []
    for section in sections:
        title = str(section.get("title") or "")
        body = str(section.get("body") or "")
        blocks.append(
            f'<section class="report-section" id="{_slug(title)}">'
            f"<h2>{_inline(title)}</h2>"
            f"{_markdown_to_html(body)}"
            "</section>"
        )
    return "".join(blocks)


def _styles(font_family: str) -> str:
    return f"""
    @page {{
      size: A4;
      margin: 22mm 16mm 18mm 16mm;
      @top-left {{ content: "帕金森患者健康分析报告"; color: #6b7280; font-size: 9px; }}
      @bottom-left {{ content: "仅供健康管理与复诊沟通参考"; color: #6b7280; font-size: 8px; }}
      @bottom-right {{ content: counter(page) " / " counter(pages); color: #6b7280; font-size: 9px; }}
    }}
    @page cover {{ margin: 0; @top-left {{ content: none; }} @bottom-left {{ content: none; }} @bottom-right {{ content: none; }} }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: {font_family}; color: #172033; line-height: 1.68; font-size: 11px; }}
    .cover {{ page: cover; min-height: 297mm; padding: 34mm 26mm 24mm; background: linear-gradient(180deg, #f5f9fb 0%, #ffffff 40%); }}
    .brand {{ display: flex; align-items: center; gap: 10px; color: #1e5f8c; font-weight: 700; letter-spacing: .08em; }}
    .logo {{ width: 42px; height: 42px; border-radius: 8px; background: #1e5f8c; color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 17px; }}
    .cover h1 {{ margin: 46mm 0 8mm; text-align: center; font-size: 28px; color: #12364f; letter-spacing: .04em; }}
    .report-tag {{ text-align: center; color: #2c5f4a; font-weight: 700; border: 1px solid #cfe0dc; border-radius: 999px; padding: 6px 14px; width: max-content; margin: 0 auto 18mm; }}
    .patient-card {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; padding: 18px; background: white; border: 1px solid #dbe6ec; border-radius: 8px; box-shadow: 0 8px 24px rgba(30, 95, 140, .08); }}
    .patient-field span {{ display: block; color: #64748b; font-size: 9px; }}
    .patient-field strong {{ display: block; margin-top: 2px; color: #172033; font-size: 12px; }}
    .cover-disclaimer {{ margin-top: 18mm; padding: 14px 16px; border-left: 4px solid #1e5f8c; background: #eef5f8; color: #405466; }}
    .toc h1 {{ font-size: 22px; color: #12364f; border-bottom: 2px solid #1e5f8c; padding-bottom: 8px; }}
    .toc ol {{ padding-left: 0; list-style: none; }}
    .toc li {{ border-bottom: 1px dotted #cbd5e1; padding: 7px 0; }}
    .toc a {{ text-decoration: none; color: #172033; }}
    .toc a::after {{ content: leader(".") target-counter(attr(href), page); color: #64748b; }}
    .page-break {{ break-after: page; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 0 0 18px; }}
    .kpi-card {{ border: 1px solid #dbe6ec; border-radius: 8px; padding: 12px; background: #f8fbfc; }}
    .kpi-card span {{ color: #64748b; font-size: 9px; }}
    .kpi-card strong {{ display: block; color: #1e5f8c; font-size: 20px; line-height: 1.2; margin: 4px 0; }}
    .kpi-card small {{ color: #6b7280; }}
    .visualizations {{ margin: 10px 0 18px; }}
    .visualizations h2, .report-section h2 {{ font-size: 16px; color: #12364f; border-bottom: 2px solid #1e5f8c; padding-bottom: 6px; margin: 22px 0 12px; }}
    .chart-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
    .chart-card {{ border: 1px solid #dbe6ec; border-radius: 8px; padding: 10px; background: #ffffff; break-inside: avoid; }}
    .chart-card h3 {{ margin: 0 0 6px; color: #2c5f4a; font-size: 11px; }}
    svg {{ width: 100%; height: auto; }}
    svg text {{ font-size: 10px; fill: #64748b; }}
    .axis {{ stroke: #94a3b8; stroke-width: 1; }}
    .bars rect {{ fill: #8fb7ca; }}
    .line {{ fill: none; stroke: #1e5f8c; stroke-width: 2; }}
    .dots circle {{ fill: #2c5f4a; opacity: .78; }}
    .taken {{ fill: #2c5f4a; }} .pending {{ fill: #d97706; }}
    .report-section {{ break-inside: auto; }}
    .report-section h3 {{ margin: 14px 0 8px; padding: 6px 10px; border-left: 4px solid #2c5f4a; background: #f0f7f4; color: #183f31; font-size: 12px; }}
    p {{ margin: 7px 0; }}
    ul, ol {{ margin: 8px 0 10px 20px; padding: 0; }}
    li {{ margin: 3px 0; }}
    blockquote {{ margin: 10px 0; padding: 9px 12px; border-left: 4px solid #1e5f8c; background: #eef5f8; color: #405466; }}
    .table-wrap {{ margin: 10px 0; break-inside: avoid; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
    thead {{ display: table-header-group; background: #e7f0f5; }}
    th, td {{ border: 1px solid #dbe6ec; padding: 6px 7px; vertical-align: top; }}
    tr:nth-child(even) td {{ background: #f8fafc; }}
    code {{ font-family: "SFMono-Regular", Consolas, monospace; background: #eef2f7; padding: 1px 3px; border-radius: 3px; }}
    .conclusion-disclaimer {{ margin-top: 18px; padding: 12px; border: 1px solid #dbe6ec; background: #f8fafc; color: #405466; }}
    """


def _html_document(title: str, markdown: str, metadata: dict[str, object], disclaimer_text: str) -> str:
    settings = get_settings()
    context = _safe_dict(metadata.get("context"))
    payload = _safe_dict(metadata.get("report_payload"))
    report_meta = _safe_dict(context.get("report_metadata"))
    sections = _sections_from_metadata(markdown, metadata)
    display_title = escape(title)
    report_type = escape(str(report_meta.get("report_type_label") or "TremorGuard 健康管理报告"))
    body = _body_sections(sections, markdown)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>{display_title}</title>
  <style>{_styles(settings.health_report_font_family)}</style>
</head>
<body>
  <section class="cover">
    <div class="brand"><span class="logo">TG</span><span>TremorGuard</span></div>
    <h1>{display_title}</h1>
    <div class="report-tag">{report_type}</div>
    <div class="patient-card">{_patient_card(context, metadata)}</div>
    <div class="cover-disclaimer"><strong>医疗免责声明</strong><br/>{escape(disclaimer_text)}</div>
  </section>
  {_toc(sections)}
  {_kpi_cards(payload, context)}
  {_visualizations(payload, context)}
  {body}
  <section class="conclusion-disclaimer"><strong>结论页免责声明：</strong>{escape(disclaimer_text)}</section>
</body>
</html>"""


class MarkdownPdfRenderer:
    def render(self, title: str, markdown: str, metadata: Mapping[str, object] | None = None) -> bytes:
        raise NotImplementedError


@dataclass(slots=True)
class BuiltinMarkdownPdfRenderer(MarkdownPdfRenderer):
    disclaimer_text: str

    def render(self, title: str, markdown: str, metadata: Mapping[str, object] | None = None) -> bytes:
        normalized_metadata = _metadata_dict(metadata)
        html = _html_document(title, markdown, normalized_metadata, self.disclaimer_text)
        if not _can_load_weasyprint_native_libs():
            return _build_minimal_pdf_bytes(title, markdown, self.disclaimer_text)
        try:
            with _WEASYPRINT_LOCK:
                from weasyprint import HTML

                buffer = BytesIO()
                HTML(string=html).write_pdf(buffer)
                return buffer.getvalue()
        except Exception:
            return _build_minimal_pdf_bytes(title, markdown, self.disclaimer_text)
