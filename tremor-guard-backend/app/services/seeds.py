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
    RehabPlan,
    RehabPlanTemplate,
    ReportRecord,
    TremorEvent,
)
from app.models.identity import AuthCredential, User
from app.services.rehab_guidance import to_plan_items

settings = get_settings()

REHAB_DISCLAIMER = (
    "本计划仅用于日常康复参考，不涉及诊断、处方或药物调整；"
    "如今日状态明显异常，请联系线下医疗团队。"
)


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
    seed_rehab_guidance_templates(session)

    profile = session.scalar(select(PatientProfile).where(PatientProfile.user_id == user_id))
    if profile:
        seed_active_rehab_plan(session, user_id)
        session.commit()
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

    seed_active_rehab_plan(session, user_id)
    session.commit()


def seed_rehab_guidance_templates(session: Session) -> None:
    existing_template = session.scalar(select(RehabPlanTemplate).limit(1))
    if existing_template:
        return

    templates = [
        RehabPlanTemplate(
            template_key="daily-base-breathing",
            name="呼吸放松热身",
            category="warmup",
            scenario_key="daily_base",
            intensity="low",
            duration_minutes=8,
            frequency_label="每日 2 次",
            cautions=["请在坐姿稳定后开始", "如出现头晕请暂停"],
            sort_order=10,
        ),
        RehabPlanTemplate(
            template_key="stable-rhythm-open-close",
            name="节律开合训练",
            category="upper_limb",
            scenario_key="stable_support",
            intensity="low",
            duration_minutes=12,
            frequency_label="每日 2 次",
            cautions=["保持动作缓慢均匀", "如疲劳明显请缩短时长"],
            sort_order=20,
        ),
        RehabPlanTemplate(
            template_key="moderate-posture-reset",
            name="躯干姿势重置",
            category="posture",
            scenario_key="moderate_adjustment",
            intensity="moderate",
            duration_minutes=15,
            frequency_label="每日 2 次",
            cautions=["避免快速转体", "站立不稳时请扶靠桌面"],
            sort_order=30,
        ),
        RehabPlanTemplate(
            template_key="moderate-weight-shift",
            name="重心转移练习",
            category="balance",
            scenario_key="moderate_adjustment",
            intensity="moderate",
            duration_minutes=10,
            frequency_label="每日 1 次",
            cautions=["请在安全支撑环境下完成", "如步态不稳请减少幅度"],
            sort_order=40,
        ),
        RehabPlanTemplate(
            template_key="high-segmented-lift",
            name="分段缓慢抬手训练",
            category="upper_limb",
            scenario_key="high_support",
            intensity="low",
            duration_minutes=10,
            frequency_label="每日 2 次",
            cautions=["每次只做小幅度动作", "如震颤明显加重请立即停止"],
            sort_order=50,
        ),
        RehabPlanTemplate(
            template_key="high-seated-gait-prep",
            name="坐姿步态预备训练",
            category="mobility",
            scenario_key="high_support",
            intensity="low",
            duration_minutes=8,
            frequency_label="每日 1 次",
            cautions=["全程保持坐姿", "站起前先确认头晕与疲劳情况"],
            sort_order=60,
        ),
    ]
    session.add_all(templates)
    session.flush()


def seed_active_rehab_plan(session: Session, user_id: str) -> None:
    existing_plan = session.scalar(select(RehabPlan).where(RehabPlan.user_id == user_id, RehabPlan.is_current_active.is_(True)))
    if existing_plan:
        return

    templates = list(
        session.scalars(
            select(RehabPlanTemplate)
            .where(RehabPlanTemplate.template_key.in_(("daily-base-breathing", "stable-rhythm-open-close")))
            .order_by(RehabPlanTemplate.sort_order)
        )
    )
    if not templates:
        return

    session.add(
        RehabPlan(
            user_id=user_id,
            as_of_date=date(2026, 4, 4),
            evaluation_window="calendar_day",
            status="active_only",
            scenario="stable_support",
            title="基础维持训练方案",
            version=1,
            rationale="当前激活方案用于维持日常康复节奏，后续可根据目标日证据重新生成 AI 候选方案。",
            disclaimer=REHAB_DISCLAIMER,
            conflict_status="consistent",
            risk_flags=[],
            requires_confirmation=False,
            is_current_active=True,
            evidence_snapshot={
                "summary": {
                    "as_of_date": "2026-04-04",
                    "evaluation_window": "calendar_day",
                    "signal_consistency": "consistent",
                }
            },
            plan_payload={
                "items": [
                    {
                        "template_id": template.id,
                        "name": template.name,
                        "category": template.category,
                        "duration_minutes": template.duration_minutes,
                        "frequency_label": template.frequency_label,
                        "cautions": template.cautions,
                        **next(item for item in to_plan_items([template])),
                    }
                    for template in templates
                ],
                "difference_summary": "当前激活方案为基线训练组合。",
            },
            generated_at=datetime(2026, 4, 4, 7, 0, tzinfo=UTC),
            activated_at=datetime(2026, 4, 4, 7, 5, tzinfo=UTC),
            confirmed_at=datetime(2026, 4, 4, 7, 5, tzinfo=UTC),
        )
    )
