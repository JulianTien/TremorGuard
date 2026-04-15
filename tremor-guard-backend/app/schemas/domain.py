from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PatientProfileDTO(BaseModel):
    id: str
    name: str
    age: int
    gender: str
    diagnosis: str
    duration: str
    hospital: str
    device_id: str


class DeviceStatusDTO(BaseModel):
    battery: int
    connection: str
    connection_label: str
    last_sync: str
    available_days: str
    firmware: str


class TremorMetricSummaryDTO(BaseModel):
    label: str
    value: str | int | float
    unit: str
    subtitle: str
    tone: str


class TremorTrendPointDTO(BaseModel):
    time: str
    amplitude: float
    label: str | None = None
    medication_taken: bool = False


class AiInsightDTO(BaseModel):
    id: str
    title: str
    summary: str
    emphasis: str | None = None


class AiChatMessageInput(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AiChatMessageResponse(BaseModel):
    role: Literal["assistant"]
    content: str


class AiChatUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AiChatRequest(BaseModel):
    messages: list[AiChatMessageInput] = Field(min_length=1, max_length=20)


class AiChatResponse(BaseModel):
    message: AiChatMessageResponse
    model: str
    usage: AiChatUsage | None = None


class MedicationEntryDTO(BaseModel):
    id: int
    time: str
    name: str
    dose: str
    status: str


class ReportSummaryDTO(BaseModel):
    id: str
    date: date
    type: str
    size: str
    status: str


class ConsentSettingsDTO(BaseModel):
    share_with_doctor: bool
    rag_analysis_enabled: bool
    cloud_sync_enabled: bool


class MeProfileResponse(BaseModel):
    patient_profile: PatientProfileDTO
    device_status: DeviceStatusDTO
    consent_settings: ConsentSettingsDTO


class PatientProfileUpsertRequest(BaseModel):
    name: str
    age: int
    gender: str
    diagnosis: str
    duration: str
    hospital: str


class ProfileCompletionStatus(BaseModel):
    onboarding_state: str
    has_profile: bool
    has_bound_device: bool


class PatientProfileUpsertResponse(BaseModel):
    patient_profile: PatientProfileDTO
    completion: ProfileCompletionStatus


class DeviceBindingDTO(BaseModel):
    id: str
    device_serial: str
    device_name: str
    firmware_version: str
    binding_status: str
    bound_at: datetime | None = None
    unbound_at: datetime | None = None


class DeviceBindingRequest(BaseModel):
    device_serial: str
    activation_code: str


class DeviceBindingResponse(BaseModel):
    device_binding: DeviceBindingDTO | None
    completion: ProfileCompletionStatus


class BindingConflictError(BaseModel):
    code: str
    detail: str


class DashboardOverviewResponse(BaseModel):
    metric_summaries: list[TremorMetricSummaryDTO]
    device_status: DeviceStatusDTO
    trend_points: list[TremorTrendPointDTO]
    overview_insight: AiInsightDTO


class MedicationListResponse(BaseModel):
    medication_entries: list[MedicationEntryDTO]


class CreateMedicationRequest(BaseModel):
    taken_at: datetime
    name: str
    dose: str
    status: str


class UpdateMedicationRequest(BaseModel):
    taken_at: datetime | None = None
    name: str | None = None
    dose: str | None = None
    status: str | None = None


class ReportListResponse(BaseModel):
    report_summaries: list[ReportSummaryDTO]


class CreateReportRequest(BaseModel):
    report_date: date | None = None
    report_type: str = "周度病情评估摘要"


class CreateReportResponse(BaseModel):
    report: ReportSummaryDTO


class TremorEventIngestItem(BaseModel):
    start_at: datetime
    duration_sec: int
    dominant_hz: float
    rms_amplitude: float
    confidence: float
    source: str


class TremorEventIngestRequest(BaseModel):
    items: list[TremorEventIngestItem]


class TremorIngestResponse(BaseModel):
    accepted_count: int
    duplicate: bool
    batch_key: str | None


AsyncJobStatus = Literal["queued", "processing", "succeeded", "failed"]
RehabPlanStatus = Literal[
    "active_only",
    "candidate_pending_confirmation",
    "candidate_confirmed",
    "candidate_superseded",
]
RehabConflictStatus = Literal["consistent", "conflicting", "insufficient_data"]
RehabGenerationEligibility = Literal["eligible", "insufficient_data"]


class MedicalRecordExtractionDTO(BaseModel):
    id: str
    version: int
    status: AsyncJobStatus
    error_summary: str | None = None
    document_type: str | None = None
    summary_text: str | None = None
    raw_text: str | None = None
    structured_payload: dict[str, Any] | None = None
    source_model: str | None = None
    prompt_version: str | None = None
    completed_at: datetime | None = None
    updated_at: datetime


class MedicalRecordFileDTO(BaseModel):
    id: str
    archive_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    processing_status: AsyncJobStatus
    processing_error: str | None = None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None = None
    latest_extraction: MedicalRecordExtractionDTO | None = None


class MedicalRecordArchiveSummaryDTO(BaseModel):
    id: str
    title: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    file_count: int
    report_count: int
    latest_activity_at: datetime | None = None
    latest_report: "MedicalRecordReportSummaryDTO | None" = None


class MedicalRecordArchiveDetailDTO(MedicalRecordArchiveSummaryDTO):
    disclaimer: str
    consent_policy: str
    retention_policy: str
    delete_policy: str
    export_policy: str
    files: list[MedicalRecordFileDTO] = Field(default_factory=list)
    reports: list["MedicalRecordReportSummaryDTO"] = Field(default_factory=list)


class MedicalRecordArchiveListResponse(BaseModel):
    archives: list[MedicalRecordArchiveSummaryDTO]


class CreateMedicalRecordArchiveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)


