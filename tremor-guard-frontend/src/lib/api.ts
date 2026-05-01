import type {
  AiChatAction,
  AiChatActionCard,
  AiChatUsage,
  AiInsight,
  AuthSession,
  ChatMessage,
  ConsentSettings,
  CurrentUser,
  DeviceBinding,
  DeviceStatus,
  HealthReportDetail,
  HealthReportSummary,
  LegacyMonitoringReportSummary,
  MedicalRecordArchiveDetail,
  MedicalRecordArchiveSummary,
  MedicalRecordFile,
  MedicalRecordInputSnapshot,
  MedicalRecordProcessingStatus,
  MedicalRecordReportDetail,
  MedicalRecordReportPipelineState,
  MedicalRecordReportSection,
  MedicalRecordReportSummary,
  MedicationEntry,
  OverviewEvidenceReadiness,
  PatientProfile,
  ProfileCompletionStatus,
  RehabConflictStatus,
  RehabGenerationEligibility,
  RehabGuidanceViewData,
  RehabPlan,
  RehabPlanItem,
  RehabPlanStatus,
  TremorMetricSummary,
  TremorTrendPoint,
} from '../types/domain'

function resolveApiBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  if (typeof window !== 'undefined') {
    const localHosts = new Set(['localhost', '127.0.0.1', '::1'])
    if (localHosts.has(window.location.hostname)) {
      return `${window.location.protocol}//${window.location.hostname}:8000`
    }

    return window.location.origin
  }

  return 'http://127.0.0.1:8000'
}

const API_BASE_URL = resolveApiBaseUrl()
const SESSION_KEY = 'tremor-guard-session'
const REQUEST_TIMEOUT_MS = 15000
export const AUTH_EVENT = 'tremor-guard-auth-changed'
export const DEFAULT_DATA_DATE = '2026-04-05'

interface BackendCurrentUser {
  id: string
  email: string
  display_name: string
  status: string
  onboarding_state: CurrentUser['onboardingState']
  last_login_at?: string | null
  has_profile: boolean
  has_bound_device: boolean
  bound_device_serial?: string | null
}

interface BackendAuthResponse {
  access_token: string
  refresh_token: string
  user_id: string
  access_token_expires_at: string
  refresh_token_expires_at: string
  current_user: BackendCurrentUser
}

interface BackendCurrentUserResponse {
  user: BackendCurrentUser
}

interface BackendCompletionStatus {
  onboarding_state: ProfileCompletionStatus['onboardingState']
  has_profile: boolean
  has_bound_device: boolean
}

interface BackendOverviewResponse {
  metric_summaries: Array<{
    label: string
    value: string | number
    unit: string
    subtitle: string
    tone: 'neutral' | 'safe' | 'alert'
  }>
  device_status: {
    battery: number
    connection: 'stable' | 'syncing' | 'offline'
    connection_label: string
    last_sync: string
    available_days: string
    firmware: string
  }
  trend_points: Array<{
    time: string
    amplitude: number
    label?: string
    medication_taken?: boolean
  }>
  overview_insight: {
    id: string
    title: string
    summary: string
    emphasis?: string
  }
  evidence_readiness: {
    has_device_binding: boolean
    has_monitoring_events: boolean
    monitoring_event_count: number
    has_medication_logs: boolean
    medication_log_count: number
    has_medical_record_archives: boolean
    medical_record_archive_count: number
    ai_interpretation_ready: boolean
    rehab_plan_ready: boolean
    health_report_ready: boolean
    next_steps: string[]
  }
}

interface BackendProfileResponse {
  patient_profile: Omit<PatientProfile, 'deviceId'> & { device_id: string }
  device_status: BackendOverviewResponse['device_status']
  consent_settings: {
    share_with_doctor: boolean
    rag_analysis_enabled: boolean
    cloud_sync_enabled: boolean
  }
}

interface BackendMedicationResponse {
  medication_entries: MedicationEntry[]
}

interface BackendRehabPlanItem {
  template_id: string
  name: string
  category: string
  duration_minutes: number
  frequency_label: string
  cautions?: string[] | null
  goal?: string | null
  preparation?: string[] | null
  steps?: string[] | null
  completion_check?: string | null
}

interface BackendRehabPlan {
  id: string
  title?: string | null
  status: string
  scenario: string
  version: number
  rationale: string
  items: BackendRehabPlanItem[]
  risk_flags?: Array<string | { label?: string | null; message?: string | null }> | null
  requires_confirmation: boolean
  generated_at?: string | null
  confirmed_at?: string | null
  activated_at?: string | null
  difference_summary?: string | null
}

interface BackendRehabEvidenceSummary {
  as_of_date?: string | null
  evaluation_window?: string | null
  medication_window_summary?: string | null
  tremor_trend_summary?: string | null
  signal_consistency?: string | null
  explanation?: string | null
  generation_eligibility?: string | null
  missing_inputs?: Array<string | null> | null
}

interface BackendRehabGuidanceResponse {
  active_plan?: BackendRehabPlan | null
  candidate_plan?: BackendRehabPlan | null
  evidence_summary?: BackendRehabEvidenceSummary | null
  conflict_status?: string | null
  disclaimer?: string | null
  generated_at?: string | null
}

interface BackendReportsResponse {
  report_summaries: Array<{
    id: string
    date: string
    type: string
    size: string
    status: string
    kind?: 'legacy_monitoring_summary'
  }>
}

interface BackendHealthReportsResponse {
  health_reports: BackendMedicalRecordReportSummary[]
}

