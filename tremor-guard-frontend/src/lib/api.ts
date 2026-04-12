import type {
  AiChatUsage,
  AiInsight,
  AuthSession,
  ChatMessage,
  ConsentSettings,
  CurrentUser,
  DeviceBinding,
  DeviceStatus,
  MedicationEntry,
  PatientProfile,
  ProfileCompletionStatus,
  ReportSummary,
  TremorMetricSummary,
  TremorTrendPoint,
} from '../types/domain'

function resolveApiBaseUrl() {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }

  return 'http://127.0.0.1:8000'
}

const API_BASE_URL = resolveApiBaseUrl()
const SESSION_KEY = 'tremor-guard-session'
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

interface BackendReportsResponse {
  report_summaries: Array<{
    id: string
    date: string
    type: string
    size: string
    status: string
  }>
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
}

export interface ProfileViewData {
  patientProfile: PatientProfile
  deviceStatus: DeviceStatus
  consentSettings: ConsentSettings
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

function notifyAuthChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_EVENT))
  }
}

export function loadStoredSession(): AuthSession | null {
  const raw = localStorage.getItem(SESSION_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as AuthSession
  } catch {
    localStorage.removeItem(SESSION_KEY)
    return null
  }
}

function storeSession(session: AuthSession) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  notifyAuthChanged()
}

export function clearStoredSession() {
  localStorage.removeItem(SESSION_KEY)
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
  const response = await fetch(`${API_BASE_URL}${path}`, {
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
    const response = await fetch(`${API_BASE_URL}/v1/auth/refresh`, {
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
    await fetch(`${API_BASE_URL}/v1/auth/logout`, {
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

  const headers = buildRequestHeaders(init?.headers, Boolean(init?.body))
  headers.set('Authorization', `Bearer ${session.accessToken}`)

  const response = await fetch(`${API_BASE_URL}${path}`, {
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
  }
}

export async function getMedicationEntries(date = DEFAULT_DATA_DATE): Promise<MedicationEntry[]> {
  const response = await authenticatedFetch(`/v1/medications?date=${date}`)
  const payload = await parseJson<BackendMedicationResponse>(response)
  return payload.medication_entries
}

export async function getReports(): Promise<ReportSummary[]> {
  const response = await authenticatedFetch('/v1/reports')
  const payload = await parseJson<BackendReportsResponse>(response)
  return payload.report_summaries.map((report) => ({
    id: report.id,
    date: report.date,
    type: report.type,
    size: report.size,
    status: report.status,
  }))
}

export async function createReport(date = DEFAULT_DATA_DATE) {
  const response = await authenticatedFetch('/v1/reports', {
    method: 'POST',
    body: JSON.stringify({ report_date: date }),
  })
  return parseJson(response)
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
  }
}
