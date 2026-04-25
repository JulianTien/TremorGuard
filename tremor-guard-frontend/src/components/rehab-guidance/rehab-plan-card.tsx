import { ActivitySquare, Clock3, ShieldAlert, Waves } from 'lucide-react'
import type { ReactNode } from 'react'
import type { RehabPlan } from '../../types/domain'
import { RehabPlanStatusBadge } from './rehab-plan-status-badge'

interface RehabPlanCardProps {
  title: string
  description: string
  plan: RehabPlan
  footer?: ReactNode
}

export function RehabPlanCard({ title, description, plan, footer }: RehabPlanCardProps) {
  return (
    <article className="rounded-xl border border-slate-200 bg-slate-50 p-5">
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-4 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-base font-semibold text-slate-900">{title}</h4>
            <RehabPlanStatusBadge status={plan.status} />
            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">
              V{plan.version}
            </span>
          </div>
          <p className="text-sm text-slate-500">{description}</p>
          <p className="text-sm font-medium text-slate-800">{plan.title}</p>
          <div className="inline-flex items-center gap-2 rounded-full border border-teal-100 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-700">
            <Waves className="h-3.5 w-3.5" />
            {plan.scenario}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
        <div className="space-y-3">
          {plan.items.map((item, index) => (
            <div
              key={`${plan.id}-${item.templateId}-${index}`}
              className="rounded-xl border border-slate-200 bg-white p-4"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
                      {item.category}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">模板来源：{item.templateId}</p>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 md:min-w-[180px]">
                  <div className="rounded-lg bg-slate-50 px-3 py-2">
                    <span className="flex items-center gap-1.5 font-medium text-slate-500">
                      <Clock3 className="h-3.5 w-3.5" />
                      时长
                    </span>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{item.durationMinutes} 分钟</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 px-3 py-2">
                    <span className="flex items-center gap-1.5 font-medium text-slate-500">
                      <ActivitySquare className="h-3.5 w-3.5" />
                      频率
                    </span>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{item.frequencyLabel}</p>
                  </div>
                </div>
              </div>

              <div className="mt-3 rounded-lg border border-amber-100 bg-amber-50 px-3 py-3">
                <p className="flex items-center gap-1.5 text-xs font-medium text-amber-800">
                  <ShieldAlert className="h-3.5 w-3.5" />
                  注意事项
                </p>
                {item.cautions.length > 0 ? (
                  <ul className="mt-2 space-y-1 text-sm text-amber-900">
                    {item.cautions.map((caution) => (
                      <li key={caution}>- {caution}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-sm text-amber-900">请按页面提示适度训练，若不适加重请暂停并联系医生。</p>
                )}
              </div>

              <div className="mt-3 rounded-lg border border-teal-100 bg-teal-50 px-3 py-3">
                <p className="text-xs font-medium text-teal-800">训练目标</p>
                <p className="mt-2 text-sm text-teal-900">
                  {item.goal ?? `本训练用于帮助完成${item.name}这一模块。`}
                </p>
              </div>

              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-xs font-medium text-slate-700">训练前准备</p>
                  {item.preparation.length > 0 ? (
                    <ul className="mt-2 space-y-1 text-sm text-slate-700">
                      {item.preparation.map((step) => (
                        <li key={step}>- {step}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">按当前页面环境保持安全、稳定后开始训练。</p>
                  )}
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-xs font-medium text-slate-700">完成标准</p>
                  <p className="mt-2 text-sm text-slate-700">
                    {item.completionCheck ?? '完成后应保持动作稳定，且没有出现明显不适。'}
                  </p>
                </div>
              </div>

              <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-3">
                <p className="text-xs font-medium text-slate-700">具体训练步骤</p>
                {item.steps.length > 0 ? (
                  <ol className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
                    {item.steps.map((step, index) => (
                      <li key={`${item.templateId}-${index}`} className="flex gap-2">
                        <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600">
                          {index + 1}
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="mt-2 text-sm text-slate-500">当前方案暂无分步骤说明，请结合训练时长和频率缓慢完成。</p>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm font-semibold text-slate-900">调整说明</p>
            <p className="mt-3 text-sm leading-6 text-slate-600">{plan.rationale}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm font-semibold text-slate-900">风险标记</p>
            {plan.riskFlags.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {plan.riskFlags.map((flag) => (
                  <span
                    key={flag}
                    className="rounded-full border border-amber-100 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800"
                  >
                    {flag}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">当前计划没有额外风险标记。</p>
            )}
          </div>

          {footer ? (
            <div className="rounded-xl border border-slate-200 bg-white p-4">{footer}</div>
          ) : null}
        </div>
      </div>
    </article>
  )
}
