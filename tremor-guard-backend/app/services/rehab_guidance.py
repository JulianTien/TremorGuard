from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO
from statistics import mean
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
from app.services.medical_records import _build_pdf_bytes

DISPLAY_TZ = ZoneInfo("Asia/Shanghai")
CALENDAR_DAY = "calendar_day"
REHAB_ANALYSIS_PROMPT_VERSION = "rehab-guidance-v1"
DISCLAIMER_TEXT = (
    "本计划仅用于日常康复参考，不涉及诊断、处方或药物调整；"
    "如今日状态明显异常，请联系线下医疗团队。"
)
REHAB_BANNED_PHRASES = ("确诊", "诊断为", "分期", "处方", "药量调整", "增加剂量", "停药", "换药")
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
        explanation = "用药记录与震颤强度信号存在张力，系统会保留风险提示，并由 AI 生成更保守的训练候选方案。"
    else:
        explanation = "目标日用药记录与震颤信号可用于触发 AI 结构化分析，生成可复核的训练候选方案。"

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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 康复分析服务尚未配置 DASHSCOPE_API_KEY。",
        )

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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 康复分析服务连接失败，请稍后重试。",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 康复分析服务调用失败：{_extract_error_message(response)}",
        )

    data = response.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 康复分析服务返回格式异常。",
        )
    return data


def _parse_json_content(data: dict) -> dict:
    message = data["choices"][0].get("message", {})
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI 康复分析服务返回了无法解析的 JSON。",
            ) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="AI 康复分析服务返回了空内容。",
    )


def _assert_non_diagnostic(text: str) -> None:
    for phrase in REHAB_BANNED_PHRASES:
        if phrase in text:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI 康复分析结果触发安全边界校验：包含“{phrase}”。",
            )


def _normalize_string_list(value: object, *, max_items: int) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if not stripped:
            continue
        _assert_non_diagnostic(stripped)
        normalized.append(stripped)
    return normalized[:max_items]


def _serialize_active_plan(plan: RehabPlan | None) -> dict[str, object] | None:
    if plan is None:
        return None

    items = plan.plan_payload.get("items", []) if isinstance(plan.plan_payload, dict) else []
    return {
        "id": plan.id,
        "title": plan.title,
        "scenario": plan.scenario,
        "version": plan.version,
        "rationale": plan.rationale,
        "items": [
            {
                "template_id": item.get("template_id"),
                "name": item.get("name"),
                "category": item.get("category"),
                "duration_minutes": item.get("duration_minutes"),
                "frequency_label": item.get("frequency_label"),
            }
            for item in items
            if isinstance(item, dict)
        ],
    }


def _build_rehab_analysis_context(
    *,
    evidence_bundle: EvidenceBundle,
    current_active: RehabPlan | None,
    scenario_key: str,
    templates: list[RehabPlanTemplate],
) -> dict[str, object]:
    tremor_amplitudes = [event.rms_amplitude for event in evidence_bundle.tremor_events]
    tremor_peaks = {
        "event_count": len(evidence_bundle.tremor_events),
        "average_rms_amplitude": round(mean(tremor_amplitudes), 3) if tremor_amplitudes else None,
        "peak_rms_amplitude": round(max(tremor_amplitudes), 3) if tremor_amplitudes else None,
        "samples": [
            {
                "start_at": event.start_at.isoformat(),
                "duration_sec": event.duration_sec,
                "dominant_hz": event.dominant_hz,
                "rms_amplitude": event.rms_amplitude,
                "confidence": event.confidence,
            }
            for event in evidence_bundle.tremor_events[:8]
        ],
    }

    medication_logs = [
        {
            "taken_at": log.taken_at.isoformat(),
            "name": log.name,
            "dose": log.dose,
            "status": log.status,
        }
        for log in evidence_bundle.medication_logs[:8]
    ]

    template_catalog = [
        {
            "template_key": template.template_key,
            "name": template.name,
            "category": template.category,
            "scenario_key": template.scenario_key,
            "intensity": template.intensity,
            "duration_minutes": template.duration_minutes,
            "frequency_label": template.frequency_label,
            "cautions": template.cautions,
        }
        for template in templates
    ]

    return {
        "prompt_version": REHAB_ANALYSIS_PROMPT_VERSION,
        "scenario_key": scenario_key,
        "evidence_summary": evidence_bundle.summary.model_dump(mode="json"),
        "medication_logs": medication_logs,
        "tremor_summary": tremor_peaks,
        "current_active_plan": _serialize_active_plan(current_active),
        "allowed_templates": template_catalog,
        "constraints": {
            "non_diagnostic_notice": DISCLAIMER_TEXT,
            "must_use_allowed_template_keys_only": True,
            "must_not_recommend_medication_changes": True,
        },
    }


