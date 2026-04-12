export type NavKey =
  | 'overview'
  | 'ai-doctor'
  | 'medication'
  | 'reports'
  | 'profile'

export interface PatientProfile {
  id: string
  name: string
  age: number
  gender: string
  diagnosis: string
  duration: string
  hospital: string
  deviceId: string
}

export interface DeviceStatus {
  battery: number
  connection: 'stable' | 'syncing' | 'offline'
  connectionLabel: string
  lastSync: string
  availableDays: string
  firmware: string
}

export interface TremorMetricSummary {
  label: string
  value: string | number
  unit: string
  subtitle: string
  tone: 'neutral' | 'safe' | 'alert'
}

export interface TremorTrendPoint {
  time: string
  amplitude: number
  label?: string
  medicationTaken?: boolean
}

export interface AiInsight {
  id: string
  title: string
  summary: string
  emphasis?: string
}

export interface ChatMessage {
  id: string | number
  role: 'assistant' | 'user'
  content: string
}

export interface AiChatUsage {
  promptTokens?: number | null
  completionTokens?: number | null
  totalTokens?: number | null
}

export interface MedicationEntry {
  id: number
  time: string
  name: string
  dose: string
  status: 'taken' | 'pending' | 'missed'
}

export interface ReportSummary {
  id: string
  date: string
  type: string
  size: string
  status?: string
}

export interface ConsentSettings {
  shareWithDoctor: boolean
  ragAnalysisEnabled: boolean
  cloudSyncEnabled: boolean
}

export interface CurrentUser {
  id: string
  email: string
  displayName: string
  status: string
  onboardingState: 'profile_required' | 'device_binding_required' | 'active'
  lastLoginAt?: string | null
  hasProfile: boolean
  hasBoundDevice: boolean
  boundDeviceSerial?: string | null
}

export interface AuthSession {
  accessToken: string
  refreshToken: string
  userId: string
  accessTokenExpiresAt: string
  refreshTokenExpiresAt: string
}

export interface ProfileCompletionStatus {
  onboardingState: CurrentUser['onboardingState']
  hasProfile: boolean
  hasBoundDevice: boolean
}

export interface DeviceBinding {
  id: string
  deviceSerial: string
  deviceName: string
  firmwareVersion: string
  bindingStatus: string
  boundAt?: string | null
  unboundAt?: string | null
}
