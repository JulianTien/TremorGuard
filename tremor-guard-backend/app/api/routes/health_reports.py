from fastapi import APIRouter, HTTPException

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.schemas.domain import HealthReportListResponse, MedicalRecordReportDetailDTO
from app.services import medical_records as medical_records_service

router = APIRouter()


@router.get("", response_model=HealthReportListResponse)
def list_health_reports(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> HealthReportListResponse:
    return HealthReportListResponse(
        health_reports=medical_records_service.list_ai_health_reports(clinical_session, current_user)
    )


@router.get("/{report_id}", response_model=MedicalRecordReportDetailDTO)
def get_health_report(
    report_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> MedicalRecordReportDetailDTO:
    return medical_records_service.get_ai_health_report_detail(clinical_session, current_user, report_id)


@router.get("/{report_id}/pdf")
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
