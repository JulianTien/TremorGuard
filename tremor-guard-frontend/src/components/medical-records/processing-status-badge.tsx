import { CheckCircle2, CircleAlert, Clock3, LoaderCircle } from 'lucide-react'
import { StatusBadge } from '../ui/status-badge'
import type { MedicalRecordProcessingStatus } from '../../types/domain'

interface ProcessingStatusBadgeProps {
  status: MedicalRecordProcessingStatus
}

const statusConfig: Record<
  MedicalRecordProcessingStatus,
  {
    label: string
    tone: 'safe' | 'alert' | 'danger' | 'neutral'
    Icon: typeof Clock3
  }
> = {
  queued: {
    label: '等待处理',
    tone: 'neutral',
    Icon: Clock3,
  },
  processing: {
    label: '处理中',
    tone: 'alert',
    Icon: LoaderCircle,
  },
  succeeded: {
    label: '已完成',
    tone: 'safe',
    Icon: CheckCircle2,
  },
  failed: {
    label: '处理失败',
    tone: 'danger',
    Icon: CircleAlert,
  },
}

export function ProcessingStatusBadge({ status }: ProcessingStatusBadgeProps) {
  const { label, tone, Icon } = statusConfig[status]

  return (
    <StatusBadge tone={tone}>
      <span className="inline-flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 ${status === 'processing' ? 'animate-spin' : ''}`} />
        {label}
      </span>
    </StatusBadge>
  )
}
