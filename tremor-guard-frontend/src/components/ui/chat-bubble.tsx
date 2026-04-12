import { Stethoscope, User } from 'lucide-react'
import type { ChatMessage } from '../../types/domain'

interface ChatBubbleProps {
  message: ChatMessage
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isAssistant = message.role === 'assistant'

  return (
    <div className={`flex gap-4 ${isAssistant ? '' : 'flex-row-reverse'}`}>
      <div
        className={[
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isAssistant ? 'bg-teal-600 text-white' : 'bg-slate-300 text-slate-700',
        ].join(' ')}
      >
        {isAssistant ? <Stethoscope className="h-4 w-4" /> : <User className="h-4 w-4" />}
      </div>
      <article
        className={[
          'max-w-[80%] rounded-2xl p-4 text-sm leading-relaxed shadow-sm',
          isAssistant
            ? 'rounded-tl-sm border border-slate-200 bg-white text-slate-700'
            : 'rounded-tr-sm bg-teal-600 text-white',
        ].join(' ')}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
      </article>
    </div>
  )
}
