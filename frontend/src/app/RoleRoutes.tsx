import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { canManageUsers, canUpload, canViewAnalytics, isSuperAdmin } from '../utils/permissions'

function useRoleGuard(check: (user: ReturnType<typeof useAuth>['user']) => boolean) {
  const { user, loading } = useAuth()
  if (loading) return { allowed: false, loading: true }
  return { allowed: check(user), loading: false }
}

export function UploadRoute() {
  const { allowed, loading } = useRoleGuard(canUpload)
  if (loading) return null
  if (!allowed) return <Navigate to="/forbidden" replace />
  return <Outlet />
}

export function SuperAdminRoute() {
  const { allowed, loading } = useRoleGuard(isSuperAdmin)
  if (loading) return null
  if (!allowed) return <Navigate to="/forbidden" replace />
  return <Outlet />
}

export function ManageUsersRoute() {
  const { allowed, loading } = useRoleGuard(canManageUsers)
  if (loading) return null
  if (!allowed) return <Navigate to="/forbidden" replace />
  return <Outlet />
}

export function AnalyticsRoute() {
  const { allowed, loading } = useRoleGuard(canViewAnalytics)
  if (loading) return null
  if (!allowed) return <Navigate to="/forbidden" replace />
  return <Outlet />
}
