import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownTone = 'default' | 'inverse' | 'muted'

interface MarkdownRendererProps {
  content: string
  tone?: MarkdownTone
  className?: string
}

function joinClasses(...classes: Array<string | null | undefined | false>) {
  return classes.filter(Boolean).join(' ')
}

export function MarkdownRenderer({
  content,
  tone = 'default',
  className,
}: MarkdownRendererProps) {
  const palette =
    tone === 'inverse'
      ? {
          body: 'text-white',
          strong: 'text-white',
          blockquote: 'border-l-white/40 text-white/85',
          inlineCode: 'bg-white/10 text-white',
          codeBlock: 'border border-white/10 bg-slate-950/60 text-white',
          hr: 'border-white/15',
          link: 'text-white underline underline-offset-4',
          tableHead: 'bg-white/10',
          tableCell: 'border-t border-white/10',
        }
      : tone === 'muted'
        ? {
            body: 'text-slate-600',
            strong: 'text-slate-900',
            blockquote: 'border-l-slate-300 text-slate-600',
            inlineCode: 'bg-slate-200 text-slate-900',
            codeBlock: 'border border-slate-200 bg-slate-900 text-slate-100',
            hr: 'border-slate-200',
            link: 'text-teal-700 underline underline-offset-4',
            tableHead: 'bg-slate-100',
            tableCell: 'border-t border-slate-200',
          }
        : {
            body: 'text-slate-700',
            strong: 'text-slate-900',
            blockquote: 'border-l-slate-300 text-slate-600',
            inlineCode: 'bg-slate-100 text-slate-900',
            codeBlock: 'border border-slate-200 bg-slate-900 text-slate-100',
            hr: 'border-slate-200',
            link: 'text-teal-700 underline underline-offset-4',
            tableHead: 'bg-slate-100',
            tableCell: 'border-t border-slate-200',
          }

  return (
    <div className={joinClasses('text-sm leading-7', palette.body, className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className={joinClasses('mt-5 text-lg font-semibold', palette.strong)}>{children}</h1>,
          h2: ({ children }) => <h2 className={joinClasses('mt-5 text-base font-semibold', palette.strong)}>{children}</h2>,
          h3: ({ children }) => <h3 className={joinClasses('mt-4 text-sm font-semibold', palette.strong)}>{children}</h3>,
          h4: ({ children }) => <h4 className={joinClasses('mt-4 text-sm font-medium', palette.strong)}>{children}</h4>,
          p: ({ children }) => <p className="my-3 whitespace-pre-wrap">{children}</p>,
          ul: ({ children }) => <ul className="my-3 list-disc space-y-2 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="my-3 list-decimal space-y-2 pl-5">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          strong: ({ children }) => <strong className={joinClasses('font-semibold', palette.strong)}>{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          hr: () => <hr className={joinClasses('my-4 border-t', palette.hr)} />,
          blockquote: ({ children }) => (
            <blockquote className={joinClasses('my-4 border-l-4 pl-4 italic', palette.blockquote)}>
              {children}
            </blockquote>
          ),
          a: ({ children, ...props }) => (
            <a {...props} className={palette.link} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
          pre: ({ children }) => <pre className="my-4 overflow-x-auto">{children}</pre>,
          code: ({ children, className: codeClassName, ...props }) => {
            const isBlock = Boolean(codeClassName)
            if (isBlock) {
              return (
                <code
                  {...props}
                  className={joinClasses(
                    'block overflow-x-auto rounded-lg px-3 py-2 font-mono text-xs leading-6',
                    palette.codeBlock,
                    codeClassName,
                  )}
                >
                  {children}
                </code>
              )
            }

            return (
              <code
                {...props}
                className={joinClasses('rounded px-1.5 py-0.5 font-mono text-[0.85em]', palette.inlineCode)}
              >
                {children}
              </code>
            )
          },
          table: ({ children }) => <table className="my-4 w-full border-collapse text-left">{children}</table>,
          thead: ({ children }) => <thead className={palette.tableHead}>{children}</thead>,
          th: ({ children }) => <th className="px-3 py-2 text-xs font-semibold">{children}</th>,
          td: ({ children }) => <td className={joinClasses('px-3 py-2 align-top', palette.tableCell)}>{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
