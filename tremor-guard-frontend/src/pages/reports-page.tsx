import { Calendar, Download } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../components/ui/page-header'
import { useApiResource } from '../hooks/use-api-resource'
import { createReport, getReports } from '../lib/api'
import { ReportListItem } from '../components/ui/report-list-item'
import { SectionPanel } from '../components/ui/section-panel'

export function ReportsPage() {
  const { data, error, isLoading, reload } = useApiResource(getReports, [])
  const [isGenerating, setIsGenerating] = useState(false)

  async function handleGenerateReport() {
    try {
      setIsGenerating(true)
      await createReport()
      reload()
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="监测摘要报告"
        subtitle="这里保留的是 legacy TremorGuard 监测摘要报告，用于汇总近一段时间的客观震颤波形和用药关联数据。病历联合健康报告请前往“病历档案”入口。"
        trailing={
          <div className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            legacy-only
          </div>
        }
      />

      <div className="flex flex-col items-start justify-between gap-4 rounded-xl border border-teal-100 bg-teal-50 p-6 md:flex-row md:items-center">
        <div>
          <h3 className="mb-1 flex items-center gap-2 text-base font-semibold text-slate-900">
            <Calendar className="h-5 w-5 text-teal-600" />
            监测摘要导出
          </h3>
          <p className="text-sm text-slate-600">
            系统会汇总近一个月的客观震颤波形及用药关联数据，生成 legacy 监测摘要报告。它不会读取病历档案，也不会生成病历联合健康报告。
          </p>
        </div>
        <button
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className="flex shrink-0 items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-teal-300"
        >
          <Download className="h-4 w-4" />
          {isGenerating ? '正在生成...' : '生成最新复诊摘要'}
        </button>
      </div>

      <SectionPanel
        title="legacy 历史报告归档"
        description="此列表只展示现有 `/reports` 路径下的监测摘要报告，和病历档案里的版本化健康报告严格分离。"
        className="overflow-hidden"
        bodyClassName="p-0"
      >
        {isLoading ? (
          <div className="p-4 text-sm text-slate-500">正在加载报告归档...</div>
        ) : null}
        {error ? (
          <div className="p-4 text-sm text-rose-700">无法加载报告归档：{error}</div>
        ) : null}
        <div className="divide-y divide-slate-100">
          {(data ?? []).map((report) => (
            <ReportListItem key={report.id} report={report} />
          ))}
        </div>
      </SectionPanel>
    </div>
  )
}
