import json

from pydantic import SecretStr

from app.core.config import get_settings
from app.services import ai_chat as ai_chat_service
from app.services import medical_records as medical_records_service
from app.services import rehab_guidance as rehab_guidance_service


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


def _mock_rehab_guidance_analysis(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-dashscope-key"))

    def fake_generate_structured_rehab_plan(*, evidence_bundle, current_active, scenario_key, templates):
        selected_keys = [template.template_key for template in templates[:2]]
        return {
            "title": "AI 康复候选计划",
            "rationale": f"{evidence_bundle.summary.explanation} AI 已完成结构化分析。",
            "difference_summary": None,
            "recommended_template_keys": selected_keys,
            "item_overrides": {},
            "model_name": "qwen-plus",
            "prompt_version": "rehab-guidance-v1",
        }

    monkeypatch.setattr(
        rehab_guidance_service,
        "_generate_structured_rehab_plan",
        fake_generate_structured_rehab_plan,
    )


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
    assert body["evidence_readiness"]["has_device_binding"] is True
    assert body["evidence_readiness"]["has_medication_logs"] is True
    assert body["evidence_readiness"]["rehab_plan_ready"] is True
    assert body["evidence_readiness"]["ai_interpretation_ready"] is True


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


def test_ai_health_reports_are_listed_via_primary_resource(client):
    payload = login(client)
    headers = auth_headers(payload["access_token"])

    generate_response = client.post("/v1/ai/actions/health-report/generate", headers=headers)
    assert generate_response.status_code == 200
    action_cards = generate_response.json()["action_cards"]
    assert action_cards[0]["type"] == "health_report_candidate"
    report_id = action_cards[0]["resource_id"]

    list_response = client.get("/v1/health-reports", headers=headers)
    assert list_response.status_code == 200
    health_reports = list_response.json()["health_reports"]
    assert any(report["id"] == report_id for report in health_reports)

    detail_response = client.get(f"/v1/health-reports/{report_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "帕金森患者健康分析报告"

    pdf_response = client.get(f"/v1/health-reports/{report_id}/pdf", headers=headers)
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")


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


def test_demo_device_binding_shortcut_activates_user(client):
    session = register(client, "demo-shortcut@tremorguard.local", display_name="快捷体验用户")
    headers = auth_headers(session["access_token"])

    profile_response = client.put(
        "/v1/me/profile",
        headers=headers,
        json={
            "name": "快捷体验用户",
            "age": 60,
            "gender": "男",
            "diagnosis": "帕金森病 (PD)",
            "duration": "1年",
            "hospital": "上海市第六人民医院",
        },
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["completion"]["onboarding_state"] == "device_binding_required"

    demo_bind_response = client.post("/v1/me/device-binding/demo", headers=headers)
    assert demo_bind_response.status_code == 200
    assert demo_bind_response.json()["completion"]["onboarding_state"] == "active"
    assert demo_bind_response.json()["device_binding"]["binding_status"] == "bound"


def test_ai_chat_returns_assistant_response(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-dashscope-key"))

    class FakeResponse:
        status_code = 200
        text = '{"ok": true}'

        @staticmethod
        def json():
            return {
                "output": {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "结合您今天的监测摘要，午后波动更值得继续记录并在复诊时展示给医生。",
                            }
                        }
                    ]
                },
                "usage": {
                    "input_tokens": 180,
                    "output_tokens": 42,
                    "total_tokens": 222,
                },
            }

    def fake_post(url, headers, json, timeout):
        assert url == ai_chat_service._resolve_dashscope_generation_url()
        assert headers["Authorization"] == "Bearer test-dashscope-key"
        assert json["model"] == settings.dashscope_chat_model
        assert json["input"]["messages"][0]["role"] == "system"
        assert "张建国" in json["input"]["messages"][1]["content"]
        assert json["input"]["messages"][-1]["content"] == "今天下午为什么手抖更明显？"
        assert json["parameters"]["result_format"] == "message"
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
    assert body["action_cards"] == []


def test_ai_chat_stream_returns_sse_chunks(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-dashscope-key"))

    class FakeStreamResponse:
        status_code = 200
        text = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        @staticmethod
        def iter_lines():
            return iter(
                [
                    'data: {"output":{"choices":[{"message":{"role":"assistant","content":"先看一下"}}]}}',
                    "",
                    'data: {"output":{"choices":[{"message":{"role":"assistant","content":"，今天下午波动更明显。"},"finish_reason":"stop"}]},"usage":{"input_tokens":180,"output_tokens":18,"total_tokens":198}}',
                    "",
                ]
            )

    def fake_stream(method, url, headers, json, timeout):
        assert method == "POST"
        assert url == ai_chat_service._resolve_dashscope_generation_url()
        assert headers["X-DashScope-SSE"] == "enable"
        assert json["parameters"]["incremental_output"] is True
        assert json["parameters"]["result_format"] == "message"
        assert timeout == settings.dashscope_timeout_seconds
        return FakeStreamResponse()

    monkeypatch.setattr(ai_chat_service.httpx, "stream", fake_stream)

    payload = login(client)
    response = client.post(
        "/v1/ai/chat/stream",
        headers=auth_headers(payload["access_token"]),
        json={
            "messages": [
                {"role": "user", "content": "今天下午为什么手抖更明显？"},
            ]
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "event: chunk" in body
    assert "event: done" in body
    assert "先看一下" in body
    assert "今天下午波动更明显" in body
    assert '"total_tokens": 198' in body


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


def test_ai_chat_returns_rehab_and_health_report_action_cards(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-dashscope-key"))
    _mock_rehab_guidance_analysis(monkeypatch)

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
                            "content": "我已经根据近期多维数据为您整理了康复训练候选计划和 AI 健康报告。",
                        }
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160},
            }

    monkeypatch.setattr(ai_chat_service.httpx, "post", lambda *args, **kwargs: FakeResponse())

    payload = login(client)
    response = client.post(
        "/v1/ai/chat",
        headers=auth_headers(payload["access_token"]),
        json={
            "messages": [
                {"role": "user", "content": "请根据我的数据生成康复训练计划和健康报告"},
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["action_cards"]) == 2
    assert {item["type"] for item in body["action_cards"]} == {
        "rehab_plan_candidate",
        "health_report_candidate",
    }
    rehab_card = next(item for item in body["action_cards"] if item["type"] == "rehab_plan_candidate")
    report_card = next(item for item in body["action_cards"] if item["type"] == "health_report_candidate")
    assert any(action["kind"] == "confirm_plan" for action in rehab_card["actions"])
    assert any(action["kind"] == "download_report_pdf" for action in report_card["actions"])


def test_ai_action_endpoints_confirm_rehab_plan_and_generate_health_report_pdf(client, monkeypatch):
    _mock_rehab_guidance_analysis(monkeypatch)
    payload = login(client)
    headers = auth_headers(payload["access_token"])

    rehab_generate = client.post("/v1/ai/actions/rehab-plan/generate", headers=headers)
    assert rehab_generate.status_code == 200
    rehab_card = rehab_generate.json()["action_cards"][0]
    plan_id = rehab_card["resource_id"]

    confirm = client.post(f"/v1/ai/actions/rehab-plan/{plan_id}/confirm", headers=headers)
    assert confirm.status_code == 200
    confirmed_card = confirm.json()["action_cards"][0]
    assert confirmed_card["status"] == "candidate_confirmed"

    rehab_pdf = client.get(f"/v1/ai/actions/rehab-plan/{plan_id}/pdf", headers=headers)
    assert rehab_pdf.status_code == 200
    assert rehab_pdf.headers["content-type"] == "application/pdf"
    assert rehab_pdf.content.startswith(b"%PDF-1.4")

    report_generate = client.post("/v1/ai/actions/health-report/generate", headers=headers)
    assert report_generate.status_code == 200
    report_card = report_generate.json()["action_cards"][0]
    report_id = report_card["resource_id"]

    report_detail = client.get(f"/v1/medical-records/reports/{report_id}", headers=headers)
    assert report_detail.status_code == 200
    assert report_detail.json()["title"] == "帕金森患者健康分析报告"
    assert report_detail.json()["report_markdown"].startswith("# 帕金森患者健康分析报告")
    assert "未纳入历史病历资料" in str(report_detail.json()["report_payload"]["historical_record_summary"][0])

    report_pdf = client.get(f"/v1/ai/actions/health-report/{report_id}/pdf", headers=headers)
    assert report_pdf.status_code == 200
    assert report_pdf.headers["content-type"] == "application/pdf"
    assert report_pdf.content.startswith(b"%PDF-1.4")


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
                            "content": "\n".join(
                                [
                                    "# 帕金森患者健康分析报告",
                                    "",
                                    "## 1. 基本信息",
                                    "- 姓名：张建国",
                                    "",
                                    "## 2. 评估目的",
                                    "用于辅助健康管理与复诊沟通。",
                                    "",
                                    "## 3. 主诉与现病史",
                                    "近期存在午后震颤波动。",
                                    "",
                                    "## 4. 既往史、家族史及生活方式",
                                    "- 历史病历主要记录静止性震颤与症状波动。",
                                    "",
                                    "## 5. 当前治疗与用药情况",
                                    "- 服药后数小时内仍可见一定波动，建议复诊时结合记录沟通。",
                                    "",
                                    "## 6. 运动症状评估",
                                    "- 最近监测窗口内存在午后震颤幅度升高的现象。",
                                    "",
                                    "## 7. 非运动症状评估",
                                    "数据不足/待补充。",
                                    "",
                                    "## 8. 日常生活能力评估",
                                    "数据不足/待补充。",
                                    "",
                                    "## 9. 体格检查",
                                    "数据不足/待补充。",
                                    "",
                                    "## 10. 辅助检查结果",
                                    "缺少影像检查原文。",
                                    "",
                                    "## 11. 量表评分与疾病分期",
                                    "当前未采集标准化量表评分，且本系统不提供疾病分期结论。",
                                    "",
                                    "## 12. 主要健康问题总结",
                                    "结合历史病例与近期 TremorGuard 监测，当前更适合围绕症状波动与复诊准备做连续观察。",
                                    "",
                                    "## 13. 综合分析",
                                    "需结合线下复诊进一步综合评估。",
                                    "",
                                    "## 14. 干预建议",
                                    "- 继续记录午后症状波动。",
                                    "",
                                    "## 15. 随访计划",
                                    "- 复诊时重点沟通午后震颤波动与既往病历中的症状描述是否一致。",
                                    "",
                                    "## 16. 结论",
                                    "本报告用于辅助健康管理与复诊沟通，不替代医生诊断。",
                                ]
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