interface BackendMedicalRecordArchiveSummary {
  id: string
  title: string
  description?: string | null
  created_at: string
  updated_at: string
  file_count: number
  report_count: number
  latest_activity_at?: string | null
  latest_report?: {
    id: string
    version: number
    status: MedicalRecordProcessingStatus
  } | null
}

interface BackendMedicalRecordExtraction {
  id: string
  version: number
  status: MedicalRecordProcessingStatus
  document_type?: string | null
  summary_text?: string | null
  raw_text?: string | null
  structured_payload?: Record<string, unknown> | null
  source_model?: string | null
  prompt_version?: string | null
  completed_at?: string | null
  updated_at: string
  error_summary?: string | null
}

interface BackendMedicalRecordFile {
  id: string
  archive_id: string
  original_filename: string
  content_type: string
  size_bytes: number
  processing_status: MedicalRecordProcessingStatus
  processing_error?: string | null
  created_at: string
  updated_at: string
  processed_at?: string | null
  latest_extraction?: BackendMedicalRecordExtraction | null
}

interface BackendMedicalRecordReportSummary {
  id: string
  agent_type?: string | null
  archive_id: string
  archive_title?: string | null
  version: number
  title: string
  status: MedicalRecordProcessingStatus
  generated_at?: string | null
  summary?: string | null
  pdf_ready: boolean
  pdf_file_name?: string | null
  report_window_label?: string | null
  template_name?: string | null
  template_version?: string | null
  quality_warnings?: string[] | null
  pipeline_state?: {
    template: {
      status: MedicalRecordProcessingStatus
      started_at?: string | null
      completed_at?: string | null
      detail?: string | null
      error?: string | null
    }
    llm: {
      status: MedicalRecordProcessingStatus
      started_at?: string | null
      completed_at?: string | null
      detail?: string | null
      error?: string | null
    }
    pdf: {
      status: MedicalRecordProcessingStatus
      started_at?: string | null
      completed_at?: string | null
      detail?: string | null
      error?: string | null
    }
    updated_at?: string | null
  } | null
}

interface BackendMedicalRecordArchiveDetailResponse {
  archive: BackendMedicalRecordArchiveSummary & {
    disclaimer: string
    files: BackendMedicalRecordFile[]
    reports: BackendMedicalRecordReportSummary[]
  }
}

interface BackendMedicalRecordArchivesResponse {
  archives: BackendMedicalRecordArchiveSummary[]
}

interface BackendMedicalRecordReportDetailResponse {
  report: BackendMedicalRecordReportSummary & {
    archive_description?: string | null
    disclaimer: string
    sections?: Array<{
      id?: string | null
      title: string
      body: string
    }> | null
    report_markdown?: string | null
    source_files?: BackendMedicalRecordFile[] | null
    history?: BackendMedicalRecordReportSummary[] | null
    input_snapshot?: {
      report_window?: string | { start?: string | null; end?: string | null } | null
      monitoring_window?: string | { start?: string | null; end?: string | null } | null
      medication_window?: string | { start?: string | null; end?: string | null } | null
      disclaimer_version?: string | null
      prompt_version?: string | null
      model_version?: string | null
    } | null
  }
}

interface BackendProfileUpsertResponse {
  patient_profile: Omit<PatientProfile, 'deviceId'> & { device_id: string }
  completion: BackendCompletionStatus
}

interface BackendAiChatResponse {
  message: {
    role: 'assistant'
    content: string
  }
  model: string
  usage?: {
    prompt_tokens?: number | null
    completion_tokens?: number | null
    total_tokens?: number | null
  } | null
  action_cards?: Array<{
    type: 'rehab_plan_candidate' | 'health_report_candidate'
    agent_type?: string | null
    title: string
    summary: string
    status: string
    resource_id: string
    resource_path?: string | null
    pipeline_state?: BackendMedicalRecordReportSummary['pipeline_state']
    actions?: Array<{
      key: string
      label: string
      kind: AiChatAction['kind']
      api_path?: string | null
      url?: string | null
      download_name?: string | null
    }> | null
  }> | null
}

interface BackendDeviceBinding {
  id: string
  device_serial: string
  device_name: string
  firmware_version: string
  binding_status: string
  bound_at?: string | null
  unbound_at?: string | null
}

interface BackendDeviceBindingResponse {
  device_binding: BackendDeviceBinding | null
  completion: BackendCompletionStatus
}

export interface AuthResult {
  session: AuthSession
  currentUser: CurrentUser
}

export interface OverviewViewData {
  metricSummaries: TremorMetricSummary[]
  deviceStatus: DeviceStatus
  trendPoints: TremorTrendPoint[]
  overviewInsight: AiInsight
  evidenceReadiness: OverviewEvidenceReadiness
}

export interface ProfileViewData {
  patientProfile: PatientProfile
  deviceStatus: DeviceStatus
  consentSettings: ConsentSettings
}

interface DownloadFileNameOptions {
  preferredName?: string | null
  patientName?: string | null
  generatedAt?: string | null
  version?: number | null
  reportId?: string | null
  defaultLabel?: string
}

export interface PatientProfileInput {
  name: string
  age: number
  gender: string
  diagnosis: string
  duration: string
  hospital: string
}

export interface DeviceBindingInput {
  deviceSerial: string
  activationCode: string
}

export interface AiChatResult {
  message: {
    role: 'assistant'
    content: string
  }
  model: string
  usage?: AiChatUsage | null
  actionCards: AiChatActionCard[]
}

type BackendAiChatStreamDonePayload = BackendAiChatResponse

