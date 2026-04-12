import { Plus } from 'lucide-react'
import { useApiResource } from '../hooks/use-api-resource'
import { DEFAULT_DATA_DATE, getMedicationEntries } from '../lib/api'
import { SectionPanel } from '../components/ui/section-panel'
import { TimelineItem } from '../components/ui/timeline-item'

export function MedicationPage() {
  const { data, error, isLoading } = useApiResource(() => getMedicationEntries(DEFAULT_DATA_DATE), [])

  return (
    <div className="space-y-6">
      <SectionPanel
        title="今日用药执行记录"
        description="精准记录用药时间，有助于医生评估药效开关周期。"
        action={
          <button className="flex items-center gap-2 rounded-lg bg-teal-50 px-4 py-2 text-sm font-medium text-teal-700 transition-colors hover:bg-teal-100">
            <Plus className="h-4 w-4" />
            补记用药
          </button>
        }
      >
        {isLoading ? (
          <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
            正在加载用药记录...
          </div>
        ) : null}
        {error ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            无法加载用药记录：{error}
          </div>
        ) : null}
        <div className="relative ml-3 space-y-8 border-l-2 border-slate-100 py-2 md:ml-4">
          {(data ?? []).map((entry) => (
            <TimelineItem key={entry.id} entry={entry} />
          ))}
        </div>
      </SectionPanel>
    </div>
  )
}
