import json

from pydantic import SecretStr

from app.core.config import get_settings
from app.services import ai_chat as ai_chat_service
from app.services import medical_records as medical_records_service


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
    initial_count = len(list_response.json()["report_summaries"])
    assert initial_count == 3

    create_response = client.post("/v1/reports", headers=headers, json={"report_date": "2026-04-06"})
    assert create_response.status_code == 201
    assert create_response.json()["report"]["status"] == "pending"

    refreshed = client.get("/v1/reports", headers=headers)
    assert refreshed.status_code == 200
    assert len(refreshed.json()["report_summaries"]) == initial_count + 1

    archives_response = client.get("/v1/medical-records/archives", headers=headers)
    assert archives_response.status_code == 200
    assert archives_response.json()["archives"] == []


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


def _mock_medical_records_dashscope(monkeypatch):
    def fake_post(payload):
        model = payload["model"]
        settings = get_settings()
        if model == settings.dashscope_medical_extraction_model:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "document_type": "门诊病历",
                                    "summary_text": "病例提示近两年持续存在震颤症状，建议整理既往检查结果并结合近期监测趋势复诊沟通。",
                                    "raw_text": "门诊记录：双上肢静止性震颤，症状波动，建议定期复诊。",
                                    "structured_payload": {
                                        "institution": "上海市第一人民医院",
                                        "visit_date": "2026-03-18",
                                        "diagnoses_mentioned": ["帕金森相关震颤待评估"],
                                        "medications_mentioned": ["多巴丝肼片"],
                                        "exams_mentioned": ["门诊查体"],
                                        "symptoms_mentioned": ["静止性震颤", "下午波动"],
                                        "information_gaps": ["缺少影像检查原文"],
                                    },
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
        if model == settings.dashscope_medical_report_model:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "病历联合健康报告",
                                    "executive_summary": "结合历史病例与近期 TremorGuard 监测，当前更适合围绕症状波动与复诊准备做连续观察。",
                                    "historical_record_summary": [
                                        "历史病历主要记录静止性震颤与症状波动。"
                                    ],
                                    "monitoring_observations": [
                                        "最近监测窗口内存在午后震颤幅度升高的现象。"
                                    ],
                                    "medication_observations": [
                                        "服药后数小时内仍可见一定波动，建议复诊时结合记录沟通。"
                                    ],
                                    "information_gaps": ["缺少影像检查原文"],
                                    "doctor_discussion_points": [
                                        "复诊时可重点沟通午后震颤波动与既往病历中的症状描述是否一致。"
                                    ],
                                    "non_diagnostic_notice": medical_records_service.DISCLAIMER_TEXT,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
        raise AssertionError(f"unexpected model {model}")

    monkeypatch.setattr(medical_records_service, "_post_dashscope", fake_post)


