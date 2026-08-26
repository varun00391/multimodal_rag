import { useEffect, useState } from 'react'
import { departmentsApi } from '../../api/departments'
import { Button } from '../../components/Button'
import { ErrorBanner, LoadingSkeleton, PageHeader } from '../../components/PageHeader'
import { useToast } from '../../hooks/useToast'
import type { Department } from '../../types'

export function DepartmentsPage() {
  const { showToast } = useToast()
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  async function load() {
    setLoading(true)
    try {
      setDepartments(await departmentsApi.list())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load departments')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    try {
      await departmentsApi.create(newName.trim())
      showToast('Department created', 'success')
      setNewName('')
      await load()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Create failed', 'error')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Departments"
        description="Manage organization departments. Super Admin only."
      />

      <form onSubmit={(e) => void handleCreate(e)} className="mb-6 flex gap-3">
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="New department name"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <Button type="submit" loading={creating}>
          Add department
        </Button>
      </form>

      {loading && <LoadingSkeleton rows={4} />}
      {error && <ErrorBanner message={error} onRetry={() => void load()} />}

      {!loading && departments.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  ID
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {departments.map((d) => (
                <tr key={d.department_id}>
                  <td className="px-4 py-3 font-medium text-slate-900">{d.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{d.department_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
