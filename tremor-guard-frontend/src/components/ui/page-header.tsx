interface PageHeaderProps {
  title: string
  subtitle?: string
  trailing?: React.ReactNode
}

export function PageHeader({ title, subtitle, trailing }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:flex-row md:items-center md:justify-between">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {subtitle ? <p className="mt-1 text-sm text-slate-500">{subtitle}</p> : null}
      </div>
      {trailing}
    </div>
  )
}
