import { AlertTriangle, Shield } from 'lucide-react'

interface ComplianceBannerProps {
  variant?: 'global' | 'ai'
}

export function ComplianceBanner({ variant = 'global' }: ComplianceBannerProps) {
  if (variant === 'ai') {
    return (
      <section className="flex items-start gap-3 border-b border-amber-200 bg-amber-50 px-4 py-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <p className="text-xs leading-relaxed text-amber-800">
          <strong>安全警告：</strong>
          本 AI 助手的回答仅基于通用医学知识及您的穿戴数据生成，仅供日常健康参考。
          <strong>绝不可替代专业医师的面诊结论与处方建议。</strong>
          严禁依此自行增减药量。
        </p>
      </section>
    )
  }

  return (
    <section className="flex items-center justify-center gap-2 border-t border-slate-200 bg-slate-100 px-6 py-2 text-center text-xs text-slate-500">
      <Shield className="h-3 w-3 shrink-0" />
      <p>
        【医疗合规郑重声明】本系统及“震颤卫士”设备仅界定为 <strong>辅助监测，非诊断设备</strong>
        。数据与 AI 建议仅供健康管理参考，绝不能替代专业医师的当面医学诊断与处方决策。
      </p>
    </section>
  )
}
