import type { ApiError } from '../types'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

export class ApiClientError extends Error {
  code: string
  requestId: string
  status: number

  constructor(message: string, code: string, requestId: string, status: number) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.requestId = requestId
    this.status = status
  }
}

async function parseError(response: Response): Promise<ApiClientError> {
  let code = 'INTERNAL_ERROR'
  let message = response.statusText || 'Request failed'
  let requestId = ''

  try {
    const body = (await response.json()) as ApiError
    if (body.error) {
      code = body.error.code
      message = body.error.message
      requestId = body.error.request_id
    }
  } catch {
    // ignore parse errors
  }

  return new ApiClientError(message, code, requestId, response.status)
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)

  if (!(options.body instanceof FormData) && !headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  })

  if (!response.ok) {
    throw await parseError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export function getLoginUrl(): string {
  return `${API_BASE}/auth/google/login`
}
