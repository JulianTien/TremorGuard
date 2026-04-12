from fastapi import APIRouter, HTTPException

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.schemas.domain import AiChatRequest, AiChatResponse
from app.services.ai_chat import AiChatServiceError, create_ai_chat_completion

router = APIRouter()


@router.post("/chat", response_model=AiChatResponse)
def create_chat(
    payload: AiChatRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> AiChatResponse:
    try:
        return create_ai_chat_completion(clinical_session, current_user, payload.messages)
    except AiChatServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
