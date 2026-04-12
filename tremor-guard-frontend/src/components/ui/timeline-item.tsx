import { CheckCircle2, Clock } from 'lucide-react'
import type { MedicationEntry } from '../../types/domain'

interface TimelineItemProps {
  entry: MedicationEntry
}

export function TimelineItem({ entry }: TimelineItemProps) {
  const taken = entry.status === 'taken'

  return (
    <div className="group relative pl-8">
      <div
        className={[
          'absolute -left-[9px] top-1 h-4 w-4 rounded-full border-2 border-white',
          taken ? 'bg-teal-500' : 'bg-slate-300',
        ].join(' ')}
      />
      <div className="flex flex-col gap-2 rounded-lg border border-slate-100 bg-slate-50 p-4 transition-colors group-hover:border-slate-200 md:flex-row md:items-center md:gap-6">
        <div className="w-20 shrink-0 font-mono text-xl font-semibold text-slate-700">{entry.time}</div>
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-slate-900">{entry.name}</h4>
          <p className="mt-1 font-mono text-xs text-slate-500">剂量: {entry.dose}</p>
        </div>
        <div>
          {taken ? (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-100 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              已按时服药
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              <Clock className="h-3.5 w-3.5" />
              待服药
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
