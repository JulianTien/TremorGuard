import { type FormEvent, useEffect, useRef, useState } from 'react'
import { Info, MessageSquare, Send } from 'lucide-react'
import { ChatBubble } from '../components/ui/chat-bubble'
import { ComplianceBanner } from '../components/ui/compliance-banner'
import { quickQuestions } from '../mocks/patient-data'
import { sendAiChat } from '../lib/api'
import type { ChatMessage } from '../types/domain'

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: 'welcome-message',
    role: 'assistant',
    content:
      '您好，我是 TremorGuard AI 健康助手。我可以结合您的监测摘要，帮助解释震颤波动、整理复诊沟通重点，并提供通俗的健康管理建议。',
  },
]

function createMessage(role: ChatMessage['role'], content: string): ChatMessage {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return { id: crypto.randomUUID(), role, content }
  }

  return {
    id: `${role}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    content,
  }
}

export function AiDoctorPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) {
      return
    }

    container.scrollTop = container.scrollHeight
  }, [messages, isSending, error])

  async function submitQuestion(rawQuestion: string) {
    const question = rawQuestion.trim()
    if (!question || isSending) {
      return
    }

    const userMessage = createMessage('user', question)
    const nextMessages = [...messages, userMessage]

    setMessages(nextMessages)
    setDraft('')
    setError(null)
    setIsSending(true)

    try {
      const result = await sendAiChat(nextMessages)
      setMessages([...nextMessages, createMessage('assistant', result.message.content)])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'AI 服务暂时不可用，请稍后重试。')
    } finally {
      setIsSending(false)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void submitQuestion(draft)
  }

  return (
    <div className="flex min-h-[calc(100vh-12rem)] flex-col gap-6 lg:flex-row">
      <div className="hidden w-64 shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-white md:flex md:flex-col">
        <div className="border-b border-slate-100 bg-slate-50 p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <MessageSquare className="h-4 w-4 text-teal-600" />
            快速提问
          </h3>
        </div>
        <div className="space-y-2 overflow-y-auto p-3">
          {quickQuestions.map((question) => (
            <button
              key={question}
              type="button"
              className="w-full rounded-lg border border-slate-200 bg-white p-3 text-left text-xs leading-relaxed text-slate-600 transition-colors hover:bg-teal-50 hover:text-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSending}
              onClick={() => {
                void submitQuestion(question)
              }}
            >
              "{question}"
            </button>
          ))}
        </div>
        <div className="mt-auto border-t border-slate-100 p-4">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Info className="h-4 w-4" />
            <span>当前回答基于用户档案、设备状态和当日监测摘要生成。</span>
          </div>
        </div>
      </div>

      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <ComplianceBanner variant="ai" />

        <div ref={scrollContainerRef} className="flex-1 space-y-6 overflow-y-auto bg-slate-50 p-6">
          {messages.map((message) => (
            <ChatBubble key={message.id} message={message} />
          ))}
          {isSending ? (
            <ChatBubble
              message={{
                id: 'sending-message',
                role: 'assistant',
                content: '正在整理您的问题与最新监测摘要，请稍候...',
              }}
            />
          ) : null}
        </div>

        <div className="border-t border-slate-200 bg-white p-4">
          {error ? (
            <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {error}
            </div>
          ) : null}

          <form className="relative flex items-center" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="描述您的症状或疑问..."
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value)
              }}
              className="w-full rounded-full border border-slate-200 bg-slate-50 py-3 pl-4 pr-12 text-sm transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-500"
              disabled={isSending}
            />
            <button
              type="submit"
              className="absolute right-2 rounded-full bg-teal-600 p-2 text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={isSending || !draft.trim()}
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
          <p className="mt-2 text-center text-[10px] text-slate-400">
            AI 生成内容可能存在误差，请以执业医生意见为准。
          </p>
        </div>
      </div>
    </div>
  )
}
