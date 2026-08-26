import { useEffect, useState } from 'react'
import { queryApi } from '../../api/query'
import { EmptyState, ErrorBanner, LoadingSkeleton, PageHeader } from '../../components/PageHeader'
import type { QueryHistoryItem } from '../../types'

export function HistoryPage() {
  const [queries, setQueries] = useState<QueryHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    queryApi
      .history()
      .then(setQueries)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load history'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <PageHeader
        title="Query history"
        description="Your past questions and answers within your authorized scope."
      />

      {loading && <LoadingSkeleton rows={5} />}
      {error && <ErrorBanner message={error} />}

      {!loading && !error && queries.length === 0 && (
        <EmptyState
          title="No query history"
          description="Your questions will appear here after you use the Ask feature."
        />
      )}

      {!loading && queries.length > 0 && (
        <div className="space-y-4">
          {queries.map((q) => (
            <div
              key={q.query_id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <p className="font-medium text-slate-900">{q.query}</p>
              {q.answer && (
                <p className="mt-3 line-clamp-4 text-sm text-slate-600">{q.answer}</p>
              )}
              {q.created_at && (
                <p className="mt-2 text-xs text-slate-400">{new Date(q.created_at).toLocaleString()}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