def _normalize_rehab_analysis_payload(
    payload: dict,
    *,
    allowed_template_keys: set[str],
) -> dict[str, object]:
    title = str(payload.get("title") or "").strip()
    rationale = str(payload.get("rationale") or "").strip()
    difference_summary = str(payload.get("difference_summary") or "").strip()

    if rationale:
        _assert_non_diagnostic(rationale)
    if difference_summary:
        _assert_non_diagnostic(difference_summary)
    if title:
        _assert_non_diagnostic(title)

    raw_keys = payload.get("recommended_template_keys")
    selected_template_keys: list[str] = []
    if isinstance(raw_keys, list):
        for item in raw_keys:
            if not isinstance(item, str):
                continue
            template_key = item.strip()
            if template_key and template_key in allowed_template_keys and template_key not in selected_template_keys:
                selected_template_keys.append(template_key)

    if not selected_template_keys:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 康复分析结果缺少有效的训练模板选择。",
        )

    item_overrides: dict[str, dict[str, object]] = {}
    raw_overrides = payload.get("item_overrides")
    if isinstance(raw_overrides, list):
        for entry in raw_overrides:
            if not isinstance(entry, dict):
                continue
            template_key = str(entry.get("template_key") or "").strip()
            if not template_key or template_key not in allowed_template_keys:
                continue

            goal = str(entry.get("goal") or "").strip()
            completion_check = str(entry.get("completion_check") or "").strip()
            if goal:
                _assert_non_diagnostic(goal)
            if completion_check:
                _assert_non_diagnostic(completion_check)

            item_overrides[template_key] = {
                "goal": goal or None,
                "preparation": _normalize_string_list(entry.get("preparation"), max_items=4),
                "steps": _normalize_string_list(entry.get("steps"), max_items=6),
                "completion_check": completion_check or None,
                "additional_cautions": _normalize_string_list(entry.get("additional_cautions"), max_items=4),
            }

    return {
        "title": title or None,
        "rationale": rationale or None,
        "difference_summary": difference_summary or None,
        "recommended_template_keys": selected_template_keys,
        "item_overrides": item_overrides,
    }


def _generate_structured_rehab_plan(
    *,
    evidence_bundle: EvidenceBundle,
    current_active: RehabPlan | None,
    scenario_key: str,
    templates: list[RehabPlanTemplate],
) -> dict[str, object]:
    settings = get_settings()
    context = _build_rehab_analysis_context(
        evidence_bundle=evidence_bundle,
        current_active=current_active,
        scenario_key=scenario_key,
        templates=templates,
    )
    payload = {
        "model": settings.dashscope_rehab_guidance_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 TremorGuard 的康复训练计划分析助手。"
                    "你的任务是基于当天用药记录和震颤趋势，生成可复核、非诊断、非处方的辅助性康复候选计划。"
                    "你只能从提供的 allowed_templates 中选择 template_key，绝不能新增模板、给出诊断、分期、处方、改药或药量建议。"
                    "请严格输出 JSON，对象必须包含字段：title, rationale, difference_summary, "
                    "recommended_template_keys, item_overrides。"
                    "item_overrides 中每项必须包含 template_key，可选包含 goal, preparation, steps, completion_check, additional_cautions。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请根据以下上下文生成 TremorGuard 康复训练候选计划。"
                    "要求：\n"
                    "1. 至少选择 1 个 allowed_templates 内的 template_key。\n"
                    "2. 解释为什么这些训练更适合今天的状态。\n"
                    "3. 措辞必须是康复辅助建议，不能出现诊断、处方或药量调整。\n"
                    "4. 所有内容面向患者阅读，语言简洁、具体、可执行。\n"
                    f"{json.dumps(context, ensure_ascii=False)}"
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 1800,
    }
    data = _post_dashscope(payload)
    normalized = _normalize_rehab_analysis_payload(
        _parse_json_content(data),
        allowed_template_keys={template.template_key for template in templates},
    )
    normalized["model_name"] = str(data.get("model") or settings.dashscope_rehab_guidance_model)
    normalized["prompt_version"] = REHAB_ANALYSIS_PROMPT_VERSION
    return normalized


