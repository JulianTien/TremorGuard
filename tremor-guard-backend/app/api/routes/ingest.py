from fastapi import APIRouter, Header
from sqlalchemy import select

from app.api.deps import ClinicalSessionDep, CurrentDeviceDep
from app.models.clinical import ApiAuditLog, TremorEvent
from app.schemas.domain import TremorEventIngestRequest, TremorIngestResponse
from app.services.audit import record_audit_log

router = APIRouter()


@router.post("/tremor-events", response_model=TremorIngestResponse)
def ingest_tremor_events(
    payload: TremorEventIngestRequest,
    current_device: CurrentDeviceDep,
    clinical_session: ClinicalSessionDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TremorIngestResponse:
    if idempotency_key:
        existing = clinical_session.scalar(
            select(ApiAuditLog).where(
                ApiAuditLog.endpoint == "/v1/ingest/tremor-events",
                ApiAuditLog.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return TremorIngestResponse(accepted_count=0, duplicate=True, batch_key=idempotency_key)

    accepted_count = 0
    for item in payload.items:
        event = TremorEvent(
            user_id=current_device.user_id,
            device_binding_id=current_device.id,
            start_at=item.start_at,
            duration_sec=item.duration_sec,
            dominant_hz=item.dominant_hz,
            rms_amplitude=item.rms_amplitude,
            confidence=item.confidence,
            source=item.source,
        )
        clinical_session.add(event)
        accepted_count += 1

    record_audit_log(
        clinical_session,
        user_id=current_device.user_id,
        endpoint="/v1/ingest/tremor-events",
        method="POST",
        action="ingest_tremor_events",
        idempotency_key=idempotency_key,
        request_summary={"count": len(payload.items), "device_serial": current_device.device_serial},
        response_summary={"accepted_count": accepted_count},
    )
    clinical_session.commit()
    return TremorIngestResponse(accepted_count=accepted_count, duplicate=False, batch_key=idempotency_key)
