from datetime import date, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.models.clinical import MedicalRecordArchive, MedicationLog, TremorEvent
from app.schemas.domain import DashboardOverviewResponse
from app.services.dashboard import (
    build_evidence_readiness,
    build_metric_summaries,
    build_overview_insight,
    build_trend_points,
    day_bounds,
    format_device_status,
    get_latest_device_status,
)

router = APIRouter()


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_overview(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
    target_date: date = Query(alias="date"),
) -> DashboardOverviewResponse:
    today_start, today_end = day_bounds(target_date)
    yesterday_start, yesterday_end = day_bounds(target_date - timedelta(days=1))

    events_today = list(
        clinical_session.scalars(
            select(TremorEvent)
            .where(TremorEvent.user_id == current_user.id, TremorEvent.start_at >= today_start, TremorEvent.start_at < today_end)
            .order_by(TremorEvent.start_at)
        )
    )
    events_yesterday = list(
        clinical_session.scalars(
            select(TremorEvent).where(
                TremorEvent.user_id == current_user.id,
                TremorEvent.start_at >= yesterday_start,
                TremorEvent.start_at < yesterday_end,
            )
        )
    )
    medications = list(
        clinical_session.scalars(
            select(MedicationLog)
            .where(
                MedicationLog.user_id == current_user.id,
                MedicationLog.taken_at >= today_start,
                MedicationLog.taken_at < today_end,
            )
            .order_by(MedicationLog.taken_at)
        )
    )
    device_binding, snapshot = get_latest_device_status(clinical_session, current_user.id)
    archive_count = int(
        clinical_session.scalar(
            select(func.count(MedicalRecordArchive.id)).where(MedicalRecordArchive.user_id == current_user.id)
        )
        or 0
    )

    trend_points = build_trend_points(events_today, medications, target_date)
    return DashboardOverviewResponse(
        metric_summaries=build_metric_summaries(events_today, events_yesterday),
        device_status=format_device_status(device_binding, snapshot),
        trend_points=trend_points,
        overview_insight=build_overview_insight(trend_points, medications),
        evidence_readiness=build_evidence_readiness(
            has_device_binding=device_binding is not None,
            events_today=events_today,
            medications=medications,
            medical_record_archive_count=archive_count,
        ),
    )
