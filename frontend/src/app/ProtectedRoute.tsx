import { Navigate, Outlet } from 'react-router-dom'
import { LoadingSkeleton } from '../components/PageHeader'
import { useAuth } from '../hooks/useAuth'

export function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-8">
        <div className="w-full max-w-md">
          <LoadingSkeleton rows={4} />
        </div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (user.status !== 'ACTIVE') {
    return <Navigate to="/access-denied" replace />
  }

  return <Outlet />
}