def to_plan_items(templates: list[RehabPlanTemplate]) -> list[dict]:
    def instruction_bundle(template: RehabPlanTemplate) -> dict:
        instructions_by_key: dict[str, dict] = {
            "daily-base-breathing": {
                "goal": "先把呼吸和身体节奏稳定下来，为后续训练做热身。",
                "preparation": ["坐在稳固椅子上，双脚平放地面。", "肩膀放松，背部轻轻挺直。"],
                "steps": [
                    "双手自然放在大腿上，先正常呼吸 3 次。",
                    "用鼻子缓慢吸气约 4 秒，感受腹部轻轻鼓起。",
                    "嘴巴缓慢呼气约 6 秒，呼气时肩颈继续放松。",
                    "连续完成 6 到 8 轮，期间不要憋气。",
                ],
                "completion_check": "完成后呼吸更平稳，没有明显头晕或胸闷。",
            },
            "stable-rhythm-open-close": {
                "goal": "帮助上肢在稳定节律下做重复开合，减少动作慌乱感。",
                "preparation": ["保持坐姿稳定，前臂放松。", "双手抬到胸前舒适高度。"],
                "steps": [
                    "双手先慢慢张开五指，再缓慢合拢握拳。",
                    "每次张开和合拢都尽量数到 2 到 3 秒。",
                    "连续做 8 到 12 次后休息 30 秒，再开始下一组。",
                    "全程保持动作均匀，不追求速度。",
                ],
                "completion_check": "训练结束时双手没有明显抽紧，动作仍能保持节律。",
            },
            "moderate-posture-reset": {
                "goal": "帮助躯干重新找回中立姿势，减少长期前倾或僵硬。",
                "preparation": ["站在椅背或桌边附近，确保身边有支撑。", "双脚与肩同宽站立。"],
                "steps": [
                    "先把肩膀轻轻向后打开，头顶向上延展。",
                    "收下巴、伸展胸口，保持 5 秒。",
                    "缓慢回到自然站姿，再重复 6 到 8 次。",
                    "每次动作幅度以舒适、稳定为准，不做快速扭转。",
                ],
                "completion_check": "完成后站姿更稳，胸口打开但没有明显腰背疼痛。",
            },
            "moderate-weight-shift": {
                "goal": "训练左右重心转移，帮助站立和移动前的平衡准备。",
                "preparation": ["站在桌边或扶手旁，必要时单手轻扶。", "双脚自然分开。"],
                "steps": [
                    "身体重心缓慢向左脚移动，保持 2 到 3 秒。",
                    "回到中间后，再缓慢向右脚移动。",
                    "左右各完成 6 到 10 次，动作过程中保持膝盖微屈。",
                    "如果出现明显晃动，立刻减小移动幅度。",
                ],
                "completion_check": "左右转移时没有明显失衡，能控制停留 2 秒以上。",
            },
            "high-segmented-lift": {
                "goal": "把上肢抬举动作拆分成更小阶段，降低一次性大动作带来的紧张感。",
                "preparation": ["坐姿完成，背部有支撑更稳。", "先确认肩部没有疼痛。"],
                "steps": [
                    "双手放在大腿上，先抬到腰部高度停 2 秒。",
                    "再抬到胸口高度停 2 秒，然后缓慢放下。",
                    "整个抬起和放下过程都尽量分段完成，不要一口气抬高。",
                    "每侧做 6 到 8 次，必要时双手交替进行。",
                ],
                "completion_check": "训练后肩颈没有明显代偿或疼痛，动作仍能分段控制。",
            },
            "high-seated-gait-prep": {
                "goal": "在安全坐姿下提前练习步态启动的节奏和下肢协调。",
                "preparation": ["全程坐在稳固椅子前 1/3 处。", "双脚平放地面，膝盖自然分开。"],
                "steps": [
                    "先交替抬起左脚、右脚，模拟迈步准备。",
                    "配合手臂轻摆，保持身体正中，不前冲。",
                    "连续做 10 到 12 次为一组，组间休息 30 秒。",
                    "如果感到疲劳或头晕，立即停止并休息。",
                ],
                "completion_check": "交替抬脚时节奏稳定，没有明显慌乱或头晕。",
            },
        }
        return instructions_by_key.get(
            template.template_key,
            {
                "goal": f"帮助完成{template.name}这一训练模块。",
                "preparation": ["请选择稳定、安全、无遮挡的训练环境。"],
                "steps": ["请按页面给出的训练名称、时长和频率缓慢完成动作。"],
                "completion_check": "训练后没有明显不适，且能保持动作稳定。",
            },
        )

    return [
        {
            "template_id": template.id,
            "name": template.name,
            "category": template.category,
            "duration_minutes": template.duration_minutes,
            "frequency_label": template.frequency_label,
            "cautions": template.cautions,
            **instruction_bundle(template),
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


def to_plan_dto(session: Session, plan: RehabPlan | None) -> RehabPlanDTO | None:
    if plan is None:
        return None

    template_rows = list(session.scalars(select(RehabPlanTemplate)))
    template_by_id = {row.id: row for row in template_rows}

    def fallback_instruction(item: dict) -> dict:
        template = template_by_id.get(item["template_id"])
        if template is None:
            return {
                "goal": None,
                "preparation": [],
                "steps": [],
                "completion_check": None,
            }

        for enriched in to_plan_items([template]):
            return {
                "goal": enriched.get("goal"),
                "preparation": enriched.get("preparation", []),
                "steps": enriched.get("steps", []),
                "completion_check": enriched.get("completion_check"),
            }

        return {
            "goal": None,
            "preparation": [],
            "steps": [],
            "completion_check": None,
        }

    items = [
        RehabPlanItemDTO(
            template_id=item["template_id"],
            name=item["name"],
            category=item["category"],
            duration_minutes=item["duration_minutes"],
            frequency_label=item["frequency_label"],
            cautions=item.get("cautions", []),
            goal=item.get("goal") or fallback_instruction(item)["goal"],
            preparation=item.get("preparation", fallback_instruction(item)["preparation"]),
            steps=item.get("steps", fallback_instruction(item)["steps"]),
            completion_check=item.get("completion_check") or fallback_instruction(item)["completion_check"],
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
        active_plan=to_plan_dto(session, active_plan),
        candidate_plan=to_plan_dto(session, candidate_plan),
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
    analysis = _generate_structured_rehab_plan(
        evidence_bundle=evidence_bundle,
        current_active=current_active,
        scenario_key=scenario_key,
        templates=templates,
    )
    base_items_by_key = {
        template.template_key: item for template, item in zip(templates, to_plan_items(templates), strict=True)
    }
    candidate_items: list[dict] = []
    for template_key in analysis["recommended_template_keys"]:
        base_item = dict(base_items_by_key[template_key])
        override = analysis["item_overrides"].get(template_key, {})
        additional_cautions = override.get("additional_cautions", [])
        if isinstance(additional_cautions, list) and additional_cautions:
            merged_cautions = list(dict.fromkeys([*base_item.get("cautions", []), *additional_cautions]))
            base_item["cautions"] = merged_cautions
        if override.get("goal"):
            base_item["goal"] = override["goal"]
        if override.get("preparation"):
            base_item["preparation"] = override["preparation"]
        if override.get("steps"):
            base_item["steps"] = override["steps"]
        if override.get("completion_check"):
            base_item["completion_check"] = override["completion_check"]
        candidate_items.append(base_item)

    risk_flags = (
        [RISK_FLAG_MEDICATION_TREMOR_CONFLICT]
        if evidence_bundle.summary.signal_consistency == "conflicting"
        else []
    )
    difference_summary = analysis["difference_summary"] or build_difference_summary(current_active, candidate_items)
    rationale = analysis["rationale"] or evidence_bundle.summary.explanation

    new_plan = RehabPlan(
        user_id=user_id,
        as_of_date=payload.as_of_date,
        evaluation_window=CALENDAR_DAY,
        status="candidate_pending_confirmation",
        scenario=scenario_key,
        title=analysis["title"] or build_plan_title(scenario_key),
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
            "analysis": {
                "model_name": analysis["model_name"],
                "prompt_version": analysis["prompt_version"],
                "selected_template_keys": analysis["recommended_template_keys"],
            },
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


def get_rehab_plan_by_id(session: Session, *, user_id: str, plan_id: str) -> RehabPlan:
    plan = session.scalar(select(RehabPlan).where(RehabPlan.id == plan_id, RehabPlan.user_id == user_id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rehab plan not found")
    return plan


def get_rehab_plan_detail(session: Session, *, user_id: str, plan_id: str) -> RehabPlanDTO:
    return to_plan_dto(session, get_rehab_plan_by_id(session, user_id=user_id, plan_id=plan_id))


def download_rehab_plan_pdf(session: Session, *, user_id: str, plan_id: str) -> StreamingResponse:
    plan = get_rehab_plan_by_id(session, user_id=user_id, plan_id=plan_id)
    items = plan.plan_payload.get("items", [])
    sections: list[tuple[str, list[str]]] = [
        ("计划说明", [plan.rationale, plan.disclaimer]),
    ]
    for item in items:
        sections.append(
            (
                str(item.get("name") or "训练项"),
                [
                    f"分类：{item.get('category') or '未分类'}",
                    f"时长：{item.get('duration_minutes') or 0} 分钟",
                    f"频率：{item.get('frequency_label') or '按需'}",
                    *(f"准备：{step}" for step in item.get("preparation", [])),
                    *(f"步骤：{step}" for step in item.get("steps", [])),
                    *(f"注意：{step}" for step in item.get("cautions", [])),
                ],
            )
        )
    pdf_bytes = _build_pdf_bytes(plan.title, sections)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{plan.id}.pdf"'},
    )
