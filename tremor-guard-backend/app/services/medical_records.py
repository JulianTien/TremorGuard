from __future__ import annotations

import base64
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
from statistics import mean
from types import SimpleNamespace
from urllib.parse import quote
from uuid import uuid4

import httpx
from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import ClinicalSessionLocal
from app.models.clinical import (
    ApiAuditLog,
    ConsentSettings,
    LongitudinalReport,
    MedicationLog,
    MedicalRecordArchive,
    MedicalRecordExtraction,
    MedicalRecordFile,
    PatientProfile,
    ReportInputLink,
    TremorEvent,
)
from app.models.identity import User
from app.schemas.domain import (
    CreateMedicalRecordArchiveRequest,
    CreateMedicalRecordReportRequest,
    MedicalRecordArchiveDetailDTO,
    MedicalRecordArchiveSummaryDTO,
    MedicalRecordExtractionDTO,
    MedicalRecordFileDTO,
    MedicalRecordReportDetailDTO,
    MedicalRecordReportPipelineStageDTO,
    MedicalRecordReportPipelineStateDTO,
    MedicalRecordReportSummaryDTO,
)
from app.services.audit import record_audit_log
from app.services.dashboard import format_device_status, get_latest_device_status
from app.services.health_report_analytics import enrich_health_report_context, report_patient_token
from app.services.markdown_pdf import BuiltinMarkdownPdfRenderer
from app.services.report_agent import HealthReportAgent, ReportContextAssembler

DISCLAIMER_TEXT = "本报告仅供健康管理与复诊沟通参考，不能替代医生诊断、分期、处方或药量调整。"
DISCLAIMER_VERSION = "non-diagnostic-v1"
PROMPT_VERSION = "medical-records-v2"
AI_HEALTH_ARCHIVE_TITLE = "AI健康报告档案"
AI_HEALTH_REPORT_TITLE = "AI健康报告"
HEALTH_REPORT_TEMPLATE_NAME = "Parkinson-health-analysis-report"
HEALTH_REPORT_TEMPLATE_VERSION = "v2"
HEALTH_REPORT_TEMPLATE_TITLE = "帕金森患者健康分析报告"
HEALTH_REPORT_TEMPLATE_SECTIONS = [
    "基本信息",
    "评估目的",
    "本次监测亮点与异常提示",
    "主诉与现病史",
    "既往史、家族史及生活方式",
    "当前治疗与用药情况",
    "用药-症状关联分析",
    "运动症状评估",
    "非运动症状评估",
    "日常生活能力评估",
    "体格检查",
    "辅助检查结果",
    "量表评分与疾病分期",
    "主要健康问题总结",
    "综合分析",
    "干预建议",
    "复诊准备清单",
    "症状自评问卷",
    "知识科普卡片",
    "随访计划",
    "结论",
]
MISSING_DATA_PLACEHOLDER = "数据不足/待补充。"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
BANNED_PHRASES = ("确诊", "诊断为", "分期", "处方", "药量调整", "排除")
MARKDOWN_PDF_RENDERER = BuiltinMarkdownPdfRenderer(DISCLAIMER_TEXT)
REPORT_CONTEXT_ASSEMBLER = ReportContextAssembler()
HEALTH_REPORT_AGENT = HealthReportAgent()


@dataclass(slots=True)
class MedicalRecordsServiceError(Exception):
    status_code: int
    detail: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _storage_root() -> Path:
    settings = get_settings()
    root = Path(settings.medical_records_storage_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_pdf_bytes(title: str, sections: list[tuple[str, list[str]]]) -> bytes:
    markdown_parts = [f"# {title}"]
    for section_title, items in sections:
        markdown_parts.append(f"## {section_title}")
        normalized_items = [str(item).strip() for item in items if str(item).strip()]
        if not normalized_items:
            markdown_parts.append(MISSING_DATA_PLACEHOLDER)
            continue
        for item in normalized_items:
            markdown_parts.append(f"- {item}")
    markdown = "\n\n".join(markdown_parts)
    return MARKDOWN_PDF_RENDERER.render(title, markdown)


def _archive_path(archive_id: str) -> Path:
    path = _storage_root() / archive_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_download_filename_segment(value: str | None) -> str:
    if not value:
        return ""
    sanitized = "".join(" " if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in value)
    return " ".join(sanitized.split())


def _ascii_filename_fallback(value: str) -> str:
    ascii_only = "".join(char if ord(char) < 128 else "-" for char in value)
    ascii_only = "".join(char for char in ascii_only if char.isalnum() or char in ("-", "_", ".", " "))
    normalized = "-".join(part for part in ascii_only.replace(" ", "-").split("-") if part)
    return normalized or "tremorguard-health-report.pdf"


def _report_download_filename(report: LongitudinalReport) -> str:
    patient_id = report_patient_token(report.user_id)
    if isinstance(report.input_snapshot, dict):
        report_metadata = report.input_snapshot.get("report_metadata")
        if isinstance(report_metadata, dict):
            patient_id = str(report_metadata.get("patient_token") or patient_id)
        patient_token = report.input_snapshot.get("patient_token")
        if isinstance(patient_token, str) and patient_token.strip():
            patient_id = patient_token.strip()

    generated_date = (report.completed_at or report.created_at or _utcnow()).strftime("%Y%m%d")
    return f"PD_Report_{_sanitize_download_filename_segment(patient_id)}_{generated_date}.pdf"


def _content_disposition_headers(filename: str) -> dict[str, str]:
    safe_filename = _sanitize_download_filename_segment(filename) or "tremorguard-health-report.pdf"
    ascii_fallback = _ascii_filename_fallback(safe_filename)
    encoded_filename = quote(safe_filename, safe="")
    return {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_filename}"
        )
    }


def _reports_path(archive_id: str) -> Path:
    path = _archive_path(archive_id) / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _build_pipeline_stage(
    status: str = "queued",
    *,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    detail: str | None = None,
    error: str | None = None,
) -> dict[str, str | None]:
    return {
        "status": status,
        "started_at": _to_iso(started_at),
        "completed_at": _to_iso(completed_at),
        "detail": detail,
        "error": error,
    }


def _initial_pipeline_state() -> dict[str, object]:
    now = _utcnow()
    return {
        "router": _build_pipeline_stage("queued"),
        "context_assembly": _build_pipeline_stage("queued"),
        "report_agent_llm": _build_pipeline_stage("queued"),
        "markdown_validation": _build_pipeline_stage("queued"),
        "pdf_render": _build_pipeline_stage("queued"),
        "template": _build_pipeline_stage("queued"),
        "llm": _build_pipeline_stage("queued"),
        "pdf": _build_pipeline_stage("queued"),
        "updated_at": _to_iso(now),
    }


def _get_pipeline_state(report: LongitudinalReport) -> dict[str, object]:
    if isinstance(report.pipeline_state, dict):
        state = dict(report.pipeline_state)
    else:
        state = {}
    state.setdefault(
        "template",
        _build_pipeline_stage(
            "succeeded" if report.input_snapshot else "queued",
            completed_at=report.completed_at if report.input_snapshot else None,
            detail="已完成模板上下文准备。" if report.input_snapshot else None,
        ),
    )
    state.setdefault(
        "llm",
        _build_pipeline_stage(
            report.status if report.status in {"queued", "processing", "succeeded", "failed"} else "queued",
            completed_at=report.completed_at if report.status == "succeeded" else None,
            error=report.error_summary if report.status == "failed" else None,
        ),
    )
    state.setdefault(
        "pdf",
        _build_pipeline_stage(
            report.pdf_status if report.pdf_status in {"queued", "processing", "succeeded", "failed"} else "queued",
            completed_at=report.completed_at if report.pdf_status == "succeeded" else None,
        ),
    )
    state.setdefault("updated_at", _to_iso(report.updated_at))
    return state


def _set_pipeline_stage(
    report: LongitudinalReport,
    stage_name: str,
    status: str,
    *,
    detail: str | None = None,
    error: str | None = None,
) -> None:
    state = _get_pipeline_state(report)
    stage = dict(state.get(stage_name) or _build_pipeline_stage())
    now = _utcnow()
    if status == "processing" and not stage.get("started_at"):
        stage["started_at"] = _to_iso(now)
    if status in {"succeeded", "failed"}:
        stage["started_at"] = stage.get("started_at") or _to_iso(now)
        stage["completed_at"] = _to_iso(now)
    stage["status"] = status
    if detail is not None:
        stage["detail"] = detail
    if error is not None:
        stage["error"] = error
    elif status != "failed":
        stage["error"] = None
    state[stage_name] = stage
    state["updated_at"] = _to_iso(now)
    report.pipeline_state = state


def _pipeline_state_dto(report: LongitudinalReport) -> MedicalRecordReportPipelineStateDTO:
    state = _get_pipeline_state(report)

    def build_stage(name: str) -> MedicalRecordReportPipelineStageDTO:
        stage = state.get(name) if isinstance(state.get(name), dict) else {}
        return MedicalRecordReportPipelineStageDTO(
            status=str(stage.get("status") or "queued"),
            started_at=_parse_iso_datetime(stage.get("started_at")),
            completed_at=_parse_iso_datetime(stage.get("completed_at")),
            detail=str(stage.get("detail")) if stage.get("detail") is not None else None,
            error=str(stage.get("error")) if stage.get("error") is not None else None,
        )

    return MedicalRecordReportPipelineStateDTO(
        router=build_stage("router"),
        context_assembly=build_stage("context_assembly"),
        report_agent_llm=build_stage("report_agent_llm"),
        markdown_validation=build_stage("markdown_validation"),
        pdf_render=build_stage("pdf_render"),
        template=build_stage("template"),
        llm=build_stage("llm"),
        pdf=build_stage("pdf"),
        updated_at=_parse_iso_datetime(state.get("updated_at") if isinstance(state.get("updated_at"), str) else None),
    )


def _normalize_heading_key(text: str) -> str:
    normalized = text.strip().lstrip("#").strip()
    normalized = re.sub(r"^\d+[\.\u3001、\s]+", "", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _strip_markdown_text(text: str) -> str:
    normalized = re.sub(r"`([^`]*)`", r"\1", text)
    normalized = normalized.replace("**", "").replace("__", "").replace("*", "").replace("_", "")
    normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", normalized)
    normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized)
    normalized = normalized.lstrip("#").strip()
    return normalized


