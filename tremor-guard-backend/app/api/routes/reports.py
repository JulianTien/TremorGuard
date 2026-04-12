from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import desc, select

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.models.clinical import ReportRecord
from app.schemas.domain import CreateReportRequest, CreateReportResponse, ReportListResponse, ReportSummaryDTO
from app.services.audit import record_audit_log

router = APIRouter()


def to_report_summary(report: ReportRecord) -> ReportSummaryDTO:
    return ReportSummaryDTO(
        id=report.id,
        date=report.report_date,
        type=report.report_type,
        size=report.size_label,
        status=report.status,
    )


@router.get("", response_model=ReportListResponse)
def list_reports(current_user: CurrentUserDep, clinical_session: ClinicalSessionDep) -> ReportListResponse:
    rows = list(
        clinical_session.scalars(
            select(ReportRecord)
            .where(ReportRecord.user_id == current_user.id)
            .order_by(desc(ReportRecord.report_date), desc(ReportRecord.created_at))
        )
    )
    return ReportListResponse(report_summaries=[to_report_summary(row) for row in rows])


@router.post("", response_model=CreateReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: CreateReportRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> CreateReportResponse:
    report_date = payload.report_date or datetime.now(UTC).date()
    report_id = f"R-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    report = ReportRecord(
        id=report_id,
        user_id=current_user.id,
        report_date=report_date,
        report_type=payload.report_type,
        size_label="生成中",
        status="pending",
    )
    clinical_session.add(report)
    clinical_session.flush()
    record_audit_log(
        clinical_session,
        user_id=current_user.id,
        endpoint="/v1/reports",
        method="POST",
        action="create_report_request",
        request_summary=payload.model_dump(mode="json"),
        response_summary={"id": report_id},
    )
    clinical_session.commit()
    return CreateReportResponse(report=to_report_summary(report))
