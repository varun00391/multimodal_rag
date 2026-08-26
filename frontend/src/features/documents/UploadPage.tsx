import { FileUp, X } from 'lucide-react'
import { useCallback, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { documentsApi } from '../../api/documents'
import { departmentsApi } from '../../api/departments'
import { Button } from '../../components/Button'
import { ErrorBanner, PageHeader } from '../../components/PageHeader'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { isSuperAdmin } from '../../utils/permissions'
import type { Department } from '../../types'
import { useEffect } from 'react'

export function UploadPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [departments, setDepartments] = useState<Department[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  useEffect(() => {
    if (isSuperAdmin(user)) {
      departmentsApi
        .list()
        .then(setDepartments)
        .catch(() => setDepartments([]))
    } else if (user?.department_ids.length) {
      setDepartmentId(user.department_ids[0])
    }
  }, [user])

  const validateFile = useCallback((f: File) => {
    if (f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are supported.')
      return false
    }
    if (f.size > 50 * 1024 * 1024) {
      setError('File exceeds 50 MB limit.')
      return false
    }
    setError(null)
    return true
  }, [])

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped && validateFile(dropped)) {
      setFile(dropped)
      if (!title) setTitle(dropped.name.replace(/\.pdf$/i, ''))
    }
  }

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const result = await documentsApi.upload(
        file,
        title || undefined,
        departmentId || undefined,
      )
      showToast('Document uploaded and queued for processing', 'success')
      navigate(`/documents/${result.document_id}?job=${result.ingestion_job_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Upload document"
        description="Upload a PDF containing text, tables, images, or scanned pages."
      />

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          dragOver ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-white'
        }`}
      >
        <FileUp className="mx-auto h-12 w-12 text-slate-400" />
        <p className="mt-4 font-medium text-slate-900">Drag and drop your PDF here</p>
        <p className="mt-1 text-sm text-slate-500">or browse to select a file (max 50 MB)</p>
        <label className="mt-4 inline-block">
          <input
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f && validateFile(f)) {
                setFile(f)
                if (!title) setTitle(f.name.replace(/\.pdf$/i, ''))
              }
            }}
          />
          <span className="cursor-pointer rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            Browse files
          </span>
        </label>
      </div>

      {file && (
        <div className="mt-4 flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3">
          <div>
            <p className="font-medium text-slate-900">{file.name}</p>
            <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
          <button type="button" onClick={() => setFile(null)} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>
      )}

      <div className="mt-6 space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        <div>
          <label className="block text-sm font-medium text-slate-700">Title (optional)</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Document title"
          />
        </div>

        {isSuperAdmin(user) && departments.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-700">Department</label>
            <select
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">Select department</option>
              {departments.map((d) => (
                <option key={d.department_id} value={d.department_id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="mt-6 flex gap-3">
        <Button loading={uploading} disabled={!file} onClick={() => void handleUpload()}>
          Upload
        </Button>
        <Link to="/documents">
          <Button variant="secondary">Cancel</Button>
        </Link>
      </div>
    </div>
  )
}
