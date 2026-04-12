import { Activity, Battery, Clock, Stethoscope, Wifi } from 'lucide-react'
import { MetricTile } from '../components/ui/metric-tile'
import { TrendChart } from '../components/ui/trend-chart'
import { useApiResource } from '../hooks/use-api-resource'
import { DEFAULT_DATA_DATE, getOverview } from '../lib/api'

export function OverviewPage() {
  const { data, error, isLoading } = useApiResource(() => getOverview(DEFAULT_DATA_DATE), [])

  if (isLoading && !data) {
    return <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">正在加载总览数据...</div>
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
        无法加载后端数据：{error ?? '未知错误'}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile metric={data.metricSummaries[0]} icon={Activity} />
        <MetricTile metric={data.metricSummaries[1]} icon={Activity} />
        <MetricTile metric={data.metricSummaries[2]} icon={Clock} />

        <div className="flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900 p-5 text-white shadow-sm">
          <div className="flex items-start justify-between">
            <span className="text-sm font-medium text-slate-300">设备状态</span>
            <Wifi className="h-5 w-5 text-teal-400" />
          </div>
          <div>
            <div className="mb-1 flex items-center gap-2">
              <Battery className="h-4 w-4 text-green-400" />
              <span className="font-mono text-xl font-semibold">{data.deviceStatus.battery}%</span>
            </div>
            <p className="font-mono text-xs text-slate-400">{data.deviceStatus.lastSync}</p>
          </div>
        </div>
      </div>

      <div className="flex items-start gap-4 rounded-xl border border-teal-100 bg-teal-50 p-4">
        <div className="mt-0.5 shrink-0 rounded-lg bg-teal-600 p-2 text-white">
          <Stethoscope className="h-5 w-5" />
        </div>
        <div>
          <h4 className="mb-1 text-sm font-semibold text-slate-900">{data.overviewInsight.title}</h4>
          <p className="text-sm leading-relaxed text-slate-700">{data.overviewInsight.summary}</p>
        </div>
      </div>

      <TrendChart points={data.trendPoints} />
    </div>
  )
}