def test_medical_records_archive_upload_report_pdf_flow(client, monkeypatch):
    _mock_medical_records_dashscope(monkeypatch)
    payload = login(client)
    headers = auth_headers(payload["access_token"])

    create_archive = client.post(
        "/v1/medical-records/archives",
        headers=headers,
        json={"title": "神经内科既往病历", "description": "用于长期追踪"},
    )
    assert create_archive.status_code == 201
    archive = create_archive.json()["archive"]
    assert archive["file_count"] == 0
    archive_id = archive["id"]

    upload_response = client.post(
        f"/v1/medical-records/archives/{archive_id}/files",
        headers=headers,
        files=[("files", ("record.png", b"\x89PNG\r\n\x1a\nfake-image", "image/png"))],
    )
    assert upload_response.status_code == 201
    uploaded_file = upload_response.json()["files"][0]
    assert uploaded_file["processing_status"] == "queued"

    archive_detail = client.get(f"/v1/medical-records/archives/{archive_id}", headers=headers)
    assert archive_detail.status_code == 200
    detail_body = archive_detail.json()
    assert detail_body["file_count"] == 1
    assert detail_body["files"][0]["processing_status"] == "succeeded"
    assert detail_body["files"][0]["latest_extraction"]["document_type"] == "门诊病历"

    create_report = client.post(
        f"/v1/medical-records/archives/{archive_id}/reports",
        headers={**headers, "Idempotency-Key": "report-create-1"},
        json={"report_window_days": 30, "monitoring_window_days": 21, "medication_window_days": 14},
    )
    assert create_report.status_code == 201
    report_summary = create_report.json()["report"]
    assert report_summary["status"] == "queued"
    assert report_summary["version"] == 1
    report_id = report_summary["id"]

    report_detail = client.get(f"/v1/medical-records/reports/{report_id}", headers=headers)
    assert report_detail.status_code == 200
    report_body = report_detail.json()
    assert report_body["status"] == "succeeded"
    assert report_body["pdf_status"] == "succeeded"
    assert report_body["report_payload"]["non_diagnostic_notice"] == medical_records_service.DISCLAIMER_TEXT
    assert "report_window" in report_body["input_snapshot"]
    assert "selected_extraction_versions" in report_body["input_snapshot"]

    report_list = client.get(f"/v1/medical-records/archives/{archive_id}/reports", headers=headers)
    assert report_list.status_code == 200
    assert len(report_list.json()["reports"]) == 1

    pdf_response = client.get(f"/v1/medical-records/reports/{report_id}/pdf", headers=headers)
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF-1.4")


def test_medical_records_report_versioning_and_access_control(client, monkeypatch):
    _mock_medical_records_dashscope(monkeypatch)
    payload = login(client)
    headers = auth_headers(payload["access_token"])

    archive_response = client.post(
        "/v1/medical-records/archives",
        headers=headers,
        json={"title": "长期病历档案"},
    )
    archive_id = archive_response.json()["archive"]["id"]

    for name in ("record-1.png", "record-2.png"):
        upload = client.post(
            f"/v1/medical-records/archives/{archive_id}/files",
            headers=headers,
            files=[("files", (name, b"\x89PNG\r\n\x1a\nflow", "image/png"))],
        )
        assert upload.status_code == 201

    first_report = client.post(
        f"/v1/medical-records/archives/{archive_id}/reports",
        headers=headers,
        json={"report_window_days": 30, "monitoring_window_days": 30, "medication_window_days": 30},
    )
    assert first_report.status_code == 201
    assert first_report.json()["report"]["version"] == 1

    second_report = client.post(
        f"/v1/medical-records/archives/{archive_id}/reports",
        headers=headers,
        json={"report_window_days": 45, "monitoring_window_days": 30, "medication_window_days": 30},
    )
    assert second_report.status_code == 201
    assert second_report.json()["report"]["version"] == 2

    report_rows = client.get(f"/v1/medical-records/archives/{archive_id}/reports", headers=headers)
    assert report_rows.status_code == 200
    assert [item["version"] for item in report_rows.json()["reports"]] == [2, 1]

    other_user = register(client, "records-access@tremorguard.local", display_name="隔离用户")
    other_headers = auth_headers(other_user["access_token"])
    detail_response = client.get(f"/v1/medical-records/archives/{archive_id}", headers=other_headers)
    assert detail_response.status_code == 404

    report_id = second_report.json()["report"]["id"]
    report_response = client.get(f"/v1/medical-records/reports/{report_id}", headers=other_headers)
    assert report_response.status_code == 404


def test_medical_records_reject_invalid_upload_format(client):
    payload = login(client)
    headers = auth_headers(payload["access_token"])
    archive_response = client.post(
        "/v1/medical-records/archives",
        headers=headers,
        json={"title": "格式校验档案"},
    )
    archive_id = archive_response.json()["archive"]["id"]

    upload = client.post(
        f"/v1/medical-records/archives/{archive_id}/files",
        headers=headers,
        files=[("files", ("record.txt", b"not-an-image", "text/plain"))],
    )
    assert upload.status_code == 400
    assert "仅支持" in upload.json()["detail"]
