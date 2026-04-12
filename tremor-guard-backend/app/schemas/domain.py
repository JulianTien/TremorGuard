from datetime import date, datetime
from typing import Literal

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
