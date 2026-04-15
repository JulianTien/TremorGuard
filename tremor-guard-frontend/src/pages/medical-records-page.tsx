import { ArrowRight, FilePlus2, Files, FolderOpenDot, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/ui/page-header'
import { SectionPanel } from '../components/ui/section-panel'
import { ProcessingStatusBadge } from '../components/medical-records/processing-status-badge'
import { useApiResource } from '../hooks/use-api-resource'
import { createMedicalRecordArchive, getMedicalRecordArchives } from '../lib/api'
import { formatMedicalRecordDateTime } from '../lib/medical-records'

export function MedicalRecordsPage() {
  const navigate = useNavigate()
  const { data, error, isLoading, reload } = useApiResource(getMedicalRecordArchives, [])
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const archiveCountLabel = useMemo(() => {
    const count = data?.length ?? 0
    return `${count} 份病历档案`
  }, [data])

  async function handleCreateArchive(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!title.trim()) {
      setCreateError('请先填写档案标题，例如“北京协和门诊资料”或“2026 春季复诊档案”。')
      return
    }

    try {
      setIsCreating(true)
      setCreateError(null)
      const archive = await createMedicalRecordArchive({
        title: title.trim(),
        description: description.trim() || undefined,
      })
      setTitle('')
      setDescription('')
      reload()
      navigate(`/records/${archive.id}`)
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : '创建病历档案失败。'
      setCreateError(message)
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="病历档案"
        subtitle="用于长期保存历史病例图片、抽取摘要和病历联合健康报告。该入口独立于 AI 医生聊天，也独立于 legacy 监测摘要报告中心。"
        trailing={
          <div className="rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
            非诊断沟通材料
          </div>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <SectionPanel
          title="档案总览"
          description="集中管理历史病例图片、抽取结果和版本化健康报告。新增病例后，可在单个档案内重新生成新版本报告。"
        >
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-3">
                <FolderOpenDot className="h-5 w-5 text-teal-600" />
                <p className="text-sm font-semibold text-slate-900">{archiveCountLabel}</p>
              </div>
              <p className="mt-2 text-sm text-slate-500">每份档案可持续追加病例图片并保留报告历史。</p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-3">
                <Files className="h-5 w-5 text-teal-600" />
                <p className="text-sm font-semibold text-slate-900">状态机驱动</p>
              </div>
              <p className="mt-2 text-sm text-slate-500">
                上传与报告生成都按 `queued / processing / succeeded / failed` 展示。
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-5 w-5 text-teal-600" />
                <p className="text-sm font-semibold text-slate-900">报告边界固定</p>
              </div>
              <p className="mt-2 text-sm text-slate-500">
                新报告只在本域展示，不混入 `/reports` 里的监测摘要报告。
              </p>
            </div>
          </div>
        </SectionPanel>

        <SectionPanel
          title="新建病历档案"
          description="建议按就诊医院、病程阶段或复诊批次创建，便于持续追加和版本跟踪。"
        >
          <form className="space-y-4" onSubmit={handleCreateArchive}>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700">档案标题</span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="例如：2026 春季复诊档案"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:ring-4 focus:ring-teal-100"
              />
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700">备注说明</span>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={4}
                placeholder="记录本档案涵盖的就诊资料、影像检查或阶段说明。"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-teal-500 focus:ring-4 focus:ring-teal-100"
              />
            </label>

            {createError ? (
              <div className="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {createError}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={isCreating}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-teal-300"
            >
              <FilePlus2 className="h-4 w-4" />
              {isCreating ? '正在创建...' : '创建档案'}
            </button>
          </form>
        </SectionPanel>
      </div>

      <SectionPanel
        title="档案列表"
        description="点击任一档案进入详情，查看文件处理状态、抽取摘要和报告版本历史。"
      >
        {isLoading ? <p className="text-sm text-slate-500">正在加载病历档案...</p> : null}
        {error ? (
          <div className="rounded-lg border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            无法加载病历档案：{error}
          </div>
        ) : null}
        {!isLoading && !error && (data?.length ?? 0) === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
            <p className="text-sm font-medium text-slate-700">还没有病历档案</p>
            <p className="mt-2 text-sm text-slate-500">
              先创建一份档案，再上传既往检查单、门诊记录或病例图片。
            </p>
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-2">
          {(data ?? []).map((archive) => (
            <Link
              key={archive.id}
              to={`/records/${archive.id}`}
              className="group rounded-xl border border-slate-200 bg-slate-50 p-5 transition hover:border-teal-200 hover:bg-white hover:shadow-sm"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <FolderOpenDot className="h-5 w-5 text-teal-600" />
                    <h3 className="text-base font-semibold text-slate-900">{archive.title}</h3>
                  </div>
                  {archive.description ? (
                    <p className="text-sm text-slate-500">{archive.description}</p>
                  ) : (
                    <p className="text-sm text-slate-400">暂无额外备注，适合继续追加病例图片和新报告。</p>
                  )}
                </div>
                <ArrowRight className="h-5 w-5 shrink-0 text-slate-300 transition group-hover:text-teal-600" />
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                <span className="rounded-full bg-white px-2.5 py-1 font-medium text-slate-600">
                  {archive.fileCount} 个文件
                </span>
                <span className="rounded-full bg-white px-2.5 py-1 font-medium text-slate-600">
                  {archive.reportCount} 个报告版本
                </span>
                <span>
                  最近活动：{formatMedicalRecordDateTime(archive.latestActivityAt ?? archive.updatedAt)}
                </span>
              </div>

              {archive.latestReportStatus ? (
                <div className="mt-4 flex items-center gap-3">
                  <ProcessingStatusBadge status={archive.latestReportStatus} />
                  <span className="text-xs text-slate-500">
                    最近报告版本 V{archive.latestReportVersion ?? 1}
                  </span>
                </div>
              ) : (
                <p className="mt-4 text-xs text-slate-500">尚未生成病历联合健康报告。</p>
              )}
            </Link>
          ))}
        </div>
      </SectionPanel>
    </div>
  )
}
