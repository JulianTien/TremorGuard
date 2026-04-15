from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.schemas.domain import GenerateRehabGuidanceRequest, RehabGuidanceResponse
from app.services.audit import record_audit_log
from app.services.rehab_guidance import (
    build_guidance_response,
    confirm_rehab_guidance,
    generate_rehab_guidance,
)

router = APIRouter()


def record_rehab_guidance_audit(
    clinical_session: ClinicalSessionDep,
    *,
    user_id: str,
    endpoint: str,
    action: str,
    request_summary: dict,
    response_summary: dict,
    risk_flag: bool,
) -> None:
    record_audit_log(
        clinical_session,
        user_id=user_id,
        endpoint=endpoint,
        method="POST",
        action=action,
        request_summary=request_summary,
        response_summary=response_summary,
        risk_flag=risk_flag,
    )


@router.get("", response_model=RehabGuidanceResponse)
def get_rehab_guidance(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
    as_of_date: date = Query(),
) -> RehabGuidanceResponse:
    return build_guidance_response(clinical_session, current_user.id, as_of_date)


@router.post("/generate", response_model=RehabGuidanceResponse)
def generate_guidance(
    payload: GenerateRehabGuidanceRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> RehabGuidanceResponse:
    try:
        plan = generate_rehab_guidance(clinical_session, user_id=current_user.id, payload=payload)
    except HTTPException as exc:
        record_rehab_guidance_audit(
            clinical_session,
            user_id=current_user.id,
            endpoint="/v1/rehab-guidance/generate",
            action="generate_rehab_guidance",
            request_summary=payload.model_dump(mode="json"),
            response_summary={"detail": exc.detail},
            risk_flag=True,
        )
        clinical_session.commit()
        raise
    record_rehab_guidance_audit(
        clinical_session,
        user_id=current_user.id,
        endpoint="/v1/rehab-guidance/generate",
        action="generate_rehab_guidance",
        request_summary=payload.model_dump(mode="json"),
        response_summary={"plan_id": plan.id, "status": plan.status, "version": plan.version},
        risk_flag=bool(plan.risk_flags),
    )
    clinical_session.commit()
    return build_guidance_response(clinical_session, current_user.id, payload.as_of_date)


@router.post("/{plan_id}/confirm", response_model=RehabGuidanceResponse)
def confirm_guidance(
    plan_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> RehabGuidanceResponse:
    try:
        plan = confirm_rehab_guidance(clinical_session, user_id=current_user.id, plan_id=plan_id)
    except HTTPException as exc:
        record_rehab_guidance_audit(
            clinical_session,
            user_id=current_user.id,
            endpoint=f"/v1/rehab-guidance/{plan_id}/confirm",
            action="confirm_rehab_guidance",
            request_summary={"plan_id": plan_id},
            response_summary={"detail": exc.detail},
            risk_flag=True,
        )
        clinical_session.commit()
        raise
    record_rehab_guidance_audit(
        clinical_session,
        user_id=current_user.id,
        endpoint=f"/v1/rehab-guidance/{plan_id}/confirm",
        action="confirm_rehab_guidance",
        request_summary={"plan_id": plan_id},
        response_summary={"plan_id": plan.id, "status": plan.status},
        risk_flag=bool(plan.risk_flags),
    )
    clinical_session.commit()
    return build_guidance_response(clinical_session, current_user.id, plan.as_of_date)
