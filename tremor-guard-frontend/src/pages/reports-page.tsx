import { Calendar, Download } from 'lucide-react'
import { useState } from 'react'
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
      <div className="flex flex-col items-start justify-between gap-4 rounded-xl border border-teal-100 bg-teal-50 p-6 md:flex-row md:items-center">
        <div>
          <h3 className="mb-1 flex items-center gap-2 text-base font-semibold text-slate-900">
            <Calendar className="h-5 w-5 text-teal-600" />
            复诊数据准备
          </h3>
          <p className="text-sm text-slate-600">
            系统已为您自动汇总近一个月的客观震颤波形及用药关联数据，可直接出示给主治医生。
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

      <SectionPanel title="历史报告归档" className="overflow-hidden" bodyClassName="p-0">
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
