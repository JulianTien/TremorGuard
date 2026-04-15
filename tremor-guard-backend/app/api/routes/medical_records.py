from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Header, HTTPException, UploadFile, status

from app.api.deps import ClinicalSessionDep, CurrentUserDep
from app.schemas.domain import (
    CreateMedicalRecordArchiveRequest,
    CreateMedicalRecordArchiveResponse,
    CreateMedicalRecordReportRequest,
    CreateMedicalRecordReportResponse,
    MedicalRecordArchiveDetailDTO,
    MedicalRecordArchiveListResponse,
    MedicalRecordFileListResponse,
    MedicalRecordReportDetailDTO,
    MedicalRecordReportListResponse,
)
from app.services import medical_records as medical_records_service

router = APIRouter()


@router.get("/archives", response_model=MedicalRecordArchiveListResponse)
def list_archives(
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> MedicalRecordArchiveListResponse:
    return MedicalRecordArchiveListResponse(
        archives=medical_records_service.list_archives(clinical_session, current_user)
    )


@router.post(
    "/archives",
    response_model=CreateMedicalRecordArchiveResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_archive(
    payload: CreateMedicalRecordArchiveRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> CreateMedicalRecordArchiveResponse:
    try:
        return CreateMedicalRecordArchiveResponse(
            archive=medical_records_service.create_archive(clinical_session, current_user, payload)
        )
    except medical_records_service.MedicalRecordsServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/archives/{archive_id}", response_model=MedicalRecordArchiveDetailDTO)
def get_archive(
    archive_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> MedicalRecordArchiveDetailDTO:
    return medical_records_service.get_archive_detail(clinical_session, current_user, archive_id)


@router.get("/archives/{archive_id}/files", response_model=MedicalRecordFileListResponse)
def list_archive_files(
    archive_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> MedicalRecordFileListResponse:
    return MedicalRecordFileListResponse(
        files=medical_records_service.list_archive_files(clinical_session, current_user, archive_id)
    )


@router.post(
    "/archives/{archive_id}/files",
    response_model=MedicalRecordFileListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_archive_file(
    archive_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
    background_tasks: BackgroundTasks,
    file: list[UploadFile] | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
) -> MedicalRecordFileListResponse:
    archive = medical_records_service._ensure_archive_owner(clinical_session, current_user, archive_id)
    try:
        uploads = [*(file or []), *(files or [])]
        if not uploads:
            raise HTTPException(status_code=422, detail="至少需要上传一个病例文件。")
        stored_files = []
        for item in uploads:
            stored_file = await medical_records_service.store_archive_file(
                clinical_session,
                current_user,
                archive,
                item,
            )
            stored_files.append(stored_file)
            background_tasks.add_task(
                medical_records_service.run_file_processing_task,
                current_user.id,
                stored_file.id,
            )
        return MedicalRecordFileListResponse(files=stored_files)
    except medical_records_service.MedicalRecordsServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/archives/{archive_id}/files/{file_id}/content")
def get_archive_file_content(
    archive_id: str,
    file_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
):
    return medical_records_service.preview_medical_record_file(
        clinical_session,
        current_user,
        archive_id,
        file_id,
    )


@router.get("/archives/{archive_id}/reports", response_model=MedicalRecordReportListResponse)
def list_archive_reports(
    archive_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> MedicalRecordReportListResponse:
    return MedicalRecordReportListResponse(
        reports=medical_records_service.list_archive_reports(clinical_session, current_user, archive_id)
    )


@router.post(
    "/archives/{archive_id}/reports",
    response_model=CreateMedicalRecordReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    archive_id: str,
    payload: CreateMedicalRecordReportRequest,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
    background_tasks: BackgroundTasks,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CreateMedicalRecordReportResponse:
    archive = medical_records_service._ensure_archive_owner(clinical_session, current_user, archive_id)
    try:
        report = medical_records_service.create_report(
            clinical_session,
            current_user,
            archive,
            payload,
            idempotency_key=idempotency_key,
        )
        background_tasks.add_task(
            medical_records_service.run_report_processing_task,
            current_user.id,
            current_user.display_name,
            report.id,
        )
        return CreateMedicalRecordReportResponse(report=report)
    except medical_records_service.MedicalRecordsServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/reports/{report_id}", response_model=MedicalRecordReportDetailDTO)
def get_report(
    report_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
) -> MedicalRecordReportDetailDTO:
    return medical_records_service.get_report_detail(clinical_session, current_user, report_id)


@router.get("/reports/{report_id}/pdf")
def download_pdf(
    report_id: str,
    current_user: CurrentUserDep,
    clinical_session: ClinicalSessionDep,
):
    try:
        return medical_records_service.download_report_pdf(clinical_session, current_user, report_id)
    except medical_records_service.MedicalRecordsServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