def _markdown_lines_to_items(text: str) -> list[str]:
    items: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        stripped = _strip_markdown_text(stripped)
        stripped = re.sub(r"^[\-\*\u2022]\s*", "", stripped)
        stripped = re.sub(r"^\d+[\.\)]\s*", "", stripped)
        if stripped:
            items.append(stripped)
    return items


def _parse_report_markdown_sections(markdown: str) -> list[dict[str, str]]:
    title_map = {_normalize_heading_key(title): title for title in HEALTH_REPORT_TEMPLATE_SECTIONS}
    section_bodies: dict[str, list[str]] = {title: [] for title in HEALTH_REPORT_TEMPLATE_SECTIONS}
    current_title: str | None = None

    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if current_title:
                section_bodies[current_title].append("")
            continue

        normalized = _normalize_heading_key(stripped)
        matched_title = title_map.get(normalized)
        if matched_title and (stripped.startswith("#") or re.match(r"^\d+[\.\u3001、\s]+", stripped)):
            current_title = matched_title
            continue
        if stripped.startswith("#") and normalized == _normalize_heading_key(HEALTH_REPORT_TEMPLATE_TITLE):
            continue
        if current_title:
            section_bodies[current_title].append(raw_line.rstrip())

    sections: list[dict[str, str]] = []
    for index, title in enumerate(HEALTH_REPORT_TEMPLATE_SECTIONS, start=1):
        body = "\n".join(section_bodies[title]).strip()
        sections.append(
            {
                "id": f"template-section-{index}",
                "title": f"{index}. {title}",
                "body": body or MISSING_DATA_PLACEHOLDER,
            }
        )
    return sections


def _build_canonical_report_markdown(sections: Sequence[dict[str, str]]) -> str:
    lines = [f"# {HEALTH_REPORT_TEMPLATE_TITLE}", ""]
    for section in sections:
        lines.append(f"## {section['title']}")
        lines.append(section["body"].strip() or MISSING_DATA_PLACEHOLDER)
        lines.append("")
    return "\n".join(lines).strip()


def _build_summary_from_sections(sections: Sequence[dict[str, str]]) -> str:
    important_titles = {"14. 主要健康问题总结", "21. 结论"}
    blocks: list[str] = []
    for section in sections:
        if section["title"] in important_titles:
            body_lines = _markdown_lines_to_items(section["body"])
            body = "；".join(body_lines[:3]) if body_lines else MISSING_DATA_PLACEHOLDER
            blocks.append(f"**{section['title']}**\n{body}")
    return "\n\n".join(blocks) if blocks else MISSING_DATA_PLACEHOLDER


def _build_quality_warnings(sections: Sequence[dict[str, str]]) -> list[str]:
    warnings: list[str] = []
    for section in sections:
        body = section["body"].strip()
        if not body:
            warnings.append(f"{section['title']} 未生成有效内容。")
            continue
        sentence_count = len(
            [
                item
                for item in re.split(r"[。！？!?]", _strip_markdown_text(body))
                if item.strip()
            ]
        )
        if sentence_count < 2:
            warnings.append(f"{section['title']} 分析性内容偏少，建议后续补充。")
    return warnings


def _build_report_payload_from_sections(
    sections: Sequence[dict[str, str]],
    context: dict,
) -> dict[str, object]:
    section_map = {section["title"]: section["body"] for section in sections}

    def section_body(title: str) -> str:
        for section_title, body in section_map.items():
            if section_title.endswith(title):
                return body
        return ""
    information_gaps = [
        item
        for item in context.get("information_gaps") or []
        if isinstance(item, str) and item.strip()
    ]
    if not information_gaps:
        information_gaps = [
            section["title"]
            for section in sections
            if MISSING_DATA_PLACEHOLDER in section["body"]
        ]

    payload = {
        "title": HEALTH_REPORT_TEMPLATE_TITLE,
        "executive_summary": _strip_markdown_text(
            section_body("主要健康问题总结") or section_body("结论") or MISSING_DATA_PLACEHOLDER
        ),
        "historical_record_summary": _markdown_lines_to_items(
            section_body("既往史、家族史及生活方式")
        ) or [MISSING_DATA_PLACEHOLDER],
        "monitoring_observations": (
            _markdown_lines_to_items(section_body("本次监测亮点与异常提示"))
            + _markdown_lines_to_items(section_body("运动症状评估"))
            + _markdown_lines_to_items(section_body("非运动症状评估"))
            + _markdown_lines_to_items(section_body("日常生活能力评估"))
        ) or [MISSING_DATA_PLACEHOLDER],
        "medication_observations": _markdown_lines_to_items(
            section_body("当前治疗与用药情况") + "\n" + section_body("用药-症状关联分析")
        ) or [MISSING_DATA_PLACEHOLDER],
        "information_gaps": information_gaps or [MISSING_DATA_PLACEHOLDER],
        "doctor_discussion_points": (
            _markdown_lines_to_items(section_body("干预建议"))
            + _markdown_lines_to_items(section_body("复诊准备清单"))
            + _markdown_lines_to_items(section_body("随访计划"))
        ) or [MISSING_DATA_PLACEHOLDER],
        "non_diagnostic_notice": DISCLAIMER_TEXT,
    }
    for key in (
        "analytics_summary_text",
        "kpi_cards",
        "visualization_data",
        "tremor_severity_distribution",
        "time_distribution",
        "medication_adherence",
        "medication_correlation_summary",
        "baseline_summary",
        "monitoring_highlights",
    ):
        if key in context:
            payload[key] = context[key]
    payload["analytics_summary"] = context.get("analytics_summary_text")
    payload["pdf_render_metadata"] = {
        "patient_token": context.get("patient_token"),
        "report_metadata": context.get("report_metadata"),
        "mask_identifiers": (context.get("report_metadata") or {}).get("mask_identifiers")
        if isinstance(context.get("report_metadata"), dict)
        else None,
    }
    return payload


def _render_report_markdown_from_payload(report_payload: dict | None) -> str | None:
    if not isinstance(report_payload, dict):
        return None
    analytics_summary = str(report_payload.get("analytics_summary") or MISSING_DATA_PLACEHOLDER)
    medication_observations = "\n".join(
        str(item) for item in report_payload.get("medication_observations", []) if str(item).strip()
    ) or MISSING_DATA_PLACEHOLDER
    monitoring_observations = "\n".join(
        str(item) for item in report_payload.get("monitoring_observations", []) if str(item).strip()
    ) or MISSING_DATA_PLACEHOLDER
    doctor_discussion_points = "\n".join(
        str(item) for item in report_payload.get("doctor_discussion_points", []) if str(item).strip()
    ) or MISSING_DATA_PLACEHOLDER
    legacy_body_by_title = {
        "基本信息": MISSING_DATA_PLACEHOLDER,
        "评估目的": "用于辅助健康管理与复诊沟通，不替代医生诊断。",
        "本次监测亮点与异常提示": analytics_summary,
        "主诉与现病史": analytics_summary,
        "既往史、家族史及生活方式": "\n".join(
            str(item) for item in report_payload.get("historical_record_summary", []) if str(item).strip()
        ) or MISSING_DATA_PLACEHOLDER,
        "当前治疗与用药情况": medication_observations,
        "用药-症状关联分析": str(
            (report_payload.get("medication_correlation_summary") or {}).get("wearing_off_signal")
            if isinstance(report_payload.get("medication_correlation_summary"), dict)
            else MISSING_DATA_PLACEHOLDER
        ),
        "运动症状评估": monitoring_observations,
        "非运动症状评估": "当前未采集非运动症状问卷，建议补充睡眠、便秘、情绪、认知和自主神经相关观察。",
        "日常生活能力评估": "当前未采集日常生活能力量表，建议补充穿衣、进食、行走、转身和跌倒风险记录。",
        "体格检查": "当前未纳入线下查体结果，建议复诊时由医生结合肌张力、步态和平衡检查综合评估。",
        "辅助检查结果": "当前未纳入影像、化验或量表原文，建议补充既往检查资料。",
        "量表评分与疾病分期": "当前未采集标准化量表评分，且本系统不提供疾病分期结论。",
        "主要健康问题总结": str(report_payload.get("executive_summary") or MISSING_DATA_PLACEHOLDER),
        "综合分析": analytics_summary,
        "干预建议": doctor_discussion_points,
        "复诊准备清单": doctor_discussion_points,
        "症状自评问卷": "复诊前建议记录震颤最明显时段、诱因、服药后变化、跌倒或近跌倒、头晕和睡眠情况。",
        "知识科普卡片": "本报告中的剂末波动、幅度分层和用药依从率均为健康管理观察指标，不替代医生判断。",
        "随访计划": "建议携带本报告与原始病历资料复诊，由专业医生综合评估。",
        "结论": str(report_payload.get("executive_summary") or MISSING_DATA_PLACEHOLDER),
    }
    legacy_sections = [
        (f"{index}. {title}", legacy_body_by_title.get(title, MISSING_DATA_PLACEHOLDER))
        for index, title in enumerate(HEALTH_REPORT_TEMPLATE_SECTIONS, start=1)
    ]
    return _build_canonical_report_markdown(
        [{"id": f"legacy-{index}", "title": title, "body": body} for index, (title, body) in enumerate(legacy_sections, start=1)]
    )


def _validate_upload(file: UploadFile, content: bytes) -> None:
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_IMAGE_TYPES or suffix not in ALLOWED_EXTENSIONS:
        raise MedicalRecordsServiceError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 JPG、PNG、WEBP 病例图片上传。",
        )
    if not content:
        raise MedicalRecordsServiceError(status_code=400, detail="上传文件不能为空。")
    if len(content) > settings.medical_records_max_upload_bytes:
        raise MedicalRecordsServiceError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件超过当前大小限制。",
        )


def _ensure_archive_owner(session: Session, user: User, archive_id: str) -> MedicalRecordArchive:
    archive = session.scalar(
        select(MedicalRecordArchive).where(
            MedicalRecordArchive.id == archive_id,
            MedicalRecordArchive.user_id == user.id,
        )
    )
    if not archive:
        raise HTTPException(status_code=404, detail="病历档案不存在。")
    return archive


