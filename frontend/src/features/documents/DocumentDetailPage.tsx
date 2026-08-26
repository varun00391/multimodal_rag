import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { documentsApi } from '../../api/documents'
import { ingestionApi } from '../../api/ingestion'
import { Button } from '../../components/Button'
import { StatusBadge } from '../../components/Badge'
import { Card } from '../../components/Card'
import { ErrorBanner, LoadingSkeleton, PageHeader } from '../../components/PageHeader'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { canUpload } from '../../utils/permissions'
import { elementTypeLabel, formatBytes } from '../../utils/format'
import type { Document, DocumentElement, IngestionJob } from '../../types'

function ElementPreview({ element }: { element: DocumentElement }) {
  const type = element.element_type.toLowerCase()

  if (type === 'table' && element.content) {
    return (
      <div className="overflow-x-auto rounded border border-slate-200 bg-white p-3 text-xs">
        <pre className="whitespace-pre-wrap">{element.content}</pre>
      </div>
    )
  }

  if (['image', 'graph', 'picture'].includes(type)) {
    return (
      <div className="rounded border border-slate-200 bg-slate-100 p-4 text-center text-sm text-slate-500">
        {element.source_ref ? (
          <p>Visual element · ref: {element.source_ref}</p>
        ) : (
          <p>Image / graph preview</p>
        )}
        {element.page != null && <p className="mt-1 text-xs">Page {element.page}</p>}
      </div>
    )
  }

  return (
    <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
      {element.content || 'No preview available'}
    </div>
  )
}

export function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const [searchParams] = useSearchParams()
  const jobId = searchParams.get('job')
  const { user } = useAuth()
  const { showToast } = useToast()
  const [document, setDocument] = useState<Document | null>(null)
  const [job, setJob] = useState<IngestionJob | null>(null)
  const [elements, setElements] = useState<DocumentElement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!documentId) return

    async function load() {
      setLoading(true)
      try {
        const doc = await documentsApi.get(documentId!)
        setDocument(doc)
        const els = await documentsApi.elements(documentId!).catch(() => [])
        setElements(els)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Document not found')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [documentId])

  useEffect(() => {
    if (!jobId || !document) return
    if (['READY', 'COMPLETED', 'FAILED'].includes(document.status.toUpperCase())) return

    async function poll() {
      try {
        const j = await ingestionApi.getJob(jobId!)
        setJob(j)
      } catch {
        // ignore polling errors
      }
    }

    void poll()
    const interval = setInterval(() => void poll(), 3000)
    return () => clearInterval(interval)
  }, [document, jobId])

  async function handleRetry() {
    if (!job) return
    try {
      await ingestionApi.retry(job.job_id)
      showToast('Ingestion retry started', 'success')
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Retry failed', 'error')
    }
  }

  if (loading) return <LoadingSkeleton rows={4} />
  if (error || !document) {
    return (
      <ErrorBanner
        message={error || 'Document not found'}
        onRetry={() => window.location.reload()}
      />
    )
  }

  const isReady = ['READY', 'COMPLETED'].includes(document.status.toUpperCase())

  return (
    <div>
      <PageHeader
        title={document.title || document.filename}
        description={document.filename}
        action={
          <div className="flex gap-2">
            {isReady && (
              <Link to={`/ask?doc=${document.document_id}`}>
                <Button>Ask about this document</Button>
              </Link>
            )}
            {canUpload(user) && job?.status === 'FAILED' && (
              <Button variant="secondary" onClick={() => void handleRetry()}>
                Retry ingestion
              </Button>
            )}
          </div>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs text-slate-500">Status</p>
          <div className="mt-2">
            <StatusBadge status={document.status} />
          </div>
        </Card>
        <Card>
          <p className="text-xs text-slate-500">Size</p>
          <p className="mt-2 font-semibold">{formatBytes(document.size_bytes)}</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-500">Department</p>
          <p className="mt-2 truncate font-semibold">{document.department_id}</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-500">Elements extracted</p>
          <p className="mt-2 font-semibold">{elements.length}</p>
        </Card>
      </div>

      {job && !isReady && (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-amber-900">Processing: {job.status}</p>
              {job.current_step && (
                <p className="text-sm text-amber-700">{job.current_step}</p>
              )}
            </div>
            <span className="text-lg font-bold text-amber-900">{job.progress}%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-amber-200">
            <div
              className="h-full rounded-full bg-amber-500 transition-all"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      <Card title="Extracted elements">
        {elements.length === 0 ? (
          <p className="text-sm text-slate-500">
            {isReady ? 'No elements returned.' : 'Elements will appear after processing completes.'}
          </p>
        ) : (
          <div className="space-y-4">
            {elements.map((el) => (
              <div key={el.element_id} className="rounded-lg border border-slate-100 p-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                    {elementTypeLabel(el.element_type)}
                  </span>
                  {el.page != null && (
                    <span className="text-xs text-slate-500">Page {el.page}</span>
                  )}
                </div>
                <ElementPreview element={el} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
