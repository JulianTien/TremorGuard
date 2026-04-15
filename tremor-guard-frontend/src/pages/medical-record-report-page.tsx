import { Download, FileImage, LoaderCircle, RefreshCcw, ScrollText } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ProcessingStatusBadge } from '../components/medical-records/processing-status-badge'
import { PageHeader } from '../components/ui/page-header'
import { SectionPanel } from '../components/ui/section-panel'
import { useApiResource } from '../hooks/use-api-resource'
import { downloadMedicalRecordReportPdf, getMedicalRecordReport } from '../lib/api'
import { formatMedicalRecordDateTime, isMedicalRecordStatusActive } from '../lib/medical-records'
import type { MedicalRecordReportDetail } from '../types/domain'

function isPending(report: MedicalRecordReportDetail | null) {
  return Boolean(report && isMedicalRecordStatusActive(report.status))
}

export function MedicalRecordReportPage() {
  const { reportId = '' } = useParams()
  const {
    data: report,
    error,
    isLoading,
    reload,
  } = useApiResource(() => getMedicalRecordReport(reportId), [reportId])
  const [actionError, setActionError] = useState<string | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)

  const shouldPoll = useMemo(() => isPending(report), [report])

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
      await downloadMedicalRecordReportPdf(report.id, report.pdfFileName ?? undefined)
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
      await downloadMedicalRecordReportPdf(
        reportToDownload.id,
        reportToDownload.pdfFileName ?? undefined,
      )
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
              to={`/records/${report.archiveId}`}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-700"
            >
              返回档案
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
        description="该报告属于 medical records 域，不会在 legacy `/reports` 监测摘要中心中展示。"
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
            </div>
            {report.summary ? (
              <p className="mt-4 text-sm leading-6 text-slate-600">{report.summary}</p>
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

      <SectionPanel title="报告正文" description="结构化报告 JSON 是真实来源，页面与 PDF 只负责渲染与导出。">
        {report.sections.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
            <p className="text-sm font-medium text-slate-700">报告内容尚未准备完成</p>
            <p className="mt-2 text-sm text-slate-500">当状态进入“已完成”后，结构化报告章节会显示在这里。</p>
          </div>
        ) : null}

        <div className="space-y-4">
          {report.sections.map((section) => (
            <article key={section.id} className="rounded-xl border border-slate-200 bg-slate-50 p-5">
              <div className="flex items-center gap-3">
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white text-teal-600">
                  <ScrollText className="h-5 w-5" />
                </div>
                <h3 className="text-base font-semibold text-slate-900">{section.title}</h3>
              </div>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-600">{section.body}</p>
            </article>
          ))}
        </div>
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
