import { useEffect, useState } from 'react'
import { adminsApi } from '../../api/admins'
import { departmentsApi } from '../../api/departments'
import { Button } from '../../components/Button'
import { RoleBadge, StatusBadge } from '../../components/Badge'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorBanner, LoadingSkeleton, PageHeader, ScopeBanner } from '../../components/PageHeader'
import { useToast } from '../../hooks/useToast'
import type { Department, User } from '../../types'

export function AdminsPage() {
  const { showToast } = useToast()
  const [departments, setDepartments] = useState<Department[]>([])
  const [selectedDept, setSelectedDept] = useState('')
  const [admins, setAdmins] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', email: '', department_name: '' })
  const [creating, setCreating] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<User | null>(null)
  const [removing, setRemoving] = useState(false)

  useEffect(() => {
    departmentsApi
      .list()
      .then((depts) => {
        setDepartments(depts)
        if (depts.length) setSelectedDept(depts[0].department_id)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedDept) return
    departmentsApi
      .admins(selectedDept)
      .then(setAdmins)
      .catch(() => setAdmins([]))
  }, [selectedDept])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    try {
      await adminsApi.create(form.name, form.email, form.department_name)
      showToast('Admin created', 'success')
      setForm({ name: '', email: '', department_name: '' })
      if (selectedDept) {
        setAdmins(await departmentsApi.admins(selectedDept))
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Create failed', 'error')
    } finally {
      setCreating(false)
    }
  }

  async function handleRemove() {
    if (!removeTarget || !selectedDept) return
    setRemoving(true)
    try {
      await departmentsApi.removeAdmin(selectedDept, removeTarget.user_id)
      showToast('Admin removed', 'success')
      setRemoveTarget(null)
      setAdmins(await departmentsApi.admins(selectedDept))
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Remove failed', 'error')
    } finally {
      setRemoving(false)
    }
  }

  const deptName = departments.find((d) => d.department_id === selectedDept)?.name

  return (
    <div>
      <PageHeader
        title="Department admins"
        description="Create and manage departmental administrators."
      />
      {deptName && <ScopeBanner text={`Viewing admins for: ${deptName}`} />}

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

      <div className="mb-4">
        <select
          value={selectedDept}
          onChange={(e) => setSelectedDept(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          {departments.map((d) => (
            <option key={d.department_id} value={d.department_id}>
              {d.name}
            </option>
          ))}
        </select>
      </div>

      {loading && <LoadingSkeleton rows={4} />}
      {error && <ErrorBanner message={error} />}

      {!loading && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  Admin
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
        message={`Remove ${removeTarget?.name} (${removeTarget?.email}) from this department? They will lose admin access.`}
        confirmLabel="Remove"
        destructive
        loading={removing}
        onConfirm={() => void handleRemove()}
        onCancel={() => setRemoveTarget(null)}
      />
    </div>
  )
}
