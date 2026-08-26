import { apiRequest } from './client'
import type { QueryHistoryItem, QueryResponse } from '../types'

export interface QueryRequest {
  query: string
  document_ids?: string[]
  conversation_id?: string | null
}

export const queryApi = {
  ask: (payload: QueryRequest) =>
    apiRequest<QueryResponse>('/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  history: () => apiRequest<QueryHistoryItem[]>('/users/me/queries'),

  get: (queryId: string) => apiRequest<QueryResponse>(`/query/${queryId}`),
}