interface StreamAiChatOptions {
  onChunk?: (content: string) => void
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function mapCurrentUser(user: BackendCurrentUser): CurrentUser {
  return {
    id: user.id,
    email: user.email,
    displayName: user.display_name,
    status: user.status,
    onboardingState: user.onboarding_state,
    lastLoginAt: user.last_login_at,
    hasProfile: user.has_profile,
    hasBoundDevice: user.has_bound_device,
    boundDeviceSerial: user.bound_device_serial,
  }
}

function mapCompletionStatus(status: BackendCompletionStatus): ProfileCompletionStatus {
  return {
    onboardingState: status.onboarding_state,
    hasProfile: status.has_profile,
    hasBoundDevice: status.has_bound_device,
  }
}

function mapDeviceStatus(status: BackendOverviewResponse['device_status']): DeviceStatus {
  return {
    battery: status.battery,
    connection: status.connection,
    connectionLabel: status.connection_label,
    lastSync: status.last_sync,
    availableDays: status.available_days,
    firmware: status.firmware,
  }
}

function mapOverviewEvidenceReadiness(
  readiness: BackendOverviewResponse['evidence_readiness'],
): OverviewEvidenceReadiness {
  return {
    hasDeviceBinding: readiness.has_device_binding,
    hasMonitoringEvents: readiness.has_monitoring_events,
    monitoringEventCount: readiness.monitoring_event_count,
    hasMedicationLogs: readiness.has_medication_logs,
    medicationLogCount: readiness.medication_log_count,
    hasMedicalRecordArchives: readiness.has_medical_record_archives,
    medicalRecordArchiveCount: readiness.medical_record_archive_count,
    aiInterpretationReady: readiness.ai_interpretation_ready,
    rehabPlanReady: readiness.rehab_plan_ready,
    healthReportReady: readiness.health_report_ready,
    nextSteps: readiness.next_steps,
  }
}

function mapDeviceBinding(binding: BackendDeviceBinding | null): DeviceBinding | null {
  if (!binding) {
    return null
  }

  return {
    id: binding.id,
    deviceSerial: binding.device_serial,
    deviceName: binding.device_name,
    firmwareVersion: binding.firmware_version,
    bindingStatus: binding.binding_status,
    boundAt: binding.bound_at,
    unboundAt: binding.unbound_at,
  }
}

function toSizeLabel(bytes?: number | null) {
  if (!bytes || bytes <= 0) {
    return '未知大小'
  }

  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  if (bytes >= 1024) {
    return `${Math.round(bytes / 1024)} KB`
  }

  return `${bytes} B`
}

function mapMedicalRecordArchiveSummary(
  archive: BackendMedicalRecordArchiveSummary,
): MedicalRecordArchiveSummary {
  return {
    id: archive.id,
    title: archive.title,
    description: archive.description,
    createdAt: archive.created_at,
    updatedAt: archive.updated_at,
    fileCount: archive.file_count,
    reportCount: archive.report_count,
    latestActivityAt: archive.latest_activity_at,
    latestReportId: archive.latest_report?.id ?? null,
    latestReportVersion: archive.latest_report?.version ?? null,
    latestReportStatus: archive.latest_report?.status ?? null,
  }
}

function mapMedicalRecordExtraction(
  extraction: BackendMedicalRecordExtraction | null | undefined,
) {
  if (!extraction) {
    return null
  }

  return {
    status: extraction.status,
    summary: extraction.summary_text,
    highlights: Array.isArray(extraction.structured_payload?.information_gaps)
      ? extraction.structured_payload.information_gaps.map((item) => String(item))
      : [],
    extractedAt: extraction.completed_at,
    errorSummary: extraction.error_summary,
  }
}

function mapMedicalRecordFile(file: BackendMedicalRecordFile): MedicalRecordFile {
  return {
    id: file.id,
    archiveId: file.archive_id,
    fileName: file.original_filename,
    fileType: file.content_type,
    sizeLabel: toSizeLabel(file.size_bytes),
    uploadedAt: file.created_at,
    processingStatus: file.processing_status,
    previewUrl: `${API_BASE_URL}/v1/medical-records/archives/${file.archive_id}/files/${file.id}/content`,
    statusSummary: file.processing_error ?? undefined,
    extraction: mapMedicalRecordExtraction(file.latest_extraction),
  }
}

function mapReportPipelineState(
  pipelineState?: BackendMedicalRecordReportSummary['pipeline_state'] | null,
): MedicalRecordReportPipelineState | null {
  if (!pipelineState) {
    return null
  }

  return {
    template: {
      status: pipelineState.template.status,
      startedAt: pipelineState.template.started_at,
      completedAt: pipelineState.template.completed_at,
      detail: pipelineState.template.detail,
      error: pipelineState.template.error,
    },
    llm: {
      status: pipelineState.llm.status,
      startedAt: pipelineState.llm.started_at,
      completedAt: pipelineState.llm.completed_at,
      detail: pipelineState.llm.detail,
      error: pipelineState.llm.error,
    },
    pdf: {
      status: pipelineState.pdf.status,
      startedAt: pipelineState.pdf.started_at,
      completedAt: pipelineState.pdf.completed_at,
      detail: pipelineState.pdf.detail,
      error: pipelineState.pdf.error,
    },
    updatedAt: pipelineState.updated_at,
  }
}

function mapMedicalRecordReportSummary(
  report: BackendMedicalRecordReportSummary,
  archiveTitleFallback = '',
): MedicalRecordReportSummary {
  return {
    id: report.id,
    agentType: report.agent_type,
    archiveId: report.archive_id,
    archiveTitle: report.archive_title ?? archiveTitleFallback,
    version: report.version,
    title: report.title,
    status: report.status,
    generatedAt: report.generated_at,
    summary: report.summary,
    pdfReady: report.pdf_ready,
    pdfFileName: report.pdf_file_name,
    reportWindowLabel: report.report_window_label,
    templateName: report.template_name,
    templateVersion: report.template_version,
    pipelineState: mapReportPipelineState(report.pipeline_state),
    qualityWarnings: (report.quality_warnings ?? []).map((warning) => String(warning)),
  }
}

function mapMedicalRecordInputSnapshot(
  snapshot: BackendMedicalRecordReportDetailResponse['report']['input_snapshot'],
): MedicalRecordInputSnapshot | null {
  if (!snapshot) {
    return null
  }

  const formatWindow = (
    value?: string | { start?: string | null; end?: string | null } | null,
  ) => {
    if (!value) {
      return null
    }

    if (typeof value === 'string') {
      return value
    }

    if (value.start && value.end) {
      return `${value.start} 至 ${value.end}`
    }

    return value.start ?? value.end ?? null
  }

  return {
    reportWindow: formatWindow(snapshot.report_window),
    monitoringWindow: formatWindow(snapshot.monitoring_window),
    medicationWindow: formatWindow(snapshot.medication_window),
    disclaimerVersion: snapshot.disclaimer_version,
    promptVersion: snapshot.prompt_version,
    modelVersion: snapshot.model_version,
  }
}

function mapAiChatAction(action: NonNullable<NonNullable<BackendAiChatResponse['action_cards']>[number]['actions']>[number]): AiChatAction {
  return {
    key: action.key,
    label: action.label,
    kind: action.kind,
    apiPath: action.api_path ?? null,
    url: action.url ?? null,
    downloadName: action.download_name ?? null,
  }
}

function mapAiChatActionCard(
  card: NonNullable<BackendAiChatResponse['action_cards']>[number],
): AiChatActionCard {
  return {
    type: card.type,
    agentType: card.agent_type ?? null,
    title: card.title,
    summary: card.summary,
    status: card.status,
    resourceId: card.resource_id,
    resourcePath: card.resource_path ?? null,
    pipelineState: mapReportPipelineState(card.pipeline_state),
    actions: (card.actions ?? []).map(mapAiChatAction),
  }
}

function mapAiChatResult(payload: BackendAiChatResponse): AiChatResult {
  return {
    message: payload.message,
    model: payload.model,
    usage: payload.usage
      ? {
          promptTokens: payload.usage.prompt_tokens,
          completionTokens: payload.usage.completion_tokens,
          totalTokens: payload.usage.total_tokens,
        }
      : null,
    actionCards: (payload.action_cards ?? []).map(mapAiChatActionCard),
  }
}

function parseSseEventBlock(block: string) {
  let event = 'message'
  const dataLines: string[] = []

  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim() || 'message'
      continue
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }

