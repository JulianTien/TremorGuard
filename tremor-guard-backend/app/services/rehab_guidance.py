from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from statistics import mean
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.clinical import MedicationLog, RehabPlan, RehabPlanTemplate, TremorEvent
from app.schemas.domain import (
    GenerateRehabGuidanceRequest,
    RehabConflictStatus,
    RehabEvidenceSummaryDTO,
    RehabGenerationEligibility,
    RehabGuidanceResponse,
    RehabPlanDTO,
    RehabPlanItemDTO,
)

DISPLAY_TZ = ZoneInfo("Asia/Shanghai")
CALENDAR_DAY = "calendar_day"
DISCLAIMER_TEXT = (
    "本计划仅用于日常康复参考，不涉及诊断、处方或药物调整；"
    "如今日状态明显异常，请联系线下医疗团队。"
)
RISK_FLAG_MEDICATION_TREMOR_CONFLICT = "medication_tremor_conflict"


@dataclass(slots=True)
class EvidenceBundle:
    summary: RehabEvidenceSummaryDTO
    medication_logs: list[MedicationLog]
    tremor_events: list[TremorEvent]
    tremor_bucket: Literal["stable", "moderate", "elevated"] | None


def local_day_bounds(target_date: date) -> tuple[datetime, datetime]:
    local_start = datetime.combine(target_date, time.min, tzinfo=DISPLAY_TZ)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def classify_tremor_bucket(events: list[TremorEvent]) -> Literal["stable", "moderate", "elevated"] | None:
    if not events:
        return None

    average_amplitude = mean(event.rms_amplitude for event in events)
    peak_amplitude = max(event.rms_amplitude for event in events)
    if peak_amplitude >= 0.70 or average_amplitude >= 0.45:
        return "elevated"
    if peak_amplitude >= 0.45 or average_amplitude >= 0.30:
        return "moderate"
    return "stable"


def derive_medication_signal(logs: list[MedicationLog]) -> Literal["adherent", "partial", "missed"] | None:
    if not logs:
        return None

    statuses = {log.status for log in logs}
    if "missed" in statuses or "skipped" in statuses:
        return "missed"
    if statuses == {"taken"}:
        return "adherent"
    return "partial"


def determine_signal_consistency(
    medication_signal: Literal["adherent", "partial", "missed"] | None,
    tremor_bucket: Literal["stable", "moderate", "elevated"] | None,
) -> RehabConflictStatus:
    if medication_signal is None or tremor_bucket is None:
        return "insufficient_data"
    if medication_signal == "adherent" and tremor_bucket == "elevated":
        return "conflicting"
    if medication_signal in {"partial", "missed"} and tremor_bucket == "stable":
        return "conflicting"
    return "consistent"


def load_rehab_evidence(session: Session, user_id: str, as_of_date: date) -> EvidenceBundle:
    start_at, end_at = local_day_bounds(as_of_date)

    medication_logs = list(
        session.scalars(
            select(MedicationLog)
            .where(
                MedicationLog.user_id == user_id,
                MedicationLog.taken_at >= start_at,
                MedicationLog.taken_at < end_at,
            )
            .order_by(MedicationLog.taken_at)
        )
    )
    tremor_events = list(
        session.scalars(
            select(TremorEvent)
            .where(
                TremorEvent.user_id == user_id,
                TremorEvent.start_at >= start_at,
                TremorEvent.start_at < end_at,
            )
            .order_by(TremorEvent.start_at)
        )
    )

    missing_inputs: list[str] = []
    if not medication_logs:
        missing_inputs.append("medication_logs")
    if not tremor_events:
        missing_inputs.append("tremor_events")

    eligibility: RehabGenerationEligibility = "eligible" if not missing_inputs else "insufficient_data"
    tremor_bucket = classify_tremor_bucket(tremor_events)
    medication_signal = derive_medication_signal(medication_logs)
    signal_consistency = determine_signal_consistency(medication_signal, tremor_bucket)

    taken_count = sum(1 for log in medication_logs if log.status == "taken")
    pending_count = sum(1 for log in medication_logs if log.status != "taken")
    medication_window_summary = (
        f"目标日已记录 {len(medication_logs)} 条用药，已完成 {taken_count} 次，待补记/未完成 {pending_count} 次。"
        if medication_logs
        else "目标日暂无足够用药记录，当前无法完成计划生成。"
    )

    if tremor_events:
        average_amplitude = round(mean(event.rms_amplitude for event in tremor_events), 2)
        peak_amplitude = round(max(event.rms_amplitude for event in tremor_events), 2)
        tremor_trend_summary = (
            f"目标日共记录 {len(tremor_events)} 次震颤事件，平均幅度 {average_amplitude}，峰值 {peak_amplitude}。"
        )
    else:
        tremor_trend_summary = "目标日暂无足够震颤事件，当前无法完成计划生成。"

    if eligibility == "insufficient_data":
        explanation = "当前证据不足，系统不会生成伪训练计划，请先补齐目标日用药记录和震颤事件。"
        signal_consistency = "insufficient_data"
    elif signal_consistency == "conflicting":
        explanation = "用药记录与震颤强度信号存在张力，系统会保留风险提示并给出更保守的训练建议。"
    else:
        explanation = "目标日用药记录与震颤信号可用于生成结构化训练建议，系统会从预设模板中组合方案。"

    summary = RehabEvidenceSummaryDTO(
        as_of_date=as_of_date,
        evaluation_window=CALENDAR_DAY,
        medication_window_summary=medication_window_summary,
        tremor_trend_summary=tremor_trend_summary,
        signal_consistency=signal_consistency,
        explanation=explanation,
        generation_eligibility=eligibility,
        missing_inputs=missing_inputs,
    )
    return EvidenceBundle(
        summary=summary,
        medication_logs=medication_logs,
        tremor_events=tremor_events,
        tremor_bucket=tremor_bucket,
    )


