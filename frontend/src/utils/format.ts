export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function formatDate(value?: string): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

export function documentStatusColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'READY':
    case 'COMPLETED':
      return 'bg-emerald-100 text-emerald-800'
    case 'QUEUED':
    case 'PROCESSING':
    case 'EXTRACTING':
    case 'CHUNKING':
    case 'EMBEDDING':
    case 'INDEXING':
      return 'bg-amber-100 text-amber-800'
    case 'FAILED':
      return 'bg-red-100 text-red-800'
    default:
      return 'bg-slate-100 text-slate-700'
  }
}

export function elementTypeLabel(type: string): string {
  return type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' ')
}
