import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { documentsApi } from '../../api/documents'
import { Button } from '../../components/Button'
import { StatusBadge } from '../../components/Badge'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { EmptyState, ErrorBanner, LoadingSkeleton, PageHeader } from '../../components/PageHeader'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { canUpload } from '../../utils/permissions'
import { formatBytes } from '../../utils/format'
import type { Document } from '../../types'

export function DocumentsPage() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null)
  const [deleting, setDeleting] = useState(false)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const params = statusFilter ? { status: statusFilter } : undefined
      const docs = await documentsApi.list(params)
      setDocuments(docs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [statusFilter])

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await documentsApi.delete(deleteTarget.document_id)
      showToast('Document deleted', 'success')
      setDeleteTarget(null)
      await load()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Delete failed', 'error')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Documents"
        description="Browse and manage documents in your authorized scope."
        action={
          canUpload(user) ? (
            <Link to="/documents/upload">
              <Button>Upload document</Button>
            </Link>
          ) : undefined
        }
      />

      <div className="mb-4 flex gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          <option value="READY">Ready</option>
          <option value="QUEUED">Queued</option>
          <option value="PROCESSING">Processing</option>
          <option value="FAILED">Failed</option>
        </select>
      </div>

      {loading && <LoadingSkeleton rows={5} />}
      {error && <ErrorBanner message={error} onRetry={() => void load()} />}

      {!loading && !error && documents.length === 0 && (
        <EmptyState
          title="No documents yet"
          description={
            canUpload(user)
              ? 'Upload a PDF to start indexing content for question answering.'
              : 'No documents are available in your scope yet.'
          }
          action={
            canUpload(user) ? (
              <Link to="/documents/upload">
                <Button>Upload document</Button>
              </Link>
            ) : undefined
          }
        />
      )}

      {!loading && documents.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Document
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Size
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase text-slate-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {documents.map((doc) => (
                <tr key={doc.document_id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link
                      to={`/documents/${doc.document_id}`}
                      className="font-medium text-slate-900 hover:text-brand-600"
                    >
                      {doc.title || doc.filename}
                    </Link>
                    <p className="text-xs text-slate-500">{doc.filename}</p>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={doc.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {formatBytes(doc.size_bytes)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <Link to={`/documents/${doc.document_id}`}>
                        <Button variant="ghost" size="sm">
                          View
                        </Button>
                      </Link>
                      {canUpload(user) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:bg-red-50"
                          onClick={() => setDeleteTarget(doc)}
                        >
                          Delete
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete document"
        message={`Are you sure you want to delete "${deleteTarget?.title || deleteTarget?.filename}"? This will remove the document and its indexed content.`}
        confirmLabel="Delete"
        destructive
        loading={deleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
