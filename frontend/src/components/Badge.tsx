import clsx from 'clsx'

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toUpperCase()
  const color =
    normalized === 'ACTIVE' || normalized === 'READY' || normalized === 'COMPLETED'
      ? 'bg-emerald-100 text-emerald-800'
      : normalized === 'FAILED' || normalized === 'INACTIVE'
        ? 'bg-red-100 text-red-800'
        : normalized.includes('ING') ||
            normalized === 'QUEUED' ||
            normalized === 'EXTRACTING' ||
            normalized === 'CHUNKING' ||
            normalized === 'EMBEDDING' ||
            normalized === 'INDEXING'
          ? 'bg-amber-100 text-amber-800'
          : 'bg-slate-100 text-slate-700'

  return (
    <span className={clsx('inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium', color)}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

export function RoleBadge({ role }: { role: string }) {
  const color =
    role === 'SUPER_ADMIN'
      ? 'bg-purple-100 text-purple-800'
      : role === 'ADMIN'
        ? 'bg-blue-100 text-blue-800'
        : 'bg-slate-100 text-slate-700'

  const label =
    role === 'SUPER_ADMIN' ? 'Super Admin' : role === 'ADMIN' ? 'Admin' : 'User'

  return (
    <span className={clsx('inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium', color)}>
      {label}
    </span>
  )
}