def determine_scenario_key(
    tremor_bucket: Literal["stable", "moderate", "elevated"] | None,
    signal_consistency: RehabConflictStatus,
) -> str:
    if signal_consistency == "conflicting":
        return "moderate_adjustment"
    if tremor_bucket == "elevated":
        return "high_support"
    if tremor_bucket == "moderate":
        return "moderate_adjustment"
    return "stable_support"


def load_plan_templates(session: Session, scenario_key: str) -> list[RehabPlanTemplate]:
    templates = list(
        session.scalars(
            select(RehabPlanTemplate)
            .where(
                RehabPlanTemplate.is_active.is_(True),
                RehabPlanTemplate.scenario_key.in_(("daily_base", scenario_key)),
            )
            .order_by(RehabPlanTemplate.sort_order, RehabPlanTemplate.name)
        )
    )
    if not templates:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Rehab plan templates are unavailable",
        )
    return templates


def to_plan_items(templates: list[RehabPlanTemplate]) -> list[dict]:
    return [
        {
            "template_id": template.id,
            "name": template.name,
            "category": template.category,
            "duration_minutes": template.duration_minutes,
            "frequency_label": template.frequency_label,
            "cautions": template.cautions,
        }
        for template in templates
    ]


def build_difference_summary(active_plan: RehabPlan | None, candidate_items: list[dict]) -> str | None:
    if not active_plan:
        return "当前尚无激活计划，本次候选方案将作为新的参考起点。"

    active_items = active_plan.plan_payload.get("items", [])
    active_template_ids = {item["template_id"] for item in active_items}
    candidate_template_ids = {item["template_id"] for item in candidate_items}
    added_count = len(candidate_template_ids - active_template_ids)
    retained_count = len(candidate_template_ids & active_template_ids)
    if added_count == 0:
        return "候选方案延续现有训练方向，并按目标日信号调整了训练强度说明。"
    return f"候选方案新增 {added_count} 个训练模块，保留 {retained_count} 个既有模块。"


def build_plan_title(scenario_key: str) -> str:
    return {
        "high_support": "症状波动稳态支持方案",
        "moderate_adjustment": "症状波动调整方案",
        "stable_support": "症状平稳维持方案",
    }[scenario_key]


def to_plan_dto(plan: RehabPlan | None) -> RehabPlanDTO | None:
    if plan is None:
        return None

    items = [
        RehabPlanItemDTO(
            template_id=item["template_id"],
            name=item["name"],
            category=item["category"],
            duration_minutes=item["duration_minutes"],
            frequency_label=item["frequency_label"],
            cautions=item.get("cautions", []),
        )
        for item in plan.plan_payload.get("items", [])
    ]
    return RehabPlanDTO(
        id=plan.id,
        title=plan.title,
        status=plan.status,
        scenario=plan.scenario,
        version=plan.version,
        rationale=plan.rationale,
        items=items,
        risk_flags=plan.risk_flags or [],
        requires_confirmation=plan.requires_confirmation,
        difference_summary=plan.plan_payload.get("difference_summary"),
        generated_at=plan.generated_at,
        confirmed_at=plan.confirmed_at,
        activated_at=plan.activated_at,
    )


def get_active_plan(session: Session, user_id: str) -> RehabPlan | None:
    return session.scalar(
        select(RehabPlan)
        .where(RehabPlan.user_id == user_id, RehabPlan.is_current_active.is_(True))
        .order_by(desc(RehabPlan.activated_at), desc(RehabPlan.generated_at))
    )


