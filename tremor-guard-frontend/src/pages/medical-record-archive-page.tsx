import {
  FileImage,
  FileUp,
  LoaderCircle,
  RefreshCcw,
  ScrollText,
  Sparkles,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '../components/ui/page-header'
import { SectionPanel } from '../components/ui/section-panel'
import { ProcessingStatusBadge } from '../components/medical-records/processing-status-badge'
import { useApiResource } from '../hooks/use-api-resource'
import {
  createMedicalRecordReport,
  downloadMedicalRecordReportPdf,
  getMedicalRecordArchive,
  uploadMedicalRecordFiles,
} from '../lib/api'
import { formatMedicalRecordDateTime, isMedicalRecordStatusActive } from '../lib/medical-records'
import type { MedicalRecordArchiveDetail } from '../types/domain'

function hasPendingWork(archive: MedicalRecordArchiveDetail | null) {
  if (!archive) {
    return false
  }

  return (
    archive.files.some((file) => isMedicalRecordStatusActive(file.processingStatus)) ||
    archive.reports.some((report) => isMedicalRecordStatusActive(report.status))
  )
}

export function MedicalRecordArchivePage() {
  const { archiveId = '' } = useParams()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const {
    data: archive,
    error,
    isLoading,
    reload,
  } = useApiResource(() => getMedicalRecordArchive(archiveId), [archiveId])
  const [actionError, setActionError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [downloadingReportId, setDownloadingReportId] = useState<string | null>(null)

  const shouldPoll = useMemo(() => hasPendingWork(archive), [archive])

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

  async function handleUploadSelection(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    if (files.length === 0 || !archiveId) {
      return
    }

    try {
      setIsUploading(true)
      setActionError(null)
      await uploadMedicalRecordFiles(archiveId, files)
      reload()
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '追加上传失败。'
      setActionError(message)
    } finally {
      event.target.value = ''
      setIsUploading(false)
    }
  }

  async function handleGenerateReport() {
    if (!archiveId) {
      return
    }

    try {
      setIsGenerating(true)
      setActionError(null)
      await createMedicalRecordReport(archiveId)
      reload()
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '生成报告失败。'
      setActionError(message)
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleDownload(reportId: string, pdfFileName?: string | null) {
    try {
      setDownloadingReportId(reportId)
      setActionError(null)
      await downloadMedicalRecordReportPdf(reportId, pdfFileName ?? undefined)
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'PDF 下载失败。'
      setActionError(message)
    } finally {
      setDownloadingReportId(null)
    }
  }

  if (isLoading) {
    return <div className="text-sm text-slate-500">正在加载病历档案详情...</div>
  }

  if (error || !archive) {
    return (
      <div className="rounded-xl border border-rose-100 bg-rose-50 px-5 py-4 text-sm text-rose-700">
        无法加载病历档案详情：{error ?? '档案不存在或尚未同步。'}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={archive.title}
        subtitle={archive.description ?? '该档案用于持续追加病例图片、查看抽取结果并生成版本化健康报告。'}
        trailing={
          <div className="flex flex-wrap items-center gap-2">
            {shouldPoll ? (
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-100 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                正在自动刷新处理状态
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-700 disabled:cursor-not-allowed disabled:text-slate-400"
            >
              <FileUp className="h-4 w-4" />
              {isUploading ? '正在上传...' : '追加病例图片'}
            </button>
            <button
              type="button"
              onClick={handleGenerateReport}
              disabled={isGenerating || archive.files.length === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-teal-300"
            >
              <Sparkles className="h-4 w-4" />
              {isGenerating ? '正在发起...' : '生成新版健康报告'}
            </button>
          </div>
        }
      />

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={handleUploadSelection}
      />

      <SectionPanel
        title="使用边界"
        description="本档案页展示的是病历联合健康报告链路，不会写入 AI 医生聊天上下文，也不会混入 legacy `/reports` 的监测摘要报告。"
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-900">报告免责声明</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">{archive.disclaimer}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-900">档案统计</p>
            <div className="mt-3 space-y-2 text-sm text-slate-600">
              <p>文件数量：{archive.fileCount}</p>
              <p>报告版本：{archive.reportCount}</p>
              <p>最近更新：{formatMedicalRecordDateTime(archive.updatedAt)}</p>
            </div>
          </div>
        </div>
        {actionError ? (
          <div className="mt-4 rounded-lg border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {actionError}
          </div>
        ) : null}
      </SectionPanel>

      <SectionPanel
        title="病例文件"
        description="文件上传后会进入正式处理状态机。成功后会展示抽取摘要；失败则保留错误摘要，便于重试或重新上传。"
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
        {archive.files.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
            <p className="text-sm font-medium text-slate-700">还没有上传病例图片</p>
            <p className="mt-2 text-sm text-slate-500">建议先上传门诊记录、检查单或病例照片，再生成第一版健康报告。</p>
          </div>
        ) : null}

        <div className="space-y-4">
          {archive.files.map((file) => (
            <article key={file.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex min-w-0 gap-4">
                  <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-white">
                    {file.previewUrl ? (
                      <img src={file.previewUrl} alt={file.fileName} className="h-full w-full object-cover" />
                    ) : (
                      <FileImage className="h-8 w-8 text-slate-300" />
                    )}
                  </div>

                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="truncate text-sm font-semibold text-slate-900">{file.fileName}</h3>
                      <ProcessingStatusBadge status={file.processingStatus} />
                    </div>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                      <span>{file.fileType}</span>
                      <span>{file.sizeLabel}</span>
                      <span>上传于 {formatMedicalRecordDateTime(file.uploadedAt)}</span>
                    </div>
                    {file.statusSummary ? (
                      <p className="mt-3 text-sm leading-6 text-slate-600">{file.statusSummary}</p>
                    ) : null}
                  </div>
                </div>

                {file.extraction ? (
                  <div className="rounded-xl border border-slate-200 bg-white p-4 lg:max-w-md">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-slate-900">抽取摘要</p>
                      <ProcessingStatusBadge status={file.extraction.status} />
                    </div>
                    {file.extraction.summary ? (
                      <p className="mt-3 text-sm leading-6 text-slate-600">{file.extraction.summary}</p>
                    ) : null}
                    {file.extraction.highlights.length > 0 ? (
                      <ul className="mt-3 space-y-2 text-sm text-slate-600">
                        {file.extraction.highlights.map((highlight) => (
                          <li key={highlight} className="rounded-lg bg-slate-50 px-3 py-2">
                            {highlight}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {file.extraction.errorSummary ? (
                      <p className="mt-3 text-sm text-rose-700">{file.extraction.errorSummary}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </SectionPanel>

      <SectionPanel
        title="报告历史"
        description="每次重新生成都会保留旧版本。legacy `/reports` 中的监测摘要不会显示在这里。"
      >
        {archive.reports.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
            <p className="text-sm font-medium text-slate-700">尚未生成健康报告</p>
            <p className="mt-2 text-sm text-slate-500">在当前档案内上传病例图片并完成处理后，可发起第一版报告生成。</p>
          </div>
        ) : null}

        <div className="space-y-4">
          {archive.reports.map((report) => (
            <article key={report.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white text-teal-600">
                      <ScrollText className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="text-sm font-semibold text-slate-900">{report.title}</h3>
                        <ProcessingStatusBadge status={report.status} />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                        <span>版本 V{report.version}</span>
                        <span>{report.reportWindowLabel ?? '报告窗口待后端返回'}</span>
                        <span>生成于 {formatMedicalRecordDateTime(report.generatedAt)}</span>
                      </div>
                    </div>
                  </div>
                  {report.summary ? (
                    <p className="mt-3 text-sm leading-6 text-slate-600">{report.summary}</p>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Link
                    to={`/records/reports/${report.id}`}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-700"
                  >
                    查看详情
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleDownload(report.id, report.pdfFileName)}
                    disabled={!report.pdfReady || downloadingReportId === report.id}
                    className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    {downloadingReportId === report.id ? '下载中...' : '下载 PDF'}
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
