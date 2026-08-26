import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { dashboardApi } from '../../api/dashboard'
import { documentsApi } from '../../api/documents'
import { queryApi } from '../../api/query'
import { Button } from '../../components/Button'
import { KpiCard } from '../../components/Card'
import { ErrorBanner, LoadingSkeleton, PageHeader, ScopeBanner } from '../../components/PageHeader'
import { useAuth } from '../../hooks/useAuth'
import { isAdmin, isSuperAdmin, roleLabel } from '../../utils/permissions'
import type { Document, QueryHistoryItem, SuperAdminDashboard, UserDashboard } from '../../types'

export function DashboardPage() {
  const { user } = useAuth()
  const [userDash, setUserDash] = useState<UserDashboard | null>(null)
  const [superDash, setSuperDash] = useState<SuperAdminDashboard | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [queries, setQueries] = useState<QueryHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [dash, docs, history] = await Promise.all([
          dashboardApi.me(),
          documentsApi.list({ page_size: 5 }),
          queryApi.history().catch(() => [] as QueryHistoryItem[]),
        ])
        setUserDash(dash)
        setDocuments(docs.slice(0, 5))
        setQueries(history.slice(0, 5))

        if (isSuperAdmin(user)) {
          const sd = await dashboardApi.superAdmin()
          setSuperDash(sd)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [user])

  if (loading) return <LoadingSkeleton rows={4} />
  if (error) return <ErrorBanner message={error} onRetry={() => window.location.reload()} />

  const scopeText = isSuperAdmin(user)
    ? 'Organization-wide view'
    : isAdmin(user)
      ? `Department scope: ${user?.department_ids.length ? user.department_ids.join(', ') : 'assigned departments'}`
      : 'Your personal workspace'

  return (
    <div>
      <PageHeader
        title={`Welcome, ${user?.name}`}
        description="Your summary of documents, queries, and activity."
        action={
          <div className="flex gap-2">
            <Link to="/ask">
              <Button>Ask a question</Button>
            </Link>
          </div>
        }
      />
      <ScopeBanner text={`${roleLabel(user!.role)} · ${scopeText}`} />

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Your queries" value={userDash?.query_count ?? 0} />
        <KpiCard label="Recent documents" value={documents.length} />
        {superDash && (
          <>
            <KpiCard label="Total documents" value={superDash.documents} />
            <KpiCard label="Total queries" value={superDash.queries} />
          </>
        )}
        {!superDash && (
          <KpiCard label="Recent activity" value={queries.length} hint="Last 5 queries" />
        )}
      </div>

      {superDash && (
        <div className="mb-8 grid gap-4 sm:grid-cols-3">
          {Object.entries(superDash.users_by_role).map(([role, count]) => (
            <KpiCard key={role} label={`${role.replace('_', ' ')} users`} value={count} />
          ))}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Recent documents</h2>
            <Link to="/documents" className="text-sm text-brand-600 hover:underline">
              View all
            </Link>
          </div>
          {documents.length === 0 ? (
            <p className="text-sm text-slate-500">No documents yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {documents.map((doc) => (
                <li key={doc.document_id} className="py-3">
                  <Link
                    to={`/documents/${doc.document_id}`}
                    className="font-medium text-slate-900 hover:text-brand-600"
                  >
                    {doc.title || doc.filename}
                  </Link>
                  <p className="text-xs text-slate-500">{doc.status}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Recent queries</h2>
            <Link to="/history" className="text-sm text-brand-600 hover:underline">
              View history
            </Link>
          </div>
          {queries.length === 0 ? (
            <p className="text-sm text-slate-500">No queries yet. Start by asking a question.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {queries.map((q) => (
                <li key={q.query_id} className="py-3">
                  <p className="line-clamp-2 text-sm text-slate-800">{q.query}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
