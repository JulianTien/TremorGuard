import {
  Activity,
  CalendarDays,
  RefreshCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Waves,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { RehabPlanCard } from '../components/rehab-guidance/rehab-plan-card'
import { RehabPlanStatusBadge } from '../components/rehab-guidance/rehab-plan-status-badge'
import { PageHeader } from '../components/ui/page-header'
import { SectionPanel } from '../components/ui/section-panel'
import { useApiResource } from '../hooks/use-api-resource'
import {
  confirmRehabGuidancePlan,
  DEFAULT_DATA_DATE,
  generateRehabGuidance,
  getRehabGuidance,
} from '../lib/api'
import type { RehabPlan } from '../types/domain'

const missingInputLabels: Record<string, string> = {
  medication_logs: '目标自然日内缺少至少 1 条用药记录',
  tremor_events: '目标自然日内缺少至少 1 条震颤事件',
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return '待生成'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatAsOfDate(value?: string | null) {
  if (!value) {
    return DEFAULT_DATA_DATE
  }

  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

function describePlanDiff(activePlan: RehabPlan | null, candidatePlan: RehabPlan | null) {
  if (!activePlan || !candidatePlan) {
    return []
  }

  const diffs: string[] = []
  const maxLength = Math.max(activePlan.items.length, candidatePlan.items.length)

  for (let index = 0; index < maxLength; index += 1) {
    const activeItem = activePlan.items[index]
    const candidateItem = candidatePlan.items[index]

    if (!activeItem && candidateItem) {
      diffs.push(`新增训练项：${candidateItem.name}`)
      continue
    }

    if (activeItem && !candidateItem) {
      diffs.push(`移除训练项：${activeItem.name}`)
      continue
    }

    if (!activeItem || !candidateItem) {
      continue
    }

    if (activeItem.name !== candidateItem.name) {
      diffs.push(`训练项由“${activeItem.name}”调整为“${candidateItem.name}”`)
    }

    if (activeItem.durationMinutes !== candidateItem.durationMinutes) {
      diffs.push(
        `${candidateItem.name} 时长由 ${activeItem.durationMinutes} 分钟调整为 ${candidateItem.durationMinutes} 分钟`,
      )
    }

    if (activeItem.frequencyLabel !== candidateItem.frequencyLabel) {
      diffs.push(
        `${candidateItem.name} 频率由“${activeItem.frequencyLabel}”调整为“${candidateItem.frequencyLabel}”`,
      )
    }
  }

  return diffs.slice(0, 5)
}

export function RehabGuidancePage() {
  const {
    data,
    error,
    isLoading,
    reload,
  } = useApiResource(() => getRehabGuidance(DEFAULT_DATA_DATE), [])
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isConfirming, setIsConfirming] = useState(false)

  const candidatePlan = data?.candidatePlan ?? null
  const activePlan = data?.activePlan ?? null
  const canGenerate = data?.generationEligibility === 'eligible'
  const hasConflict = data?.conflictStatus === 'conflicting'
  const hasInsufficientData = data?.conflictStatus === 'insufficient_data'
  const diffSummary = useMemo(
    () => describePlanDiff(activePlan, candidatePlan),
    [activePlan, candidatePlan],
  )

  async function handleGenerate() {
    try {
      setIsGenerating(true)
      setActionError(null)
      setActionMessage(null)
      await generateRehabGuidance(DEFAULT_DATA_DATE)
      setActionMessage('已生成新的候选康复计划，请先复核后再确认启用。')
      reload()
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : '生成康复训练计划失败。'
      setActionError(message)
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleConfirm() {
    if (!candidatePlan) {
      return
    }

    try {
      setIsConfirming(true)
      setActionError(null)
      setActionMessage(null)
      await confirmRehabGuidancePlan(candidatePlan.id)
      setActionMessage('候选计划已确认并切换为当前激活计划。')
      reload()
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : '确认康复训练计划失败。'
      setActionError(message)
    } finally {
      setIsConfirming(false)
    }
  }

  if (isLoading && !data) {
    return <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">正在加载康复训练计划...</div>
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
        无法加载康复训练计划：{error ?? '未知错误'}
      </div>
    )
  }

  const visibleStatus = candidatePlan?.status ?? activePlan?.status ?? null

  return (
    <div className="space-y-6">
      <PageHeader
        title="个性化训练计划"
        subtitle="基于目标自然日的用药记录与震颤趋势，生成可复核、可确认的辅助性康复训练建议。"
        trailing={
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
              {formatAsOfDate(data.evidenceSummary.asOfDate)}
            </span>
            {visibleStatus ? <RehabPlanStatusBadge status={visibleStatus} /> : null}
          </div>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="rounded-xl border border-slate-200 bg-slate-900 p-5 text-white shadow-sm">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-white/10 p-2.5 text-teal-300">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">辅助指导边界</h3>
              <p className="mt-2 text-sm leading-6 text-slate-300">{data.disclaimer}</p>
            </div>
          </div>
        </div>

        <div
          className={[
            'rounded-xl border p-5 shadow-sm',
            hasConflict
              ? 'border-amber-100 bg-amber-50 text-amber-900'
              : hasInsufficientData
                ? 'border-slate-200 bg-slate-100 text-slate-900'
                : 'border-emerald-100 bg-emerald-50 text-emerald-900',
          ].join(' ')}
        >
          <div className="flex items-start gap-3">
            <div
              className={[
                'rounded-xl p-2.5',
                hasConflict
                  ? 'bg-amber-100 text-amber-700'
                  : hasInsufficientData
                    ? 'bg-white text-slate-600'
                    : 'bg-emerald-100 text-emerald-700',
              ].join(' ')}
            >
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">
                {hasConflict
                  ? '检测到用药与震颤信号冲突'
                  : hasInsufficientData
                    ? '当前目标日证据不足'
                    : '当前证据可用于计划生成'}
              </h3>
              <p className="mt-2 text-sm leading-6">
                {hasConflict
                  ? '系统仍会生成候选计划，但会保留风险标记并要求你显式确认后才生效。'
                  : hasInsufficientData
                    ? '当前页面会明确告知缺失输入项，并在证据补齐前隐藏“生成新计划”操作。'
                    : '当前页面只提供白名单内的辅助训练建议，所有候选计划都需要你确认后才会激活。'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <SectionPanel
        title="目标日证据摘要"
        description="V1 固定按 `calendar_day` 聚合目标自然日证据；数据不足时不生成伪计划。"
        action={
          canGenerate ? (
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating}
              className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-teal-300"
            >
              <Sparkles className="h-4 w-4" />
              {isGenerating ? '生成中...' : '生成新计划'}
            </button>
          ) : null
        }
      >
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <CalendarDays className="h-4 w-4 text-teal-600" />
              证据窗口
            </p>
            <p className="mt-3 text-sm text-slate-600">{formatAsOfDate(data.evidenceSummary.asOfDate)}</p>
            <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-400">
              {data.evidenceSummary.evaluationWindow ?? 'calendar_day'}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <ShieldCheck className="h-4 w-4 text-teal-600" />
              用药摘要
            </p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              {data.evidenceSummary.medicationWindowSummary}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Waves className="h-4 w-4 text-teal-600" />
              震颤趋势
            </p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              {data.evidenceSummary.tremorTrendSummary}
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Activity className="h-4 w-4 text-teal-600" />
              一致性解释
            </p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              {data.evidenceSummary.signalConsistency}
            </p>
            <p className="mt-2 text-xs leading-5 text-slate-500">{data.evidenceSummary.explanation}</p>
          </div>
        </div>

        {actionError ? (
          <div className="mt-4 rounded-lg border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {actionError}
          </div>
        ) : null}

        {actionMessage ? (
          <div className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {actionMessage}
          </div>
        ) : null}

        {!canGenerate ? (
          <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-6">
            <p className="text-sm font-semibold text-slate-900">当前目标日证据不足，暂不开放“生成新计划”。</p>
            <p className="mt-2 text-sm text-slate-500">
              需要至少 1 条用药记录和 1 条震颤事件后，系统才会按目标自然日组合候选计划。
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {data.missingInputs.map((input) => (
                <span
                  key={input}
                  className="rounded-full border border-amber-100 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800"
                >
                  {missingInputLabels[input] ?? input}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </SectionPanel>

      <SectionPanel
        title="候选计划与当前计划"
        description="候选计划只有在你明确确认后才会替换当前激活计划。再次生成会覆盖旧候选计划，但不会自动覆盖激活计划。"
      >
        <div className="space-y-6">
          {candidatePlan ? (
            <RehabPlanCard
              title="待确认候选计划"
              description={`最近生成时间：${formatDateTime(candidatePlan.generatedAt ?? data.generatedAt)}`}
              plan={candidatePlan}
              footer={
                <div className="space-y-3">
                  <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-3 text-sm text-amber-900">
                    该计划尚未生效。请先核对训练类型、时长、频率和注意事项，再决定是否启用。
                  </div>
                  {candidatePlan.requiresConfirmation ? (
                    <button
                      type="button"
                      onClick={handleConfirm}
                      disabled={isConfirming}
                      className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      <ShieldCheck className="h-4 w-4" />
                      {isConfirming ? '确认中...' : '确认启用该计划'}
                    </button>
                  ) : (
                    <p className="text-sm text-slate-500">当前候选计划不需要再次确认。</p>
                  )}
                </div>
              }
            />
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center">
              <p className="text-sm font-semibold text-slate-900">还没有新的候选计划</p>
              <p className="mt-2 text-sm text-slate-500">
                {canGenerate
                  ? '点击“生成新计划”后，系统会按目标自然日生成一份待确认候选计划。'
                  : '当前先补齐目标自然日的用药与震颤数据，之后才会开放候选计划生成。'}
              </p>
            </div>
          )}

          {candidatePlan && activePlan ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h4 className="text-base font-semibold text-slate-900">候选计划与当前计划差异</h4>
                  <p className="mt-1 text-sm text-slate-500">帮助用户在确认前快速判断本次调整是否合理。</p>
                </div>
                <button
                  type="button"
                  onClick={reload}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-teal-200 hover:text-teal-700"
                >
                  <RefreshCcw className="h-3.5 w-3.5" />
                  刷新状态
                </button>
              </div>
              {diffSummary.length > 0 ? (
                <ul className="mt-4 space-y-2 text-sm text-slate-700">
                  {diffSummary.map((diff) => (
                    <li key={diff} className="rounded-lg border border-slate-200 bg-white px-3 py-3">
                      {diff}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-4 text-sm text-slate-500">本次候选计划与当前计划结构相同，主要差异来自解释文本或风险标记。</p>
              )}
            </div>
          ) : null}

          {activePlan ? (
            <RehabPlanCard
              title="当前激活计划"
              description={`当前有效计划更新时间：${formatDateTime(activePlan.confirmedAt ?? activePlan.generatedAt ?? data.generatedAt)}`}
              plan={activePlan}
              footer={
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-600">
                  当前激活计划在你确认新的候选计划之前会持续保持有效。
                </div>
              }
            />
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center">
              <p className="text-sm font-semibold text-slate-900">当前还没有激活计划</p>
              <p className="mt-2 text-sm text-slate-500">当候选计划确认后，它会成为这里展示的当前激活计划。</p>
            </div>
          )}
        </div>
      </SectionPanel>
    </div>
  )
}
