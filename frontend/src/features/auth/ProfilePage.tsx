import { RoleBadge, StatusBadge } from '../../components/Badge'
import { Card } from '../../components/Card'
import { PageHeader } from '../../components/PageHeader'
import { useAuth } from '../../hooks/useAuth'
import { roleLabel } from '../../utils/permissions'

export function ProfilePage() {
  const { user, logout } = useAuth()

  if (!user) return null

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Profile" description="Your account information and session." />

      <Card>
        <dl className="space-y-4">
          <div>
            <dt className="text-xs font-medium uppercase text-slate-500">Name</dt>
            <dd className="mt-1 text-lg font-semibold text-slate-900">{user.name}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-slate-500">Email</dt>
            <dd className="mt-1 text-slate-900">{user.email}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-slate-500">Role</dt>
            <dd className="mt-2 flex items-center gap-2">
              <RoleBadge role={user.role} />
              <span className="text-sm text-slate-600">{roleLabel(user.role)}</span>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-slate-500">Status</dt>
            <dd className="mt-2">
              <StatusBadge status={user.status} />
            </dd>
          </div>
          {user.department_ids.length > 0 && (
            <div>
              <dt className="text-xs font-medium uppercase text-slate-500">Departments</dt>
              <dd className="mt-2 space-y-1">
                {user.department_ids.map((id) => (
                  <p key={id} className="font-mono text-sm text-slate-700">
                    {id}
                  </p>
                ))}
              </dd>
            </div>
          )}
          {user.is_super_admin_seed && (
            <p className="rounded-lg bg-purple-50 px-3 py-2 text-sm text-purple-800">
              This is the protected Super Admin seed account.
            </p>
          )}
        </dl>

        <button
          type="button"
          onClick={() => void logout()}
          className="mt-6 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Sign out
        </button>
      </Card>
    </div>
  )
}
