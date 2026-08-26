import { apiRequest } from './client'
import type { DepartmentDashboard, SuperAdminDashboard, UserDashboard } from '../types'

export const dashboardApi = {
  me: () => apiRequest<UserDashboard>('/dashboard/me'),

  department: (departmentId: string) =>
    apiRequest<DepartmentDashboard>(`/dashboard/departments/${departmentId}`),

  superAdmin: () => apiRequest<SuperAdminDashboard>('/dashboard/super-admin'),
}