  return {
    event,
    data: dataLines.join('\n'),
  }
}

function mapRiskLabel(
  riskFlag: string | { label?: string | null; message?: string | null } | null | undefined,
) {
  if (!riskFlag) {
    return null
  }

  if (typeof riskFlag === 'string') {
    return riskFlag
  }

  return riskFlag.message ?? riskFlag.label ?? null
}

function mapRehabPlanStatus(status: string): RehabPlanStatus {
  switch (status) {
    case 'active_only':
    case 'candidate_pending_confirmation':
    case 'candidate_confirmed':
    case 'candidate_superseded':
      return status
    default:
      return 'candidate_pending_confirmation'
  }
}

function mapRehabPlanItem(item: BackendRehabPlanItem): RehabPlanItem {
  return {
    templateId: item.template_id,
    name: item.name,
    category: item.category,
    durationMinutes: item.duration_minutes,
    frequencyLabel: item.frequency_label,
    cautions: (item.cautions ?? []).map((caution) => String(caution)),
    goal: item.goal ?? null,
    preparation: (item.preparation ?? []).map((step) => String(step)),
    steps: (item.steps ?? []).map((step) => String(step)),
    completionCheck: item.completion_check ?? null,
  }
}

function mapRehabPlan(plan: BackendRehabPlan | null | undefined): RehabPlan | null {
  if (!plan) {
    return null
  }

  return {
    id: plan.id,
    title: plan.title ?? '个性化训练计划',
    status: mapRehabPlanStatus(plan.status),
    scenario: plan.scenario,
    version: plan.version,
    rationale: plan.rationale,
    items: plan.items.map(mapRehabPlanItem),
    riskFlags: (plan.risk_flags ?? [])
      .map((riskFlag) => mapRiskLabel(riskFlag))
      .filter((riskFlag): riskFlag is string => Boolean(riskFlag)),
    requiresConfirmation: plan.requires_confirmation,
    generatedAt: plan.generated_at,
    confirmedAt: plan.confirmed_at,
    activatedAt: plan.activated_at,
  }
}

function mapRehabConflictStatus(status?: string | null): RehabConflictStatus {
  switch (status) {
    case 'consistent':
    case 'conflicting':
    case 'insufficient_data':
      return status
    default:
      return 'unknown'
  }
}

function mapRehabGenerationEligibility(
  status?: string | null,
): RehabGenerationEligibility {
  return status === 'eligible' ? 'eligible' : 'insufficient_data'
}

