import type { MedicalRecordProcessingStatus } from '../types/domain'

const ACTIVE_STATUSES = new Set<MedicalRecordProcessingStatus>(['queued', 'processing'])
const ISO_TIMEZONE_PATTERN = /(Z|[+-]\d{2}:?\d{2})$/i

function parseMedicalRecordDate(value: string) {
  const normalized = value.includes(' ') ? value.replace(' ', 'T') : value
  const dateInput = ISO_TIMEZONE_PATTERN.test(normalized) ? normalized : `${normalized}Z`
  return new Date(dateInput)
}

export function formatMedicalRecordDateTime(value?: string | null) {
  if (!value) {
    return '暂无时间'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parseMedicalRecordDate(value))
}

export function isMedicalRecordStatusActive(status: MedicalRecordProcessingStatus) {
  return ACTIVE_STATUSES.has(status)
}
