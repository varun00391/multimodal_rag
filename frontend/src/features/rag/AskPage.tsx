import { Copy, RefreshCw, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { documentsApi } from '../../api/documents'
import { queryApi } from '../../api/query'
import { Button } from '../../components/Button'
import { ErrorBanner, PageHeader } from '../../components/PageHeader'
import { useToast } from '../../hooks/useToast'
import type { Document, QueryResponse, QuerySource } from '../../types'
import { elementTypeLabel } from '../../utils/format'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: QuerySource[]
  error?: boolean
}

function SourceChip({ source, documents }: { source: QuerySource; documents: Document[] }) {
  const doc = documents.find((d) => d.document_id === source.document_id)
  const label = doc?.title || doc?.filename || source.document_id.slice(0, 8)
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs text-brand-800">
      {label}
      {source.page != null && <span>· p.{source.page}</span>}
      <span>· {elementTypeLabel(source.element_type)}</span>
    </span>
  )
}

export function AskPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocs, setSelectedDocs] = useState<string[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const { showToast } = useToast()

  useEffect(() => {
    documentsApi
      .list()
      .then(setDocuments)
      .catch(() => setDocuments([]))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const readyDocs = documents.filter((d) =>
    ['READY', 'COMPLETED'].includes(d.status.toUpperCase()),
  )

  function toggleDoc(id: string) {
    setSelectedDocs((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const question = input.trim()
    if (!question || loading) return

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: question }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const response: QueryResponse = await queryApi.ask({
        query: question,
        document_ids: selectedDocs.length > 0 ? selectedDocs : undefined,
      })
      setMessages((prev) => [
        ...prev,
        {
          id: response.query_id,
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
        },
      ])
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Query failed'
      setError(msg)
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'assistant', content: msg, error: true },
      ])
    } finally {
      setLoading(false)
    }
  }

  function startNewChat() {
    setMessages([])
    setError(null)
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <PageHeader
        title="Ask"
        description="Ask natural-language questions against your authorized documents."
        action={
          <Button variant="secondary" onClick={startNewChat}>
            New conversation
          </Button>
        }
      />

      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden">
        <aside className="hidden w-56 shrink-0 flex-col rounded-xl border border-slate-200 bg-white p-4 lg:flex">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Document scope
          </p>
          <p className="mb-3 text-xs text-slate-500">
            {selectedDocs.length === 0
              ? 'All authorized documents'
              : `${selectedDocs.length} selected`}
          </p>
          <div className="flex-1 space-y-2 overflow-y-auto">
            {readyDocs.map((doc) => (
              <label
                key={doc.document_id}
                className="flex cursor-pointer items-start gap-2 rounded-lg p-2 hover:bg-slate-50"
              >
                <input
                  type="checkbox"
                  checked={selectedDocs.includes(doc.document_id)}
                  onChange={() => toggleDoc(doc.document_id)}
                  className="mt-0.5 rounded border-slate-300"
                />
                <span className="text-xs text-slate-700">{doc.title || doc.filename}</span>
              </label>
            ))}
            {readyDocs.length === 0 && (
              <p className="text-xs text-slate-400">No ready documents yet.</p>
            )}
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex-1 overflow-y-auto p-4 lg:p-6">
            {messages.length === 0 && !loading && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <p className="text-lg font-medium text-slate-700">Start a conversation</p>
                <p className="mt-2 max-w-md text-sm text-slate-500">
                  Ask a question about your documents. Answers include source evidence so you can
                  verify the response.
                </p>
              </div>
            )}

            <div className="space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-brand-600 text-white'
                        : msg.error
                          ? 'border border-red-200 bg-red-50 text-red-800'
                          : 'border border-slate-200 bg-slate-50 text-slate-900'
                    }`}
                  >
                    <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 border-t border-slate-200 pt-3">
                        <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                          Evidence
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {msg.sources.map((s, i) => (
                            <SourceChip key={`${s.chunk_id}-${i}`} source={s} documents={documents} />
                          ))}
                        </div>
                      </div>
                    )}
                    {msg.role === 'assistant' && !msg.error && (
                      <button
                        type="button"
                        className="mt-2 flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
                        onClick={() => {
                          void navigator.clipboard.writeText(msg.content)
                          showToast('Answer copied', 'success')
                        }}
                      >
                        <Copy className="h-3 w-3" />
                        Copy
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Retrieving evidence and generating answer...
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          {error && (
            <div className="border-t border-slate-100 px-4 py-2">
              <ErrorBanner message={error} />
            </div>
          )}

          <form onSubmit={(e) => void handleSubmit(e)} className="border-t border-slate-200 p-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question about your documents..."
                className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                disabled={loading}
              />
              <Button type="submit" loading={loading} disabled={!input.trim()}>
                <Send className="h-4 w-4" />
                Ask
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