def _ensure_report_owner(session: Session, user: User, report_id: str) -> LongitudinalReport:
    report = session.scalar(
        select(LongitudinalReport).where(
            LongitudinalReport.id == report_id,
            LongitudinalReport.user_id == user.id,
        )
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在。")
    return report


def _ensure_ai_health_report_owner(session: Session, user: User, report_id: str) -> LongitudinalReport:
    report = _ensure_report_owner(session, user, report_id)
    if report.title not in {AI_HEALTH_REPORT_TITLE, HEALTH_REPORT_TEMPLATE_TITLE} and report.template_name != HEALTH_REPORT_TEMPLATE_NAME:
        raise HTTPException(status_code=404, detail="AI 健康报告不存在。")
    return report


def _ensure_medical_record_consent(session: Session, user_id: str) -> ConsentSettings:
    consent = session.scalar(select(ConsentSettings).where(ConsentSettings.user_id == user_id))
    if not consent or not consent.cloud_sync_enabled or not consent.rag_analysis_enabled:
        raise MedicalRecordsServiceError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号未开启病历分析所需的数据同步与智能分析授权。",
        )
    return consent


def _latest_extraction(session: Session, file_id: str) -> MedicalRecordExtraction | None:
    return session.scalar(
        select(MedicalRecordExtraction)
        .where(MedicalRecordExtraction.file_id == file_id)
        .order_by(desc(MedicalRecordExtraction.version), desc(MedicalRecordExtraction.created_at))
    )


def _to_extraction_dto(extraction: MedicalRecordExtraction | None) -> MedicalRecordExtractionDTO | None:
    if extraction is None:
        return None
    return MedicalRecordExtractionDTO(
        id=extraction.id,
        version=extraction.version,
        status=extraction.status,
        error_summary=extraction.error_summary,
        document_type=extraction.document_type,
        summary_text=extraction.summary_text,
        raw_text=extraction.raw_text,
        structured_payload=extraction.structured_payload,
        source_model=extraction.source_model,
        prompt_version=extraction.prompt_version,
        completed_at=extraction.completed_at,
        updated_at=extraction.updated_at,
    )


def _to_file_dto(session: Session, medical_file: MedicalRecordFile) -> MedicalRecordFileDTO:
    extraction = _latest_extraction(session, medical_file.id)
    return MedicalRecordFileDTO(
        id=medical_file.id,
        archive_id=medical_file.archive_id,
        original_filename=medical_file.original_filename,
        content_type=medical_file.content_type,
        size_bytes=medical_file.size_bytes,
        processing_status=medical_file.processing_status,
        processing_error=medical_file.processing_error,
        created_at=medical_file.created_at,
        updated_at=medical_file.updated_at,
        processed_at=medical_file.processed_at,
        latest_extraction=_to_extraction_dto(extraction),
    )


def _to_archive_summary(session: Session, archive: MedicalRecordArchive) -> MedicalRecordArchiveSummaryDTO:
    file_count = session.scalar(
        select(func.count(MedicalRecordFile.id)).where(MedicalRecordFile.archive_id == archive.id)
    )
    report_count = session.scalar(
        select(func.count(LongitudinalReport.id)).where(LongitudinalReport.archive_id == archive.id)
    )
    latest_file_activity = session.scalar(
        select(func.max(MedicalRecordFile.updated_at)).where(MedicalRecordFile.archive_id == archive.id)
    )
    latest_report = session.scalar(
        select(LongitudinalReport)
        .where(LongitudinalReport.archive_id == archive.id)
        .order_by(desc(LongitudinalReport.version), desc(LongitudinalReport.created_at))
    )
    latest_activity_candidates = [archive.updated_at]
    if latest_file_activity is not None:
        latest_activity_candidates.append(latest_file_activity)
    if latest_report is not None:
        latest_activity_candidates.append(latest_report.updated_at)
    return MedicalRecordArchiveSummaryDTO(
        id=archive.id,
        title=archive.title,
        description=archive.description,
        created_at=archive.created_at,
        updated_at=archive.updated_at,
        file_count=int(file_count or 0),
        report_count=int(report_count or 0),
        latest_activity_at=max(latest_activity_candidates),
        latest_report=_to_report_summary(latest_report, archive.title) if latest_report else None,
    )


def _to_archive_detail(session: Session, archive: MedicalRecordArchive) -> MedicalRecordArchiveDetailDTO:
    files = list(
        session.scalars(
            select(MedicalRecordFile)
            .where(MedicalRecordFile.archive_id == archive.id)
            .order_by(desc(MedicalRecordFile.created_at))
        )
    )
    reports = list(
        session.scalars(
            select(LongitudinalReport)
            .where(LongitudinalReport.archive_id == archive.id)
            .order_by(desc(LongitudinalReport.version), desc(LongitudinalReport.created_at))
        )
    )
    summary = _to_archive_summary(session, archive)
    return MedicalRecordArchiveDetailDTO(
        **summary.model_dump(),
        disclaimer=DISCLAIMER_TEXT,
        consent_policy=archive.consent_policy,
        retention_policy=archive.retention_policy,
        delete_policy=archive.delete_policy,
        export_policy=archive.export_policy,
        files=[_to_file_dto(session, item) for item in files],
        reports=[_to_report_summary(item, archive.title) for item in reports],
    )


def _to_report_summary(
    report: LongitudinalReport,
    archive_title: str | None = None,
) -> MedicalRecordReportSummaryDTO:
    pipeline_state = _pipeline_state_dto(report)
    sections = _report_sections(report)
    return MedicalRecordReportSummaryDTO(
        id=report.id,
        agent_type="health_report_agent" if report.template_name == HEALTH_REPORT_TEMPLATE_NAME else "medical_record_report_agent",
        archive_id=report.archive_id,
        archive_title=archive_title,
        version=report.version,
        title=report.title,
        status=report.status,
        pdf_status=report.pdf_status,
        error_summary=report.error_summary,
        created_at=report.created_at,
        updated_at=report.updated_at,
        completed_at=report.completed_at,
        generated_at=report.completed_at,
        summary=(report.report_payload or {}).get("executive_summary")
        if isinstance(report.report_payload, dict)
        else None,
        pdf_ready=bool(report.pdf_path and report.pdf_status == "succeeded"),
        pdf_file_name=_report_download_filename(report)
        if report.pdf_path and report.pdf_status == "succeeded"
        else None,
        report_window_label=f"{report.report_window_start.isoformat()} 至 {report.report_window_end.isoformat()}",
        template_name=report.template_name or HEALTH_REPORT_TEMPLATE_NAME,
        template_version=report.template_version or HEALTH_REPORT_TEMPLATE_VERSION,
        pipeline_state=pipeline_state,
        quality_warnings=_build_quality_warnings(sections),
    )


def _report_sections(report: LongitudinalReport) -> list[dict[str, str]]:
    markdown = report.report_markdown or _render_report_markdown_from_payload(report.report_payload)
    if markdown:
        return _parse_report_markdown_sections(markdown)
    return []


def _to_report_detail(
    session: Session,
    report: LongitudinalReport,
    archive: MedicalRecordArchive,
) -> MedicalRecordReportDetailDTO:
    file_links = list(
        session.scalars(
            select(ReportInputLink).where(
                ReportInputLink.report_id == report.id,
                ReportInputLink.input_type == "file",
            )
        )
    )
    source_files = []
    for link in file_links:
        medical_file = session.scalar(select(MedicalRecordFile).where(MedicalRecordFile.id == link.input_id))
        if medical_file:
            source_files.append(_to_file_dto(session, medical_file))
    history = list(
        session.scalars(
            select(LongitudinalReport)
            .where(
                LongitudinalReport.archive_id == report.archive_id,
                LongitudinalReport.user_id == report.user_id,
            )
            .order_by(desc(LongitudinalReport.version), desc(LongitudinalReport.created_at))
        )
    )
    report_markdown = report.report_markdown or _render_report_markdown_from_payload(report.report_payload)
    sections = _report_sections(report)
    return MedicalRecordReportDetailDTO(
        **_to_report_summary(report, archive.title).model_dump(),
        archive_description=archive.description,
        disclaimer=DISCLAIMER_TEXT,
        disclaimer_version=report.disclaimer_version,
        model_name=report.model_name,
        prompt_version=report.prompt_version,
        report_window_start=report.report_window_start,
        report_window_end=report.report_window_end,
        monitoring_window_start=report.monitoring_window_start,
        monitoring_window_end=report.monitoring_window_end,
        medication_window_start=report.medication_window_start,
        medication_window_end=report.medication_window_end,
        input_snapshot=report.input_snapshot,
        report_payload=report.report_payload,
        report_markdown=report_markdown,
        narrative_text=report.narrative_text,
        has_pdf=bool(report.pdf_path and report.pdf_status == "succeeded"),
        sections=sections,
        source_files=source_files,
        history=[_to_report_summary(item, archive.title) for item in history],
    )


def list_archives(session: Session, user: User) -> list[MedicalRecordArchiveSummaryDTO]:
    rows = list(
        session.scalars(
            select(MedicalRecordArchive)
            .where(MedicalRecordArchive.user_id == user.id)
            .order_by(desc(MedicalRecordArchive.updated_at), desc(MedicalRecordArchive.created_at))
        )
    )
    return [_to_archive_summary(session, row) for row in rows]


def create_archive(
    session: Session,
    user: User,
    payload: CreateMedicalRecordArchiveRequest,
) -> MedicalRecordArchiveDetailDTO:
    _ensure_medical_record_consent(session, user.id)
    archive = MedicalRecordArchive(
        user_id=user.id,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
    )
    session.add(archive)
    session.flush()
    record_audit_log(
        session,
        user_id=user.id,
        endpoint="/v1/medical-records/archives",
        method="POST",
        action="create_medical_record_archive",
        request_summary=payload.model_dump(),
        response_summary={"archive_id": archive.id},
        risk_flag=True,
    )
    session.commit()
    session.refresh(archive)
    return _to_archive_detail(session, archive)


