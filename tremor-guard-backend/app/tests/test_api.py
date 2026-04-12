from pydantic import SecretStr

from app.core.config import get_settings
from app.services import ai_chat as ai_chat_service


def login(client):
    settings = get_settings()
    response = client.post(
        "/v1/auth/login",
        json={"email": settings.demo_user_email, "password": settings.demo_user_password},
    )
    assert response.status_code == 200
    return response.json()


def register(client, email: str, display_name: str = "新患者"):
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "test-password-123", "display_name": display_name},
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_onboarding_and_device_binding_flow(client):
    settings = get_settings()
    session = register(client, "new-patient@tremorguard.local", display_name="李明")
    headers = auth_headers(session["access_token"])

    me_response = client.get("/v1/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["user"]["onboarding_state"] == "profile_required"

    profile_response = client.put(
        "/v1/me/profile",
        headers=headers,
        json={
            "name": "李明",
            "age": 59,
            "gender": "男",
            "diagnosis": "帕金森病 (PD)",
            "duration": "1年",
            "hospital": "上海市第六人民医院",
        },
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["completion"]["onboarding_state"] == "device_binding_required"

    binding_response = client.post(
        "/v1/me/device-binding",
        headers=headers,
        json={
            "device_serial": settings.demo_available_device_serial,
            "activation_code": settings.demo_available_device_activation_code,
        },
    )
    assert binding_response.status_code == 200
    assert binding_response.json()["completion"]["onboarding_state"] == "active"
    assert binding_response.json()["device_binding"]["device_serial"] == settings.demo_available_device_serial

    overview_response = client.get(
        "/v1/dashboard/overview",
        params={"date": "2026-04-05"},
        headers=headers,
    )
    assert overview_response.status_code == 200
    assert overview_response.json()["device_status"]["firmware"] == "v1.0.6"


def test_duplicate_email_registration_rejected(client):
    response = client.post(
        "/v1/auth/register",
        json={
            "email": get_settings().demo_user_email,
            "password": "test-password-123",
            "display_name": "重复用户",
        },
    )
    assert response.status_code == 409


def test_login_and_profile_flow(client):
    payload = login(client)

    profile_response = client.get("/v1/me/profile", headers=auth_headers(payload["access_token"]))
    assert profile_response.status_code == 200

    body = profile_response.json()
    assert body["patient_profile"]["name"] == "张建国"
    assert body["device_status"]["battery"] == 82
    assert body["consent_settings"]["share_with_doctor"] is True


def test_dashboard_overview_returns_expected_seed_metrics(client):
    payload = login(client)

    response = client.get(
        "/v1/dashboard/overview",
        params={"date": "2026-04-05"},
        headers=auth_headers(payload["access_token"]),
    )
    assert response.status_code == 200

    body = response.json()
    assert body["metric_summaries"][0]["value"] == 12
    assert body["metric_summaries"][1]["value"] == 4.8
    assert body["metric_summaries"][2]["value"] == 45
    assert any(point["medication_taken"] for point in body["trend_points"])


def test_reports_creation_and_listing(client):
    payload = login(client)
    headers = auth_headers(payload["access_token"])

    list_response = client.get("/v1/reports", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["report_summaries"]) == 3

    create_response = client.post("/v1/reports", headers=headers, json={"report_date": "2026-04-06"})
    assert create_response.status_code == 201
    assert create_response.json()["report"]["status"] == "pending"


def test_ingest_endpoint_is_idempotent(client):
    settings = get_settings()
    payload = {
        "items": [
            {
                "start_at": "2026-04-06T10:00:00Z",
                "duration_sec": 45,
                "dominant_hz": 4.8,
                "rms_amplitude": 0.31,
                "confidence": 0.92,
                "source": "device",
            }
        ]
    }
    headers = {
        "X-Device-Key": settings.demo_device_key,
        "Idempotency-Key": "batch-001",
    }

    first = client.post("/v1/ingest/tremor-events", headers=headers, json=payload)
    assert first.status_code == 200
    assert first.json()["accepted_count"] == 1
    assert first.json()["duplicate"] is False

    second = client.post("/v1/ingest/tremor-events", headers=headers, json=payload)
    assert second.status_code == 200
    assert second.json()["accepted_count"] == 0
    assert second.json()["duplicate"] is True


def test_logout_revokes_refresh_token(client):
    session = login(client)

    logout_response = client.post(
        "/v1/auth/logout",
        json={"refresh_token": session["refresh_token"]},
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["success"] is True

    refresh_response = client.post(
        "/v1/auth/refresh",
        json={"refresh_token": session["refresh_token"]},
    )
    assert refresh_response.status_code == 401


def test_device_binding_conflict_for_other_user(client):
    settings = get_settings()
    session = register(client, "bind-conflict@tremorguard.local", display_name="王芳")
    headers = auth_headers(session["access_token"])

    profile_response = client.put(
        "/v1/me/profile",
        headers=headers,
        json={
            "name": "王芳",
            "age": 62,
            "gender": "女",
            "diagnosis": "帕金森病 (PD)",
            "duration": "2年",
            "hospital": "上海交通大学医学院附属仁济医院",
        },
    )
    assert profile_response.status_code == 200

    conflict_response = client.post(
        "/v1/me/device-binding",
        headers=headers,
        json={
            "device_serial": "TG-V1.0-ESP-8A92",
            "activation_code": settings.demo_device_activation_code,
        },
    )
    assert conflict_response.status_code == 409


def test_ai_chat_returns_assistant_response(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-dashscope-key"))

    class FakeResponse:
        status_code = 200
        text = '{"ok": true}'

        @staticmethod
        def json():
            return {
                "model": "qwen-plus",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "结合您今天的监测摘要，午后波动更值得继续记录并在复诊时展示给医生。",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 180,
                    "completion_tokens": 42,
                    "total_tokens": 222,
                },
            }

    def fake_post(url, headers, json, timeout):
        assert url == f"{settings.dashscope_base_url}/chat/completions"
        assert headers["Authorization"] == "Bearer test-dashscope-key"
        assert json["model"] == settings.dashscope_chat_model
        assert json["messages"][0]["role"] == "system"
        assert "张建国" in json["messages"][1]["content"]
        assert json["messages"][-1]["content"] == "今天下午为什么手抖更明显？"
        assert timeout == settings.dashscope_timeout_seconds
        return FakeResponse()

    monkeypatch.setattr(ai_chat_service.httpx, "post", fake_post)

    payload = login(client)
    response = client.post(
        "/v1/ai/chat",
        headers=auth_headers(payload["access_token"]),
        json={
            "messages": [
                {"role": "assistant", "content": "您好，我可以帮您解读 TremorGuard 数据。"},
                {"role": "user", "content": "今天下午为什么手抖更明显？"},
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["role"] == "assistant"
    assert body["model"] == "qwen-plus"
    assert body["usage"]["total_tokens"] == 222


def test_ai_chat_requires_dashscope_api_key(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", None)

    payload = login(client)
    response = client.post(
        "/v1/ai/chat",
        headers=auth_headers(payload["access_token"]),
        json={"messages": [{"role": "user", "content": "帮我分析今天的震颤趋势"}]},
    )

    assert response.status_code == 503
    assert "DASHSCOPE_API_KEY" in response.json()["detail"]
