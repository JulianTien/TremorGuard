from __future__ import annotations

import html
import io
import json
import keyword
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "neuro-pulse-showcase"
HTML_DIR = OUTPUT_DIR / "html"


def read_lines(path: Path, start: int, end: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[start - 1 : end])


def token_class(token_type: int, token_text: str) -> str | None:
    if token_type == tokenize.COMMENT:
        return "tok-comment"
    if token_type == tokenize.STRING:
        return "tok-string"
    if token_type == tokenize.NUMBER:
        return "tok-number"
    if token_type == tokenize.OP and token_text in {"=", "==", "!=", ">=", "<=", "->", ":", ".", ",", "(", ")", "[", "]", "{", "}"}:
        return "tok-operator"
    if token_type == tokenize.NAME:
        if keyword.iskeyword(token_text):
            return "tok-keyword"
        if token_text and token_text[0].isupper():
            return "tok-class"
        return "tok-name"
    return None


def highlight_python(code: str) -> list[str]:
    if not code.endswith("\n"):
        code = f"{code}\n"

    line_starts = [0]
    for index, char in enumerate(code):
        if char == "\n":
            line_starts.append(index + 1)

    def absolute_offset(position: tuple[int, int]) -> int:
        row, col = position
        return line_starts[row - 1] + col

    pieces: list[str] = []
    cursor = 0
    reader = io.StringIO(code).readline
    try:
        for token in tokenize.generate_tokens(reader):
            token_type, token_text, start, end, _ = token
            if token_type == tokenize.ENDMARKER:
                break

            start_offset = absolute_offset(start)
            end_offset = absolute_offset(end)
            if start_offset > cursor:
                pieces.append(html.escape(code[cursor:start_offset]))

            css_class = token_class(token_type, token_text)
            escaped = html.escape(code[start_offset:end_offset])
            if css_class:
                pieces.append(f'<span class="{css_class}">{escaped}</span>')
            else:
                pieces.append(escaped)
            cursor = end_offset
    except tokenize.TokenError:
        return [html.escape(line) for line in code.splitlines()]

    if cursor < len(code):
        pieces.append(html.escape(code[cursor:]))

    highlighted = "".join(pieces)
    lines = highlighted.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def code_block_html(code: str, starting_line: int = 1) -> str:
    lines = highlight_python(code)
    rows: list[str] = []
    for offset, line in enumerate(lines):
        rows.append(
            "".join(
                [
                    '<div class="code-row">',
                    f'<div class="line-no">{starting_line + offset}</div>',
                    f'<pre class="line-code">{line or " "}</pre>',
                    "</div>",
                ]
            )
        )
    return "\n".join(rows)


