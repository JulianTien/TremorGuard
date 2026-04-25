import { Download, FileImage, LoaderCircle, RefreshCcw, ScrollText, UserRound } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ProcessingStatusBadge } from '../components/medical-records/processing-status-badge'
import { ReportPipelineStatus } from '../components/medical-records/report-pipeline-status'
import { MarkdownRenderer } from '../components/ui/markdown-renderer'
import { PageHeader } from '../components/ui/page-header'
import { SectionPanel } from '../components/ui/section-panel'
import { useApiResource } from '../hooks/use-api-resource'
import { downloadHealthReportPdf, downloadMedicalRecordReportPdf, getHealthReport, getMedicalRecordReport, getProfile } from '../lib/api'
import { formatMedicalRecordDateTime, isMedicalRecordStatusActive } from '../lib/medical-records'
import type { MedicalRecordReportDetail } from '../types/domain'

function isPending(report: MedicalRecordReportDetail | null) {
  return Boolean(
    report &&
      (isMedicalRecordStatusActive(report.status) ||
        report.pipelineState?.template.status === 'queued' ||
        report.pipelineState?.template.status === 'processing' ||
        report.pipelineState?.llm.status === 'queued' ||
        report.pipelineState?.llm.status === 'processing' ||
        report.pipelineState?.pdf.status === 'queued' ||
        report.pipelineState?.pdf.status === 'processing'),
  )
}

