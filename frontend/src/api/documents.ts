import { apiRequest } from './client'
import type { Document, DocumentElement, DocumentUploadResponse } from '../types'

export interface DocumentListParams {
  status?: string
  department_id?: string
  page?: number
  page_size?: number
}

export const documentsApi = {
  list: (params?: DocumentListParams) => {
    const search = new URLSearchParams()
    if (params?.status) search.set('status', params.status)
    if (params?.department_id) search.set('department_id', params.department_id)
    if (params?.page) search.set('page', String(params.page))
    if (params?.page_size) search.set('page_size', String(params.page_size))
    const qs = search.toString()
    return apiRequest<Document[]>(`/documents${qs ? `?${qs}` : ''}`)
  },

  get: (documentId: string) => apiRequest<Document>(`/documents/${documentId}`),

  upload: (file: File, title?: string, departmentId?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (title) form.append('title', title)
    if (departmentId) form.append('department_id', departmentId)
    return apiRequest<DocumentUploadResponse>('/documents', { method: 'POST', body: form })
  },

  delete: (documentId: string) =>
    apiRequest<void>(`/documents/${documentId}`, { method: 'DELETE' }),

  elements: (documentId: string) =>
    apiRequest<DocumentElement[]>(`/documents/${documentId}/elements`),

  element: (documentId: string, elementId: string) =>
    apiRequest<DocumentElement>(`/documents/${documentId}/elements/${elementId}`),
}
