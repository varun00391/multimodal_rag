import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '../../components/Button'
import { useAuth } from '../../hooks/useAuth'
import { RoleBadge } from '../../components/Badge'

export function AccessDeniedPage() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-100">
          <ShieldAlert className="h-7 w-7 text-amber-600" />
        </div>
        <h1 className="text-xl font-bold text-slate-900">Account not authorized</h1>
        {user ? (
          <>
            <p className="mt-2 text-sm text-slate-600">
              Signed in as <strong>{user.email}</strong>
            </p>
            <div className="mt-3 flex justify-center gap-2">
              <RoleBadge role={user.role} />
              <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800">
                {user.status}
              </span>
            </div>
            <p className="mt-4 text-sm text-slate-500">
              Your Google account is authenticated but not provisioned for this application.
              Contact your administrator to request access.
            </p>
          </>
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            Your session could not be verified. Please sign in again.
          </p>
        )}
        <div className="mt-6 flex justify-center gap-3">
          <Button variant="secondary" onClick={() => void logout()}>
            Sign out
          </Button>
          <Link to="/login">
            <Button>Back to login</Button>
          </Link>
        </div>
      </div>
    </div>
  )
}

export function ForbiddenPage() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <h1 className="text-6xl font-bold text-slate-300">403</h1>
      <p className="mt-4 text-lg font-semibold text-slate-900">Access forbidden</p>
      <p className="mt-2 text-sm text-slate-500">You do not have permission to view this page.</p>
      <Link to="/dashboard" className="mt-6 text-sm font-medium text-brand-600 hover:underline">
        Return to dashboard
      </Link>
    </div>
  )
}

export function NotFoundPage() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
      <h1 className="text-6xl font-bold text-slate-300">404</h1>
      <p className="mt-4 text-lg font-semibold text-slate-900">Page not found</p>
      <p className="mt-2 text-sm text-slate-500">The resource you requested does not exist.</p>
      <Link to="/dashboard" className="mt-6 text-sm font-medium text-brand-600 hover:underline">
        Return to dashboard
      </Link>
    </div>
  )
}
