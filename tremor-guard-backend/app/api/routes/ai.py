from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.schemas.domain import AiChatActionCardDTO, AiChatRequest, AiChatResponse
from app.services import medical_records as medical_records_service
from app.services import rehab_guidance as rehab_guidance_service
from app.services.ai_chat import (
    AiChatServiceError,
    confirm_rehab_plan_action,
    create_ai_chat_completion,
    generate_health_report_action,
    generate_rehab_plan_action,
    get_health_report_action_card,
    get_rehab_plan_action_card,
    stream_ai_chat_completion,
)

router = APIRouter()


@router.post("/chat", response_model=AiChatResponse)
def create_chat(
    payload: AiChatRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
    background_tasks: BackgroundTasks,
) -> AiChatResponse:
    try:
        return create_ai_chat_completion(
            clinical_session,
            current_user,
            payload.messages,
            background_tasks=background_tasks,
        )
    except AiChatServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/chat/stream")
def create_chat_stream(
    payload: AiChatRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
    background_tasks: BackgroundTasks,
):
    try:
        stream = stream_ai_chat_completion(
            clinical_session,
            current_user,
            payload.messages,
            background_tasks=background_tasks,
        )
    except AiChatServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/actions/rehab-plan/generate", response_model=AiChatResponse)
def create_rehab_plan_action(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> AiChatResponse:
    try:
        return generate_rehab_plan_action(clinical_session, current_user)
    except AiChatServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/actions/rehab-plan/{plan_id}/confirm", response_model=AiChatResponse)
def confirm_rehab_plan(
    plan_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> AiChatResponse:
    try:
        return confirm_rehab_plan_action(clinical_session, current_user, plan_id)
    except AiChatServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/actions/rehab-plan/{plan_id}", response_model=AiChatActionCardDTO)
def get_rehab_plan_card(
    plan_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> AiChatActionCardDTO:
    return get_rehab_plan_action_card(clinical_session, current_user, plan_id)


@router.get("/actions/rehab-plan/{plan_id}/pdf")
def download_rehab_plan_pdf(
    plan_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
):
    return rehab_guidance_service.download_rehab_plan_pdf(
        clinical_session,
        user_id=current_user.id,
        plan_id=plan_id,
    )


@router.post("/actions/health-report/generate", response_model=AiChatResponse)
def generate_health_report(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
    background_tasks: BackgroundTasks,
) -> AiChatResponse:
    return generate_health_report_action(
        clinical_session,
        current_user,
        background_tasks=background_tasks,
    )


@router.get("/actions/health-report/{report_id}", response_model=AiChatActionCardDTO)
def get_health_report_card(
    report_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> AiChatActionCardDTO:
    return get_health_report_action_card(clinical_session, current_user, report_id)


@router.get("/actions/health-report/{report_id}/pdf")
def download_health_report_pdf(
    report_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
):
    try:
        medical_records_service.get_ai_health_report_detail(clinical_session, current_user, report_id)
        return medical_records_service.download_report_pdf(clinical_session, current_user, report_id)
    except medical_records_service.MedicalRecordsServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
