import { Activity, Clock } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { TremorMetricSummary } from '../../types/domain'

interface MetricTileProps {
  metric: TremorMetricSummary
  icon?: LucideIcon
}

const toneIconMap: Record<TremorMetricSummary['tone'], LucideIcon> = {
  alert: Activity,
  neutral: Clock,
  safe: Activity,
}

export function MetricTile({ metric, icon }: MetricTileProps) {
  const Icon = icon ?? toneIconMap[metric.tone]
  const isAlert = metric.tone === 'alert'

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-colors hover:border-teal-200">
      {isAlert ? <div className="absolute right-0 top-0 h-full w-2 bg-amber-500" /> : null}
      <div className="mb-2 flex items-start justify-between">
        <span className="text-sm font-medium text-slate-500">{metric.label}</span>
        <Icon className={`h-5 w-5 ${isAlert ? 'text-amber-500' : 'text-teal-600'}`} />
      </div>
      <div className="flex items-baseline gap-1">
        <span className="font-mono text-3xl font-semibold tracking-tight text-slate-900">
          {metric.value}
        </span>
        <span className="text-sm text-slate-500">{metric.unit}</span>
      </div>
      <span className="mt-2 block font-mono text-xs text-slate-400">{metric.subtitle}</span>
    </div>
  )
}
