from datetime import datetime

from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import get_settings
from app.models.clinical import ApiAuditLog, MedicationLog, RehabPlan
import app.services.rehab_guidance as rehab_guidance_service
from app.services.rehab_guidance import determine_signal_consistency, local_day_bounds


def login(client):
    settings = get_settings()
    response = client.post(
        "/v1/auth/login",
        json={"email": settings.demo_user_email, "password": settings.demo_user_password},
    )
    assert response.status_code == 200
    return response.json()


def register(client, email: str, display_name: str = "康复患者"):
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "test-password-123", "display_name": display_name},
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def mock_rehab_analysis(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", SecretStr("test-dashscope-key"))

    def fake_generate_structured_rehab_plan(*, evidence_bundle, current_active, scenario_key, templates):
        selected_keys = [template.template_key for template in templates[:2]]
        return {
            "title": f"{scenario_key}-ai-plan",
            "rationale": f"{evidence_bundle.summary.explanation} AI 已基于目标日证据生成候选方案。",
            "difference_summary": None,
            "recommended_template_keys": selected_keys,
            "item_overrides": {
                selected_keys[0]: {
                    "goal": "帮助今天先建立更稳定的训练节奏。",
                    "preparation": ["选择稳定坐姿，先确认周围无障碍物。"],
                    "steps": ["先做低强度启动动作，再按页面节奏完成训练。"],
                    "completion_check": "训练后没有明显不适，动作节奏保持稳定。",
                    "additional_cautions": ["若出现明显疲劳，请立即停止并休息。"],
                }
            },
            "model_name": "qwen-plus",
            "prompt_version": "rehab-guidance-v1",
        }

    monkeypatch.setattr(
        rehab_guidance_service,
        "_generate_structured_rehab_plan",
        fake_generate_structured_rehab_plan,
    )


def test_local_day_bounds_uses_calendar_day_in_shanghai_timezone():
    start_at, end_at = local_day_bounds(datetime(2026, 4, 5).date())

    assert start_at.isoformat() == "2026-04-04T16:00:00+00:00"
    assert end_at.isoformat() == "2026-04-05T16:00:00+00:00"


def test_determine_signal_consistency_detects_conflicts():
    assert determine_signal_consistency("adherent", "elevated") == "conflicting"
    assert determine_signal_consistency("partial", "stable") == "conflicting"
    assert determine_signal_consistency("partial", "moderate") == "consistent"


def test_rehab_guidance_requires_auth(client):
    response = client.get("/v1/rehab-guidance", params={"as_of_date": "2026-04-05"})

    assert response.status_code == 401


def test_rehab_guidance_get_returns_active_plan_and_generation_eligibility(client):
    session = login(client)
    response = client.get(
        "/v1/rehab-guidance",
        params={"as_of_date": "2026-04-05"},
        headers=auth_headers(session["access_token"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evidence_summary"]["evaluation_window"] == "calendar_day"
    assert body["evidence_summary"]["generation_eligibility"] == "eligible"
    assert body["evidence_summary"]["missing_inputs"] == []
    assert body["active_plan"]["status"] == "active_only"
    assert body["active_plan"]["items"][0]["steps"]
    assert body["active_plan"]["items"][0]["preparation"]
    assert body["candidate_plan"] is None
    assert "药物调整" in body["disclaimer"]


def test_rehab_guidance_generate_and_confirm_flow(client, clinical_session_factory, monkeypatch):
    mock_rehab_analysis(monkeypatch)
    session = login(client)
    headers = auth_headers(session["access_token"])

    generate_response = client.post(
        "/v1/rehab-guidance/generate",
        json={"as_of_date": "2026-04-05"},
        headers=headers,
    )
    assert generate_response.status_code == 200
    generated = generate_response.json()
    candidate_plan = generated["candidate_plan"]
    assert candidate_plan["status"] == "candidate_pending_confirmation"
    assert candidate_plan["requires_confirmation"] is True
    assert candidate_plan["version"] == 2
    assert len(candidate_plan["items"]) >= 2
    assert all(item["template_id"] for item in candidate_plan["items"])
    assert all(item["steps"] for item in candidate_plan["items"])
    assert candidate_plan["title"] == "moderate_adjustment-ai-plan"
    assert "AI 已基于目标日证据生成候选方案" in candidate_plan["rationale"]

    with clinical_session_factory() as db_session:
        generate_log = db_session.scalar(
            select(ApiAuditLog)
            .where(ApiAuditLog.action == "generate_rehab_guidance")
            .order_by(ApiAuditLog.created_at.desc())
        )
        persisted_plan = db_session.scalar(select(RehabPlan).where(RehabPlan.id == candidate_plan["id"]))
        assert generate_log is not None
        assert generate_log.response_summary["plan_id"] == candidate_plan["id"]
        assert persisted_plan is not None
        assert persisted_plan.evidence_snapshot["analysis"]["model_name"] == "qwen-plus"

    confirm_response = client.post(
        f"/v1/rehab-guidance/{candidate_plan['id']}/confirm",
        headers=headers,
    )
    assert confirm_response.status_code == 200
    confirmed = confirm_response.json()
    assert confirmed["candidate_plan"] is None
    assert confirmed["active_plan"]["id"] == candidate_plan["id"]
    assert confirmed["active_plan"]["status"] == "candidate_confirmed"
    assert confirmed["active_plan"]["requires_confirmation"] is False

    with clinical_session_factory() as db_session:
        confirm_log = db_session.scalar(
            select(ApiAuditLog)
            .where(ApiAuditLog.action == "confirm_rehab_guidance")
            .order_by(ApiAuditLog.created_at.desc())
        )
        active_plan = db_session.scalar(select(RehabPlan).where(RehabPlan.id == candidate_plan["id"]))
        assert confirm_log is not None
        assert confirm_log.response_summary["status"] == "candidate_confirmed"
        assert active_plan is not None
        assert active_plan.is_current_active is True


def test_rehab_guidance_generate_marks_previous_candidate_superseded(client, clinical_session_factory, monkeypatch):
    mock_rehab_analysis(monkeypatch)
    session = login(client)
    headers = auth_headers(session["access_token"])

    first = client.post(
        "/v1/rehab-guidance/generate",
        json={"as_of_date": "2026-04-05"},
        headers=headers,
    )
    assert first.status_code == 200
    first_candidate = first.json()["candidate_plan"]

    second = client.post(
        "/v1/rehab-guidance/generate",
        json={"as_of_date": "2026-04-05"},
        headers=headers,
    )
    assert second.status_code == 200
    second_candidate = second.json()["candidate_plan"]
    assert second_candidate["id"] != first_candidate["id"]

    with clinical_session_factory() as db_session:
        previous_candidate = db_session.scalar(select(RehabPlan).where(RehabPlan.id == first_candidate["id"]))
        latest_candidate = db_session.scalar(select(RehabPlan).where(RehabPlan.id == second_candidate["id"]))
        assert previous_candidate is not None
        assert previous_candidate.status == "candidate_superseded"
        assert previous_candidate.superseded_by_plan_id == second_candidate["id"]
        assert latest_candidate is not None
        assert latest_candidate.status == "candidate_pending_confirmation"


def test_rehab_guidance_generate_flags_conflicts(client, clinical_session_factory, monkeypatch):
    mock_rehab_analysis(monkeypatch)
    session = login(client)
    headers = auth_headers(session["access_token"])

    with clinical_session_factory() as db_session:
        user_id = db_session.scalar(select(RehabPlan.user_id).limit(1))
        medication_logs = list(
            db_session.scalars(
                select(MedicationLog).where(MedicationLog.user_id == user_id).order_by(MedicationLog.taken_at)
            )
        )
        for log in medication_logs:
            log.status = "taken"
        db_session.commit()

    response = client.post(
        "/v1/rehab-guidance/generate",
        json={"as_of_date": "2026-04-05"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["conflict_status"] == "conflicting"
    assert "medication_tremor_conflict" in body["candidate_plan"]["risk_flags"]

    with clinical_session_factory() as db_session:
        audit_log = db_session.scalar(
            select(ApiAuditLog)
            .where(ApiAuditLog.action == "generate_rehab_guidance")
            .order_by(ApiAuditLog.created_at.desc())
        )
        assert audit_log is not None
        assert audit_log.risk_flag is True


def test_rehab_guidance_insufficient_data_returns_empty_state_and_blocks_generate(client):
    new_session = register(client, "rehab-empty@tremorguard.local")
    headers = auth_headers(new_session["access_token"])

    read_response = client.get("/v1/rehab-guidance", params={"as_of_date": "2026-04-05"}, headers=headers)
    assert read_response.status_code == 200
    read_body = read_response.json()
    assert read_body["active_plan"] is None
    assert read_body["candidate_plan"] is None
    assert read_body["evidence_summary"]["generation_eligibility"] == "insufficient_data"
    assert set(read_body["evidence_summary"]["missing_inputs"]) == {"medication_logs", "tremor_events"}

    generate_response = client.post(
        "/v1/rehab-guidance/generate",
        json={"as_of_date": "2026-04-05"},
        headers=headers,
    )
    assert generate_response.status_code == 409
    assert generate_response.json()["detail"]["code"] == "insufficient_data"


def test_rehab_guidance_non_owner_cannot_confirm_other_users_plan(client, monkeypatch):
    mock_rehab_analysis(monkeypatch)
    demo_session = login(client)
    demo_headers = auth_headers(demo_session["access_token"])
    generate_response = client.post(
        "/v1/rehab-guidance/generate",
        json={"as_of_date": "2026-04-05"},
        headers=demo_headers,
    )
    assert generate_response.status_code == 200
    candidate_id = generate_response.json()["candidate_plan"]["id"]

    other_session = register(client, "rehab-other@tremorguard.local", display_name="另一位患者")
    other_headers = auth_headers(other_session["access_token"])
    confirm_response = client.post(f"/v1/rehab-guidance/{candidate_id}/confirm", headers=other_headers)

    assert confirm_response.status_code == 404


def test_rehab_guidance_generate_requires_dashscope_api_key(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dashscope_api_key", None)

    session = login(client)
    response = client.post(
        "/v1/rehab-guidance/generate",
        json={"as_of_date": "2026-04-05"},
        headers=auth_headers(session["access_token"]),
    )

    assert response.status_code == 503
    assert "DASHSCOPE_API_KEY" in response.json()["detail"]
