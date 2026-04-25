import { Calendar, Download, FileText, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/ui/page-header'
import { useApiResource } from '../hooks/use-api-resource'
import { executeAiAction, getHealthReports, getLegacyMonitoringSummaries } from '../lib/api'
import { ReportListItem } from '../components/ui/report-list-item'
import { SectionPanel } from '../components/ui/section-panel'

export function ReportsPage() {
  const navigate = useNavigate()
  const {
    data: healthReports,
    error: healthReportError,
    isLoading: isLoadingHealthReports,
    reload,
  } = useApiResource(getHealthReports, [])
  const {
    data: legacyReports,
    error: legacyError,
    isLoading: isLoadingLegacy,
  } = useApiResource(getLegacyMonitoringSummaries, [])
  const [isGenerating, setIsGenerating] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  async function handleGenerateReport() {
    try {
      setIsGenerating(true)
      setActionError(null)
      const result = await executeAiAction('/v1/ai/actions/health-report/generate')
      const reportCard = result.actionCards.find((card) => card.type === 'health_report_candidate')
      if (reportCard?.resourcePath) {
        navigate(reportCard.resourcePath)
      }
      reload()
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : '生成 AI 健康报告失败。')
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI 健康报告"
        subtitle="这里是患者侧结果输出中心。统一的 AI 健康报告会整合监测摘要、用药记录与可用病历档案，并保留历史监测摘要作为兼容分区。"
        trailing={
          <div className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            unified-report
          </div>
        }
      />

      <div className="flex flex-col items-start justify-between gap-4 rounded-xl border border-teal-100 bg-teal-50 p-6 md:flex-row md:items-center">
        <div>
          <h3 className="mb-1 flex items-center gap-2 text-base font-semibold text-slate-900">
            <Calendar className="h-5 w-5 text-teal-600" />
            生成 AI 健康报告
          </h3>
          <p className="text-sm text-slate-600">
            系统会优先复用现有档案资料，并结合近期监测与用药记录生成统一的 AI 健康报告。生成完成后会自动跳转到在线详情页。
          </p>
          {actionError ? <p className="mt-2 text-sm text-rose-700">{actionError}</p> : null}
        </div>
        <button
          onClick={handleGenerateReport}
          disabled={isGenerating}
          className="flex shrink-0 items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-teal-300"
        >
          <Download className="h-4 w-4" />
          {isGenerating ? '正在生成...' : '生成 AI 健康报告'}
        </button>
      </div>

      <SectionPanel
        title="AI 健康报告列表"
        description="这里展示统一的 AI 健康报告主产物。优先从此处进入详情页，而不是从 legacy 监测摘要理解当前主报告。"
      >
        {isLoadingHealthReports ? (
          <div className="p-4 text-sm text-slate-500">正在加载 AI 健康报告...</div>
        ) : null}
        {healthReportError ? (
          <div className="p-4 text-sm text-rose-700">无法加载 AI 健康报告：{healthReportError}</div>
        ) : null}
        {!isLoadingHealthReports && !healthReportError && (healthReports?.length ?? 0) === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-teal-50 text-teal-600">
              <Sparkles className="h-5 w-5" />
            </div>
            <p className="mt-4 text-sm font-medium text-slate-700">还没有 AI 健康报告</p>
            <p className="mt-2 text-sm text-slate-500">
              先从 AI 医生或本页生成第一份报告，系统会结合监测、用药和可用病历资料自动整理。
            </p>
          </div>
        ) : null}
        <div className="grid gap-4 lg:grid-cols-2">
          {(healthReports ?? []).map((report) => (
            <Link
              key={report.id}
              to={`/reports/${report.id}`}
              className="group rounded-xl border border-slate-200 bg-slate-50 p-5 transition hover:border-teal-200 hover:bg-white hover:shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="rounded-lg bg-teal-50 p-2 text-teal-600">
                      <FileText className="h-4 w-4" />
                    </div>
                    <h3 className="text-base font-semibold text-slate-900">{report.title}</h3>
                  </div>
                  <p className="text-sm text-slate-500">
                    {report.summary ?? 'AI 健康报告已生成，可进入详情页查看结构化章节和 PDF。'}
                  </p>
                </div>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600">
                  V{report.version}
                </span>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                <span className="rounded-full bg-white px-2.5 py-1 font-medium text-slate-600">
                  {report.reportWindowLabel ?? '报告窗口待同步'}
                </span>
                <span>{report.generatedAt ? `生成时间：${report.generatedAt.slice(0, 10)}` : '等待生成完成'}</span>
                <span>{report.pdfReady ? 'PDF 已就绪' : 'PDF 生成中'}</span>
              </div>
            </Link>
          ))}
        </div>
      </SectionPanel>

      <SectionPanel
        title="历史监测摘要"
        description="此列表保留旧版 `/reports` 路径下的监测摘要，仅用于兼容历史数据，不再作为患者侧主报告入口。"
        className="overflow-hidden"
        bodyClassName="p-0"
      >
        {isLoadingLegacy ? (
          <div className="p-4 text-sm text-slate-500">正在加载报告归档...</div>
        ) : null}
        {legacyError ? (
          <div className="p-4 text-sm text-rose-700">无法加载历史监测摘要：{legacyError}</div>
        ) : null}
        <div className="divide-y divide-slate-100">
          {(legacyReports ?? []).map((report) => (
            <ReportListItem key={report.id} report={report} />
          ))}
        </div>
      </SectionPanel>
    </div>
  )
}