export function MedicalRecordReportPage() {
  const { reportId = '' } = useParams()
  const location = useLocation()
  const isHealthReportRoute = location.pathname.startsWith('/reports/')
  const {
    data: report,
    error,
    isLoading,
    reload,
  } = useApiResource(
    () => (isHealthReportRoute ? getHealthReport(reportId) : getMedicalRecordReport(reportId)),
    [reportId, isHealthReportRoute],
  )
  const { data: profile } = useApiResource(getProfile, [])
  const [actionError, setActionError] = useState<string | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)

  const shouldPoll = useMemo(() => isPending(report), [report])
  const patientProfile = profile?.patientProfile ?? null
  const medicationSection = useMemo(
    () =>
      report?.sections.find((section) => /用药|药效|关联|剂末|波动/i.test(section.title)) ?? null,
    [report],
  )
  const monitoringSection = useMemo(
    () =>
      report?.sections.find((section) => /趋势|监测|分析|总结|概览|洞察/i.test(section.title)) ?? null,
    [report],
  )

  useEffect(() => {
    if (!shouldPoll) {
      return undefined
    }

    const handle = window.setInterval(() => {
      reload()
    }, 4000)

    return () => {
      window.clearInterval(handle)
    }
  }, [reload, shouldPoll])

  async function handleDownload() {
    if (!report) {
      return
    }

    try {
      setIsDownloading(true)
      setActionError(null)
      const downloadReport = isHealthReportRoute ? downloadHealthReportPdf : downloadMedicalRecordReportPdf
      await downloadReport(report.id, {
        preferredName: report.pdfFileName ?? undefined,
        patientName: patientProfile?.name ?? null,
        generatedAt: report.generatedAt ?? null,
        version: report.version,
      })
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'PDF 下载失败。'
      setActionError(message)
    } finally {
      setIsDownloading(false)
    }
  }

  async function handleHistoryDownload(reportToDownload: MedicalRecordReportDetail['history'][number]) {
    try {
      setActionError(null)
      const downloadReport =
        reportToDownload.templateName ? downloadHealthReportPdf : downloadMedicalRecordReportPdf
      await downloadReport(reportToDownload.id, {
        preferredName: reportToDownload.pdfFileName ?? undefined,
        patientName: patientProfile?.name ?? null,
        generatedAt: reportToDownload.generatedAt ?? null,
        version: reportToDownload.version,
      })
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'PDF 下载失败。'
      setActionError(message)
    }
  }

  if (isLoading) {
    return <div className="text-sm text-slate-500">正在加载报告详情...</div>
  }

  if (error || !report) {
    return (
      <div className="rounded-xl border border-rose-100 bg-rose-50 px-5 py-4 text-sm text-rose-700">
        无法加载报告详情：{error ?? '报告不存在或尚未同步。'}
      </div>
    )
  }

  const backLink = isHealthReportRoute ? '/reports' : `/records/${report.archiveId}`
  const backLabel = isHealthReportRoute ? '返回 AI 健康报告' : '返回档案'

  return (
    <div className="space-y-6">
      <PageHeader
        title={report.title}
        subtitle={`${report.archiveTitle} · 版本 V${report.version}`}
        trailing={
          <div className="flex flex-wrap items-center gap-2">
            {shouldPoll ? (
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-100 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                报告生成中，页面自动刷新
              </div>
            ) : null}
            <Link
              to={backLink}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-700"
            >
              {backLabel}
            </Link>
            <button
              type="button"
              onClick={handleDownload}
              disabled={!report.pdfReady || isDownloading}
              className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <Download className="h-4 w-4" />
              {isDownloading ? '下载中...' : '下载 PDF'}
            </button>
          </div>
        }
      />

      <SectionPanel
        title="报告元信息"
        description={
          isHealthReportRoute
            ? '该报告属于 AI 健康报告主资源，用于复诊沟通与健康管理结果输出。'
            : '该报告属于病历档案域，用于保留档案内的版本化健康报告。'
        }
        action={
          <button
            type="button"
            onClick={reload}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-teal-200 hover:text-teal-700"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            手动刷新
          </button>
        }
      >
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(300px,0.9fr)]">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <ProcessingStatusBadge status={report.status} />
              <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600">
                版本 V{report.version}
              </span>
              <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600">
                {report.reportWindowLabel ?? '报告窗口待后端返回'}
              </span>
              {report.templateVersion ? (
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600">
                  模板 {report.templateVersion}
                </span>
              ) : null}
              {report.agentType ? (
                <span className="rounded-full bg-teal-100 px-2.5 py-1 text-xs font-medium text-teal-700">
                  {report.agentType === 'health_report_agent' ? '报告生成 Agent' : report.agentType}
                </span>
              ) : null}
            </div>
            {report.summary ? (
              <MarkdownRenderer content={report.summary} tone="muted" className="mt-4 max-w-none" />
            ) : (
              <p className="mt-4 text-sm text-slate-500">报告摘要将在生成完成后显示。</p>
            )}
            <div className="mt-4 text-xs text-slate-500">
              <p>生成时间：{formatMedicalRecordDateTime(report.generatedAt)}</p>
              {report.archiveDescription ? <p className="mt-2">{report.archiveDescription}</p> : null}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-900">免责声明</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">{report.disclaimer}</p>
            {actionError ? (
              <div className="mt-4 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {actionError}
              </div>
            ) : null}
          </div>
        </div>
      </SectionPanel>

      <SectionPanel
        title="生成状态"
        description="显示模板注入、AI Markdown 生成与 PDF 转换的最新状态。"
      >
        <ReportPipelineStatus pipelineState={report.pipelineState} />
      </SectionPanel>

      {report.qualityWarnings.length > 0 ? (
        <SectionPanel
          title="质量提醒"
          description="这些提醒不会阻止在线查看或 PDF 下载，但表示某些章节仍可进一步增强。"
        >
          <div className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
            {report.qualityWarnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        </SectionPanel>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <SectionPanel
          title="患者信息"
          description="优先读取患者档案；未返回的字段明确显示为待补充。"
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">患者姓名</p>
              <p className="mt-2 flex items-center gap-2 text-sm font-medium text-slate-900">
                <UserRound className="h-4 w-4 text-teal-600" />
                {patientProfile?.name ?? '待患者档案补充'}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">年龄 / 性别</p>
              <p className="mt-2 text-sm text-slate-700">
                {patientProfile ? `${patientProfile.age}岁 / ${patientProfile.gender}` : '待患者档案补充'}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">临床背景</p>
              <p className="mt-2 text-sm text-slate-700">
                {patientProfile?.diagnosis ?? '待患者档案补充'}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">主治机构</p>
              <p className="mt-2 text-sm text-slate-700">
                {patientProfile?.hospital ?? '待患者档案补充'}
              </p>
            </div>
          </div>
        </SectionPanel>

        <SectionPanel
          title="核心结论"
          description="首页摘要面向复诊场景，保留后端原始结构化文本，不补写未返回的医学结论。"
        >
          {report.summary ? (
            <MarkdownRenderer content={report.summary} className="max-w-none" />
          ) : (
            <p className="text-sm text-slate-500">报告核心结论待后端生成完成后返回。</p>
          )}
        </SectionPanel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.95fr)]">
        <SectionPanel
          title="监测趋势摘要"
          description="优先展示报告中与监测概览、趋势或洞察最相关的章节。"
        >
          {monitoringSection ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
              <h3 className="text-base font-semibold text-slate-900">{monitoringSection.title}</h3>
              <MarkdownRenderer content={monitoringSection.body} tone="muted" className="mt-3 max-w-none" />
            </div>
          ) : (
            <p className="text-sm text-slate-500">当前报告未单独返回监测趋势摘要章节。</p>
          )}
        </SectionPanel>

        <SectionPanel
          title="用药-症状关联"
          description="仅展示报告中已返回的用药、药效或波动关联内容，不推断额外治疗建议。"
        >
          {medicationSection ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
              <h3 className="text-base font-semibold text-slate-900">{medicationSection.title}</h3>
              <MarkdownRenderer content={medicationSection.body} tone="muted" className="mt-3 max-w-none" />
            </div>
          ) : (
            <p className="text-sm text-slate-500">当前报告未单独返回用药-症状关联章节。</p>
          )}
        </SectionPanel>
      </div>

      <SectionPanel
        title="在线文档"
        description="在线页直接展示 Markdown 报告正文；PDF 由同一份 Markdown 文档转换而来。"
      >
        {report.reportMarkdown ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <MarkdownRenderer content={report.reportMarkdown} className="max-w-none" />
          </div>
        ) : report.sections.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
            <p className="text-sm font-medium text-slate-700">报告内容尚未准备完成</p>
            <p className="mt-2 text-sm text-slate-500">Markdown 文档生成完成后会直接显示在这里。</p>
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <div className="space-y-6">
          {report.sections.map((section) => (
              <article key={section.id} className="rounded-xl border border-slate-200 bg-slate-50 p-5">
              <div className="flex items-center gap-3">
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white text-teal-600">
                  <ScrollText className="h-5 w-5" />
                </div>
                <h3 className="text-base font-semibold text-slate-900">{section.title}</h3>
              </div>
              <MarkdownRenderer content={section.body} tone="muted" className="mt-4 max-w-none" />
              </article>
          ))}
            </div>
          </div>
        )}
      </SectionPanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)]">
        <SectionPanel title="输入快照" description="用于验证长期报告链路没有复用聊天域的日级上下文组装器。">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Report Window</p>
              <p className="mt-2 text-sm text-slate-700">{report.inputSnapshot?.reportWindow ?? '待后端返回'}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Monitoring Window</p>
              <p className="mt-2 text-sm text-slate-700">{report.inputSnapshot?.monitoringWindow ?? '待后端返回'}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Medication Window</p>
              <p className="mt-2 text-sm text-slate-700">{report.inputSnapshot?.medicationWindow ?? '待后端返回'}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Snapshot Lineage</p>
              <p className="mt-2 text-sm text-slate-700">
                {report.inputSnapshot?.modelVersion ?? '待后端返回'} · {report.inputSnapshot?.promptVersion ?? '待后端返回'}
              </p>
            </div>
          </div>
        </SectionPanel>

        <SectionPanel title="源文件" description="本次报告所引用的病例文件版本。">
          {report.sourceFiles.length === 0 ? (
            <p className="text-sm text-slate-500">待后端返回源文件列表。</p>
          ) : null}
          <div className="space-y-3">
            {report.sourceFiles.map((file) => (
              <div key={file.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-slate-400">
                    {file.previewUrl ? (
                      <img src={file.previewUrl} alt={file.fileName} className="h-full w-full rounded-xl object-cover" />
                    ) : (
                      <FileImage className="h-5 w-5" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium text-slate-900">{file.fileName}</p>
                      <ProcessingStatusBadge status={file.processingStatus} />
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      {file.fileType} · {file.sizeLabel} · {formatMedicalRecordDateTime(file.uploadedAt)}
                    </p>
                    {file.extraction?.summary ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{file.extraction.summary}</p>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </SectionPanel>
      </div>

      <SectionPanel title="版本历史" description="同一档案内的新旧版本需要同时可访问，且支持分别导出 PDF。">
        <div className="space-y-4">
          {report.history.map((item) => (
            <article key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="text-sm font-semibold text-slate-900">{item.title}</h3>
                    <ProcessingStatusBadge status={item.status} />
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>版本 V{item.version}</span>
                    <span>{item.reportWindowLabel ?? '报告窗口待后端返回'}</span>
                    <span>生成于 {formatMedicalRecordDateTime(item.generatedAt)}</span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link
                    to={`/records/reports/${item.id}`}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-700"
                  >
                    查看该版本
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      void handleHistoryDownload(item)
                    }}
                    disabled={!item.pdfReady}
                    className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    下载 PDF
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      </SectionPanel>
    </div>
  )
}
