import { apiRequest } from './client'
import type { User } from '../types'

export const authApi = {
  me: () => apiRequest<User>('/auth/me'),
  logout: () => apiRequest<{ status: string }>('/auth/logout', { method: 'POST' }),
}
