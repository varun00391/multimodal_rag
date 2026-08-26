import {
  BarChart3,
  Building2,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Shield,
  Upload,
  UserCircle,
  Users,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import {
  canManageUsers,
  canUpload,
  canViewAnalytics,
  isSuperAdmin,
  roleLabel,
} from '../../utils/permissions'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-brand-50 text-brand-700'
      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`

export function AppLayout() {
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)

  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, show: true },
    { to: '/ask', label: 'Ask', icon: MessageSquare, show: true },
    { to: '/documents', label: 'Documents', icon: FileText, show: true },
    { to: '/documents/upload', label: 'Upload', icon: Upload, show: canUpload(user) },
    { to: '/history', label: 'History', icon: History, show: true },
    { to: '/admin/departments', label: 'Departments', icon: Building2, show: isSuperAdmin(user) },
    { to: '/admin/admins', label: 'Admins', icon: Shield, show: isSuperAdmin(user) },
    { to: '/admin/users', label: 'Users', icon: Users, show: canManageUsers(user) },
    { to: '/analytics', label: 'Analytics', icon: BarChart3, show: canViewAnalytics(user) },
    { to: '/profile', label: 'Profile', icon: UserCircle, show: true },
  ].filter((item) => item.show)

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-4 py-5">
        <Link to="/dashboard" className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <MessageSquare className="h-5 w-5" />
          </div>
          <div>
            <p className="font-semibold text-slate-900">MultiModal RAG</p>
            <p className="text-xs text-slate-500">Documents · Ask · Evidence</p>
          </div>
        </Link>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={navLinkClass} onClick={() => setMobileOpen(false)}>
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-200 p-4">
        <div className="mb-3 rounded-lg bg-slate-50 p-3">
          <p className="truncate text-sm font-medium text-slate-900">{user?.name}</p>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
          <p className="mt-1 text-xs font-medium text-brand-700">{user ? roleLabel(user.role) : ''}</p>
        </div>
        <button
          type="button"
          onClick={() => void logout()}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block">
        {sidebar}
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-72 bg-white shadow-xl">{sidebar}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:px-6">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            onClick={() => setMobileOpen((v) => !v)}
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <div className="hidden text-sm text-slate-500 lg:block">
            Ask questions against your authorized documents with grounded evidence.
          </div>
          <div className="text-sm font-medium text-slate-700">{user?.name}</div>
        </header>
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
