from __future__ import annotations

import httpx

from app.core.config import get_settings


class DashScopeClientError(RuntimeError):
    pass


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


def post_chat_completion(payload: dict[str, object]) -> dict:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise DashScopeClientError("DASHSCOPE_API_KEY 未配置。")

    response = httpx.post(
        f"{settings.dashscope_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.dashscope_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=settings.dashscope_timeout_seconds,
    )
    if response.status_code >= 400:
        raise DashScopeClientError(f"DashScope 调用失败：{_extract_error_message(response)}")
    return response.json()
