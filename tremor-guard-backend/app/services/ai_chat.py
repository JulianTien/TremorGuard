from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.clinical import MedicationLog, PatientProfile, TremorEvent
from app.models.identity import User
from app.schemas.domain import AiChatMessageInput, AiChatMessageResponse, AiChatResponse, AiChatUsage
from app.services.dashboard import (
    build_metric_summaries,
    build_overview_insight,
    build_trend_points,
    day_bounds,
    get_latest_device_status,
    to_display_datetime,
)

SYSTEM_PROMPT = """
你是 TremorGuard（震颤卫士）的 AI 健康问答助手。

你的职责：
1. 结合用户提供的问题与 TremorGuard 监测摘要，给出通俗、克制、可执行的健康管理解释。
2. 可以帮助用户理解震颤波动、服药记录、监测趋势，以及为复诊沟通做准备。
3. 必须始终使用中文回答。

严格限制：
1. 你不是医生，不能做诊断、不能开药、不能调整处方或药量。
2. 不得虚构不存在的监测数据、检查结果、影像结论或医生判断。
3. 如果信息不足，要明确说明“目前信息不足，需要结合线下医生评估”。
4. 如果用户出现胸痛、呼吸困难、意识障碍、严重跌倒外伤、无法进食饮水、突发明显恶化等紧急情况，要立即建议尽快线下就医或联系急救。
5. 回答结尾补充一句简短提醒：内容仅供健康管理参考，请以专业医生意见为准。
""".strip()


@dataclass(slots=True)
class AiChatServiceError(Exception):
    status_code: int
    detail: str


def _format_medications(medications: list[MedicationLog]) -> str:
    if not medications:
        return "暂无服药记录。"

    return "；".join(
        f"{to_display_datetime(item.taken_at).strftime('%H:%M')} {item.name} {item.dose}（{item.status}）"
        for item in medications
    )


def build_monitoring_context(clinical_session: Session, current_user: User) -> str:
    profile = clinical_session.scalar(
        select(PatientProfile).where(PatientProfile.user_id == current_user.id)
    )
    device_binding, snapshot = get_latest_device_status(clinical_session, current_user.id)
    latest_event = clinical_session.scalar(
        select(TremorEvent)
        .where(TremorEvent.user_id == current_user.id)
        .order_by(desc(TremorEvent.start_at))
    )

    target_date = latest_event.start_at.date() if latest_event else datetime.now(UTC).date()
    yesterday = target_date - timedelta(days=1)
    start, end = day_bounds(target_date)
    yesterday_start, yesterday_end = day_bounds(yesterday)

    events_today = list(
        clinical_session.scalars(
            select(TremorEvent)
            .where(
                TremorEvent.user_id == current_user.id,
                TremorEvent.start_at >= start,
                TremorEvent.start_at < end,
            )
            .order_by(TremorEvent.start_at)
        )
    )
    events_yesterday = list(
        clinical_session.scalars(
            select(TremorEvent)
            .where(
                TremorEvent.user_id == current_user.id,
                TremorEvent.start_at >= yesterday_start,
                TremorEvent.start_at < yesterday_end,
            )
        )
    )
    medications = list(
        clinical_session.scalars(
            select(MedicationLog)
            .where(
                MedicationLog.user_id == current_user.id,
                MedicationLog.taken_at >= start,
                MedicationLog.taken_at < end,
            )
            .order_by(MedicationLog.taken_at)
        )
    )

    metric_summaries = build_metric_summaries(events_today, events_yesterday)
    trend_points = build_trend_points(events_today, medications, target_date)
    overview_insight = build_overview_insight(trend_points, medications)

    profile_summary = (
        "；".join(
            [
                f"姓名：{profile.name}",
                f"年龄：{profile.age}",
                f"性别：{profile.gender}",
                f"诊断：{profile.diagnosis}",
                f"病程：{profile.duration}",
                f"就诊医院：{profile.hospital}",
            ]
        )
        if profile
        else "暂无患者建档资料。"
    )
    device_summary = "；".join(
        [
            (
                f"设备：{device_binding.device_name} ({device_binding.device_serial})"
                if device_binding
                else "设备：未绑定"
            ),
            f"固件：{snapshot.firmware_version}" if snapshot else "固件：暂无",
            f"连接：{snapshot.connection_label}" if snapshot else "连接：暂无",
            f"电量：{snapshot.battery_level}%" if snapshot else "电量：暂无",
        ]
    )
    metrics_summary = "；".join(
        f"{item.label}{item.value}{item.unit}，{item.subtitle}" for item in metric_summaries
    )

    return "\n".join(
        [
            "以下是 TremorGuard 当前可用的用户上下文，请仅在有帮助时引用：",
            f"- 账号：{current_user.display_name} / {current_user.email}",
            f"- 患者资料：{profile_summary}",
            f"- 设备状态：{device_summary}",
            f"- 监测日期：{target_date.isoformat()}",
            f"- 当日监测摘要：{metrics_summary}",
            f"- 当日服药记录：{_format_medications(medications)}",
            f"- 系统摘要：{overview_insight.summary}",
        ]
    )


def _build_request_messages(
    payload_messages: list[AiChatMessageInput], context: str
) -> list[dict[str, str]]:
    history = [
        {"role": message.role, "content": message.content.strip()}
        for message in payload_messages[-12:]
        if message.content.strip()
    ]
    if not history or history[-1]["role"] != "user":
        raise AiChatServiceError(status_code=400, detail="最后一条消息必须是用户提问。")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context},
        *history,
    ]


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
        detail = payload.get("detail")
        if isinstance(detail, str) and detail:
            return detail

    return response.text or "未知上游错误"


def create_ai_chat_completion(
    clinical_session: Session,
    current_user: User,
    messages: list[AiChatMessageInput],
) -> AiChatResponse:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise AiChatServiceError(
            status_code=503,
            detail="AI 问答服务尚未配置 DASHSCOPE_API_KEY。",
        )

    context = build_monitoring_context(clinical_session, current_user)
    request_messages = _build_request_messages(messages, context)
    payload: dict[str, object] = {
        "model": settings.dashscope_chat_model,
        "messages": request_messages,
        "temperature": 0.3,
        "max_tokens": 700,
    }
    if settings.dashscope_enable_search:
        payload["enable_search"] = True

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
        raise AiChatServiceError(
            status_code=502,
            detail="AI 服务连接失败，请稍后重试。",
        ) from exc

    if response.status_code >= 400:
        raise AiChatServiceError(
            status_code=502,
            detail=f"AI 服务调用失败：{_extract_error_message(response)}",
        )

    data = response.json()
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AiChatServiceError(status_code=502, detail="AI 服务返回结果格式异常。")

    message = choices[0].get("message", {})
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AiChatServiceError(status_code=502, detail="AI 服务返回了空内容。")

    usage = data.get("usage")
    usage_dto = None
    if isinstance(usage, dict):
        usage_dto = AiChatUsage(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    return AiChatResponse(
        message=AiChatMessageResponse(role="assistant", content=content.strip()),
        model=str(data.get("model") or settings.dashscope_chat_model),
        usage=usage_dto,
    )
