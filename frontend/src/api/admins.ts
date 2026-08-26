import { apiRequest } from './client'
import type { User } from '../types'

export const adminsApi = {
  create: (name: string, email: string, departmentName: string) =>
    apiRequest<User>('/admins', {
      method: 'POST',
      body: JSON.stringify({ name, email, department_name: departmentName }),
    }),
}
