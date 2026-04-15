from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
from statistics import mean
from types import SimpleNamespace
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
    MedicalRecordReportSummaryDTO,
)
from app.services.audit import record_audit_log
from app.services.dashboard import format_device_status, get_latest_device_status

DISCLAIMER_TEXT = "本报告仅供健康管理与复诊沟通参考，不能替代医生诊断、分期、处方或药量调整。"
DISCLAIMER_VERSION = "non-diagnostic-v1"
PROMPT_VERSION = "medical-records-v1"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
BANNED_PHRASES = ("确诊", "诊断为", "分期", "处方", "药量调整", "排除")


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


def _archive_path(archive_id: str) -> Path:
    path = _storage_root() / archive_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _reports_path(archive_id: str) -> Path:
    path = _archive_path(archive_id) / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    return MedicalRecordReportSummaryDTO(
        id=report.id,
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
        pdf_file_name=f"{report.id}.pdf" if report.pdf_path and report.pdf_status == "succeeded" else None,
        report_window_label=f"{report.report_window_start.isoformat()} 至 {report.report_window_end.isoformat()}",
    )


def _report_sections(report_payload: dict | None) -> list[dict[str, str]]:
    if not isinstance(report_payload, dict):
        return []

    section_map = [
        ("executive_summary", "执行摘要"),
        ("historical_record_summary", "历史病例整理"),
        ("monitoring_observations", "监测观察"),
        ("medication_observations", "用药与波动观察"),
        ("information_gaps", "信息缺口"),
        ("doctor_discussion_points", "复诊沟通重点"),
    ]
    sections: list[dict[str, str]] = []
    for key, title in section_map:
        value = report_payload.get(key)
        if isinstance(value, str) and value.strip():
            sections.append({"id": key, "title": title, "body": value.strip()})
        elif isinstance(value, list):
            body = "\n".join(f"- {item}" for item in value if str(item).strip())
            if body.strip():
                sections.append({"id": key, "title": title, "body": body})
    return sections


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
        narrative_text=report.narrative_text,
        has_pdf=bool(report.pdf_path and report.pdf_status == "succeeded"),
        sections=_report_sections(report.report_payload),
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


def get_report_detail(session: Session, user: User, report_id: str) -> MedicalRecordReportDetailDTO:
    report = _ensure_report_owner(session, user, report_id)
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


def _assert_non_diagnostic(text: str) -> None:
    for phrase in BANNED_PHRASES:
        if phrase in text:
            raise MedicalRecordsServiceError(
                status_code=502,
                detail=f"报告内容触发非诊断边界校验：包含“{phrase}”。",
            )


