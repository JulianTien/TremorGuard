import { CheckCircle2, Clock3, GitCompareArrows, ShieldCheck } from 'lucide-react'
import { StatusBadge } from '../ui/status-badge'
import type { RehabPlanStatus } from '../../types/domain'

interface RehabPlanStatusBadgeProps {
  status: RehabPlanStatus
}

const statusConfig: Record<
  RehabPlanStatus,
  {
    label: string
    tone: 'safe' | 'alert' | 'neutral'
    Icon: typeof Clock3
  }
> = {
  active_only: {
    label: '当前激活',
    tone: 'safe',
    Icon: ShieldCheck,
  },
  candidate_pending_confirmation: {
    label: '待确认候选',
    tone: 'alert',
    Icon: Clock3,
  },
  candidate_confirmed: {
    label: '已确认',
    tone: 'safe',
    Icon: CheckCircle2,
  },
  candidate_superseded: {
    label: '已被替换',
    tone: 'neutral',
    Icon: GitCompareArrows,
  },
}

export function RehabPlanStatusBadge({ status }: RehabPlanStatusBadgeProps) {
  const { label, tone, Icon } = statusConfig[status]

  return (
    <StatusBadge tone={tone} compact>
      <span className="inline-flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
    </StatusBadge>
  )
}