class CreateMedicalRecordArchiveResponse(BaseModel):
    archive: MedicalRecordArchiveDetailDTO


class UploadMedicalRecordFileResponse(BaseModel):
    file: MedicalRecordFileDTO


class MedicalRecordFileListResponse(BaseModel):
    files: list[MedicalRecordFileDTO]


class CreateMedicalRecordReportRequest(BaseModel):
    report_window_days: int = Field(default=30, ge=7, le=365)
    monitoring_window_days: int = Field(default=30, ge=7, le=365)
    medication_window_days: int = Field(default=30, ge=7, le=365)


class MedicalRecordReportSummaryDTO(BaseModel):
    id: str
    archive_id: str
    archive_title: str | None = None
    version: int
    title: str
    status: AsyncJobStatus
    pdf_status: AsyncJobStatus
    error_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    generated_at: datetime | None = None
    summary: str | None = None
    pdf_ready: bool
    pdf_file_name: str | None = None
    report_window_label: str | None = None


class MedicalRecordReportDetailDTO(MedicalRecordReportSummaryDTO):
    archive_description: str | None = None
    disclaimer: str
    disclaimer_version: str
    model_name: str | None = None
    prompt_version: str | None = None
    report_window_start: date
    report_window_end: date
    monitoring_window_start: date
    monitoring_window_end: date
    medication_window_start: date
    medication_window_end: date
    input_snapshot: dict[str, Any] | None = None
    report_payload: dict[str, Any] | None = None
    narrative_text: str | None = None
    has_pdf: bool
    sections: list[dict[str, str]] = Field(default_factory=list)
    source_files: list[MedicalRecordFileDTO] = Field(default_factory=list)
    history: list[MedicalRecordReportSummaryDTO] = Field(default_factory=list)


class MedicalRecordReportListResponse(BaseModel):
    reports: list[MedicalRecordReportSummaryDTO]


class CreateMedicalRecordReportResponse(BaseModel):
    report: MedicalRecordReportSummaryDTO


class RehabPlanItemDTO(BaseModel):
    template_id: str
    name: str
    category: str
    duration_minutes: int
    frequency_label: str
    cautions: list[str] = Field(default_factory=list)


class RehabPlanDTO(BaseModel):
    id: str
    title: str
    status: RehabPlanStatus
    scenario: str
    version: int
    rationale: str
    items: list[RehabPlanItemDTO]
    risk_flags: list[str] = Field(default_factory=list)
    requires_confirmation: bool
    difference_summary: str | None = None
    generated_at: datetime
    confirmed_at: datetime | None = None
    activated_at: datetime | None = None


class RehabEvidenceSummaryDTO(BaseModel):
    as_of_date: date
    evaluation_window: Literal["calendar_day"]
    medication_window_summary: str
    tremor_trend_summary: str
    signal_consistency: RehabConflictStatus
    explanation: str
    generation_eligibility: RehabGenerationEligibility
    missing_inputs: list[str] = Field(default_factory=list)


class RehabGuidanceResponse(BaseModel):
    active_plan: RehabPlanDTO | None = None
    candidate_plan: RehabPlanDTO | None = None
    evidence_summary: RehabEvidenceSummaryDTO
    conflict_status: RehabConflictStatus
    disclaimer: str
    generated_at: datetime | None = None


class GenerateRehabGuidanceRequest(BaseModel):
    as_of_date: date


MedicalRecordArchiveSummaryDTO.model_rebuild()
MedicalRecordArchiveDetailDTO.model_rebuild()
MedicalRecordReportDetailDTO.model_rebuild()
