from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json

import httpx
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.clinical import MedicationLog, PatientProfile, TremorEvent
from app.models.identity import User
from app.schemas.domain import (
    AiChatActionCardDTO,
    AiChatActionDTO,
    AiChatMessageInput,
    AiChatMessageResponse,
    AiChatResponse,
    AiChatUsage,
    GenerateRehabGuidanceRequest,
)
from app.services.agent_router import (
    AgentRouter,
    GENERAL_DOCTOR_AGENT_TYPE,
    HEALTH_REPORT_AGENT_TYPE,
)
from app.services import medical_records as medical_records_service
from app.services.dashboard import (
    build_metric_summaries,
    build_overview_insight,
    build_trend_points,
    day_bounds,
    get_latest_device_status,
    to_display_datetime,
)
from app.services.rehab_guidance import (
    build_guidance_response,
    confirm_rehab_guidance,
    generate_rehab_guidance,
    get_rehab_plan_detail,
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

REHAB_KEYWORDS = ("康复", "训练计划", "训练方案", "康复计划", "运动计划")
REPORT_KEYWORDS = ("健康报告", "监测摘要", "摘要报告", "报告", "复诊报告")


@dataclass(slots=True)
class AiChatServiceError(Exception):
    status_code: int
    detail: str


@dataclass(slots=True)
class GeneralDoctorAgent:
    agent_type: str = GENERAL_DOCTOR_AGENT_TYPE
    system_prompt: str = SYSTEM_PROMPT


@dataclass(slots=True)
class DashScopeChatCompletion:
    content: str
    model: str
    usage: AiChatUsage | None


def _format_medications(medications: list[MedicationLog]) -> str:
    if not medications:
        return "暂无服药记录。"

    return "；".join(
        f"{to_display_datetime(item.taken_at).strftime('%H:%M')} {item.name} {item.dose}（{item.status}）"
        for item in medications
    )


def resolve_monitoring_target_date(clinical_session: Session, current_user: User):
    latest_event = clinical_session.scalar(
        select(TremorEvent)
        .where(TremorEvent.user_id == current_user.id)
        .order_by(desc(TremorEvent.start_at))
    )
    return latest_event.start_at.date() if latest_event else datetime.now(UTC).date()


def build_monitoring_context(clinical_session: Session, current_user: User) -> str:
    profile = clinical_session.scalar(
        select(PatientProfile).where(PatientProfile.user_id == current_user.id)
    )
    device_binding, snapshot = get_latest_device_status(clinical_session, current_user.id)
    target_date = resolve_monitoring_target_date(clinical_session, current_user)
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


def _resolve_dashscope_generation_url() -> str:
    settings = get_settings()
    base_url = settings.dashscope_base_url

    if base_url.endswith("/compatible-mode/v1"):
        base_url = base_url.removesuffix("/compatible-mode/v1")
    elif base_url.endswith("/api/v1"):
        base_url = base_url.removesuffix("/api/v1")

    return f"{base_url}/api/v1/services/aigc/text-generation/generation"


def _build_generation_payload(
    request_messages: list[dict[str, str]],
    *,
    incremental_output: bool = False,
) -> dict[str, object]:
    settings = get_settings()
    parameters: dict[str, object] = {
        "result_format": "message",
        "temperature": 0.3,
        "max_tokens": 700,
    }
    if incremental_output:
        parameters["incremental_output"] = True
    if settings.dashscope_enable_search:
        parameters["enable_search"] = True

    return {
        "model": settings.dashscope_chat_model,
        "input": {
            "messages": request_messages,
        },
        "parameters": parameters,
    }


def _map_usage(data: dict) -> AiChatUsage | None:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None

    return AiChatUsage(
        prompt_tokens=usage.get("input_tokens"),
        completion_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"),
    )


def _extract_message_content(data: dict, *, allow_empty: bool = False) -> str:
    output = data.get("output")
    if not isinstance(output, dict):
        raise AiChatServiceError(status_code=502, detail="AI 服务返回结果格式异常。")

    choices = output.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AiChatServiceError(status_code=502, detail="AI 服务返回结果格式异常。")

    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        raise AiChatServiceError(status_code=502, detail="AI 服务返回结果格式异常。")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if allow_empty and content is None:
        return ""

    raise AiChatServiceError(status_code=502, detail="AI 服务返回结果格式异常。")


def _create_upstream_completion(
    request_messages: list[dict[str, str]],
) -> DashScopeChatCompletion:
    settings = get_settings()
    payload = _build_generation_payload(request_messages)

    try:
        response = httpx.post(
            _resolve_dashscope_generation_url(),
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
    content = _extract_message_content(data).strip()
    if not content:
        raise AiChatServiceError(status_code=502, detail="AI 服务返回了空内容。")

    return DashScopeChatCompletion(
        content=content,
        model=str(data.get("model") or settings.dashscope_chat_model),
        usage=_map_usage(data),
    )


def _iter_sse_frames(lines):
    event = "message"
    data_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if line == "":
            if data_lines:
                yield event, "\n".join(data_lines)
            event = "message"
            data_lines = []
            continue

        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line.removeprefix("event:").strip() or "message"
            continue
        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").lstrip())

    if data_lines:
        yield event, "\n".join(data_lines)


def _encode_sse_event(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _matches_keywords(content: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in content for keyword in keywords)


def _build_rehab_card_summary(plan) -> str:
    return f"{plan.title}，共 {len(plan.items)} 个训练模块，版本 V{plan.version}。"


def build_rehab_action_card(plan) -> AiChatActionCardDTO:
    return AiChatActionCardDTO(
        type="rehab_plan_candidate",
        agent_type="rehab_guidance_agent",
        title=plan.title,
        summary=_build_rehab_card_summary(plan),
        status=plan.status,
        resource_id=plan.id,
        resource_path=f"/rehab-guidance?plan_id={plan.id}",
        actions=[
            AiChatActionDTO(
                key=f"confirm-{plan.id}",
                label="确认计划",
                kind="confirm_plan",
                api_path=f"/v1/ai/actions/rehab-plan/{plan.id}/confirm",
            ),
            AiChatActionDTO(
                key=f"view-{plan.id}",
                label="查看详情",
                kind="view_plan_detail",
                url=f"/rehab-guidance?plan_id={plan.id}",
            ),
            AiChatActionDTO(
                key=f"pdf-{plan.id}",
                label="下载 PDF",
                kind="download_plan_pdf",
                api_path=f"/v1/ai/actions/rehab-plan/{plan.id}/pdf",
                download_name=f"{plan.title}.pdf",
            ),
        ],
    )


def build_health_report_action_card(report) -> AiChatActionCardDTO:
    if getattr(report, "pipeline_state", None):
        llm_stage = report.pipeline_state.llm
        pdf_stage = report.pipeline_state.pdf
        if llm_stage.status in {"queued", "processing"}:
            summary = "已按《帕金森患者健康分析报告》模板排队生成，正在准备 Markdown 在线文档。"
        elif llm_stage.status == "failed":
            summary = llm_stage.error or "健康报告生成失败，请稍后重试。"
        elif pdf_stage.status in {"queued", "processing"}:
            summary = "Markdown 报告已生成，可在线查看；PDF 正在转换中。"
        elif pdf_stage.status == "failed":
            summary = "Markdown 报告已生成并可在线查看，但 PDF 转换失败。"
        else:
            summary = report.summary or "AI 健康报告已生成，可在线查看 Markdown 文档或下载 PDF。"
    else:
        summary = report.summary or "AI 健康报告已生成，可在线查看 Markdown 文档或下载 PDF。"

    return AiChatActionCardDTO(
        type="health_report_candidate",
        agent_type=HEALTH_REPORT_AGENT_TYPE,
        title=report.title,
        summary=summary,
        status=report.status,
        resource_id=report.id,
        resource_path=f"/records/reports/{report.id}",
        pipeline_state=getattr(report, "pipeline_state", None),
        actions=[
            AiChatActionDTO(
                key=f"view-{report.id}",
                label="在线查看",
                kind="view_report_online",
                url=f"/records/reports/{report.id}",
            ),
            AiChatActionDTO(
                key=f"pdf-{report.id}",
                label="下载 PDF",
                kind="download_report_pdf",
                api_path=f"/v1/ai/actions/health-report/{report.id}/pdf",
                download_name=f"{report.title}.pdf",
            ),
        ],
    )


def _build_action_cards(
    clinical_session: Session,
    current_user: User,
    messages: list[AiChatMessageInput],
    background_tasks: BackgroundTasks | None = None,
) -> tuple[list[AiChatActionCardDTO], list[str]]:
    latest_user_message = next((message.content.strip() for message in reversed(messages) if message.role == "user"), "")
    if not latest_user_message:
        return [], []

    content = latest_user_message.lower()
    cards: list[AiChatActionCardDTO] = []
    notes: list[str] = []

    if _matches_keywords(content, REHAB_KEYWORDS):
        try:
            target_date = resolve_monitoring_target_date(clinical_session, current_user)
            guidance = build_guidance_response(clinical_session, current_user.id, target_date)
            if guidance.candidate_plan is None:
                generate_rehab_guidance(
                    clinical_session,
                    user_id=current_user.id,
                    payload=GenerateRehabGuidanceRequest(as_of_date=target_date),
                )
                clinical_session.commit()
                guidance = build_guidance_response(clinical_session, current_user.id, target_date)

            if guidance.candidate_plan is not None:
                cards.append(build_rehab_action_card(guidance.candidate_plan))
            else:
                notes.append("当前还没有可确认的康复训练候选计划。")
        except HTTPException as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                notes.append(str(detail.get("message") or "当前暂时无法生成康复训练计划。"))
            else:
                notes.append(str(detail))

    if _matches_keywords(content, REPORT_KEYWORDS):
        report = medical_records_service.create_ai_health_report_for_chat(clinical_session, current_user)
        if background_tasks is not None:
            background_tasks.add_task(
                medical_records_service.run_report_processing_task,
                current_user.id,
                current_user.display_name,
                report.id,
            )
        cards.append(build_health_report_action_card(report))

    return cards, notes


def create_ai_chat_completion(
    clinical_session: Session,
    current_user: User,
    messages: list[AiChatMessageInput],
    background_tasks: BackgroundTasks | None = None,
) -> AiChatResponse:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise AiChatServiceError(
            status_code=503,
            detail="AI 问答服务尚未配置 DASHSCOPE_API_KEY。",
        )

    route_decision = AgentRouter.route(messages)
    if route_decision.agent_type == HEALTH_REPORT_AGENT_TYPE:
        return generate_health_report_action(
            clinical_session,
            current_user,
            background_tasks=background_tasks,
            trigger_message=route_decision.latest_user_message,
            route_reason=route_decision.trigger_reason,
        )

    context = build_monitoring_context(clinical_session, current_user)
    request_messages = _build_request_messages(messages, context)
    completion = _create_upstream_completion(request_messages)

    action_cards, notes = _build_action_cards(
        clinical_session,
        current_user,
        messages,
        background_tasks=background_tasks,
    )
    response_content = completion.content
    if notes:
        response_content = f"{response_content}\n\n" + "\n".join(f"- {note}" for note in notes)

    return AiChatResponse(
        message=AiChatMessageResponse(role="assistant", content=response_content),
        model=completion.model,
        usage=completion.usage,
        action_cards=action_cards,
    )


def stream_ai_chat_completion(
    clinical_session: Session,
    current_user: User,
    messages: list[AiChatMessageInput],
    background_tasks: BackgroundTasks | None = None,
):
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise AiChatServiceError(
            status_code=503,
            detail="AI 问答服务尚未配置 DASHSCOPE_API_KEY。",
        )

    route_decision = AgentRouter.route(messages)
    if route_decision.agent_type == HEALTH_REPORT_AGENT_TYPE:
        result = generate_health_report_action(
            clinical_session,
            current_user,
            background_tasks=background_tasks,
            trigger_message=route_decision.latest_user_message,
            route_reason=route_decision.trigger_reason,
        )

        def action_stream():
            yield _encode_sse_event("chunk", {"content": result.message.content})
            yield _encode_sse_event(
                "done",
                {
                    "message": result.message.model_dump(mode="json"),
                    "model": result.model,
                    "usage": result.usage.model_dump(mode="json") if result.usage else None,
                    "action_cards": [card.model_dump(mode="json") for card in result.action_cards],
                },
            )

        return action_stream()

    context = build_monitoring_context(clinical_session, current_user)
    request_messages = _build_request_messages(messages, context)
    action_cards, notes = _build_action_cards(
        clinical_session,
        current_user,
        messages,
        background_tasks=background_tasks,
    )
    payload = _build_generation_payload(request_messages, incremental_output=True)

    def event_stream():
        full_content = ""
        final_usage: AiChatUsage | None = None

        try:
            with httpx.stream(
                "POST",
                _resolve_dashscope_generation_url(),
                headers={
                    "Authorization": f"Bearer {settings.dashscope_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                    "X-DashScope-SSE": "enable",
                },
                json=payload,
                timeout=settings.dashscope_timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    raise AiChatServiceError(
                        status_code=502,
                        detail=f"AI 服务调用失败：{_extract_error_message(response)}",
                    )

                for event_name, event_data in _iter_sse_frames(response.iter_lines()):
                    if event_name not in {"message", "result"} or event_data == "[DONE]":
                        continue

                    try:
                        data = json.loads(event_data)
                    except json.JSONDecodeError as exc:
                        raise AiChatServiceError(status_code=502, detail="AI 服务流式结果格式异常。") from exc

                    delta = _extract_message_content(data, allow_empty=True)
                    if delta:
                        full_content += delta
                        yield _encode_sse_event("chunk", {"content": delta})

                    usage = _map_usage(data)
                    if usage is not None:
                        final_usage = usage

        except httpx.RequestError as exc:
            raise AiChatServiceError(
                status_code=502,
                detail="AI 服务连接失败，请稍后重试。",
            ) from exc
        except AiChatServiceError as exc:
            yield _encode_sse_event("error", {"detail": exc.detail})
            return

        if not full_content.strip():
            yield _encode_sse_event("error", {"detail": "AI 服务返回了空内容。"})
            return

        if notes:
            notes_chunk = "\n\n" + "\n".join(f"- {note}" for note in notes)
            full_content = f"{full_content}{notes_chunk}"
            yield _encode_sse_event("chunk", {"content": notes_chunk})

        yield _encode_sse_event(
            "done",
            {
                "message": {
                    "role": "assistant",
                    "content": full_content,
                },
                "model": settings.dashscope_chat_model,
                "usage": final_usage.model_dump(mode="json") if final_usage else None,
                "action_cards": [card.model_dump(mode="json") for card in action_cards],
            },
        )

    return event_stream()


def confirm_rehab_plan_action(clinical_session: Session, current_user: User, plan_id: str) -> AiChatResponse:
    plan = confirm_rehab_guidance(clinical_session, user_id=current_user.id, plan_id=plan_id)
    clinical_session.commit()
    plan_dto = get_rehab_plan_detail(clinical_session, user_id=current_user.id, plan_id=plan.id)
    return AiChatResponse(
        message=AiChatMessageResponse(
            role="assistant",
            content="康复训练计划已确认。你现在可以查看完整内容，或直接下载 PDF 留存。",
        ),
        model="tremorguard-action",
        action_cards=[build_rehab_action_card(plan_dto)],
    )


def generate_rehab_plan_action(clinical_session: Session, current_user: User) -> AiChatResponse:
    target_date = resolve_monitoring_target_date(clinical_session, current_user)
    guidance = build_guidance_response(clinical_session, current_user.id, target_date)
    if guidance.candidate_plan is None:
        generate_rehab_guidance(
            clinical_session,
            user_id=current_user.id,
            payload=GenerateRehabGuidanceRequest(as_of_date=target_date),
        )
        clinical_session.commit()
        guidance = build_guidance_response(clinical_session, current_user.id, target_date)

    if guidance.candidate_plan is None:
        raise AiChatServiceError(status_code=409, detail="当前暂时无法生成康复训练计划。")

    return AiChatResponse(
        message=AiChatMessageResponse(
            role="assistant",
            content="已为你生成新的康复训练候选计划。请先复核，再决定是否确认启用。",
        ),
        model="tremorguard-action",
        action_cards=[build_rehab_action_card(guidance.candidate_plan)],
    )


def get_rehab_plan_action_card(clinical_session: Session, current_user: User, plan_id: str) -> AiChatActionCardDTO:
    plan = get_rehab_plan_detail(clinical_session, user_id=current_user.id, plan_id=plan_id)
    return build_rehab_action_card(plan)


def generate_health_report_action(
    clinical_session: Session,
    current_user: User,
    background_tasks: BackgroundTasks | None = None,
    trigger_message: str | None = None,
    route_reason: str | None = None,
) -> AiChatResponse:
    report = medical_records_service.create_ai_health_report_for_chat(
        clinical_session,
        current_user,
        trigger_message=trigger_message,
        route_reason=route_reason,
    )
    if background_tasks is not None:
        background_tasks.add_task(
            medical_records_service.run_report_processing_task,
            current_user.id,
            current_user.display_name,
            report.id,
        )
    return AiChatResponse(
        message=AiChatMessageResponse(
            role="assistant",
            content="已从通用 AI 医生切换到专用报告生成 Agent，并开始按固定模板生成 AI 健康报告。Markdown 在线文档生成后可立即查看，PDF 转换完成后可下载。",
        ),
        model=HEALTH_REPORT_AGENT_TYPE,
        action_cards=[build_health_report_action_card(report)],
    )


def get_health_report_action_card(clinical_session: Session, current_user: User, report_id: str) -> AiChatActionCardDTO:
    report = medical_records_service.get_ai_health_report_detail(clinical_session, current_user, report_id)
    return build_health_report_action_card(report)