def get_pending_candidate(session: Session, user_id: str, as_of_date: date | None = None) -> RehabPlan | None:
    conditions = [RehabPlan.user_id == user_id, RehabPlan.status == "candidate_pending_confirmation"]
    if as_of_date is not None:
        conditions.append(RehabPlan.as_of_date == as_of_date)
    return session.scalar(select(RehabPlan).where(*conditions).order_by(desc(RehabPlan.generated_at)))


def build_guidance_response(session: Session, user_id: str, as_of_date: date) -> RehabGuidanceResponse:
    evidence_bundle = load_rehab_evidence(session, user_id, as_of_date)
    active_plan = get_active_plan(session, user_id)
    candidate_plan = get_pending_candidate(session, user_id, as_of_date)
    generated_at = None
    if candidate_plan is not None:
        generated_at = candidate_plan.generated_at
    elif active_plan is not None:
        generated_at = active_plan.generated_at

    return RehabGuidanceResponse(
        active_plan=to_plan_dto(active_plan),
        candidate_plan=to_plan_dto(candidate_plan),
        evidence_summary=evidence_bundle.summary,
        conflict_status=evidence_bundle.summary.signal_consistency,
        disclaimer=DISCLAIMER_TEXT,
        generated_at=generated_at,
    )


def generate_rehab_guidance(
    session: Session,
    *,
    user_id: str,
    payload: GenerateRehabGuidanceRequest,
) -> RehabPlan:
    evidence_bundle = load_rehab_evidence(session, user_id, payload.as_of_date)
    if evidence_bundle.summary.generation_eligibility != "eligible":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "insufficient_data",
                "message": evidence_bundle.summary.explanation,
                "missing_inputs": evidence_bundle.summary.missing_inputs,
            },
        )

    current_active = get_active_plan(session, user_id)
    existing_candidate = get_pending_candidate(session, user_id)
    next_version = (
        session.scalar(select(RehabPlan.version).where(RehabPlan.user_id == user_id).order_by(desc(RehabPlan.version)))
        or 0
    ) + 1

    scenario_key = determine_scenario_key(evidence_bundle.tremor_bucket, evidence_bundle.summary.signal_consistency)
    templates = load_plan_templates(session, scenario_key)
    candidate_items = to_plan_items(templates)
    risk_flags = (
        [RISK_FLAG_MEDICATION_TREMOR_CONFLICT]
        if evidence_bundle.summary.signal_consistency == "conflicting"
        else []
    )
    difference_summary = build_difference_summary(current_active, candidate_items)
    rationale = (
        f"{evidence_bundle.summary.explanation} 本次训练内容仅从预设白名单模板中组合，"
        "用于帮助用户安排当日康复节奏。"
    )

    new_plan = RehabPlan(
        user_id=user_id,
        as_of_date=payload.as_of_date,
        evaluation_window=CALENDAR_DAY,
        status="candidate_pending_confirmation",
        scenario=scenario_key,
        title=build_plan_title(scenario_key),
        version=next_version,
        rationale=rationale,
        disclaimer=DISCLAIMER_TEXT,
        conflict_status=evidence_bundle.summary.signal_consistency,
        risk_flags=risk_flags,
        requires_confirmation=True,
        is_current_active=False,
        evidence_snapshot={
            "summary": evidence_bundle.summary.model_dump(mode="json"),
            "medication_log_ids": [log.id for log in evidence_bundle.medication_logs],
            "tremor_event_ids": [event.id for event in evidence_bundle.tremor_events],
        },
        plan_payload={
            "items": candidate_items,
            "difference_summary": difference_summary,
        },
        generated_at=datetime.now(UTC),
    )
    session.add(new_plan)
    session.flush()

    if existing_candidate is not None:
        existing_candidate.status = "candidate_superseded"
        existing_candidate.superseded_at = datetime.now(UTC)
        existing_candidate.superseded_by_plan_id = new_plan.id

    return new_plan


def confirm_rehab_guidance(session: Session, *, user_id: str, plan_id: str) -> RehabPlan:
    plan = session.scalar(select(RehabPlan).where(RehabPlan.id == plan_id, RehabPlan.user_id == user_id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rehab plan not found")
    if plan.status != "candidate_pending_confirmation":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending candidate plans can be confirmed",
        )

    current_active = get_active_plan(session, user_id)
    if current_active is not None:
        current_active.is_current_active = False

    activated_at = datetime.now(UTC)
    plan.status = "candidate_confirmed"
    plan.requires_confirmation = False
    plan.confirmed_at = activated_at
    plan.activated_at = activated_at
    plan.is_current_active = True
    return plan
