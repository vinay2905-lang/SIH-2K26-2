/** Thin fetch wrapper: same-origin cookies, CSRF header on mutations, typed errors. */

const BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown
  readonly requestId?: string

  constructor(status: number, code: string, message: string, details?: unknown, requestId?: string) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }

  /** Field-level errors returned by the API, keyed by field name. */
  get fieldErrors(): Record<string, string> {
    const map: Record<string, string> = {}
    if (Array.isArray(this.details)) {
      for (const item of this.details as { field?: string | null; message?: string }[]) {
        if (item?.field && item.message && !map[item.field]) map[item.field] = item.message
      }
    }
    return map
  }
}

let csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

type Query = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, query?: Query) {
  const url = new URL(BASE + path, window.location.origin)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
    }
  }
  return url.pathname + url.search
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: { error?: { code?: string; message?: string; details?: unknown; request_id?: string } } = {}
  try {
    body = await response.json()
  } catch {
    /* non-JSON error body */
  }
  const error = body.error ?? {}
  return new ApiError(
    response.status,
    error.code ?? 'http_error',
    error.message ?? `Request failed (${response.status})`,
    error.details,
    error.request_id ?? response.headers.get('X-Request-ID') ?? undefined,
  )
}

async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Query; form?: FormData } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (options.form) {
    body = options.form
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body,
      credentials: 'same-origin',
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the server. Check that the API is running.')
  }
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, { body }),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, { body }),
  upload: <T>(path: string, form: FormData) => request<T>('POST', path, { form }),
}

/** Download a file served by the API (e.g. CSV exports) using the session cookie. */
export async function downloadFile(path: string, query?: Query): Promise<void> {
  const response = await fetch(buildUrl(path, query), { credentials: 'same-origin' })
  if (!response.ok) throw await toApiError(response)
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = /filename="([^"]+)"/.exec(disposition)
  const filename = match?.[1] ?? 'download.csv'
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
