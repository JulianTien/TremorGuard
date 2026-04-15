from fastapi import APIRouter

from app.api.routes import (
    ai,
    auth,
    dashboard,
    devices,
    ingest,
    medical_records,
    medications,
    me,
    rehab_guidance,
    reports,
)

api_router = APIRouter()
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(medications.router, prefix="/medications", tags=["medications"])
api_router.include_router(rehab_guidance.router, prefix="/rehab-guidance", tags=["rehab-guidance"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(medical_records.router, prefix="/medical-records", tags=["medical-records"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