function mapRehabGuidanceResponse(
  payload: BackendRehabGuidanceResponse,
): RehabGuidanceViewData {
  if (
    !payload.disclaimer ||
    !payload.evidence_summary?.as_of_date ||
    !payload.evidence_summary.evaluation_window ||
    !payload.evidence_summary.medication_window_summary ||
    !payload.evidence_summary.tremor_trend_summary ||
    !payload.evidence_summary.signal_consistency ||
    !payload.evidence_summary.explanation ||
    !payload.conflict_status ||
    !payload.evidence_summary.generation_eligibility ||
    !Array.isArray(payload.evidence_summary.missing_inputs)
  ) {
    throw new ApiError(500, '康复训练计划响应缺少必要字段，暂时无法渲染页面。')
  }

  return {
    activePlan: mapRehabPlan(payload.active_plan),
    candidatePlan: mapRehabPlan(payload.candidate_plan),
    evidenceSummary: {
      asOfDate: payload.evidence_summary.as_of_date,
      evaluationWindow: payload.evidence_summary.evaluation_window,
      medicationWindowSummary: payload.evidence_summary.medication_window_summary,
      tremorTrendSummary: payload.evidence_summary.tremor_trend_summary,
      signalConsistency: payload.evidence_summary.signal_consistency,
      explanation: payload.evidence_summary.explanation,
    },
    conflictStatus: mapRehabConflictStatus(payload.conflict_status),
    disclaimer: payload.disclaimer,
    generatedAt: payload.generated_at,
    generationEligibility: mapRehabGenerationEligibility(
      payload.evidence_summary.generation_eligibility,
    ),
    missingInputs: payload.evidence_summary.missing_inputs
      .map((input) => (input ? String(input) : null))
      .filter((input): input is string => Boolean(input)),
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  const rawBody = await response.text()
  const hasJson = response.headers.get('content-type')?.includes('application/json')
  const payload = hasJson && rawBody ? (JSON.parse(rawBody) as Record<string, unknown>) : null

  if (!response.ok) {
    const detail =
      (typeof payload?.detail === 'string' && payload.detail) ||
      rawBody ||
      `Request failed with status ${response.status}`
    throw new ApiError(response.status, detail)
  }

  if (!rawBody) {
    return {} as T
  }

  return (payload ?? JSON.parse(rawBody)) as T
}

function buildRequestHeaders(headers?: HeadersInit, includeJson = false): Headers {
  const requestHeaders = new Headers(headers)
  if (includeJson && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json')
  }
  return requestHeaders
}

async function fetchWithTimeout(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => {
    controller.abort()
  }, REQUEST_TIMEOUT_MS)

  try {
    return await fetch(input, {
      ...init,
      signal: init?.signal ?? controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(408, '请求超时，请确认后端服务正在运行后重试。')
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

function sanitizeDownloadFileNameSegment(value?: string | null) {
  return (value ?? '')
    .normalize('NFKC')
    .split('')
    .map((character) => {
      const codePoint = character.charCodeAt(0)
      if ('<>:"/\\|?*'.includes(character) || codePoint < 32) {
        return ' '
      }
      return character
    })
    .join('')
    .replace(/\s+/g, ' ')
    .trim()
}

function buildDownloadFileName({
  preferredName,
  patientName,
  generatedAt,
  version,
  reportId,
  defaultLabel = 'tremorguard-report',
}: DownloadFileNameOptions) {
  const normalizedPreferredName = sanitizeDownloadFileNameSegment(preferredName)
  if (normalizedPreferredName) {
    return normalizedPreferredName.toLowerCase().endsWith('.pdf')
      ? normalizedPreferredName
      : `${normalizedPreferredName}.pdf`
  }

  const normalizedPatientName = sanitizeDownloadFileNameSegment(patientName)
  const dateSegment = generatedAt
    ? sanitizeDownloadFileNameSegment(generatedAt).slice(0, 10).replace(/-/g, '')
    : ''
  const versionSegment =
    typeof version === 'number' && Number.isFinite(version) ? `v${version}` : ''
  const reportSegment = sanitizeDownloadFileNameSegment(reportId)
  const segments = [
    defaultLabel,
    normalizedPatientName,
    dateSegment,
    versionSegment,
    reportSegment && !versionSegment ? reportSegment : '',
  ].filter(Boolean)

  return `${segments.join('-') || 'tremorguard-report'}.pdf`
}

function notifyAuthChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_EVENT))
  }
}

function getSessionStorage() {
  return window.sessionStorage
}

export function loadStoredSession(): AuthSession | null {
  localStorage.removeItem(SESSION_KEY)

  const raw = getSessionStorage().getItem(SESSION_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as AuthSession
  } catch {
    getSessionStorage().removeItem(SESSION_KEY)
    return null
  }
}

function storeSession(session: AuthSession) {
  localStorage.removeItem(SESSION_KEY)
  getSessionStorage().setItem(SESSION_KEY, JSON.stringify(session))
  notifyAuthChanged()
}

export function clearStoredSession() {
  localStorage.removeItem(SESSION_KEY)
  getSessionStorage().removeItem(SESSION_KEY)
  notifyAuthChanged()
}

function persistAuthResponse(payload: BackendAuthResponse): AuthResult {
  const session = {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    userId: payload.user_id,
    accessTokenExpiresAt: payload.access_token_expires_at,
    refreshTokenExpiresAt: payload.refresh_token_expires_at,
  }
  storeSession(session)

  return {
    session,
    currentUser: mapCurrentUser(payload.current_user),
  }
}

async function postAuth(path: string, body: Record<string, unknown>): Promise<AuthResult> {
  const response = await fetchWithTimeout(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: buildRequestHeaders(undefined, true),
    body: JSON.stringify(body),
  })
  return persistAuthResponse(await parseJson<BackendAuthResponse>(response))
}

export async function loginUser(email: string, password: string): Promise<AuthResult> {
  return postAuth('/v1/auth/login', { email, password })
}

export async function registerUser(
  email: string,
  password: string,
  displayName: string,
): Promise<AuthResult> {
  return postAuth('/v1/auth/register', { email, password, display_name: displayName })
}

