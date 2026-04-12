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
