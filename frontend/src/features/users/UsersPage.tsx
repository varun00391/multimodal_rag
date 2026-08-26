import { useEffect, useState } from 'react'
import { departmentsApi } from '../../api/departments'
import { Button } from '../../components/Button'
import { RoleBadge, StatusBadge } from '../../components/Badge'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ErrorBanner, LoadingSkeleton, PageHeader, ScopeBanner } from '../../components/PageHeader'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { isSuperAdmin } from '../../utils/permissions'
import type { Department, User } from '../../types'

export function UsersPage() {
  const { user } = useAuth()
  const { showToast } = useToast()
  const [departments, setDepartments] = useState<Department[]>([])
  const [selectedDept, setSelectedDept] = useState('')
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', email: '' })
  const [creating, setCreating] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<User | null>(null)
  const [removing, setRemoving] = useState(false)

  useEffect(() => {
    async function init() {
      try {
        if (isSuperAdmin(user)) {
          const depts = await departmentsApi.list()
          setDepartments(depts)
          if (depts.length) setSelectedDept(depts[0].department_id)
        } else if (user?.department_ids.length) {
          setSelectedDept(user.department_ids[0])
          const dept = await departmentsApi.get(user.department_ids[0]).catch(() => null)
          if (dept) setDepartments([dept])
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load')
      } finally {
        setLoading(false)
      }
    }
    void init()
  }, [user])

  useEffect(() => {
    if (!selectedDept) return
    departmentsApi
      .users(selectedDept)
      .then(setUsers)
      .catch(() => setUsers([]))
  }, [selectedDept])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedDept) return
    setCreating(true)
    try {
      await departmentsApi.addUser(selectedDept, form.name, form.email)
      showToast('User created', 'success')
      setForm({ name: '', email: '' })
      setUsers(await departmentsApi.users(selectedDept))
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
      await departmentsApi.removeUser(selectedDept, removeTarget.user_id)
      showToast('User removed', 'success')
      setRemoveTarget(null)
      setUsers(await departmentsApi.users(selectedDept))
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Remove failed', 'error')
    } finally {
      setRemoving(false)
    }
  }

  const deptName = departments.find((d) => d.department_id === selectedDept)?.name

  return (
    <div>
      <PageHeader title="Users" description="Manage users within your authorized department scope." />
      {deptName && <ScopeBanner text={`Department: ${deptName}`} />}

      {isSuperAdmin(user) && departments.length > 1 && (
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
      )}

      <form
        onSubmit={(e) => void handleCreate(e)}
        className="mb-6 flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-5"
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
        <Button type="submit" loading={creating}>
          Add user
        </Button>
      </form>

      {loading && <LoadingSkeleton rows={4} />}
      {error && <ErrorBanner message={error} />}

      {!loading && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-500">
                  User
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
              {users.map((u) => (
                <tr key={u.user_id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{u.name}</p>
                    <p className="text-xs text-slate-500">{u.email}</p>
                  </td>
                  <td className="px-4 py-3">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={u.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600"
                      onClick={() => setRemoveTarget(u)}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!removeTarget}
        title="Remove user"
        message={`Remove ${removeTarget?.name} (${removeTarget?.email}) from this department? They will lose access to department documents.`}
        confirmLabel="Remove"
        destructive
        loading={removing}
        onConfirm={() => void handleRemove()}
        onCancel={() => setRemoveTarget(null)}
      />
    </div>
  )
}
