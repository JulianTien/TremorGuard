from __future__ import annotations

from dataclasses import dataclass

from app.schemas.domain import AiChatMessageInput

GENERAL_DOCTOR_AGENT_TYPE = "general_doctor_agent"
HEALTH_REPORT_AGENT_TYPE = "health_report_agent"

REPORT_KEYWORDS = (
    "生成健康报告",
    "健康报告",
    "复诊报告",
    "分析报告",
    "导出报告",
    "请整理报告",
    "生成报告",
)


@dataclass(slots=True)
class AgentRouteDecision:
    agent_type: str
    trigger_reason: str
    latest_user_message: str


class AgentRouter:
    @staticmethod
    def route(messages: list[AiChatMessageInput]) -> AgentRouteDecision:
        latest_user_message = next(
            (message.content.strip() for message in reversed(messages) if message.role == "user"),
            "",
        )
        normalized = latest_user_message.lower()
        if any(keyword in normalized for keyword in REPORT_KEYWORDS):
            return AgentRouteDecision(
                agent_type=HEALTH_REPORT_AGENT_TYPE,
                trigger_reason="matched_report_generation_keywords",
                latest_user_message=latest_user_message,
            )
        return AgentRouteDecision(
            agent_type=GENERAL_DOCTOR_AGENT_TYPE,
            trigger_reason="default_general_doctor_route",
            latest_user_message=latest_user_message,
        )
