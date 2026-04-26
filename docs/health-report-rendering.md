# TremorGuard 健康报告生成与 PDF 渲染说明

## 目标

健康分析报告采用“结构化医学分析 Markdown + WeasyPrint HTML/CSS PDF”链路。后端 API 路径保持不变，在线详情页继续返回 Markdown，PDF 下载接口使用同一份最终 Markdown、`input_snapshot` 和 `report_payload` 渲染，避免在线报告与 PDF 内容不一致。

报告仅用于健康管理和复诊沟通，不提供确诊、疾病分期、处方或药量调整结论。

## 后端配置

在 `tremor-guard-backend/.env` 中可配置：

```bash
HEALTH_REPORT_MASK_IDENTIFIERS=true
HEALTH_REPORT_TIMEZONE=Asia/Shanghai
HEALTH_REPORT_FONT_FAMILY="STHeiti, Songti SC, Noto Sans CJK SC, Source Han Sans SC, sans-serif"
```

- `HEALTH_REPORT_MASK_IDENTIFIERS`：默认开启。开启后 Markdown/PDF 展示名使用“张**”这类脱敏形式，`input_snapshot.patient_profile` 仍保留原始姓名供内部一致性校验。
- `HEALTH_REPORT_TIMEZONE`：用于震颤事件时段分布、用药时间窗分析和 PDF 生成日期展示。
- `HEALTH_REPORT_FONT_FAMILY`：PDF HTML 模板使用的字体栈。生产环境建议安装 Noto Sans CJK 或 Source Han Sans。

## WeasyPrint 原生依赖

Python 依赖已在 `tremor-guard-backend/pyproject.toml` 中声明：

```bash
./.venv/bin/python -m pip install -e .
```

WeasyPrint 还需要系统图形/字体库。常见环境：

```bash
# macOS
brew install pango

# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 fonts-noto-cjk
```

如果运行环境缺少 Pango，后端会退回最小 PDF 渲染，保证下载接口可用；生产环境应安装上述依赖以启用专业 HTML/CSS 排版、封面、目录、页眉页脚、KPI 卡片和 SVG 图表。

## 报告分析字段

报告生成前会先基于 `input_snapshot` 计算分析字段，供 Agent、fallback 模板和 PDF 共用：

- `analytics_summary`：核心指标、时段分布、幅度等级、依从率和用药窗口观察。
- `kpi_cards`：累计事件数、平均幅度、峰值幅度、用药依从率等 PDF 卡片数据。
- `visualization_data`：震颤时段分布、幅度直方图、用药时间轴、症状-用药窗口散点图。
- `tremor_severity_distribution`：轻度、中度、重度幅度区间计数与占比。
- `medication_correlation_summary`：服药前、服药后 1 小时、服药后 1-3 小时的观察性对比。
- `baseline_summary`：按监测日期形成的局部基线摘要。

这些字段追加到 `report_payload` 和 `input_snapshot`，不改变现有 REST API 路径。

## 示例 PDF 生成

先在系统中生成一份健康报告，再运行：

```bash
cd tremor-guard-backend
./.venv/bin/python -m app.scripts.generate_sample_health_report_pdf
```

也可以指定报告：

```bash
./.venv/bin/python -m app.scripts.generate_sample_health_report_pdf --report-id <report_id>
```

输出文件位于仓库 `output/` 目录，命名为：

```text
PD_Report_<patient_token>_<YYYYMMDD>.pdf
```

`patient_token` 是用户 ID 的短哈希，不使用患者姓名。

## 质量保护

报告 Markdown 生成后会做一致性和丰富度检查：

- 当输入中有患者姓名、震颤事件数、用药记录数时，正文不得与这些核心数据冲突。
- 脱敏开启时，正文不得出现完整患者姓名。
- Agent 输出缺少关键增强章节、表格或依从性分析时，降级为 deterministic fallback。
- PDF 始终从最终通过检查的 Markdown 渲染。

## 医学科普参考

报告中的科普语气保持保守，只描述健康管理观察与复诊沟通线索。当前科普内容主要参考：

- Parkinson's Foundation：Levodopa 和 wearing-off 科普。
  - https://www.parkinson.org/living-with-parkinsons/treatment/prescription-medications/levodopa
  - https://www.parkinson.org/taxonomy/term/175
- Mayo Clinic：帕金森病诊疗、运动治疗和左旋多巴相关说明。
  - https://www.mayoclinic.org/diseases-conditions/parkinsons-disease/diagnosis-treatment/drc-20376062
- NINDS：帕金森病症状、治疗和健康管理背景。
  - https://www.ninds.nih.gov/health-information/disorders/parkinsons-disease
- Movement Disorder Society：MDS-UPDRS 作为量表补充建议来源。
  - https://www.movementdisorders.org/MDS-Files1/Resources/PDFs/MDS-UPDRS.pdf
