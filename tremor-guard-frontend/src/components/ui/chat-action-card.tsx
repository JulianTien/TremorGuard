import { FileDown, FileText, CheckCircle2, Sparkles } from 'lucide-react'
import type { AiChatAction, AiChatActionCard, MedicalRecordProcessingStatus } from '../../types/domain'

interface ChatActionCardProps {
  card: AiChatActionCard
  onAction: (action: AiChatAction) => void
  disabled?: boolean
}

function resolveActionIcon(kind: AiChatAction['kind']) {
  switch (kind) {
    case 'confirm_plan':
      return CheckCircle2
    case 'download_plan_pdf':
    case 'download_report_pdf':
      return FileDown
    default:
      return FileText
  }
}

function resolveStageTone(status: MedicalRecordProcessingStatus) {
  switch (status) {
    case 'succeeded':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700'
    case 'failed':
      return 'border-rose-200 bg-rose-50 text-rose-700'
    case 'processing':
      return 'border-amber-200 bg-amber-50 text-amber-700'
    default:
      return 'border-slate-200 bg-white text-slate-500'
  }
}

export function ChatActionCard({ card, onAction, disabled = false }: ChatActionCardProps) {
  const pipelineStages = card.pipelineState
    ? [
        { key: 'template', label: '模板注入', stage: card.pipelineState.template },
        { key: 'llm', label: 'AI 生成', stage: card.pipelineState.llm },
        { key: 'pdf', label: 'PDF 转换', stage: card.pipelineState.pdf },
      ]
    : []

  return (
    <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-white p-2 text-teal-600 shadow-sm">
          {card.type === 'rehab_plan_candidate' ? (
            <Sparkles className="h-4 w-4" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-slate-900">{card.title}</h4>
            {card.agentType ? (
              <span className="rounded-full bg-teal-100 px-2.5 py-1 text-[11px] font-medium text-teal-700">
                {card.agentType === 'health_report_agent' ? '报告生成 Agent' : card.agentType}
              </span>
            ) : null}
            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">
              {card.status}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{card.summary}</p>
          {pipelineStages.length > 0 ? (
            <div className="mt-3 grid gap-2">
              {pipelineStages.map(({ key, label, stage }) => (
                <div
                  key={key}
                  className={[
                    'rounded-lg border px-3 py-2 text-xs',
                    resolveStageTone(stage.status),
                  ].join(' ')}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">{label}</span>
                    <span>{stage.status}</span>
                  </div>
                  {stage.detail ? <p className="mt-1 leading-5">{stage.detail}</p> : null}
                  {stage.error ? <p className="mt-1 leading-5">{stage.error}</p> : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {card.actions.map((action) => {
          const ActionIcon = resolveActionIcon(action.kind)
          return (
            <button
              key={action.key}
              type="button"
              disabled={disabled}
              onClick={() => onAction(action)}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-teal-200 hover:text-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ActionIcon className="h-3.5 w-3.5" />
              {action.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
