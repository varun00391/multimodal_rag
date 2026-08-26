export type UserRole = 'SUPER_ADMIN' | 'ADMIN' | 'USER'
export type UserStatus = 'ACTIVE' | 'INACTIVE'

export interface User {
  user_id: string
  email: string
  name: string
  role: UserRole
  department_ids: string[]
  status: UserStatus
  is_super_admin_seed: boolean
}

export interface Department {
  department_id: string
  name: string
}

export interface DocumentUploadResponse {
  document_id: string
  status: string
  ingestion_job_id: string
}

export interface Document {
  document_id: string
  title: string
  filename: string
  status: string
  department_id: string
  owner_user_id: string
  size_bytes: number
}

export interface DocumentElement {
  element_id: string
  document_id: string
  element_type: string
  page: number | null
  source_ref: string | null
  content: string | null
}

export interface IngestionJob {
  job_id: string
  document_id: string
  status: string
  progress: number
  current_step: string | null
}

export interface QuerySource {
  document_id: string
  page: number | null
  chunk_id: string
  element_type: string
}

export interface QueryResponse {
  query_id: string
  answer: string
  sources: QuerySource[]
  usage: { retrieved_chunks: number }
}

export interface QueryHistoryItem {
  query_id: string
  query: string
  answer?: string
  created_at?: string
}

export interface ApiError {
  error: {
    code: string
    message: string
    request_id: string
  }
}

export interface UserDashboard {
  role: string
  query_count: number
  department_ids: string[]
}

export interface DepartmentDashboard {
  department_id: string
  users: number
  documents: number
  queries: number
}

export interface SuperAdminDashboard {
  users_by_role: Record<string, number>
  documents: number
  queries: number
}