export async function refreshStoredSession(): Promise<AuthResult | null> {
  const session = loadStoredSession()
  if (!session) {
    return null
  }

  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/v1/auth/refresh`, {
      method: 'POST',
      headers: buildRequestHeaders(undefined, true),
      body: JSON.stringify({ refresh_token: session.refreshToken }),
    })
    return persistAuthResponse(await parseJson<BackendAuthResponse>(response))
  } catch {
    clearStoredSession()
    return null
  }
}

export async function logoutUser(refreshToken?: string) {
  const session = loadStoredSession()
  const token = refreshToken ?? session?.refreshToken

  if (!token) {
    clearStoredSession()
    return
  }

  try {
    await fetchWithTimeout(`${API_BASE_URL}/v1/auth/logout`, {
      method: 'POST',
      headers: buildRequestHeaders(undefined, true),
      body: JSON.stringify({ refresh_token: token }),
    })
  } finally {
    clearStoredSession()
  }
}

async function authenticatedFetch(path: string, init?: RequestInit, retry = true): Promise<Response> {
  const session = loadStoredSession()
  if (!session) {
    throw new ApiError(401, '会话已过期，请重新登录。')
  }

  const includeJson = Boolean(init?.body) && !(init?.body instanceof FormData)
  const headers = buildRequestHeaders(init?.headers, includeJson)
  headers.set('Authorization', `Bearer ${session.accessToken}`)

  const response = await fetchWithTimeout(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })

  if (response.status === 401 && retry) {
    const refreshed = await refreshStoredSession()
    if (!refreshed) {
      throw new ApiError(401, '登录状态已失效，请重新登录。')
    }
    return authenticatedFetch(path, init, false)
  }

  return response
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await authenticatedFetch('/v1/me')
  const payload = await parseJson<BackendCurrentUserResponse>(response)
  return mapCurrentUser(payload.user)
}

export async function getProfile(): Promise<ProfileViewData> {
  const response = await authenticatedFetch('/v1/me/profile')
  const payload = await parseJson<BackendProfileResponse>(response)

  return {
    patientProfile: {
      ...payload.patient_profile,
      deviceId: payload.patient_profile.device_id,
    },
    deviceStatus: mapDeviceStatus(payload.device_status),
    consentSettings: {
      shareWithDoctor: payload.consent_settings.share_with_doctor,
      ragAnalysisEnabled: payload.consent_settings.rag_analysis_enabled,
      cloudSyncEnabled: payload.consent_settings.cloud_sync_enabled,
    },
  }
}

export async function updateProfile(
  payload: PatientProfileInput,
): Promise<{ patientProfile: PatientProfile; completion: ProfileCompletionStatus }> {
  const response = await authenticatedFetch('/v1/me/profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
  const result = await parseJson<BackendProfileUpsertResponse>(response)

  return {
    patientProfile: {
      ...result.patient_profile,
      deviceId: result.patient_profile.device_id,
    },
    completion: mapCompletionStatus(result.completion),
  }
}

export async function getDeviceBinding(): Promise<{
  deviceBinding: DeviceBinding | null
  completion: ProfileCompletionStatus
}> {
  const response = await authenticatedFetch('/v1/me/device-binding')
  const payload = await parseJson<BackendDeviceBindingResponse>(response)

  return {
    deviceBinding: mapDeviceBinding(payload.device_binding),
    completion: mapCompletionStatus(payload.completion),
  }
}

export async function bindDevice(
  payload: DeviceBindingInput,
): Promise<{ deviceBinding: DeviceBinding | null; completion: ProfileCompletionStatus }> {
  const response = await authenticatedFetch('/v1/me/device-binding', {
    method: 'POST',
    body: JSON.stringify({
      device_serial: payload.deviceSerial,
      activation_code: payload.activationCode,
    }),
  })
  const result = await parseJson<BackendDeviceBindingResponse>(response)

  return {
    deviceBinding: mapDeviceBinding(result.device_binding),
    completion: mapCompletionStatus(result.completion),
  }
}

export async function bindDemoDevice(): Promise<{
  deviceBinding: DeviceBinding | null
  completion: ProfileCompletionStatus
}> {
  const response = await authenticatedFetch('/v1/me/device-binding/demo', {
    method: 'POST',
  })
  const result = await parseJson<BackendDeviceBindingResponse>(response)

  return {
    deviceBinding: mapDeviceBinding(result.device_binding),
    completion: mapCompletionStatus(result.completion),
  }
}

export async function unbindDevice(): Promise<{
  deviceBinding: DeviceBinding | null
  completion: ProfileCompletionStatus
}> {
  const response = await authenticatedFetch('/v1/me/device-binding', {
    method: 'DELETE',
  })
  const result = await parseJson<BackendDeviceBindingResponse>(response)

  return {
    deviceBinding: mapDeviceBinding(result.device_binding),
    completion: mapCompletionStatus(result.completion),
  }
}

export async function getOverview(date = DEFAULT_DATA_DATE): Promise<OverviewViewData> {
  const response = await authenticatedFetch(`/v1/dashboard/overview?date=${date}`)
  const payload = await parseJson<BackendOverviewResponse>(response)

  return {
    metricSummaries: payload.metric_summaries,
    deviceStatus: mapDeviceStatus(payload.device_status),
    trendPoints: payload.trend_points.map((point) => ({
      time: point.time,
      amplitude: point.amplitude,
      label: point.label,
      medicationTaken: point.medication_taken,
    })),
    overviewInsight: payload.overview_insight,
    evidenceReadiness: mapOverviewEvidenceReadiness(payload.evidence_readiness),
  }
}

export async function getMedicationEntries(date = DEFAULT_DATA_DATE): Promise<MedicationEntry[]> {
  const response = await authenticatedFetch(`/v1/medications?date=${date}`)
  const payload = await parseJson<BackendMedicationResponse>(response)
  return payload.medication_entries
}

export async function getLegacyMonitoringSummaries(): Promise<LegacyMonitoringReportSummary[]> {
  const response = await authenticatedFetch('/v1/reports')
  const payload = await parseJson<BackendReportsResponse>(response)
  return payload.report_summaries.map((report) => ({
    id: report.id,
    date: report.date,
    type: report.type,
    size: report.size,
    status: report.status,
    kind: report.kind ?? 'legacy_monitoring_summary',
  }))
}

export async function getReports(): Promise<LegacyMonitoringReportSummary[]> {
  return getLegacyMonitoringSummaries()
}

export async function createReport(date = DEFAULT_DATA_DATE) {
  const response = await authenticatedFetch('/v1/reports', {
    method: 'POST',
    body: JSON.stringify({ report_date: date }),
  })
  return parseJson(response)
}

export async function getHealthReports(): Promise<HealthReportSummary[]> {
  const response = await authenticatedFetch('/v1/health-reports')
  const payload = await parseJson<BackendHealthReportsResponse>(response)
  return payload.health_reports.map((report) => mapMedicalRecordReportSummary(report))
}

export async function getMedicalRecordArchives(): Promise<MedicalRecordArchiveSummary[]> {
  const response = await authenticatedFetch('/v1/medical-records/archives')
  const payload = await parseJson<BackendMedicalRecordArchivesResponse>(response)
  return payload.archives.map(mapMedicalRecordArchiveSummary)
}

export async function createMedicalRecordArchive(payload: {
  title: string
  description?: string
}): Promise<MedicalRecordArchiveDetail> {
  const response = await authenticatedFetch('/v1/medical-records/archives', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  const result = await parseJson<BackendMedicalRecordArchiveDetailResponse>(response)

  return {
    ...mapMedicalRecordArchiveSummary(result.archive),
    disclaimer: result.archive.disclaimer,
    files: result.archive.files.map(mapMedicalRecordFile),
    reports: result.archive.reports.map((report) =>
      mapMedicalRecordReportSummary(report, result.archive.title),
    ),
  }
}

export async function getMedicalRecordArchive(archiveId: string): Promise<MedicalRecordArchiveDetail> {
  const response = await authenticatedFetch(`/v1/medical-records/archives/${archiveId}`)
  const payload = await parseJson<BackendMedicalRecordArchiveDetailResponse['archive']>(response)

  return {
    ...mapMedicalRecordArchiveSummary(payload),
    disclaimer: payload.disclaimer,
    files: payload.files.map(mapMedicalRecordFile),
    reports: payload.reports.map((report) =>
      mapMedicalRecordReportSummary(report, payload.title),
    ),
  }
}

export async function uploadMedicalRecordFiles(archiveId: string, files: File[]) {
  const body = new FormData()
  files.forEach((file) => {
    body.append('files', file)
  })

  const response = await authenticatedFetch(`/v1/medical-records/archives/${archiveId}/files`, {
    method: 'POST',
    body,
  })

  return parseJson(response)
}

export async function createMedicalRecordReport(
  archiveId: string,
): Promise<MedicalRecordReportSummary> {
  const response = await authenticatedFetch(`/v1/medical-records/archives/${archiveId}/reports`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  const payload = await parseJson<BackendMedicalRecordReportDetailResponse>(response)
  return mapMedicalRecordReportSummary(payload.report)
}

export async function getMedicalRecordReport(reportId: string): Promise<MedicalRecordReportDetail> {
  const response = await authenticatedFetch(`/v1/medical-records/reports/${reportId}`)
  const payload = await parseJson<BackendMedicalRecordReportDetailResponse['report']>(response)

  const sections: MedicalRecordReportSection[] = (payload.sections ?? []).map(
    (section, index) => ({
      id: section.id ?? `${payload.id}-section-${index}`,
      title: section.title,
      body: section.body,
    }),
  )

  return {
    ...mapMedicalRecordReportSummary(payload),
    disclaimer: payload.disclaimer,
    archiveDescription: payload.archive_description,
    reportMarkdown: payload.report_markdown,
    sections,
    sourceFiles: (payload.source_files ?? []).map(mapMedicalRecordFile),
    history: (payload.history ?? []).map((report) =>
      mapMedicalRecordReportSummary(report, payload.archive_title ?? ''),
    ),
    inputSnapshot: mapMedicalRecordInputSnapshot(payload.input_snapshot),
  }
}

export async function getHealthReport(reportId: string): Promise<HealthReportDetail> {
  const response = await authenticatedFetch(`/v1/health-reports/${reportId}`)
  const payload = await parseJson<BackendMedicalRecordReportDetailResponse['report']>(response)

  const sections: MedicalRecordReportSection[] = (payload.sections ?? []).map(
    (section, index) => ({
      id: section.id ?? `${payload.id}-section-${index}`,
      title: section.title,
      body: section.body,
    }),
  )

  return {
    ...mapMedicalRecordReportSummary(payload),
    disclaimer: payload.disclaimer,
    archiveDescription: payload.archive_description,
    reportMarkdown: payload.report_markdown,
    sections,
    sourceFiles: (payload.source_files ?? []).map(mapMedicalRecordFile),
    history: (payload.history ?? []).map((report) =>
      mapMedicalRecordReportSummary(report, payload.archive_title ?? ''),
    ),
    inputSnapshot: mapMedicalRecordInputSnapshot(payload.input_snapshot),
  }
}

export async function getRehabGuidance(
  asOfDate = DEFAULT_DATA_DATE,
): Promise<RehabGuidanceViewData> {
  const response = await authenticatedFetch(`/v1/rehab-guidance?as_of_date=${asOfDate}`)
  const payload = await parseJson<BackendRehabGuidanceResponse>(response)
  return mapRehabGuidanceResponse(payload)
}

export async function generateRehabGuidance(
  asOfDate = DEFAULT_DATA_DATE,
): Promise<RehabGuidanceViewData> {
  const response = await authenticatedFetch('/v1/rehab-guidance/generate', {
    method: 'POST',
    body: JSON.stringify({ as_of_date: asOfDate }),
  })
  const payload = await parseJson<BackendRehabGuidanceResponse>(response)
  return mapRehabGuidanceResponse(payload)
}

export async function confirmRehabGuidancePlan(planId: string): Promise<RehabGuidanceViewData> {
  const response = await authenticatedFetch(`/v1/rehab-guidance/${planId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  const payload = await parseJson<BackendRehabGuidanceResponse>(response)
  return mapRehabGuidanceResponse(payload)
}

export async function downloadMedicalRecordReportPdf(
  reportId: string,
  options?: DownloadFileNameOptions | string,
) {
  const response = await authenticatedFetch(`/v1/medical-records/reports/${reportId}/pdf`)

  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(response.status, detail || 'PDF 下载失败。')
  }

  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download =
    typeof options === 'string'
      ? buildDownloadFileName({
          preferredName: options,
          reportId,
          defaultLabel: 'medical-record-report',
        })
      : buildDownloadFileName({
          ...options,
          reportId,
          defaultLabel: 'TremorGuard-health-report',
        })
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

export async function downloadHealthReportPdf(
  reportId: string,
  options?: DownloadFileNameOptions | string,
) {
  const response = await authenticatedFetch(`/v1/health-reports/${reportId}/pdf`)

  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(response.status, detail || 'PDF 下载失败。')
  }

  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download =
    typeof options === 'string'
      ? buildDownloadFileName({
          preferredName: options,
          reportId,
          defaultLabel: 'TremorGuard-health-report',
        })
      : buildDownloadFileName({
          ...options,
          reportId,
          defaultLabel: 'TremorGuard-health-report',
        })
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

export async function downloadPdfFromApiPath(
  apiPath: string,
  options?: DownloadFileNameOptions | string,
) {
  const response = await authenticatedFetch(apiPath)

  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(response.status, detail || 'PDF 下载失败。')
  }

  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download =
    typeof options === 'string'
      ? buildDownloadFileName({ preferredName: options })
      : buildDownloadFileName({
          ...options,
          defaultLabel: 'TremorGuard-health-report',
        })
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

export async function executeAiAction(apiPath: string, method: 'GET' | 'POST' = 'POST'): Promise<AiChatResult> {
  const response = await authenticatedFetch(apiPath, {
    method,
    body: method === 'POST' ? JSON.stringify({}) : undefined,
  })
  const payload = await parseJson<BackendAiChatResponse>(response)
  return mapAiChatResult(payload)
}

export async function getAiHealthReportActionCard(reportId: string): Promise<AiChatActionCard> {
  const response = await authenticatedFetch(`/v1/ai/actions/health-report/${reportId}`, {
    method: 'GET',
  })
  const payload = await parseJson<NonNullable<BackendAiChatResponse['action_cards']>[number]>(response)
  return mapAiChatActionCard(payload)
}

export async function sendAiChat(messages: ChatMessage[]): Promise<AiChatResult> {
  const response = await authenticatedFetch('/v1/ai/chat', {
    method: 'POST',
    body: JSON.stringify({
      messages: messages.map((message) => ({
        role: message.role,
        content: message.content,
      })),
    }),
  })
  const payload = await parseJson<BackendAiChatResponse>(response)
  return mapAiChatResult(payload)
}

export async function streamAiChat(
  messages: ChatMessage[],
  options: StreamAiChatOptions = {},
): Promise<AiChatResult> {
  const response = await authenticatedFetch('/v1/ai/chat/stream', {
    method: 'POST',
    body: JSON.stringify({
      messages: messages.map((message) => ({
        role: message.role,
        content: message.content,
      })),
    }),
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new ApiError(response.status, detail || 'AI 服务暂时不可用，请稍后重试。')
  }

  if (!response.body) {
    throw new ApiError(502, 'AI 服务未返回流式数据。')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: AiChatResult | null = null

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })

    let separatorMatch = buffer.match(/\r?\n\r?\n/)
    while (separatorMatch && separatorMatch.index !== undefined) {
      const separatorLength = separatorMatch[0].length
      const block = buffer.slice(0, separatorMatch.index).trim()
      buffer = buffer.slice(separatorMatch.index + separatorLength)

      if (block) {
        const { event, data } = parseSseEventBlock(block)
        const parsed = data ? (JSON.parse(data) as Record<string, unknown>) : {}

        if (event === 'chunk') {
          const content = typeof parsed.content === 'string' ? parsed.content : ''
          if (content) {
            options.onChunk?.(content)
          }
        } else if (event === 'done') {
          finalResult = mapAiChatResult(parsed as unknown as BackendAiChatStreamDonePayload)
        } else if (event === 'error') {
          const detail =
            typeof parsed.detail === 'string' && parsed.detail
              ? parsed.detail
              : 'AI 服务暂时不可用，请稍后重试。'
          throw new ApiError(response.status || 502, detail)
        }
      }

      separatorMatch = buffer.match(/\r?\n\r?\n/)
    }

    if (done) {
      break
    }
  }

  if (!finalResult) {
    throw new ApiError(502, 'AI 服务流式响应未正常结束。')
  }

  return finalResult
}
