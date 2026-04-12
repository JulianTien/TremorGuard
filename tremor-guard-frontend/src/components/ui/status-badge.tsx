import type { PropsWithChildren } from 'react'

interface StatusBadgeProps extends PropsWithChildren {
  tone: 'safe' | 'alert' | 'neutral' | 'danger'
  compact?: boolean
}

const toneStyles: Record<StatusBadgeProps['tone'], string> = {
  safe: 'border-emerald-100 bg-emerald-50 text-emerald-700',
  alert: 'border-amber-100 bg-amber-50 text-amber-700',
  neutral: 'border-slate-200 bg-slate-100 text-slate-600',
  danger: 'border-rose-100 bg-rose-50 text-rose-700',
}

export function StatusBadge({ tone, compact = false, children }: StatusBadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-md border font-medium',
        compact ? 'px-2 py-1 text-[10px]' : 'px-3 py-1.5 text-xs',
        toneStyles[tone],
      ].join(' ')}
    >
      {children}
    </span>
  )
}
