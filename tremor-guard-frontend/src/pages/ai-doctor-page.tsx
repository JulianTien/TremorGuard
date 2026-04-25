import { startTransition, type FormEvent, useEffect, useRef, useState } from 'react'
import { Eraser, FileText, Info, MessageSquare, Send, Sparkles, Stethoscope } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { ChatBubble } from '../components/ui/chat-bubble'
import { ComplianceBanner } from '../components/ui/compliance-banner'
import { quickQuestions } from '../mocks/patient-data'
import { downloadPdfFromApiPath, executeAiAction, getAiHealthReportActionCard, streamAiChat } from '../lib/api'
import { useAuth } from '../lib/auth-context'
import type { AiChatAction, ChatMessage } from '../types/domain'

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: 'welcome-message',
    role: 'assistant',
    content:
      '您好，我是 TremorGuard AI 健康助手。我可以结合您的监测摘要，帮助解释震颤波动、整理复诊沟通重点，并提供通俗的健康管理建议。',
  },
]

const AI_CHAT_STORAGE_PREFIX = 'tremor-guard-ai-chat'
const THINKING_STATUS_LINES = [
  '我先看一下你今天的监测摘要。',
  '正在对照近期用药记录和波动趋势。',
  '把重点整理成更好理解的话。',
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

function buildChatStorageKey(userId: string) {
  return `${AI_CHAT_STORAGE_PREFIX}:${userId}`
}

function loadPersistedMessages(userId: string): ChatMessage[] {
  const raw = localStorage.getItem(buildChatStorageKey(userId))
  if (!raw) {
    return INITIAL_MESSAGES
  }

  try {
    const parsed = JSON.parse(raw) as ChatMessage[]
    if (!Array.isArray(parsed) || parsed.length === 0) {
      return INITIAL_MESSAGES
    }

    return parsed
      .filter(
        (message): message is ChatMessage =>
          Boolean(
            message &&
              (typeof message.id === 'string' || typeof message.id === 'number') &&
              (message.role === 'assistant' || message.role === 'user') &&
              typeof message.content === 'string',
          ),
      )
      .slice(0, 100)
  } catch {
    return INITIAL_MESSAGES
  }
}

export function AiDoctorPage() {
  const navigate = useNavigate()
  const { currentUser } = useAuth()
  const currentUserId = currentUser?.id ?? null
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const [isExecutingAction, setIsExecutingAction] = useState(false)
  const [pendingStatusIndex, setPendingStatusIndex] = useState(0)
  const [streamingMessage, setStreamingMessage] = useState<ChatMessage | null>(null)
  const [storageReadyForUserId, setStorageReadyForUserId] = useState<string | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const composerInputRef = useRef<HTMLInputElement | null>(null)

  function focusComposerInput() {
    window.requestAnimationFrame(() => {
      composerInputRef.current?.focus({ preventScroll: true })
    })
  }

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) {
      return
    }

    container.scrollTop = container.scrollHeight
  }, [messages, streamingMessage, isSending, error])

  useEffect(() => {
    if (!(isSending || isExecutingAction) || streamingMessage) {
      setPendingStatusIndex(0)
      return undefined
    }

    const handle = window.setInterval(() => {
      setPendingStatusIndex((current) => (current + 1) % THINKING_STATUS_LINES.length)
    }, 1500)

    return () => {
      window.clearInterval(handle)
    }
  }, [isExecutingAction, isSending, streamingMessage])

  useEffect(() => {
    if (!currentUserId) {
      setStorageReadyForUserId(null)
      setMessages(INITIAL_MESSAGES)
      return
    }

    setMessages(loadPersistedMessages(currentUserId))
    setError(null)
    setStorageReadyForUserId(currentUserId)
  }, [currentUserId])

  useEffect(() => {
    if (!currentUserId || storageReadyForUserId !== currentUserId) {
      return
    }

    localStorage.setItem(buildChatStorageKey(currentUserId), JSON.stringify(messages))
  }, [currentUserId, messages, storageReadyForUserId])

  useEffect(() => {
    const reportIds = Array.from(
      new Set(
        messages.flatMap((message) =>
          (message.actionCards ?? [])
            .filter(
              (card) =>
                card.type === 'health_report_candidate' &&
                Boolean(
                  card.pipelineState &&
                    [card.pipelineState.template, card.pipelineState.llm, card.pipelineState.pdf].some(
                      (stage) => stage.status === 'queued' || stage.status === 'processing',
                    ),
                ),
            )
            .map((card) => card.resourceId),
        ),
      ),
    )

    if (reportIds.length === 0) {
      return undefined
    }

    let cancelled = false

    async function refreshCards() {
      const refreshedCards = await Promise.all(
        reportIds.map(async (reportId) => {
          try {
            return await getAiHealthReportActionCard(reportId)
          } catch {
            return null
          }
        }),
      )

      if (cancelled) {
        return
      }

      setMessages((current) =>
        current.map((message) => ({
          ...message,
          actionCards: (message.actionCards ?? []).map((card) => {
            if (card.type !== 'health_report_candidate') {
              return card
            }

            const refreshed = refreshedCards.find((candidate) => candidate?.resourceId === card.resourceId)
            return refreshed ?? card
          }),
        })),
      )
    }

    void refreshCards()
    const handle = window.setInterval(() => {
      void refreshCards()
    }, 4000)

    return () => {
      cancelled = true
      window.clearInterval(handle)
    }
  }, [messages])

  async function submitQuestion(rawQuestion: string) {
    const question = rawQuestion.trim()
    if (!question || isSending || isExecutingAction) {
      return
    }

    const userMessage = createMessage('user', question)
    const nextMessages = [...messages, userMessage]

    setMessages(nextMessages)
    setDraft('')
    setError(null)
    setIsSending(true)
    focusComposerInput()

    try {
      const assistantMessageId = createMessage('assistant', '').id
      let streamedContent = ''

      const result = await streamAiChat(nextMessages, {
        onChunk: (content) => {
          streamedContent += content
          startTransition(() => {
            setStreamingMessage({
              id: assistantMessageId,
              role: 'assistant',
              content: streamedContent,
            })
          })
        },
      })

      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: result.message.content,
        actionCards: result.actionCards,
      }
      setMessages((current) => [...current, assistantMessage])
      setStreamingMessage(null)
    } catch (requestError) {
      setStreamingMessage(null)
      setError(requestError instanceof Error ? requestError.message : 'AI 服务暂时不可用，请稍后重试。')
    } finally {
      setIsSending(false)
      focusComposerInput()
    }
  }

  async function handleAction(action: AiChatAction) {
    setError(null)

    if (action.kind === 'view_plan_detail' || action.kind === 'view_report_online') {
      if (action.url) {
        navigate(action.url)
      }
      return
    }

    if (action.kind === 'download_plan_pdf' || action.kind === 'download_report_pdf') {
      if (!action.apiPath) {
        setError('下载地址缺失，暂时无法完成该操作。')
        return
      }

      try {
        setIsExecutingAction(true)
        await downloadPdfFromApiPath(action.apiPath, action.downloadName ?? undefined)
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : 'PDF 下载失败。')
      } finally {
        setIsExecutingAction(false)
      }
      return
    }

    if (!action.apiPath) {
      setError('操作地址缺失，暂时无法完成该操作。')
      return
    }

    try {
      setIsExecutingAction(true)
      const result = await executeAiAction(action.apiPath)
      setMessages((current) => [
        ...current,
        {
          ...createMessage('assistant', result.message.content),
          actionCards: result.actionCards,
        },
      ])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '操作失败，请稍后重试。')
    } finally {
      setIsExecutingAction(false)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void submitQuestion(draft)
  }

  function handleDeleteMessage(messageId: ChatMessage['id']) {
    setMessages((current) => {
      const nextMessages = current.filter((message) => message.id !== messageId)
      return nextMessages.length > 0 ? nextMessages : INITIAL_MESSAGES
    })
  }

  function handleClearMessages() {
    setMessages(INITIAL_MESSAGES)
    setError(null)
  }

  async function handleExplainCurrentState() {
    await submitQuestion('请结合我今天的监测和用药记录，解读当前状态，并整理我下一次复诊时最值得沟通的重点。')
  }

  async function handleGenerateRehabPlan() {
    try {
      setIsExecutingAction(true)
      setError(null)
      const result = await executeAiAction('/v1/ai/actions/rehab-plan/generate')
      setMessages((current) => [
        ...current,
        {
          ...createMessage('assistant', result.message.content),
          actionCards: result.actionCards,
        },
      ])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '生成康复计划失败，请稍后重试。')
    } finally {
      setIsExecutingAction(false)
    }
  }

  async function handleGenerateHealthReport() {
    try {
      setIsExecutingAction(true)
      setError(null)
      const result = await executeAiAction('/v1/ai/actions/health-report/generate')
      setMessages((current) => [
        ...current,
        {
          ...createMessage('assistant', result.message.content),
          actionCards: result.actionCards,
        },
      ])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '生成 AI 健康报告失败，请稍后重试。')
    } finally {
      setIsExecutingAction(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-12rem)] min-h-0 flex-col gap-6 lg:flex-row">
      <div className="hidden h-full min-h-0 w-64 shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-white md:flex md:flex-col">
        <div className="shrink-0 border-b border-slate-100 bg-slate-50 p-4">
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
              disabled={isSending || isExecutingAction}
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

      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <ComplianceBanner variant="ai" />

        <div className="shrink-0 border-b border-slate-100 bg-slate-50 px-4 py-4">
          <div className="mb-4">
            <p className="text-sm font-semibold text-slate-900">统一智能入口</p>
            <p className="mt-1 text-xs leading-6 text-slate-500">
              AI 医生会优先解读监测总览、用药记录和病历档案，再触发康复计划与 AI 健康报告，不再只是单纯问答助手。
            </p>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <button
              type="button"
              onClick={() => {
                void handleExplainCurrentState()
              }}
              disabled={isSending || isExecutingAction}
              className="rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:border-teal-200 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-teal-50 p-2 text-teal-600">
                  <Stethoscope className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">解读当前监测与用药</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">快速生成今日状态说明和复诊沟通重点。</p>
                </div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => {
                void handleGenerateRehabPlan()
              }}
              disabled={isSending || isExecutingAction}
              className="rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:border-teal-200 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-teal-50 p-2 text-teal-600">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">生成或查看康复计划</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">基于证据触发候选计划，并在聊天流中继续确认。</p>
                </div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => {
                void handleGenerateHealthReport()
              }}
              disabled={isSending || isExecutingAction}
              className="rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:border-teal-200 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-teal-50 p-2 text-teal-600">
                  <FileText className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">生成 AI 健康报告</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">整合监测、用药和病历证据，输出可复诊使用的结构化结果。</p>
                </div>
              </div>
            </button>
          </div>
        </div>

        <div className="shrink-0 border-b border-slate-100 bg-white px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">对话记录</p>
              <p className="text-xs text-slate-500">离开页面后会自动保存在当前账号下，下次回来继续查看。</p>
            </div>
            <button
              type="button"
              onClick={handleClearMessages}
              disabled={isSending || isExecutingAction || messages.length <= INITIAL_MESSAGES.length}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-teal-200 hover:text-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Eraser className="h-3.5 w-3.5" />
              清空对话
            </button>
          </div>
        </div>

        <div ref={scrollContainerRef} className="min-h-0 flex-1 space-y-6 overflow-y-auto bg-slate-50 p-6">
          {messages.map((message) => (
            <ChatBubble
              key={message.id}
              message={message}
              onDelete={message.id === 'welcome-message' ? undefined : () => handleDeleteMessage(message.id)}
              onAction={handleAction}
              actionDisabled={isSending || isExecutingAction}
            />
          ))}
          {streamingMessage ? (
            <ChatBubble
              message={streamingMessage}
              actionDisabled
              isStreaming
              streamingLabel="AI 医生正在回复"
            />
          ) : null}
          {(isSending || isExecutingAction) && !streamingMessage ? (
            <ChatBubble
              message={{
                id: 'sending-message',
                role: 'assistant',
                content: THINKING_STATUS_LINES[pendingStatusIndex] ?? THINKING_STATUS_LINES[0],
              }}
              actionDisabled
              isStreaming
              streamingLabel="AI 医生正在整理思路"
            />
          ) : null}
        </div>

        <div className="shrink-0 border-t border-slate-200 bg-white p-4">
          {error ? (
            <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {error}
            </div>
          ) : null}

          <form className="relative flex items-center" onSubmit={handleSubmit}>
            <input
              ref={composerInputRef}
              type="text"
              placeholder={isSending ? 'AI 医生回复中，可继续输入下一条问题...' : '描述您的症状或疑问...'}
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value)
              }}
              className="w-full rounded-full border border-slate-200 bg-slate-50 py-3 pl-4 pr-12 text-sm transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-teal-500"
              readOnly={isExecutingAction}
              aria-busy={isSending || isExecutingAction}
            />
            <button
              type="submit"
              className="absolute right-2 rounded-full bg-teal-600 p-2 text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={isSending || isExecutingAction || !draft.trim()}
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
