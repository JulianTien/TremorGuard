import type { PropsWithChildren, ReactNode } from 'react'

interface SectionPanelProps extends PropsWithChildren {
  title?: string
  description?: string
  action?: ReactNode
  className?: string
  bodyClassName?: string
}

export function SectionPanel({
  title,
  description,
  action,
  className = '',
  bodyClassName = '',
  children,
}: SectionPanelProps) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`.trim()}>
      {title || description || action ? (
        <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            {title ? <h3 className="text-base font-semibold text-slate-900">{title}</h3> : null}
            {description ? <p className="mt-1 text-sm text-slate-500">{description}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      <div className={`p-5 ${bodyClassName}`.trim()}>{children}</div>
    </section>
  )
}
