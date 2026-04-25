import { Download, FileText } from 'lucide-react'
import type { LegacyMonitoringReportSummary } from '../../types/domain'

interface ReportListItemProps {
  report: LegacyMonitoringReportSummary
}

export function ReportListItem({ report }: ReportListItemProps) {
  return (
    <div className="flex items-center justify-between gap-4 p-4 transition-colors hover:bg-slate-50">
      <div className="flex items-start gap-4">
        <div className="rounded-lg bg-rose-50 p-2 text-rose-600">
          <FileText className="h-5 w-5" />
        </div>
        <div>
          <h4 className="text-sm font-semibold text-slate-900">{report.type}</h4>
          <div className="mt-1 flex flex-wrap items-center gap-3 font-mono text-xs text-slate-500">
            <span>日期: {report.date}</span>
            <span>大小: {report.size}</span>
            <span>ID: {report.id}</span>
          </div>
        </div>
      </div>
      <button className="p-2 text-slate-400 transition-colors hover:text-teal-600">
        <Download className="h-5 w-5" />
      </button>
    </div>
  )
}