def _normalize_report_payload(payload: dict, context: dict) -> dict:
    result = {
        "title": str(payload.get("title") or "病历联合健康报告"),
        "executive_summary": str(payload.get("executive_summary") or "暂无摘要。"),
        "historical_record_summary": payload.get("historical_record_summary") or [],
        "monitoring_observations": payload.get("monitoring_observations") or [],
        "medication_observations": payload.get("medication_observations") or [],
        "information_gaps": payload.get("information_gaps") or context.get("information_gaps") or [],
        "doctor_discussion_points": payload.get("doctor_discussion_points") or [],
        "non_diagnostic_notice": DISCLAIMER_TEXT,
    }
    for key, value in result.items():
        if key == "non_diagnostic_notice":
            continue
        if isinstance(value, str):
            _assert_non_diagnostic(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    _assert_non_diagnostic(item)
    return result


def _generate_report_payload(context: dict) -> dict:
    settings = get_settings()
    payload = {
        "model": settings.dashscope_medical_report_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 TremorGuard 的纵向健康报告整理助手。"
                    "只允许输出健康管理与复诊沟通材料，不得做诊断、分期、处方、药量调整或代替医生判断。"
                    "请严格输出 JSON。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请基于以下上下文生成病历联合健康报告，JSON 字段必须包含："
                    "title, executive_summary, historical_record_summary, monitoring_observations, "
                    "medication_observations, information_gaps, doctor_discussion_points, non_diagnostic_notice。\n"
                    f"{json.dumps(context, ensure_ascii=False)}"
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 1800,
    }
    return _normalize_report_payload(_parse_json_content(_post_dashscope(payload)), context)


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


def _build_pdf_bytes(title: str, sections: list[tuple[str, Sequence[str]]]) -> bytes:
    lines = [title, DISCLAIMER_TEXT, ""]
    for heading, items in sections:
        lines.append(heading)
        for item in items:
            lines.extend(_wrap_text(f"• {item}"))
        lines.append("")

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
    if not extractions:
        raise MedicalRecordsServiceError(status_code=400, detail="当前档案还没有可用于生成报告的成功抽取结果。")

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
        title="病历联合健康报告",
        status="queued",
        pdf_status="queued",
        report_window_start=_window_start(today, payload.report_window_days),
        report_window_end=today,
        monitoring_window_start=_window_start(today, payload.monitoring_window_days),
        monitoring_window_end=today,
        medication_window_start=_window_start(today, payload.medication_window_days),
        medication_window_end=today,
        disclaimer_version=DISCLAIMER_VERSION,
        prompt_version=PROMPT_VERSION,
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
    report.pdf_status = "processing"
    report.error_summary = None
    session.commit()

    try:
        extractions = list(
            session.scalars(
                select(MedicalRecordExtraction)
                .where(
                    MedicalRecordExtraction.archive_id == archive.id,
                    MedicalRecordExtraction.status == "succeeded",
                )
                .order_by(MedicalRecordExtraction.created_at)
            )
        )
        context = _build_longitudinal_context(session, user, archive, report, extractions)
        report_payload = _generate_report_payload(context)
        report.input_snapshot = context
        report.report_payload = report_payload
        report.narrative_text = "\n".join(
            [
                report_payload["executive_summary"],
                *[f"- {item}" for item in report_payload["doctor_discussion_points"]],
                DISCLAIMER_TEXT,
            ]
        )
        report.model_name = get_settings().dashscope_medical_report_model
        report.status = "succeeded"
        report.completed_at = _utcnow()

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

        pdf_sections = [
            ("执行摘要", [report_payload["executive_summary"]]),
            ("历史病例整理", [str(item) for item in report_payload["historical_record_summary"]]),
            ("监测观察", [str(item) for item in report_payload["monitoring_observations"]]),
            ("用药与波动观察", [str(item) for item in report_payload["medication_observations"]]),
            ("信息缺口", [str(item) for item in report_payload["information_gaps"]]),
            ("复诊沟通建议", [str(item) for item in report_payload["doctor_discussion_points"]]),
        ]
        pdf_path = _reports_path(archive.id) / f"{report.id}.pdf"
        pdf_path.write_bytes(_build_pdf_bytes(report.title, pdf_sections))
        report.pdf_status = "succeeded"
        report.pdf_path = str(pdf_path)
        record_audit_log(
            session,
            user_id=user.id,
            endpoint=f"/v1/medical-records/reports/{report.id}",
            method="POST",
            action="longitudinal_report_succeeded",
            request_summary={"archive_id": archive.id},
            response_summary={"report_id": report.id, "version": report.version},
            risk_flag=True,
        )
    except Exception as exc:  # noqa: BLE001
        report.status = "failed"
        report.pdf_status = "failed"
        report.error_summary = str(exc)
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
            filename=f"{report.id}.pdf",
        )

    if not isinstance(report.report_payload, dict):
        raise HTTPException(status_code=404, detail="报告 PDF 尚未生成。")

    pdf_sections = [
        ("执行摘要", [str(report.report_payload.get("executive_summary") or "暂无摘要")]),
        ("历史病例整理", [str(item) for item in report.report_payload.get("historical_record_summary", [])]),
        ("监测观察", [str(item) for item in report.report_payload.get("monitoring_observations", [])]),
        ("用药与波动观察", [str(item) for item in report.report_payload.get("medication_observations", [])]),
        ("信息缺口", [str(item) for item in report.report_payload.get("information_gaps", [])]),
        ("复诊沟通建议", [str(item) for item in report.report_payload.get("doctor_discussion_points", [])]),
    ]
    pdf_bytes = _build_pdf_bytes(report.title, pdf_sections)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report.id}.pdf"'},
    )
