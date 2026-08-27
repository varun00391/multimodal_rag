import { apiRequest } from './client'
import type { User } from '../types'

export interface AdminListItem extends User {
  department_names: string[]
}

export const adminsApi = {
  list: () => apiRequest<AdminListItem[]>('/admins'),

  create: (name: string, email: string, departmentName: string) =>
    apiRequest<User>('/admins', {
      method: 'POST',
      body: JSON.stringify({ name, email, department_name: departmentName }),
    }),
}