def editor_page_html(
    *,
    title: str,
    subtitle: str,
    chip: str,
    file_label: str,
    code_html: str,
) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(title)}</title>
    <style>
      :root {{
        --bg: #0b1020;
        --panel: rgba(11, 17, 32, 0.82);
        --panel-strong: rgba(10, 14, 28, 0.96);
        --border: rgba(148, 163, 184, 0.18);
        --text: #e5eefb;
        --muted: #8aa0bf;
        --accent: #53d3c6;
        --accent-2: #7aa2ff;
        --pink: #ff8cc6;
        --yellow: #f7cb5f;
        --green: #87e487;
        --line: rgba(148, 163, 184, 0.08);
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        min-height: 100vh;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(83, 211, 198, 0.18), transparent 28%),
          radial-gradient(circle at top right, rgba(122, 162, 255, 0.18), transparent 26%),
          linear-gradient(160deg, #09111c, #0e1528 48%, #0a1324 100%);
      }}

      .frame {{
        width: 1920px;
        height: 1080px;
        margin: 0 auto;
        padding: 56px;
        display: flex;
      }}

      .editor {{
        display: flex;
        flex-direction: column;
        width: 100%;
        border: 1px solid var(--border);
        border-radius: 28px;
        overflow: hidden;
        background: var(--panel);
        box-shadow: 0 30px 80px rgba(0, 0, 0, 0.35);
        backdrop-filter: blur(20px);
      }}

      .topbar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 22px 28px;
        background: rgba(13, 19, 36, 0.94);
        border-bottom: 1px solid var(--border);
      }}

      .topbar-left {{
        display: flex;
        align-items: center;
        gap: 18px;
      }}

      .lights {{
        display: flex;
        gap: 10px;
      }}

      .light {{
        width: 12px;
        height: 12px;
        border-radius: 999px;
      }}

      .light.red {{ background: #ff6b6b; }}
      .light.yellow {{ background: #ffd166; }}
      .light.green {{ background: #06d6a0; }}

      .file-pill {{
        padding: 10px 16px;
        border-radius: 999px;
        border: 1px solid rgba(122, 162, 255, 0.28);
        color: #dce7ff;
        font-size: 16px;
        letter-spacing: 0.02em;
        background: rgba(23, 33, 61, 0.82);
      }}

      .chip {{
        padding: 10px 16px;
        border-radius: 999px;
        color: #092127;
        background: linear-gradient(135deg, #65eadb, #9bd5ff);
        font-weight: 700;
        font-size: 15px;
      }}

      .content {{
        display: grid;
        grid-template-columns: 420px minmax(0, 1fr);
        min-height: 0;
        flex: 1;
      }}

      .sidebar {{
        padding: 34px 28px;
        border-right: 1px solid var(--border);
        background: linear-gradient(180deg, rgba(11, 18, 35, 0.9), rgba(10, 17, 30, 0.68));
      }}

      .eyebrow {{
        display: inline-flex;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(83, 211, 198, 0.12);
        color: var(--accent);
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}

      h1 {{
        margin: 18px 0 14px;
        font-size: 40px;
        line-height: 1.1;
      }}

      .subtitle {{
        margin: 0 0 24px;
        color: var(--muted);
        font-size: 19px;
        line-height: 1.6;
      }}

      .sidebar-card {{
        padding: 18px 18px 16px;
        border-radius: 20px;
        border: 1px solid rgba(135, 228, 135, 0.18);
        background: rgba(15, 24, 43, 0.88);
      }}

      .sidebar-card h2 {{
        margin: 0 0 10px;
        font-size: 18px;
      }}

      .sidebar-card p {{
        margin: 0;
        color: #a9bdd7;
        font-size: 15px;
        line-height: 1.7;
      }}

      .code-wrap {{
        padding: 28px 0 28px 0;
        overflow: hidden;
        background: linear-gradient(180deg, rgba(8, 12, 24, 0.85), rgba(8, 12, 24, 0.96));
      }}

      .code-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 0 28px 16px;
        padding: 16px 20px;
        border-radius: 18px;
        background: var(--panel-strong);
        border: 1px solid var(--border);
      }}

      .code-header .path {{
        color: #c2d3ef;
        font-size: 18px;
      }}

      .code-header .zoom {{
        color: var(--muted);
        font-size: 16px;
      }}

      .code-panel {{
        margin: 0 28px;
        padding: 14px 0;
        border: 1px solid var(--border);
        border-radius: 22px;
        background: rgba(8, 12, 24, 0.94);
        overflow: hidden;
      }}

      .code-row {{
        display: grid;
        grid-template-columns: 72px minmax(0, 1fr);
        align-items: start;
        border-bottom: 1px solid var(--line);
      }}

      .code-row:last-child {{
        border-bottom: 0;
      }}

      .line-no {{
        padding: 0 14px 0 0;
        color: #51647f;
        text-align: right;
        font: 500 18px/1.8 "SFMono-Regular", Consolas, monospace;
        user-select: none;
      }}

      .line-code {{
        margin: 0;
        padding: 0 24px 0 0;
        white-space: pre-wrap;
        word-break: break-word;
        font: 500 18px/1.8 "SFMono-Regular", Consolas, monospace;
      }}

      .tok-comment {{ color: #6f8aa8; }}
      .tok-string {{ color: var(--green); }}
      .tok-number {{ color: var(--yellow); }}
      .tok-keyword {{ color: var(--pink); font-weight: 700; }}
      .tok-class {{ color: #9bb8ff; }}
      .tok-name {{ color: #dfe8f8; }}
      .tok-operator {{ color: #9dc4ff; }}
    </style>
  </head>
  <body>
    <main class="frame">
      <section class="editor">
        <div class="topbar">
          <div class="topbar-left">
            <div class="lights">
              <span class="light red"></span>
              <span class="light yellow"></span>
              <span class="light green"></span>
            </div>
            <div class="file-pill">{html.escape(file_label)}</div>
          </div>
          <div class="chip">{html.escape(chip)}</div>
        </div>
        <div class="content">
          <aside class="sidebar">
            <div class="eyebrow">Neuro Pulse</div>
            <h1>{html.escape(title)}</h1>
            <p class="subtitle">{html.escape(subtitle)}</p>
            <div class="sidebar-card">
              <h2>展示重点</h2>
              <p>保留关键函数和安全边界逻辑，让评委能一眼看出系统不是普通 CRUD，而是围绕监测数据、AI 推理与辅助决策构建的后端能力。</p>
            </div>
          </aside>
          <section class="code-wrap">
            <div class="code-header">
              <div class="path">{html.escape(file_label)}</div>
              <div class="zoom">Trae-style code view · 130%</div>
            </div>
            <div class="code-panel">
              {code_html}
            </div>
          </section>
        </div>
      </section>
    </main>
  </body>
</html>
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_code_specs() -> list[dict[str, str]]:
    ai_chat = ROOT / "tremor-guard-backend" / "app" / "services" / "ai_chat.py"
    rehab = ROOT / "tremor-guard-backend" / "app" / "services" / "rehab_guidance.py"
    dashboard = ROOT / "tremor-guard-backend" / "app" / "services" / "dashboard.py"

    ai_chat_code = "\n".join(
        [
            read_lines(ai_chat, 23, 37),
            "",
            "def build_monitoring_context(clinical_session: Session, current_user: User) -> str:",
            "    profile = clinical_session.scalar(",
            "        select(PatientProfile).where(PatientProfile.user_id == current_user.id)",
            "    )",
            "    device_binding, snapshot = get_latest_device_status(clinical_session, current_user.id)",
            "    latest_event = clinical_session.scalar(",
            "        select(TremorEvent)",
            "        .where(TremorEvent.user_id == current_user.id)",
            "        .order_by(desc(TremorEvent.start_at))",
            "    )",
            "",
            "    metric_summaries = build_metric_summaries(events_today, events_yesterday)",
            "    trend_points = build_trend_points(events_today, medications, target_date)",
            "    overview_insight = build_overview_insight(trend_points, medications)",
            "    return \"\\n\".join(",
            "        [",
            "            \"以下是 TremorGuard 当前可用的用户上下文，请仅在有帮助时引用：\",",
            "            f\"- 设备状态：{device_summary}\",",
            "            f\"- 当日监测摘要：{metrics_summary}\",",
            "            f\"- 当日服药记录：{_format_medications(medications)}\",",
            "            f\"- 系统摘要：{overview_insight.summary}\",",
            "        ]",
            "    )",
            "",
            "def create_ai_chat_completion(",
            "    clinical_session: Session,",
            "    current_user: User,",
            "    messages: list[AiChatMessageInput],",
            ") -> AiChatResponse:",
            "    settings = get_settings()",
            "    context = build_monitoring_context(clinical_session, current_user)",
            "    request_messages = _build_request_messages(messages, context)",
            "    payload = {",
            "        \"model\": settings.dashscope_chat_model,",
            "        \"messages\": request_messages,",
            "        \"temperature\": 0.3,",
            "        \"max_tokens\": 700,",
            "    }",
            "    response = httpx.post(",
            "        f\"{settings.dashscope_base_url}/chat/completions\",",
            "        headers={\"Authorization\": f\"Bearer {settings.dashscope_api_key.get_secret_value()}\"},",
            "        json=payload,",
            "        timeout=settings.dashscope_timeout_seconds,",
            "    )",
            "    if response.status_code >= 400:",
            "        raise AiChatServiceError(status_code=502, detail=f\"AI 服务调用失败：{_extract_error_message(response)}\")",
        ]
    )

    rehab_code = "\n".join(
        [
            read_lines(rehab, 47, 82),
            "",
            "def load_rehab_evidence(session: Session, user_id: str, as_of_date: date) -> EvidenceBundle:",
            "    start_at, end_at = local_day_bounds(as_of_date)",
            "    medication_logs = list(",
            "        session.scalars(",
            "            select(MedicationLog)",
            "            .where(",
            "                MedicationLog.user_id == user_id,",
            "                MedicationLog.taken_at >= start_at,",
            "                MedicationLog.taken_at < end_at,",
            "            )",
            "            .order_by(MedicationLog.taken_at)",
            "        )",
            "    )",
            "    tremor_events = list(",
            "        session.scalars(",
            "            select(TremorEvent)",
            "            .where(",
            "                TremorEvent.user_id == user_id,",
            "                TremorEvent.start_at >= start_at,",
            "                TremorEvent.start_at < end_at,",
            "            )",
            "            .order_by(TremorEvent.start_at)",
            "        )",
            "    )",
            "    medication_signal = derive_medication_signal(medication_logs)",
            "    tremor_bucket = classify_tremor_bucket(tremor_events)",
            "    signal_consistency = determine_signal_consistency(medication_signal, tremor_bucket)",
            "    if signal_consistency == \"conflicting\":",
            "        explanation = \"用药记录与震颤强度信号存在张力，系统会保留风险提示并给出更保守的训练建议。\"",
            "",
            read_lines(rehab, 165, 175),
        ]
    )

    dashboard_code = "\n".join(
        [
            read_lines(dashboard, 28, 43),
            "",
            read_lines(dashboard, 71, 108),
            "",
            read_lines(dashboard, 111, 151),
            "",
            read_lines(dashboard, 154, 179),
        ]
    )

    return [
        {
            "filename": "neuro-pulse-04-ai-chat-backend.png",
            "html_name": "neuro-pulse-04-ai-chat-backend.html",
            "title": "AI 问答后端",
            "subtitle": "把用户提问、监测摘要和医疗安全边界一起送入模型，生成克制且可解释的健康管理回答。",
            "chip": "监测摘要 + 大模型问答 + 安全边界",
            "file_label": "tremor-guard-backend/app/services/ai_chat.py",
            "caption": "AI 问答后端：融合监测上下文并约束生成内容。",
            "code": ai_chat_code,
        },
        {
            "filename": "neuro-pulse-05-rehab-guidance-backend.png",
            "html_name": "neuro-pulse-05-rehab-guidance-backend.html",
            "title": "康复计划决策逻辑",
            "subtitle": "按目标自然日汇总用药与震颤证据，判断信号是否冲突，再映射到更保守或更积极的训练方案。",
            "chip": "证据驱动 + 风险判断 + 个性化康复建议",
            "file_label": "tremor-guard-backend/app/services/rehab_guidance.py",
            "caption": "康复计划引擎：按证据窗口生成可确认的辅助训练方案。",
            "code": rehab_code,
        },
        {
            "filename": "neuro-pulse-06-dashboard-analytics-backend.png",
            "html_name": "neuro-pulse-06-dashboard-analytics-backend.html",
            "title": "趋势洞察与可视化聚合",
            "subtitle": "把震颤事件与服药记录转成仪表盘指标、时间趋势和 AI 摘要，支撑前端数据卡片与趋势图。",
            "chip": "趋势聚合 + 可视化数据生成 + AI 摘要洞察",
            "file_label": "tremor-guard-backend/app/services/dashboard.py",
            "caption": "数据洞察后端：生成指标摘要、趋势点和复诊提示。",
            "code": dashboard_code,
        },
    ]


def build_frontend_specs() -> list[dict[str, str]]:
    return [
        {
            "filename": "neuro-pulse-01-home-hero.png",
            "caption": "首页封面：用一句话和核心指标说明产品价值。",
        },
        {
            "filename": "neuro-pulse-02-feature-cards.png",
            "caption": "技术特性：硬件、频谱分析与 AI 能力一屏讲清。",
        },
        {
            "filename": "neuro-pulse-03-severity-demo.png",
            "caption": "分级演示：通过交互模拟展示震颤严重度变化。",
        },
    ]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "project_name": "Neuro Pulse",
        "output_dir": str(OUTPUT_DIR),
        "screenshots": [],
    }

    for spec in build_code_specs():
        html_path = HTML_DIR / spec["html_name"]
        html_content = editor_page_html(
            title=spec["title"],
            subtitle=spec["subtitle"],
            chip=spec["chip"],
            file_label=spec["file_label"],
            code_html=code_block_html(spec["code"]),
        )
        write_text(html_path, html_content)
        manifest["screenshots"].append(
            {
                "filename": spec["filename"],
                "type": "code",
                "html": str(html_path),
                "caption": spec["caption"],
            }
        )

    for spec in build_frontend_specs():
        manifest["screenshots"].append(
            {
                "filename": spec["filename"],
                "type": "frontend",
                "caption": spec["caption"],
            }
        )

    captions_lines = ["# Neuro Pulse 截图说明", ""]
    for shot in manifest["screenshots"]:
        captions_lines.append(f"- `{shot['filename']}`: {shot['caption']}")

    write_text(OUTPUT_DIR / "captions.md", "\n".join(captions_lines) + "\n")
    write_text(OUTPUT_DIR / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
