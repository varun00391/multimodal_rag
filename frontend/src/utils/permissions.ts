import type { User, UserRole } from '../types'

export function canUpload(user: User | null): boolean {
  return user?.role === 'SUPER_ADMIN' || user?.role === 'ADMIN'
}

export function isSuperAdmin(user: User | null): boolean {
  return user?.role === 'SUPER_ADMIN'
}

export function isAdmin(user: User | null): boolean {
  return user?.role === 'ADMIN'
}

export function canManageUsers(user: User | null): boolean {
  return user?.role === 'SUPER_ADMIN' || user?.role === 'ADMIN'
}

export function canViewAnalytics(user: User | null): boolean {
  return user?.role === 'SUPER_ADMIN' || user?.role === 'ADMIN'
}

export function roleLabel(role: UserRole): string {
  switch (role) {
    case 'SUPER_ADMIN':
      return 'Super Admin'
    case 'ADMIN':
      return 'Department Admin'
    case 'USER':
      return 'User'
  }
}

export function roleBadgeColor(role: UserRole): string {
  switch (role) {
    case 'SUPER_ADMIN':
      return 'bg-purple-100 text-purple-800'
    case 'ADMIN':
      return 'bg-blue-100 text-blue-800'
    case 'USER':
      return 'bg-slate-100 text-slate-700'
  }
}
