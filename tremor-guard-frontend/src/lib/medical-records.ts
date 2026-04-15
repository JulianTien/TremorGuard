import type { MedicalRecordProcessingStatus } from '../types/domain'

const ACTIVE_STATUSES = new Set<MedicalRecordProcessingStatus>(['queued', 'processing'])

export function formatMedicalRecordDateTime(value?: string | null) {
  if (!value) {
    return '暂无时间'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function isMedicalRecordStatusActive(status: MedicalRecordProcessingStatus) {
  return ACTIVE_STATUSES.has(status)
}