def get_archive_detail(session: Session, user: User, archive_id: str) -> MedicalRecordArchiveDetailDTO:
    archive = _ensure_archive_owner(session, user, archive_id)
    return _to_archive_detail(session, archive)


async def store_archive_file(
    session: Session,
    user: User,
    archive: MedicalRecordArchive,
    upload_file: UploadFile,
) -> MedicalRecordFileDTO:
    _ensure_medical_record_consent(session, user.id)
    content = await upload_file.read()
    _validate_upload(upload_file, content)

    suffix = Path(upload_file.filename or "record.jpg").suffix.lower()
    stored_name = f"{uuid4().hex}{suffix}"
    target_path = _archive_path(archive.id) / stored_name
    target_path.write_bytes(content)

    medical_file = MedicalRecordFile(
        archive_id=archive.id,
        user_id=user.id,
        original_filename=upload_file.filename or stored_name,
        stored_filename=stored_name,
        content_type=upload_file.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_path=str(target_path),
        processing_status="queued",
    )
    session.add(medical_file)
    session.flush()
    record_audit_log(
        session,
        user_id=user.id,
        endpoint=f"/v1/medical-records/archives/{archive.id}/files",
        method="POST",
        action="upload_medical_record_file",
        request_summary={"filename": medical_file.original_filename, "size_bytes": medical_file.size_bytes},
        response_summary={"file_id": medical_file.id, "status": medical_file.processing_status},
        risk_flag=True,
    )
    response_dto = _to_file_dto(session, medical_file)
    session.commit()
    return response_dto


def list_archive_files(session: Session, user: User, archive_id: str) -> list[MedicalRecordFileDTO]:
    _ensure_archive_owner(session, user, archive_id)
    rows = list(
        session.scalars(
            select(MedicalRecordFile)
            .where(
                MedicalRecordFile.archive_id == archive_id,
                MedicalRecordFile.user_id == user.id,
            )
            .order_by(desc(MedicalRecordFile.created_at))
        )
    )
    return [_to_file_dto(session, row) for row in rows]


def list_archive_reports(
    session: Session,
    user: User,
    archive_id: str,
) -> list[MedicalRecordReportSummaryDTO]:
    _ensure_archive_owner(session, user, archive_id)
    rows = list(
        session.scalars(
            select(LongitudinalReport)
            .where(
                LongitudinalReport.archive_id == archive_id,
                LongitudinalReport.user_id == user.id,
            )
            .order_by(desc(LongitudinalReport.version), desc(LongitudinalReport.created_at))
        )
    )
    archive = _ensure_archive_owner(session, user, archive_id)
    return [_to_report_summary(row, archive.title) for row in rows]


def list_ai_health_reports(session: Session, user: User) -> list[MedicalRecordReportSummaryDTO]:
    rows = list(
        session.scalars(
            select(LongitudinalReport)
            .where(
                LongitudinalReport.user_id == user.id,
                LongitudinalReport.title.in_([AI_HEALTH_REPORT_TITLE, HEALTH_REPORT_TEMPLATE_TITLE]),
            )
            .order_by(desc(LongitudinalReport.completed_at), desc(LongitudinalReport.created_at))
        )
    )
    archive_titles = {
        archive.id: archive.title
        for archive in session.scalars(
            select(MedicalRecordArchive).where(MedicalRecordArchive.user_id == user.id)
        )
    }
    return [_to_report_summary(row, archive_titles.get(row.archive_id)) for row in rows]


def get_report_detail(session: Session, user: User, report_id: str) -> MedicalRecordReportDetailDTO:
    report = _ensure_report_owner(session, user, report_id)
    archive = _ensure_archive_owner(session, user, report.archive_id)
    return _to_report_detail(session, report, archive)


def get_ai_health_report_detail(
    session: Session,
    user: User,
    report_id: str,
) -> MedicalRecordReportDetailDTO:
    report = _ensure_ai_health_report_owner(session, user, report_id)
    archive = _ensure_archive_owner(session, user, report.archive_id)
    return _to_report_detail(session, report, archive)


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "未知上游错误"

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
    return response.text or "未知上游错误"


def _post_dashscope(payload: dict[str, object]) -> dict:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise MedicalRecordsServiceError(status_code=503, detail="病历分析服务尚未配置 DASHSCOPE_API_KEY。")

    try:
        response = httpx.post(
            f"{settings.dashscope_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.dashscope_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.dashscope_timeout_seconds,
        )
    except httpx.RequestError as exc:
        raise MedicalRecordsServiceError(status_code=502, detail="病历分析服务连接失败。") from exc

    if response.status_code >= 400:
        raise MedicalRecordsServiceError(
            status_code=502,
            detail=f"病历分析服务调用失败：{_extract_error_message(response)}",
        )

    data = response.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise MedicalRecordsServiceError(status_code=502, detail="病历分析服务返回格式异常。")
    return data


def _parse_json_content(data: dict) -> dict:
    message = data["choices"][0].get("message", {})
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise MedicalRecordsServiceError(status_code=502, detail="病历分析服务返回了无法解析的 JSON。") from exc
    raise MedicalRecordsServiceError(status_code=502, detail="病历分析服务返回了空内容。")


def _extract_document_summary(file_path: Path, content_type: str) -> tuple[str, str, dict]:
    settings = get_settings()
    data_url = f"data:{content_type};base64,{base64.b64encode(file_path.read_bytes()).decode('ascii')}"
    payload = {
        "model": settings.dashscope_medical_extraction_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 TremorGuard 的病例信息抽取助手。"
                    "只做内容整理，不做诊断、分期、处方或药量建议。"
                    "请输出 JSON，字段包括 document_type, summary_text, raw_text, structured_payload。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {
                        "type": "text",
                        "text": (
                            "请提取图片中的病例关键信息，使用中文总结。"
                            "structured_payload 中至少包含 institution, visit_date, diagnoses_mentioned, "
                            "medications_mentioned, exams_mentioned, symptoms_mentioned, information_gaps。"
                        ),
                    },
                ],
            },
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 1200,
    }
    parsed = _parse_json_content(_post_dashscope(payload))
    document_type = str(parsed.get("document_type") or "未分类病例")
    summary_text = str(parsed.get("summary_text") or "未提取到稳定摘要。")
    raw_text = str(parsed.get("raw_text") or summary_text)
    structured_payload = parsed.get("structured_payload")
    if not isinstance(structured_payload, dict):
        structured_payload = {
            "institution": None,
            "visit_date": None,
            "diagnoses_mentioned": [],
            "medications_mentioned": [],
            "exams_mentioned": [],
            "symptoms_mentioned": [],
            "information_gaps": [],
        }
    return document_type, summary_text, {"raw_text": raw_text, "structured_payload": structured_payload}


def _window_start(end_date: date, window_days: int) -> date:
    return end_date - timedelta(days=window_days - 1)


def _date_bounds(target_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _date_range_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, time.min, tzinfo=UTC)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
    return start, end


def _build_longitudinal_context(
    session: Session,
    user: User,
    archive: MedicalRecordArchive,
    report: LongitudinalReport,
    extractions: Sequence[MedicalRecordExtraction],
) -> dict:
    profile = session.scalar(select(PatientProfile).where(PatientProfile.user_id == user.id))
    device_binding, snapshot = get_latest_device_status(session, user.id)
    device_status = format_device_status(device_binding, snapshot)

    monitoring_start_dt, monitoring_end_dt = _date_range_bounds(
        report.monitoring_window_start,
        report.monitoring_window_end,
    )
    medication_start_dt, medication_end_dt = _date_range_bounds(
        report.medication_window_start,
        report.medication_window_end,
    )

    monitoring_events = list(
        session.scalars(
            select(TremorEvent)
            .where(
                TremorEvent.user_id == user.id,
                TremorEvent.start_at >= monitoring_start_dt,
                TremorEvent.start_at < monitoring_end_dt,
            )
            .order_by(TremorEvent.start_at)
        )
    )
    medication_logs = list(
        session.scalars(
            select(MedicationLog)
            .where(
                MedicationLog.user_id == user.id,
                MedicationLog.taken_at >= medication_start_dt,
                MedicationLog.taken_at < medication_end_dt,
            )
            .order_by(MedicationLog.taken_at)
        )
    )

    durations = [event.duration_sec for event in monitoring_events]
    amplitudes = [event.rms_amplitude for event in monitoring_events]
    frequencies = [event.dominant_hz for event in monitoring_events]
    medications = [
        {"name": item.name, "dose": item.dose, "taken_at": item.taken_at.isoformat(), "status": item.status}
        for item in medication_logs
    ]
    extraction_snapshots = []
    information_gaps: list[str] = []
    for extraction in extractions:
        payload = extraction.structured_payload if isinstance(extraction.structured_payload, dict) else {}
        extraction_snapshots.append(
            {
                "file_id": extraction.file_id,
                "extraction_id": extraction.id,
                "extraction_version": extraction.version,
                "document_type": extraction.document_type,
                "summary_text": extraction.summary_text,
                "structured_payload": payload,
            }
        )
        gaps = payload.get("information_gaps")
        if isinstance(gaps, list):
            information_gaps.extend(str(item) for item in gaps if item)

    return {
        "archive_id": archive.id,
        "archive_title": archive.title,
        "report_window": {
            "start": report.report_window_start.isoformat(),
            "end": report.report_window_end.isoformat(),
        },
        "monitoring_window": {
            "start": report.monitoring_window_start.isoformat(),
            "end": report.monitoring_window_end.isoformat(),
        },
        "medication_window": {
            "start": report.medication_window_start.isoformat(),
            "end": report.medication_window_end.isoformat(),
        },
        "selected_document_versions": [
            {"file_id": extraction.file_id, "document_version": 1} for extraction in extractions
        ],
        "selected_extraction_versions": [
            {"extraction_id": extraction.id, "file_id": extraction.file_id, "version": extraction.version}
            for extraction in extractions
        ],
        "disclaimer_version": DISCLAIMER_VERSION,
        "prompt_version_snapshot": PROMPT_VERSION,
        "model_version_snapshot": get_settings().dashscope_medical_report_model,
        "patient_profile": {
            "name": profile.name if profile else user.display_name,
            "age": profile.age if profile else None,
            "gender": profile.gender if profile else None,
            "diagnosis": profile.diagnosis if profile else None,
            "duration": profile.duration if profile else None,
            "hospital": profile.hospital if profile else None,
        },
        "device_snapshot": (
            {
                "connection": device_status.connection,
                "connection_label": device_status.connection_label,
                "battery": device_status.battery,
                "firmware": device_status.firmware,
            }
            if device_status
            else None
        ),
        "monitoring_summary": {
            "event_count": len(monitoring_events),
            "avg_duration_sec": round(mean(durations), 1) if durations else 0,
            "max_duration_sec": max(durations, default=0),
            "avg_amplitude": round(mean(amplitudes), 3) if amplitudes else 0,
            "max_amplitude": round(max(amplitudes), 3) if amplitudes else 0,
            "avg_frequency_hz": round(mean(frequencies), 2) if frequencies else 0,
            "events": [
                {
                    "start_at": event.start_at.isoformat(),
                    "duration_sec": event.duration_sec,
                    "dominant_hz": event.dominant_hz,
                    "rms_amplitude": event.rms_amplitude,
                    "confidence": event.confidence,
                }
                for event in monitoring_events[-50:]
            ],
        },
        "medication_summary": {
            "count": len(medication_logs),
            "entries": medications,
        },
        "document_summaries": extraction_snapshots,
        "information_gaps": information_gaps,
    }


