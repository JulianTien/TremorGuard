from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import ClinicalBase


class PatientProfile(ClinicalBase):
    __tablename__ = "patient_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(20))
    diagnosis: Mapped[str] = mapped_column(String(255))
    duration: Mapped[str] = mapped_column(String(50))
    hospital: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    consent_settings: Mapped["ConsentSettings"] = relationship(back_populates="patient_profile", uselist=False)
    device_bindings: Mapped[list["DeviceBinding"]] = relationship(back_populates="patient_profile")


class DeviceBinding(ClinicalBase):
    __tablename__ = "device_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("patient_profiles.user_id"), nullable=True, index=True
    )
    device_serial: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    device_name: Mapped[str] = mapped_column(String(100), default="TremorGuard V1")
    firmware_version: Mapped[str] = mapped_column(String(50))
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    activation_code_hash: Mapped[str] = mapped_column(String(255), default="")
    binding_status: Mapped[str] = mapped_column(String(50), default="available")
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    patient_profile: Mapped[PatientProfile] = relationship(back_populates="device_bindings")
    status_snapshots: Mapped[list["DeviceStatusSnapshot"]] = relationship(back_populates="device_binding")


class DeviceStatusSnapshot(ClinicalBase):
    __tablename__ = "device_status_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    device_binding_id: Mapped[str] = mapped_column(String(36), ForeignKey("device_bindings.id"), index=True)
    battery_level: Mapped[int] = mapped_column(Integer)
    connection: Mapped[str] = mapped_column(String(20))
    connection_label: Mapped[str] = mapped_column(String(100))
    last_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_days_label: Mapped[str] = mapped_column(String(50))
    firmware_version: Mapped[str] = mapped_column(String(50))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    device_binding: Mapped[DeviceBinding] = relationship(back_populates="status_snapshots")


class MedicationLog(ClinicalBase):
    __tablename__ = "medication_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    name: Mapped[str] = mapped_column(String(255))
    dose: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class TremorEvent(ClinicalBase):
    __tablename__ = "tremor_events"
    __table_args__ = (
        UniqueConstraint("user_id", "start_at", "source", name="uq_tremor_event_user_start_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    device_binding_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("device_bindings.id"), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_sec: Mapped[int] = mapped_column(Integer)
    dominant_hz: Mapped[float] = mapped_column(Float)
    rms_amplitude: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ReportRecord(ClinicalBase):
    __tablename__ = "report_records"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    report_date: Mapped[date] = mapped_column(Date)
    report_type: Mapped[str] = mapped_column(String(255))
    size_label: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ready")
    file_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ConsentSettings(ClinicalBase):
    __tablename__ = "consent_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("patient_profiles.user_id"), unique=True, index=True)
    share_with_doctor: Mapped[bool] = mapped_column(Boolean, default=True)
    rag_analysis_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cloud_sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    patient_profile: Mapped[PatientProfile] = relationship(back_populates="consent_settings")


class ApiAuditLog(ClinicalBase):
    __tablename__ = "api_audit_logs"
    __table_args__ = (UniqueConstraint("endpoint", "idempotency_key", name="uq_api_audit_endpoint_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), index=True)
    method: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class RehabPlanTemplate(ClinicalBase):
    __tablename__ = "rehab_plan_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    template_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100))
    scenario_key: Mapped[str] = mapped_column(String(100), index=True)
    intensity: Mapped[str] = mapped_column(String(30))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    frequency_label: Mapped[str] = mapped_column(String(100))
    cautions: Mapped[list[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RehabPlan(ClinicalBase):
    __tablename__ = "rehab_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    evaluation_window: Mapped[str] = mapped_column(String(30), default="calendar_day")
    status: Mapped[str] = mapped_column(String(50), index=True)
    scenario: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text())
    disclaimer: Mapped[str] = mapped_column(Text())
    conflict_status: Mapped[str] = mapped_column(String(30), default="consistent")
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    is_current_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    plan_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class MedicalRecordArchive(ClinicalBase):
    __tablename__ = "medical_record_archives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    consent_policy: Mapped[str] = mapped_column(String(100), default="rag_and_cloud_sync_required")
    retention_policy: Mapped[str] = mapped_column(String(100), default="retain_until_user_deletion_request")
    delete_policy: Mapped[str] = mapped_column(String(100), default="support_assisted_delete")
    export_policy: Mapped[str] = mapped_column(String(100), default="pdf_export_only")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    files: Mapped[list["MedicalRecordFile"]] = relationship(back_populates="archive")
    reports: Mapped[list["LongitudinalReport"]] = relationship(back_populates="archive")


class MedicalRecordFile(ClinicalBase):
    __tablename__ = "medical_record_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    archive_id: Mapped[str] = mapped_column(String(36), ForeignKey("medical_record_archives.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(Text())
    processing_status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    processing_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    archive: Mapped[MedicalRecordArchive] = relationship(back_populates="files")
    extractions: Mapped[list["MedicalRecordExtraction"]] = relationship(back_populates="file")


class MedicalRecordExtraction(ClinicalBase):
    __tablename__ = "medical_record_extractions"
    __table_args__ = (UniqueConstraint("file_id", "version", name="uq_medical_record_extraction_file_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    archive_id: Mapped[str] = mapped_column(String(36), ForeignKey("medical_record_archives.id"), index=True)
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("medical_record_files.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    structured_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    file: Mapped[MedicalRecordFile] = relationship(back_populates="extractions")


class LongitudinalReport(ClinicalBase):
    __tablename__ = "longitudinal_reports"
    __table_args__ = (UniqueConstraint("archive_id", "version", name="uq_longitudinal_report_archive_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    archive_id: Mapped[str] = mapped_column(String(36), ForeignKey("medical_record_archives.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    error_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="病历联合健康报告")
    report_window_start: Mapped[date] = mapped_column(Date)
    report_window_end: Mapped[date] = mapped_column(Date)
    monitoring_window_start: Mapped[date] = mapped_column(Date)
    monitoring_window_end: Mapped[date] = mapped_column(Date)
    medication_window_start: Mapped[date] = mapped_column(Date)
    medication_window_end: Mapped[date] = mapped_column(Date)
    disclaimer_version: Mapped[str] = mapped_column(String(50), default="non-diagnostic-v1")
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    narrative_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    pdf_status: Mapped[str] = mapped_column(String(20), default="queued")
    pdf_path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    archive: Mapped[MedicalRecordArchive] = relationship(back_populates="reports")
    input_links: Mapped[list["ReportInputLink"]] = relationship(back_populates="report")


class ReportInputLink(ClinicalBase):
    __tablename__ = "report_input_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("longitudinal_reports.id"), index=True)
    archive_id: Mapped[str] = mapped_column(String(36), ForeignKey("medical_record_archives.id"), index=True)
    input_type: Mapped[str] = mapped_column(String(30))
    input_id: Mapped[str] = mapped_column(String(36), index=True)
    input_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    report: Mapped[LongitudinalReport] = relationship(back_populates="input_links")
