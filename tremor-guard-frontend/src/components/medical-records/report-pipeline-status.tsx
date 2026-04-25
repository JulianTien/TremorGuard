import type { MedicalRecordPipelineStage, MedicalRecordReportPipelineState } from '../../types/domain'

interface ReportPipelineStatusProps {
  pipelineState?: MedicalRecordReportPipelineState | null
}

function resolveTone(status: MedicalRecordPipelineStage['status']) {
  switch (status) {
    case 'succeeded':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700'
    case 'failed':
      return 'border-rose-200 bg-rose-50 text-rose-700'
    case 'processing':
      return 'border-amber-200 bg-amber-50 text-amber-700'
    default:
      return 'border-slate-200 bg-slate-50 text-slate-500'
  }
}

export function ReportPipelineStatus({ pipelineState }: ReportPipelineStatusProps) {
  if (!pipelineState) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
        当前报告尚未返回流水线状态。
      </div>
    )
  }

  const stages = [
    { key: 'template', label: '模板注入', stage: pipelineState.template },
    { key: 'llm', label: 'AI 生成', stage: pipelineState.llm },
    { key: 'pdf', label: 'PDF 转换', stage: pipelineState.pdf },
  ]

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {stages.map(({ key, label, stage }) => (
        <article
          key={key}
          className={['rounded-xl border p-4', resolveTone(stage.status)].join(' ')}
        >
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">{label}</h3>
            <span className="text-xs font-medium uppercase tracking-[0.16em]">{stage.status}</span>
          </div>
          {stage.detail ? <p className="mt-2 text-sm leading-6">{stage.detail}</p> : null}
          {stage.error ? <p className="mt-2 text-sm leading-6">{stage.error}</p> : null}
        </article>
      ))}
    </div>
  )
}
