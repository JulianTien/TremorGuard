from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_device_key, hash_password
from app.models.clinical import (
    ConsentSettings,
    DeviceBinding,
    DeviceStatusSnapshot,
    MedicationLog,
    PatientProfile,
    ReportRecord,
    TremorEvent,
)
from app.models.identity import AuthCredential, User

settings = get_settings()


def seed_identity(session: Session) -> str:
    existing_user = session.scalar(select(User).where(User.email == settings.demo_user_email))
    if existing_user:
        return existing_user.id

    now = datetime.now(UTC)
    user = User(
        email=settings.demo_user_email,
        display_name="张建国",
        status="active",
        onboarding_state="active",
        last_login_at=now,
    )
    session.add(user)
    session.flush()
    session.add(
        AuthCredential(
            user_id=user.id,
            password_hash=hash_password(settings.demo_user_password),
            password_updated_at=now,
        )
    )
    session.commit()
    return user.id


def seed_clinical(session: Session, user_id: str) -> None:
    profile = session.scalar(select(PatientProfile).where(PatientProfile.user_id == user_id))
    if profile:
        return

    profile = PatientProfile(
        user_id=user_id,
        name="张建国",
        age=68,
        gender="男",
        diagnosis="帕金森病 (PD)",
        duration="3年",
        hospital="上海市第一人民医院",
    )
    session.add(profile)
    session.flush()

    device_binding = DeviceBinding(
        user_id=user_id,
        device_serial="TG-V1.0-ESP-8A92",
        firmware_version="v1.0.6",
        api_key_hash=hash_device_key(settings.demo_device_key),
        activation_code_hash=hash_password(settings.demo_device_activation_code),
        binding_status="bound",
        bound_at=datetime(2026, 4, 1, 9, 30, tzinfo=UTC),
    )
    session.add(device_binding)
    session.flush()

    session.add(
        DeviceBinding(
            user_id=None,
            device_serial=settings.demo_available_device_serial,
            firmware_version="v1.0.6",
            api_key_hash=hash_device_key(settings.demo_available_device_key),
            activation_code_hash=hash_password(settings.demo_available_device_activation_code),
            binding_status="available",
            device_name="TremorGuard V1",
        )
    )

    session.add(
        ConsentSettings(
            user_id=user_id,
            share_with_doctor=True,
            rag_analysis_enabled=True,
            cloud_sync_enabled=True,
        )
    )
    session.add(
        DeviceStatusSnapshot(
            user_id=user_id,
            device_binding_id=device_binding.id,
            battery_level=82,
            connection="stable",
            connection_label="已连接 · 实时监测中",
            last_sync_at=datetime(2026, 4, 5, 14, 22, tzinfo=UTC),
            available_days_label="预计可用 5 天",
            firmware_version="v1.0.6",
            recorded_at=datetime(2026, 4, 5, 14, 22, tzinfo=UTC),
        )
    )

    medication_rows = [
        MedicationLog(user_id=user_id, taken_at=datetime(2026, 4, 5, 8, 0, tzinfo=UTC), name="多巴丝肼片 (美多芭)", dose="125mg", status="taken"),
        MedicationLog(user_id=user_id, taken_at=datetime(2026, 4, 5, 13, 0, tzinfo=UTC), name="多巴丝肼片 (美多芭)", dose="125mg", status="taken"),
        MedicationLog(user_id=user_id, taken_at=datetime(2026, 4, 5, 18, 0, tzinfo=UTC), name="多巴丝肼片 (美多芭)", dose="125mg", status="pending"),
    ]
    session.add_all(medication_rows)

    event_rows = [
        ("2026-04-05T00:00:00+00:00", 20, 4.6, 0.20),
        ("2026-04-05T02:00:00+00:00", 25, 4.7, 0.25),
        ("2026-04-05T04:00:00+00:00", 18, 4.8, 0.15),
        ("2026-04-05T06:00:00+00:00", 30, 4.8, 0.40),
        ("2026-04-05T08:00:00+00:00", 40, 4.9, 0.62),
        ("2026-04-05T10:00:00+00:00", 35, 4.7, 0.35),
        ("2026-04-05T12:00:00+00:00", 36, 4.8, 0.30),
        ("2026-04-05T13:00:00+00:00", 32, 4.8, 0.28),
        ("2026-04-05T15:00:00+00:00", 112, 5.0, 0.72),
        ("2026-04-05T18:00:00+00:00", 58, 4.9, 0.42),
        ("2026-04-05T21:00:00+00:00", 70, 4.7, 0.32),
        ("2026-04-05T23:00:00+00:00", 64, 4.9, 0.22),
    ]
    for start_at, duration_sec, dominant_hz, rms_amplitude in event_rows:
        session.add(
            TremorEvent(
                user_id=user_id,
                device_binding_id=device_binding.id,
                start_at=datetime.fromisoformat(start_at),
                duration_sec=duration_sec,
                dominant_hz=dominant_hz,
                rms_amplitude=rms_amplitude,
                confidence=0.93,
                source="seed",
            )
        )

    previous_day_rows = [
        ("2026-04-04T08:00:00+00:00", 40, 4.7, 0.48),
        ("2026-04-04T10:00:00+00:00", 45, 4.8, 0.50),
        ("2026-04-04T12:00:00+00:00", 42, 4.8, 0.45),
        ("2026-04-04T14:00:00+00:00", 38, 4.9, 0.46),
        ("2026-04-04T16:00:00+00:00", 35, 4.7, 0.43),
        ("2026-04-04T18:00:00+00:00", 37, 4.8, 0.41),
        ("2026-04-04T20:00:00+00:00", 36, 4.8, 0.39),
        ("2026-04-04T22:00:00+00:00", 41, 4.9, 0.35),
        ("2026-04-04T23:00:00+00:00", 32, 4.8, 0.33),
        ("2026-04-04T23:30:00+00:00", 30, 4.7, 0.31),
    ]
    for start_at, duration_sec, dominant_hz, rms_amplitude in previous_day_rows:
        session.add(
            TremorEvent(
                user_id=user_id,
                device_binding_id=device_binding.id,
                start_at=datetime.fromisoformat(start_at),
                duration_sec=duration_sec,
                dominant_hz=dominant_hz,
                rms_amplitude=rms_amplitude,
                confidence=0.91,
                source="seed",
            )
        )

    reports = [
        ReportRecord(id="R-20260405", user_id=user_id, report_date=date(2026, 4, 5), report_type="周度病情评估摘要", size_label="1.2 MB", status="ready"),
        ReportRecord(id="R-20260329", user_id=user_id, report_date=date(2026, 3, 29), report_type="周度病情评估摘要", size_label="1.1 MB", status="ready"),
        ReportRecord(id="R-20260301", user_id=user_id, report_date=date(2026, 3, 1), report_type="月度长程震颤趋势报告", size_label="3.4 MB", status="ready"),
    ]
    session.add_all(reports)
    session.commit()