def _build_template_outline_text() -> str:
    return "\n".join(
        f"{index}. {title}" for index, title in enumerate(HEALTH_REPORT_TEMPLATE_SECTIONS, start=1)
    )


def _build_lightweight_report_markdown(context: dict) -> str:
    monitoring = context.get("monitoring_summary") or {}
    medication = context.get("medication_summary") or {}
    patient = context.get("display_patient_profile") or context.get("patient_profile") or {}
    document_summaries = context.get("document_summaries") or []
    information_gaps = list(context.get("information_gaps") or [])

    event_count = int(monitoring.get("event_count") or 0)
    avg_amplitude = monitoring.get("avg_amplitude") or 0
    max_amplitude = monitoring.get("max_amplitude") or 0
    medication_count = int(medication.get("count") or 0)
    patient_name = patient.get("name") or "当前用户"
    analytics_text = str(context.get("analytics_summary_text") or "")
    kpi_cards = context.get("kpi_cards") if isinstance(context.get("kpi_cards"), list) else []
    severity_rows = (
        context.get("tremor_severity_distribution")
        if isinstance(context.get("tremor_severity_distribution"), list)
        else []
    )
    time_rows = context.get("time_distribution") if isinstance(context.get("time_distribution"), list) else []
    adherence = context.get("medication_adherence") if isinstance(context.get("medication_adherence"), dict) else {}
    correlation = (
        context.get("medication_correlation_summary")
        if isinstance(context.get("medication_correlation_summary"), dict)
        else {}
    )
    baseline = context.get("baseline_summary") if isinstance(context.get("baseline_summary"), dict) else {}
    highlights = context.get("monitoring_highlights") if isinstance(context.get("monitoring_highlights"), list) else []
    clinical_notes = context.get("clinical_reference_notes") if isinstance(context.get("clinical_reference_notes"), list) else []
    completion_guidance = (
        context.get("data_completion_guidance") if isinstance(context.get("data_completion_guidance"), list) else []
    )
    followup_checklist = context.get("followup_checklist") if isinstance(context.get("followup_checklist"), list) else []
    self_questions = (
        context.get("self_assessment_questions")
        if isinstance(context.get("self_assessment_questions"), list)
        else []
    )
    knowledge_cards = context.get("knowledge_cards") if isinstance(context.get("knowledge_cards"), list) else []

    if not document_summaries:
        information_gaps.insert(0, "本次报告未纳入历史病历资料，仅基于监测与用药记录生成。")

    def bullet_lines(items: list[object]) -> str:
        return "\n".join(f"- {item}" for item in items if str(item).strip()) or f"- {MISSING_DATA_PLACEHOLDER}"

    def kpi_table() -> str:
        rows = ["| 指标 | 数值 | 说明 |", "| --- | ---: | --- |"]
        for item in kpi_cards:
            if isinstance(item, dict):
                rows.append(f"| {item.get('label', '')} | {item.get('value', '')} | {item.get('hint', '')} |")
        return "\n".join(rows)

    def distribution_table(rows_source: list[object], title: str) -> str:
        rows = [f"| {title} | 次数 | 占比 |", "| --- | ---: | ---: |"]
        for item in rows_source:
            if isinstance(item, dict):
                ratio = int(round(float(item.get("ratio") or 0) * 100))
                rows.append(f"| {item.get('label', '')} | {item.get('count', 0)} | {ratio}% |")
        return "\n".join(rows)

    def medication_table() -> str:
        rows = ["| 时间 | 药物 | 剂量 | 状态 |", "| --- | --- | --- | --- |"]
        for entry in medication.get("entries", [])[:8]:
            rows.append(
                f"| {str(entry.get('taken_at', ''))[:16]} | {entry.get('name', '')} | {entry.get('dose', '')} | {entry.get('status', '')} |"
            )
        return "\n".join(rows)

    def correlation_table() -> str:
        rows = ["| 服药时间 | 服药前均值 | 服药后1小时均值 | 服药后3小时均值 | 数据点 |", "| --- | ---: | ---: | ---: | --- |"]
        for window in correlation.get("windows", []) if isinstance(correlation.get("windows"), list) else []:
            if isinstance(window, dict):
                rows.append(
                    "| "
                    f"{window.get('taken_at', '')} | "
                    f"{window.get('before_avg') if window.get('before_avg') is not None else '不足'} | "
                    f"{window.get('after_1h_avg') if window.get('after_1h_avg') is not None else '不足'} | "
                    f"{window.get('after_3h_avg') if window.get('after_3h_avg') is not None else '不足'} | "
                    f"{window.get('before_count', 0)}/{window.get('after_1h_count', 0)}/{window.get('after_3h_count', 0)} |"
                )
        return "\n".join(rows)

    section_bodies = {
        "基本信息": (
            f"- 姓名：{patient_name}\n"
            f"- 年龄：{patient.get('age') or MISSING_DATA_PLACEHOLDER}\n"
            f"- 性别：{patient.get('gender') or MISSING_DATA_PLACEHOLDER}\n"
            f"- 当前诊断背景：{patient.get('diagnosis') or MISSING_DATA_PLACEHOLDER}"
        ),
        "评估目的": (
            "> 本报告用于辅助健康管理与复诊沟通，整理 TremorGuard 监测、用药与既往病历信息，不替代医生诊断、分期、处方或药量调整。\n\n"
            "报告重点围绕客观监测记录、用药执行记录和缺失资料清单展开，帮助患者在复诊前更有条理地准备沟通材料。"
        ),
        "本次监测亮点与异常提示": bullet_lines(highlights) + "\n\n" + kpi_table(),
        "主诉与现病史": (
            f"近期监测窗口内累计记录 {event_count} 次震颤事件，平均幅度 {avg_amplitude}，峰值 {max_amplitude}。"
            "从健康管理角度看，事件数量、幅度分布和发生时段可帮助复诊时回顾症状波动，但不能单独判断疾病进展或治疗效果。\n\n"
            f"{analytics_text}\n\n"
            + distribution_table(time_rows, "时段")
            + "\n\n"
            + distribution_table(severity_rows, "幅度等级")
        ),
        "既往史、家族史及生活方式": (
            "\n".join(
                f"- {item.get('summary_text') or MISSING_DATA_PLACEHOLDER}" for item in document_summaries[:3]
            )
            if document_summaries
            else (
                "本次报告未纳入历史病历资料，因此暂不能结合既往门诊记录、家族史或生活方式资料解释症状变化。"
                "建议后续补充既往病历、影像或化验资料、家族史、运动习惯、睡眠与饮食记录，以便复诊时进行更完整的背景梳理。"
            )
        ),
        "当前治疗与用药情况": (
            f"- 用药窗口内共记录 {medication_count} 条用药记录。\n"
            f"- {adherence.get('summary') or '当前用药执行记录仍需补充。'}\n"
            "- 多巴丝肼属于左旋多巴联合外周脱羧酶抑制剂类药物，常用于改善帕金森相关运动症状；本报告只做用药记录整理，不提供药量调整建议。\n"
            "- 当前记录显示 125mg 每日 3 次，总日记录剂量约 375mg。是否属于适合个体的剂量范围，应由医生结合年龄、病程、症状波动和不良反应综合评估。\n"
            "- 建议记录服药与进餐间隔、漏服或延迟服药情况，并观察恶心、头晕、体位性低血压、异动样动作、幻觉或意识混乱等需要复诊沟通的表现。\n\n"
            + medication_table()
            + "\n"
            + (
                "\n".join(
                    f"- {entry.get('taken_at', '')} {entry.get('name', '')} {entry.get('dose', '')}（{entry.get('status', '')}）"
                    for entry in medication.get("entries", [])[:6]
                )
                if medication.get("entries")
                else f"- {MISSING_DATA_PLACEHOLDER}"
            )
        ),
        "用药-症状关联分析": (
            f"{correlation.get('summary') or '当前缺少可匹配的服药和震颤时间戳，暂不能形成用药前后观察。'}\n\n"
            f"> {correlation.get('wearing_off_signal') or '当前未形成稳定的数据线索。'}\n\n"
            + correlation_table()
        ),
        "运动症状评估": (
            f"- 监测窗口内累计记录 {event_count} 次震颤事件。\n"
            f"- 平均幅度：{avg_amplitude}。\n"
            f"- 峰值幅度：{max_amplitude}。\n"
            f"- {baseline.get('summary') or '当前缺少可用历史基线，暂不能进行稳定对比。'}\n\n"
            "TremorGuard 记录的是可穿戴设备捕捉到的震颤相关信号，可用于观察频率、幅度和时段变化。"
            "目前数据不足以区分静止性、姿势性或动作性震颤，也不能替代 UPDRS-III 中强直、运动迟缓、步态和平衡等项目的面诊评估。"
        ),
        "非运动症状评估": (
            "当前未采集睡眠、嗅觉、便秘、疼痛、焦虑抑郁、认知和自主神经相关问卷，因此不能评价非运动症状负担。"
            "建议复诊前补充非运动症状清单，并记录是否存在睡眠行为异常、起身头晕、情绪低落、幻觉或记忆注意力变化。"
        ),
        "日常生活能力评估": (
            "当前未采集穿衣、进食、翻身、行走、上下楼梯、精细动作和跌倒风险等日常生活能力资料。"
            "建议患者或家属用一周时间记录需要协助的生活环节、近跌倒事件和外出活动受限情况。"
        ),
        "体格检查": (
            "当前报告未纳入医生查体结果，因此不能评价肌张力、运动迟缓、姿势反射或步态平衡。"
            "建议复诊时请医生结合体格检查和标准量表，与 TremorGuard 监测数据一起解读。"
        ),
        "辅助检查结果": (
            "\n".join(
                f"- {item.get('document_type') or '病例摘要'}：{item.get('summary_text') or MISSING_DATA_PLACEHOLDER}"
                for item in document_summaries[:3]
            )
            if document_summaries
            else "当前未纳入影像、化验、量表或门诊原文。建议补充既往检查资料，特别是与症状变化、用药调整讨论、认知和自主神经症状相关的记录。"
        ),
        "量表评分与疾病分期": (
            "当前未采集 MDS-UPDRS、Hoehn-Yahr、MoCA/MMSE 或日常生活能力量表，本系统不提供疾病分期结论。"
            "建议由专业人员在复诊或康复评估时完成标准化量表，以便与穿戴监测数据互相印证。"
        ),
        "主要健康问题总结": (
            f"{patient_name} 当前报告显示近期症状波动主要依据 TremorGuard 监测与用药记录整理。"
            f"本窗口记录 {event_count} 次震颤事件、{medication_count} 条用药记录，适合在复诊时围绕症状发生时段、服药后变化、重度幅度事件和资料缺口进行沟通。"
        ),
        "综合分析": (
            "综合现有数据，报告可支持对震颤频率、幅度分布、用药执行和时间相关线索的健康管理观察。"
            "由于缺少线下查体、标准量表、非运动症状问卷和完整既往病历，当前分析应定位为复诊准备材料，而不是独立医学结论。"
        ),
        "干预建议": (
            "- 症状监测：记录震颤起止时间、诱因、伴随症状、严重度自评、服药和进餐时间。\n"
            "- 用药管理：使用提醒工具记录按时服药；如漏服或延迟服药，记录时间和症状变化，并在复诊时询问处理原则。\n"
            "- 生活方式：结合医生建议开展步态、平衡、柔韧和大幅度动作训练；可讨论太极、LSVT BIG 等康复训练是否适合。\n"
            "- 饮食与睡眠：关注蛋白摄入与服药吸收的时间关系，但饮食结构调整需先咨询医生或营养师。\n"
            "- 安全防护：评估浴室、床边、夜间照明、防滑垫和扶手等居家跌倒风险。"
        ),
        "复诊准备清单": bullet_lines(followup_checklist),
        "症状自评问卷": bullet_lines(self_questions),
        "知识科普卡片": (
            "\n".join(
                f"### {item.get('title')}\n{item.get('body')}"
                for item in knowledge_cards
                if isinstance(item, dict)
            )
            or MISSING_DATA_PLACEHOLDER
        ),
        "随访计划": (
            "建议下次复诊时携带本报告与相关病历资料，由专业医生综合评估。"
            "在复诊前继续记录至少 7 天症状-用药-进餐-睡眠时间线，以便判断现有观察是否稳定。"
        ),
        "结论": (
            "本报告用于辅助健康管理与复诊沟通，不替代医生诊断、分期或治疗决策。"
            "当前最有价值的信息是震颤事件分布、幅度分层、用药执行记录和需要补充的评估项目；后续应结合医生面诊、查体和量表综合解释。"
        ),
    }
    if information_gaps:
        section_bodies["辅助检查结果"] += "\n\n待补充信息：\n" + "\n".join(f"- {item}" for item in information_gaps)
    if completion_guidance:
        section_bodies["辅助检查结果"] += "\n\n建议补充资料：\n" + bullet_lines(completion_guidance)
    if clinical_notes:
        section_bodies["知识科普卡片"] += "\n\n参考性健康管理提示：\n" + bullet_lines(clinical_notes)

    sections = [
        {"id": f"template-section-{index}", "title": f"{index}. {title}", "body": section_bodies.get(title, MISSING_DATA_PLACEHOLDER)}
        for index, title in enumerate(HEALTH_REPORT_TEMPLATE_SECTIONS, start=1)
    ]
    return _build_canonical_report_markdown(sections)


