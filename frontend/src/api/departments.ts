import { apiRequest } from './client'
import type { Department, User } from '../types'

export const departmentsApi = {
  list: () => apiRequest<Department[]>('/departments'),

  get: (departmentId: string) => apiRequest<Department>(`/departments/${departmentId}`),

  create: (name: string) =>
    apiRequest<Department>('/departments', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  admins: (departmentId: string) =>
    apiRequest<User[]>(`/departments/${departmentId}/admins`),

  removeAdmin: (departmentId: string, userId: string) =>
    apiRequest<void>(`/departments/${departmentId}/admins/${userId}`, { method: 'DELETE' }),

  users: (departmentId: string) =>
    apiRequest<User[]>(`/departments/${departmentId}/users`),

  addUser: (departmentId: string, name: string, email: string) =>
    apiRequest<User>(`/departments/${departmentId}/users`, {
      method: 'POST',
      body: JSON.stringify({ name, email }),
    }),

  removeUser: (departmentId: string, userId: string) =>
    apiRequest<void>(`/departments/${departmentId}/users/${userId}`, { method: 'DELETE' }),
}
