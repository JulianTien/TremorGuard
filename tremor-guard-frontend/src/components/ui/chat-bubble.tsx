import { Stethoscope, Trash2, User } from 'lucide-react'
import type { AiChatAction, ChatMessage } from '../../types/domain'
import { ChatActionCard } from './chat-action-card'
import { MarkdownRenderer } from './markdown-renderer'

interface ChatBubbleProps {
  message: ChatMessage
  onDelete?: () => void
  onAction?: (action: AiChatAction) => void
  actionDisabled?: boolean
  isStreaming?: boolean
  streamingLabel?: string
}

export function ChatBubble({
  message,
  onDelete,
  onAction,
  actionDisabled = false,
  isStreaming = false,
  streamingLabel,
}: ChatBubbleProps) {
  const isAssistant = message.role === 'assistant'

  return (
    <div className={`group flex gap-4 ${isAssistant ? '' : 'flex-row-reverse'}`}>
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
          'relative max-w-[80%] rounded-2xl p-4 pr-12 text-sm leading-relaxed shadow-sm',
          isAssistant
            ? 'rounded-tl-sm border border-slate-200 bg-white text-slate-700'
            : 'rounded-tr-sm bg-teal-600 text-white',
        ].join(' ')}
      >
        {onDelete ? (
          <button
            type="button"
            onClick={onDelete}
            className={[
              'absolute right-3 top-3 rounded-full p-1 transition-opacity',
              isAssistant
                ? 'text-slate-400 hover:bg-slate-100 hover:text-rose-500'
                : 'text-white/70 hover:bg-white/10 hover:text-white',
              'opacity-0 group-hover:opacity-100',
            ].join(' ')}
            aria-label="删除这条消息"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        ) : null}
        {isAssistant && isStreaming ? (
          <div className="mb-2 flex items-center gap-2 text-[11px] font-medium text-teal-600">
            <span className="inline-flex h-2 w-2 rounded-full bg-teal-500 animate-pulse" />
            <span>{streamingLabel ?? 'AI 医生正在回复'}</span>
          </div>
        ) : null}
        <MarkdownRenderer
          content={message.content}
          tone={isAssistant ? 'default' : 'inverse'}
          className="max-w-none"
        />
        {isAssistant && isStreaming ? (
          <div className="mt-1 flex items-center gap-1 text-xs text-teal-500">
            <span className="inline-flex h-4 w-1 rounded-full bg-teal-500 animate-pulse" />
          </div>
        ) : null}
        {isAssistant && onAction
          ? (message.actionCards ?? []).map((card) => (
              <ChatActionCard
                key={`${message.id}-${card.resourceId}-${card.type}`}
                card={card}
                onAction={onAction}
                disabled={actionDisabled}
              />
            ))
          : null}
      </article>
    </div>
  )
}
