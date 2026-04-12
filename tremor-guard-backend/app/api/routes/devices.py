from fastapi import APIRouter

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.schemas.domain import DeviceStatusDTO
from app.services.dashboard import format_device_status, get_latest_device_status

router = APIRouter()


@router.get("/current/status", response_model=DeviceStatusDTO)
def get_current_device_status(
    current_user: CurrentUserDep, clinical_session: ClinicalSessionDep
) -> DeviceStatusDTO:
    device_binding, snapshot = get_latest_device_status(clinical_session, current_user.id)
    return format_device_status(device_binding, snapshot)