def _has_meaningful_patient_name(patient: dict) -> bool:
    name = str(patient.get("name") or "").strip()
    return bool(name and name != "当前用户" and name != MISSING_DATA_PLACEHOLDER)


def _report_markdown_consistency_errors(markdown: str, context: dict) -> list[str]:
    patient = context.get("patient_profile") if isinstance(context.get("patient_profile"), dict) else {}
    display_patient = (
        context.get("display_patient_profile") if isinstance(context.get("display_patient_profile"), dict) else {}
    )
    monitoring = context.get("monitoring_summary") if isinstance(context.get("monitoring_summary"), dict) else {}
    medication = context.get("medication_summary") if isinstance(context.get("medication_summary"), dict) else {}
    errors: list[str] = []

    patient_name = str(patient.get("name") or "").strip()
    display_name = str(display_patient.get("name") or "").strip()
    acceptable_names = [name for name in (patient_name, display_name) if name]
    if _has_meaningful_patient_name(patient) and not any(name in markdown for name in acceptable_names):
        errors.append(f"missing patient name {patient_name}")
    if _has_meaningful_patient_name(patient) and "姓名：当前用户" in markdown:
        errors.append("uses placeholder patient name")
    report_metadata = context.get("report_metadata") if isinstance(context.get("report_metadata"), dict) else {}
    if (
        report_metadata.get("mask_identifiers")
        and _has_meaningful_patient_name(patient)
        and display_name
        and display_name != patient_name
        and patient_name in markdown
    ):
        errors.append("contains unmasked patient name despite masking configuration")

    event_count = int(monitoring.get("event_count") or 0)
    if event_count > 0 and ("0 次震颤事件" in markdown or "累计记录 0 次" in markdown):
        errors.append("uses zero tremor count despite available monitoring data")
    if event_count > 0 and str(event_count) not in markdown:
        errors.append(f"missing tremor event count {event_count}")

    medication_count = int(medication.get("count") or 0)
    if medication_count > 0 and ("0 条用药记录" in markdown or "共记录 0 条" in markdown):
        errors.append("uses zero medication count despite available medication data")
    if medication_count > 0 and str(medication_count) not in markdown:
        errors.append(f"missing medication count {medication_count}")

    return errors


def _report_markdown_richness_errors(markdown: str, context: dict) -> list[str]:
    monitoring = context.get("monitoring_summary") if isinstance(context.get("monitoring_summary"), dict) else {}
    medication = context.get("medication_summary") if isinstance(context.get("medication_summary"), dict) else {}
    errors: list[str] = []
    required_sections = (
        "本次监测亮点与异常提示",
        "用药-症状关联分析",
        "复诊准备清单",
        "症状自评问卷",
        "知识科普卡片",
    )
    for section in required_sections:
        if section not in markdown:
            errors.append(f"missing enhanced section {section}")
    if int(monitoring.get("event_count") or 0) > 0 and "|" not in markdown:
        errors.append("missing structured table for available monitoring data")
    if int(medication.get("count") or 0) > 0 and "依从" not in markdown:
        errors.append("missing medication adherence interpretation")
    return errors


def _assert_non_diagnostic(text: str) -> None:
    for phrase in BANNED_PHRASES:
        if phrase in text:
            raise MedicalRecordsServiceError(
                status_code=502,
                detail=f"报告内容触发非诊断边界校验：包含“{phrase}”。",
            )


def _assert_markdown_non_diagnostic(markdown: str) -> None:
    for line in markdown.splitlines():
        stripped = _strip_markdown_text(line.strip())
        if stripped:
            if line.lstrip().startswith("#") or re.match(r"^\d+[\.\u3001、\s]+", stripped):
                continue
            if any(marker in stripped for marker in ("不提供", "不替代", "不做", "不得", "仅供")):
                continue
            _assert_non_diagnostic(stripped)


def _parse_text_content(data: dict) -> str:
    message = data["choices"][0].get("message", {})
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        normalized = content.strip()
        if normalized.startswith("```"):
            normalized = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", normalized)
            normalized = re.sub(r"\n?```$", "", normalized).strip()
        return normalized
    raise MedicalRecordsServiceError(status_code=502, detail="病历分析服务返回了空内容。")


def _normalize_report_markdown(markdown: str) -> tuple[str, list[dict[str, str]]]:
    _assert_markdown_non_diagnostic(markdown)
    sections = _parse_report_markdown_sections(markdown)
    canonical_markdown = _build_canonical_report_markdown(sections)
    _assert_markdown_non_diagnostic(canonical_markdown)
    return canonical_markdown, sections


def _generate_report_markdown(context: dict) -> str:
    settings = get_settings()
    payload = {
        "model": settings.dashscope_medical_report_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 TremorGuard 的纵向健康报告整理助手。"
                    "只允许输出健康管理与复诊沟通材料，不得做诊断、分期、处方、药量调整或代替医生判断。"
                    "请严格输出 Markdown 文档，不要返回 JSON，不要添加模板外章节。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"请严格按照以下固定模板输出 Markdown 文档，标题必须是《{HEALTH_REPORT_TEMPLATE_TITLE}》，"
                    "章节顺序不可更改，所有章节都必须保留；若缺少数据，请在章节中明确写“数据不足/待补充”。\n\n"
                    "固定章节：\n"
                    f"{_build_template_outline_text()}\n\n"
                    "上下文如下：\n"
                    f"{json.dumps(context, ensure_ascii=False)}"
                ),
            },
        ],
        "temperature": 0.2,
        "max_tokens": 3200,
    }
    rendered = _parse_text_content(_post_dashscope(payload))
    if rendered.startswith("{"):
        try:
            legacy_payload = json.loads(rendered)
        except json.JSONDecodeError:
            return rendered
        normalized_markdown = _render_report_markdown_from_payload(legacy_payload)
        if normalized_markdown:
            return normalized_markdown
    return rendered


