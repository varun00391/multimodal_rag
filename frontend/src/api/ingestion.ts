import { apiRequest } from './client'
import type { IngestionJob } from '../types'

export const ingestionApi = {
  getJob: (jobId: string) => apiRequest<IngestionJob>(`/ingestion/jobs/${jobId}`),

  retry: (jobId: string) =>
    apiRequest<IngestionJob>(`/ingestion/jobs/${jobId}/retry`, { method: 'POST' }),

  start: (documentId: string) =>
    apiRequest<IngestionJob>(`/ingestion/${documentId}/start`, { method: 'POST' }),
}
