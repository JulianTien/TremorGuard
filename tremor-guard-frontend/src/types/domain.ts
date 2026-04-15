export type NavKey =
  | 'overview'
  | 'ai-doctor'
  | 'medication'
  | 'rehab-guidance'
  | 'medical-records'
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

export type RehabGenerationEligibility = 'eligible' | 'insufficient_data'

export type RehabConflictStatus = 'consistent' | 'conflicting' | 'insufficient_data' | 'unknown'

export type RehabPlanStatus =
  | 'active_only'
  | 'candidate_pending_confirmation'
  | 'candidate_confirmed'
  | 'candidate_superseded'

export interface RehabPlanItem {
  templateId: string
  name: string
  category: string
  durationMinutes: number
  frequencyLabel: string
  cautions: string[]
}

export interface RehabPlan {
  id: string
  title: string
  status: RehabPlanStatus
  scenario: string
  version: number
  rationale: string
  items: RehabPlanItem[]
  riskFlags: string[]
  requiresConfirmation: boolean
  generatedAt?: string | null
  confirmedAt?: string | null
  activatedAt?: string | null
}

export interface RehabEvidenceSummary {
  asOfDate?: string | null
  evaluationWindow?: string | null
  medicationWindowSummary: string
  tremorTrendSummary: string
  signalConsistency: string
  explanation: string
}

export interface RehabGuidanceViewData {
  activePlan: RehabPlan | null
  candidatePlan: RehabPlan | null
  evidenceSummary: RehabEvidenceSummary
  conflictStatus: RehabConflictStatus
  disclaimer: string
  generatedAt?: string | null
  generationEligibility: RehabGenerationEligibility
  missingInputs: string[]
}

export interface ReportSummary {
  id: string
  date: string
  type: string
  size: string
  status?: string
}

export type MedicalRecordProcessingStatus = 'queued' | 'processing' | 'succeeded' | 'failed'

export interface MedicalRecordArchiveSummary {
  id: string
  title: string
  description?: string | null
  createdAt: string
  updatedAt: string
  fileCount: number
  reportCount: number
  latestActivityAt?: string | null
  latestReportId?: string | null
  latestReportVersion?: number | null
  latestReportStatus?: MedicalRecordProcessingStatus | null
}

export interface MedicalRecordExtraction {
  status: MedicalRecordProcessingStatus
  summary?: string | null
  highlights: string[]
  extractedAt?: string | null
  errorSummary?: string | null
}

export interface MedicalRecordFile {
  id: string
  archiveId: string
  fileName: string
  fileType: string
  sizeLabel: string
  uploadedAt: string
  processingStatus: MedicalRecordProcessingStatus
  previewUrl?: string | null
  statusSummary?: string | null
  extraction?: MedicalRecordExtraction | null
}

export interface MedicalRecordReportSummary {
  id: string
  archiveId: string
  archiveTitle: string
  version: number
  title: string
  status: MedicalRecordProcessingStatus
  generatedAt?: string | null
  summary?: string | null
  pdfReady: boolean
  pdfFileName?: string | null
  reportWindowLabel?: string | null
}

export interface MedicalRecordReportSection {
  id: string
  title: string
  body: string
}

export interface MedicalRecordInputSnapshot {
  reportWindow?: string | null
  monitoringWindow?: string | null
  medicationWindow?: string | null
  disclaimerVersion?: string | null
  promptVersion?: string | null
  modelVersion?: string | null
}

export interface MedicalRecordArchiveDetail extends MedicalRecordArchiveSummary {
  disclaimer: string
  files: MedicalRecordFile[]
  reports: MedicalRecordReportSummary[]
}

export interface MedicalRecordReportDetail extends MedicalRecordReportSummary {
  disclaimer: string
  archiveDescription?: string | null
  sections: MedicalRecordReportSection[]
  sourceFiles: MedicalRecordFile[]
  history: MedicalRecordReportSummary[]
  inputSnapshot?: MedicalRecordInputSnapshot | null
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