def process_pending_file(session: Session, user: User, file_id: str) -> None:
    medical_file = session.scalar(select(MedicalRecordFile).where(MedicalRecordFile.id == file_id))
    if medical_file is None or medical_file.processing_status != "queued":
        return

    extraction = MedicalRecordExtraction(
        archive_id=medical_file.archive_id,
        file_id=medical_file.id,
        user_id=medical_file.user_id,
        version=1,
        status="processing",
        prompt_version=PROMPT_VERSION,
    )
    medical_file.processing_status = "processing"
    medical_file.processing_error = None
    session.add(extraction)
    session.commit()

    try:
        file_path = Path(medical_file.storage_path)
        document_type, summary_text, payload = _extract_document_summary(file_path, medical_file.content_type)
        extraction.document_type = document_type
        extraction.summary_text = summary_text
        extraction.raw_text = payload["raw_text"]
        extraction.structured_payload = payload["structured_payload"]
        extraction.source_model = get_settings().dashscope_medical_extraction_model
        extraction.status = "succeeded"
        extraction.completed_at = _utcnow()
        medical_file.processing_status = "succeeded"
        medical_file.processed_at = _utcnow()
        record_audit_log(
            session,
            user_id=user.id,
            endpoint=f"/v1/medical-records/archives/{medical_file.archive_id}/files",
            method="POST",
            action="medical_record_extraction_succeeded",
            request_summary={"file_id": medical_file.id},
            response_summary={"extraction_id": extraction.id},
            risk_flag=True,
        )
    except Exception as exc:  # noqa: BLE001
        extraction.status = "failed"
        extraction.error_summary = str(exc)
        medical_file.processing_status = "failed"
        medical_file.processing_error = str(exc)
        record_audit_log(
            session,
            user_id=user.id,
            endpoint=f"/v1/medical-records/archives/{medical_file.archive_id}/files",
            method="POST",
            action="medical_record_extraction_failed",
            request_summary={"file_id": medical_file.id},
            response_summary={"error": str(exc)},
            risk_flag=True,
        )
    finally:
        session.commit()


def create_report(
    session: Session,
    user: User,
    archive: MedicalRecordArchive,
    payload: CreateMedicalRecordReportRequest,
    idempotency_key: str | None = None,
) -> MedicalRecordReportSummaryDTO:
    _ensure_medical_record_consent(session, user.id)
    if idempotency_key:
        existing_audit = session.scalar(
            select(ApiAuditLog).where(
                ApiAuditLog.endpoint == f"/v1/medical-records/archives/{archive.id}/reports",
                ApiAuditLog.idempotency_key == idempotency_key,
            )
        )
        if existing_audit and existing_audit.response_summary:
            existing_report_id = existing_audit.response_summary.get("report_id")
            if isinstance(existing_report_id, str):
                existing_report = _ensure_report_owner(session, user, existing_report_id)
                return _to_report_summary(existing_report, archive.title)

    today = _utcnow().date()
    next_version = int(
        session.scalar(
            select(func.coalesce(func.max(LongitudinalReport.version), 0)).where(
                LongitudinalReport.archive_id == archive.id
            )
        )
        or 0
    ) + 1
    report = LongitudinalReport(
        archive_id=archive.id,
        user_id=user.id,
        version=next_version,
        title=HEALTH_REPORT_TEMPLATE_TITLE,
        status="queued",
        pdf_status="queued",
        report_window_start=_window_start(today, payload.report_window_days),
        report_window_end=today,
        monitoring_window_start=_window_start(today, payload.monitoring_window_days),
        monitoring_window_end=today,
        medication_window_start=_window_start(today, payload.medication_window_days),
        medication_window_end=today,
        disclaimer_version=DISCLAIMER_VERSION,
        template_name=HEALTH_REPORT_TEMPLATE_NAME,
        template_version=HEALTH_REPORT_TEMPLATE_VERSION,
        prompt_version=PROMPT_VERSION,
        pipeline_state=_initial_pipeline_state(),
    )
    session.add(report)
    session.flush()
    response_dto = _to_report_summary(report, archive.title)
    record_audit_log(
        session,
        user_id=user.id,
        endpoint=f"/v1/medical-records/archives/{archive.id}/reports",
        method="POST",
        action="create_longitudinal_report",
        idempotency_key=idempotency_key,
        request_summary=payload.model_dump(),
        response_summary={"report_id": report.id, "status": report.status},
        risk_flag=True,
    )
    session.commit()
    return response_dto


def process_pending_report(session: Session, user: User, report_id: str) -> None:
    report = session.scalar(select(LongitudinalReport).where(LongitudinalReport.id == report_id))
    if report is None or report.status != "queued":
        return

    archive = session.scalar(select(MedicalRecordArchive).where(MedicalRecordArchive.id == report.archive_id))
    if archive is None:
        return

    report.status = "processing"
    report.pdf_status = "queued"
    report.error_summary = None
    report.template_name = report.template_name or HEALTH_REPORT_TEMPLATE_NAME
    report.template_version = report.template_version or HEALTH_REPORT_TEMPLATE_VERSION
    if report.title != HEALTH_REPORT_TEMPLATE_TITLE:
        report.title = HEALTH_REPORT_TEMPLATE_TITLE
    _set_pipeline_stage(report, "router", "succeeded", detail="请求已切换到专用报告生成 Agent。")
    _set_pipeline_stage(report, "context_assembly", "processing", detail="正在装配数据库中的患者与监测上下文。")
    _set_pipeline_stage(report, "template", "processing", detail="正在注入固定模板上下文。")
    _set_pipeline_stage(report, "llm", "queued", detail="等待模板注入完成。")
    _set_pipeline_stage(report, "pdf", "queued", detail="等待 Markdown 文档生成完成。")
    session.commit()

    try:
        extractions = list(
            session.scalars(
                select(MedicalRecordExtraction)
                .where(
                    MedicalRecordExtraction.archive_id == archive.id,
                    MedicalRecordExtraction.user_id == user.id,
                    MedicalRecordExtraction.status == "succeeded",
                )
                .order_by(MedicalRecordExtraction.created_at)
            )
        )
        trigger_message = None
        if isinstance(report.pipeline_state, dict):
            request_context = report.pipeline_state.get("request_context")
            if isinstance(request_context, dict):
                trigger_message = request_context.get("trigger_message")
                if not isinstance(trigger_message, str):
                    trigger_message = None
        context = REPORT_CONTEXT_ASSEMBLER.assemble(
            session,
            user,
            report,
            trigger_message=trigger_message,
        )
        settings = get_settings()
        context = enrich_health_report_context(
            context,
            user_id=user.id,
            report_id=report.id,
            generated_at=_utcnow(),
            timezone_name=settings.health_report_timezone,
            mask_identifiers=settings.health_report_mask_identifiers,
        )
        report.input_snapshot = context
        _set_pipeline_stage(report, "context_assembly", "succeeded", detail="数据库上下文装配完成。")
        _set_pipeline_stage(report, "template", "succeeded", detail="已将《帕金森患者健康分析报告》模板注入模型上下文。")
        _set_pipeline_stage(report, "report_agent_llm", "processing", detail="专用报告生成 Agent 正在生成 Markdown。")
        _set_pipeline_stage(report, "llm", "processing", detail="正在生成 Markdown 健康报告。")
        session.commit()

        used_fallback = False
        fallback_reason = None
        if settings.dashscope_api_key:
            try:
                agent_result = HEALTH_REPORT_AGENT.generate(context=context)
                consistency_errors = _report_markdown_consistency_errors(agent_result.markdown, context)
                consistency_errors.extend(_report_markdown_richness_errors(agent_result.markdown, context))
                if consistency_errors:
                    used_fallback = True
                    fallback_reason = "AI output failed data-consistency check: " + "; ".join(
                        consistency_errors
                    )
                else:
                    raw_markdown = agent_result.markdown
                    report.model_name = agent_result.model_name
            except Exception as agent_exc:  # noqa: BLE001
                used_fallback = True
                fallback_reason = f"AI report agent failed: {agent_exc}"
        else:
            used_fallback = True
            fallback_reason = "DASHSCOPE_API_KEY 未配置，使用确定性模板生成报告。"

        if used_fallback:
            raw_markdown = _build_lightweight_report_markdown(context)
            report.model_name = "tremorguard-lightweight-template"
            _set_pipeline_stage(
                report,
                "report_agent_llm",
                "failed",
                detail=fallback_reason,
                error=fallback_reason,
            )
            _set_pipeline_stage(
                report,
                "llm",
                "processing",
                detail="已切换到确定性模板生成 Markdown 健康报告。",
            )
        else:
            _set_pipeline_stage(report, "report_agent_llm", "succeeded", detail="专用报告生成 Agent 已返回 Markdown 文档。")
        _set_pipeline_stage(report, "markdown_validation", "processing", detail="正在校验报告结构与内容质量。")

        canonical_markdown, sections = _normalize_report_markdown(raw_markdown)
        fallback_consistency_errors = _report_markdown_consistency_errors(canonical_markdown, context)
        if fallback_consistency_errors:
            raise MedicalRecordsServiceError(
                status_code=502,
                detail="报告内容与输入数据不一致：" + "; ".join(fallback_consistency_errors),
            )
        report.report_markdown = canonical_markdown
        report.report_payload = _build_report_payload_from_sections(sections, context)
        if report.template_name == HEALTH_REPORT_TEMPLATE_NAME and not context.get("document_summaries"):
            report.report_payload["historical_record_summary"] = [
                "本次报告未纳入历史病历资料，仅基于监测与用药记录生成。"
            ]
        report.narrative_text = canonical_markdown
        report.status = "succeeded"
        report.completed_at = _utcnow()
        _set_pipeline_stage(report, "markdown_validation", "succeeded", detail="Markdown 结构校验完成。")
        _set_pipeline_stage(report, "llm", "succeeded", detail="Markdown 报告已生成，可在线查看。")

        session.execute(delete(ReportInputLink).where(ReportInputLink.report_id == report.id))
        for extraction in extractions:
            session.add(
                ReportInputLink(
                    report_id=report.id,
                    archive_id=archive.id,
                    input_type="file",
                    input_id=extraction.file_id,
                    input_version=1,
                )
            )
            session.add(
                ReportInputLink(
                    report_id=report.id,
                    archive_id=archive.id,
                    input_type="extraction",
                    input_id=extraction.id,
                    input_version=extraction.version,
                )
            )

        report.pdf_status = "processing"
        _set_pipeline_stage(report, "pdf_render", "processing", detail="正在使用内置 PDF 适配器渲染文档。")
        _set_pipeline_stage(report, "pdf", "processing", detail="正在将 Markdown 报告转换为 PDF。")
        session.commit()

        pdf_path = _reports_path(archive.id) / f"{report.id}.pdf"
        try:
            pdf_path.write_bytes(
                MARKDOWN_PDF_RENDERER.render(
                    report.title,
                    canonical_markdown,
                    metadata={
                        "report_id": report.id,
                        "template_name": report.template_name,
                        "template_version": report.template_version,
                        "created_at": report.completed_at.isoformat() if report.completed_at else None,
                        "context": context,
                        "sections": sections,
                        "report_payload": report.report_payload,
                        "mask_identifiers": settings.health_report_mask_identifiers,
                    },
                )
            )
            report.pdf_status = "succeeded"
            report.pdf_path = str(pdf_path)
            _set_pipeline_stage(report, "pdf_render", "succeeded", detail="PDF 适配器渲染完成。")
            _set_pipeline_stage(report, "pdf", "succeeded", detail="PDF 已生成，可下载。")
        except Exception as pdf_exc:  # noqa: BLE001
            report.pdf_status = "failed"
            report.pdf_path = None
            _set_pipeline_stage(
                report,
                "pdf_render",
                "failed",
                detail="PDF 渲染失败。",
                error=str(pdf_exc),
            )
            _set_pipeline_stage(
                report,
                "pdf",
                "failed",
                detail="Markdown 已生成，但 PDF 转换失败。",
                error=str(pdf_exc),
            )
        record_audit_log(
            session,
            user_id=user.id,
            endpoint=f"/v1/medical-records/reports/{report.id}",
            method="POST",
            action="longitudinal_report_succeeded",
            request_summary={"archive_id": archive.id},
            response_summary={"report_id": report.id, "version": report.version, "pdf_status": report.pdf_status},
            risk_flag=True,
        )
    except Exception as exc:  # noqa: BLE001
        report.status = "failed"
        report.pdf_status = "failed"
        report.error_summary = str(exc)
        _set_pipeline_stage(report, "context_assembly", "failed", detail="上下文装配或后续流程失败。", error=str(exc))
        _set_pipeline_stage(report, "report_agent_llm", "failed", detail="专用报告生成 Agent 未完成生成。", error=str(exc))
        _set_pipeline_stage(report, "markdown_validation", "failed", detail="Markdown 校验未完成。", error=str(exc))
        _set_pipeline_stage(report, "pdf_render", "failed", detail="PDF 渲染未执行。", error=str(exc))
        _set_pipeline_stage(report, "llm", "failed", detail="Markdown 文档生成失败。", error=str(exc))
        _set_pipeline_stage(report, "pdf", "failed", detail="上游生成失败，未执行 PDF 转换。", error=str(exc))
        record_audit_log(
            session,
            user_id=user.id,
            endpoint=f"/v1/medical-records/reports/{report.id}",
            method="POST",
            action="longitudinal_report_failed",
            request_summary={"archive_id": archive.id},
            response_summary={"error": str(exc)},
            risk_flag=True,
        )
    finally:
        session.commit()


