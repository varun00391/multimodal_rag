import { useCallback, useEffect, useState } from 'react'
import { adminsApi, type AdminListItem } from '../../api/admins'
import { departmentsApi } from '../../api/departments'
import { Button } from '../../components/Button'
import { RoleBadge, StatusBadge } from '../../components/Badge'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { EmptyState, ErrorBanner, LoadingSkeleton, PageHeader } from '../../components/PageHeader'
import { useToast } from '../../hooks/useToast'

export function AdminsPage() {
  const { showToast } = useToast()
  const [admins, setAdmins] = useState<AdminListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', email: '', department_name: '' })
  const [creating, setCreating] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<AdminListItem | null>(null)
  const [removing, setRemoving] = useState(false)

  const loadAdmins = useCallback(async () => {
    setError(null)
    try {
      const data = await adminsApi.list()
      setAdmins(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load admins')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadAdmins()
  }, [loadAdmins])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    try {
      await adminsApi.create(form.name, form.email, form.department_name)
      showToast('Admin created', 'success')
      setForm({ name: '', email: '', department_name: '' })
      setLoading(true)
      await loadAdmins()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Create failed', 'error')
    } finally {
      setCreating(false)
    }
  }

  async function handleRemove() {
    if (!removeTarget) return
    const departmentId = removeTarget.department_ids[0]
    if (!departmentId) {
      showToast('Admin has no department assignment to remove.', 'error')
      return
    }
    setRemoving(true)
    try {
      await departmentsApi.removeAdmin(departmentId, removeTarget.user_id)
      showToast('Admin removed', 'success')
      setRemoveTarget(null)
      setLoading(true)
      await loadAdmins()
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Remove failed', 'error')
    } finally {
      setRemoving(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Department admins"
        description="Create and manage all departmental administrators across the organization."
      />

      <form
        onSubmit={(e) => void handleCreate(e)}
        className="mb-6 grid gap-3 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-2 lg:grid-cols-4"
      >
        <input
          placeholder="Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          required
        />
        <input
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          required
        />
        <input
          placeholder="Department name"
          value={form.department_name}
          onChange={(e) => setForm({ ...form, department_name: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          required
        />
        <Button type="submit" loading={creating}>
          Create admin
        </Button>
      </form>

      {loading && <LoadingSkeleton rows={4} />}
      {error && <ErrorBanner message={error} onRetry={() => void loadAdmins()} />}

      {!loading && !error && admins.length === 0 && (
        <EmptyState
          title="No admins yet"
          description="Create a departmental admin by providing name, email, and department name."
        />
      )}

      {!loading && admins.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Admin
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Department
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Role
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Status
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase text-slate-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {admins.map((admin) => (
                <tr key={admin.user_id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{admin.name}</p>
                    <p className="text-xs text-slate-500">{admin.email}</p>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">
                    {admin.department_names.length > 0
                      ? admin.department_names.join(', ')
                      : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <RoleBadge role={admin.role} />
                    {admin.is_super_admin_seed && (
                      <span className="ml-2 text-xs text-purple-600">Protected</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={admin.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!admin.is_super_admin_seed && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600"
                        onClick={() => setRemoveTarget(admin)}
                      >
                        Remove
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!removeTarget}
        title="Remove admin"
        message={`Remove ${removeTarget?.name} (${removeTarget?.email}) from ${
          removeTarget?.department_names.join(', ') || 'their department'
        }? They will lose admin access.`}
        confirmLabel="Remove"
        destructive
        loading={removing}
        onConfirm={() => void handleRemove()}
        onCancel={() => setRemoveTarget(null)}
      />
    </div>
  )
}
