from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.models.clinical import MedicationLog
from app.schemas.domain import (
    CreateMedicationRequest,
    MedicationEntryDTO,
    MedicationListResponse,
    UpdateMedicationRequest,
)
from app.services.audit import record_audit_log

router = APIRouter()


def to_entry_dto(entry: MedicationLog) -> MedicationEntryDTO:
    return MedicationEntryDTO(
        id=entry.id,
        time=entry.taken_at.strftime("%H:%M"),
        name=entry.name,
        dose=entry.dose,
        status=entry.status,
    )


@router.get("", response_model=MedicationListResponse)
def list_medications(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
    target_date: date = Query(alias="date"),
) -> MedicationListResponse:
    start = datetime.combine(target_date, time.min)
    end = start + timedelta(days=1)
    rows = list(
        clinical_session.scalars(
            select(MedicationLog)
            .where(MedicationLog.user_id == current_user.id, MedicationLog.taken_at >= start, MedicationLog.taken_at < end)
            .order_by(MedicationLog.taken_at)
        )
    )
    return MedicationListResponse(medication_entries=[to_entry_dto(row) for row in rows])


@router.post("", response_model=MedicationEntryDTO, status_code=status.HTTP_201_CREATED)
def create_medication(
    payload: CreateMedicationRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> MedicationEntryDTO:
    entry = MedicationLog(
        user_id=current_user.id,
        taken_at=payload.taken_at,
        name=payload.name,
        dose=payload.dose,
        status=payload.status,
    )
    clinical_session.add(entry)
    clinical_session.flush()
    record_audit_log(
        clinical_session,
        user_id=current_user.id,
        endpoint="/v1/medications",
        method="POST",
        action="create_medication",
        request_summary=payload.model_dump(mode="json"),
        response_summary={"id": entry.id},
    )
    clinical_session.commit()
    clinical_session.refresh(entry)
    return to_entry_dto(entry)


@router.patch("/{medication_id}", response_model=MedicationEntryDTO)
def update_medication(
    medication_id: int,
    payload: UpdateMedicationRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> MedicationEntryDTO:
    entry = clinical_session.scalar(
        select(MedicationLog).where(MedicationLog.id == medication_id, MedicationLog.user_id == current_user.id)
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field_name, value)

    record_audit_log(
        clinical_session,
        user_id=current_user.id,
        endpoint=f"/v1/medications/{medication_id}",
        method="PATCH",
        action="update_medication",
        request_summary=payload.model_dump(mode="json", exclude_unset=True),
        response_summary={"id": medication_id},
    )
    clinical_session.commit()
    clinical_session.refresh(entry)
    return to_entry_dto(entry)