def _select_archive_for_ai_health_report(session: Session, user: User) -> MedicalRecordArchive | None:
    archives = list(
        session.scalars(
            select(MedicalRecordArchive)
            .where(MedicalRecordArchive.user_id == user.id)
            .order_by(desc(MedicalRecordArchive.updated_at), desc(MedicalRecordArchive.created_at))
        )
    )
    if not archives:
        return None

    for archive in archives:
        has_extraction = session.scalar(
            select(MedicalRecordExtraction.id)
            .where(
                MedicalRecordExtraction.archive_id == archive.id,
                MedicalRecordExtraction.user_id == user.id,
                MedicalRecordExtraction.status == "succeeded",
            )
            .limit(1)
        )
        if has_extraction is not None:
            return archive
    return archives[0]


def _ensure_ai_health_archive(session: Session, user: User) -> MedicalRecordArchive:
    archive = _select_archive_for_ai_health_report(session, user)
    if archive is not None:
        return archive

    _ensure_medical_record_consent(session, user.id)
    archive = MedicalRecordArchive(
        user_id=user.id,
        title=AI_HEALTH_ARCHIVE_TITLE,
        description="由 AI 医生聊天流自动创建，用于保存统一的 AI 健康报告。",
    )
    session.add(archive)
    session.flush()
    return archive


def create_ai_health_report_for_chat(
    session: Session,
    user: User,
    *,
    report_window_days: int = 30,
    monitoring_window_days: int = 30,
    medication_window_days: int = 30,
    trigger_message: str | None = None,
    route_reason: str | None = None,
) -> MedicalRecordReportDetailDTO:
    _ensure_medical_record_consent(session, user.id)
    archive = _ensure_ai_health_archive(session, user)
    today = _utcnow().date()
    next_version = int(
        session.scalar(
            select(func.coalesce(func.max(LongitudinalReport.version), 0)).where(
                LongitudinalReport.archive_id == archive.id
            )
        )
        or 0
    ) + 1
    report = LongitudinalReport(
        archive_id=archive.id,
        user_id=user.id,
        version=next_version,
        title=AI_HEALTH_REPORT_TITLE,
        status="queued",
        pdf_status="queued",
        report_window_start=_window_start(today, report_window_days),
        report_window_end=today,
        monitoring_window_start=_window_start(today, monitoring_window_days),
        monitoring_window_end=today,
        medication_window_start=_window_start(today, medication_window_days),
        medication_window_end=today,
        disclaimer_version=DISCLAIMER_VERSION,
        template_name=HEALTH_REPORT_TEMPLATE_NAME,
        template_version=HEALTH_REPORT_TEMPLATE_VERSION,
        prompt_version=PROMPT_VERSION,
        pipeline_state=_initial_pipeline_state(),
    )
    if isinstance(report.pipeline_state, dict):
        report.pipeline_state["router"] = _build_pipeline_stage(
            "succeeded",
            detail="已从通用 AI 医生 Agent 切换到专用报告生成 Agent。",
        )
        report.pipeline_state["request_context"] = {
            "trigger_message": trigger_message,
            "route_reason": route_reason,
        }
    session.add(report)
    session.flush()
    record_audit_log(
        session,
        user_id=user.id,
        endpoint="/v1/ai/actions/health-report/generate",
        method="POST",
        action="create_ai_health_report",
        request_summary={
            "archive_id": archive.id,
            "report_window_days": report_window_days,
            "monitoring_window_days": monitoring_window_days,
            "medication_window_days": medication_window_days,
            "trigger_message": trigger_message,
            "route_reason": route_reason,
        },
        response_summary={"report_id": report.id, "archive_id": archive.id, "version": report.version},
        risk_flag=True,
    )
    session.commit()
    return get_report_detail(session, user, report.id)


def run_file_processing_task(user_id: str, file_id: str) -> None:
    with ClinicalSessionLocal() as session:
        process_pending_file(session, SimpleNamespace(id=user_id), file_id)


def run_report_processing_task(user_id: str, user_display_name: str, report_id: str) -> None:
    with ClinicalSessionLocal() as session:
        process_pending_report(
            session,
            SimpleNamespace(id=user_id, display_name=user_display_name),
            report_id,
        )


def preview_medical_record_file(session: Session, user: User, archive_id: str, file_id: str) -> FileResponse:
    _ensure_archive_owner(session, user, archive_id)
    medical_file = session.scalar(
        select(MedicalRecordFile).where(
            MedicalRecordFile.id == file_id,
            MedicalRecordFile.archive_id == archive_id,
            MedicalRecordFile.user_id == user.id,
        )
    )
    if medical_file is None:
        raise HTTPException(status_code=404, detail="病例文件不存在。")
    return FileResponse(
        medical_file.storage_path,
        media_type=medical_file.content_type,
        filename=medical_file.original_filename,
    )


def download_report_pdf(session: Session, user: User, report_id: str) -> FileResponse | StreamingResponse:
    report = _ensure_report_owner(session, user, report_id)
    download_name = _report_download_filename(report)
    disposition_headers = _content_disposition_headers(download_name)
    record_audit_log(
        session,
        user_id=user.id,
        endpoint=f"/v1/medical-records/reports/{report.id}/pdf",
        method="GET",
        action="download_medical_record_report_pdf",
        request_summary={"report_id": report.id},
        response_summary={"pdf_path": report.pdf_path, "pdf_status": report.pdf_status},
        risk_flag=True,
    )
    session.commit()
    if report.pdf_path and Path(report.pdf_path).exists():
        return FileResponse(
            report.pdf_path,
            media_type="application/pdf",
            filename=_ascii_filename_fallback(download_name),
            headers=disposition_headers,
        )

    markdown = report.report_markdown or _render_report_markdown_from_payload(report.report_payload)
    if not markdown:
        raise HTTPException(status_code=404, detail="报告 PDF 尚未生成。")
    pdf_bytes = MARKDOWN_PDF_RENDERER.render(
        report.title,
        markdown,
        metadata={
            "report_id": report.id,
            "template_name": report.template_name,
            "template_version": report.template_version,
            "created_at": report.completed_at.isoformat() if report.completed_at else None,
            "context": report.input_snapshot,
            "sections": _report_sections(report),
            "report_payload": report.report_payload,
            "mask_identifiers": bool(
                ((report.input_snapshot or {}).get("report_metadata") or {}).get(
                    "mask_identifiers", get_settings().health_report_mask_identifiers
                )
                if isinstance(report.input_snapshot, dict)
                else get_settings().health_report_mask_identifiers
            ),
        },
    )
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=disposition_headers,
    )
