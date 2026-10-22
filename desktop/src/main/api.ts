import type { ApiError, ApiResponse } from '../shared/api'

/** The backend's address; set CLIPNERA_API_URL to point the app at another one. */
export const API_URL = (process.env.CLIPNERA_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string
  ) {
    super(message)
  }
}

async function request<T>(method: 'GET' | 'POST' | 'DELETE', path: string, body?: unknown, token?: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      method,
      headers: {
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: body === undefined ? undefined : JSON.stringify(body)
    })
  } catch {
    throw new ApiRequestError(0, 'OFFLINE', "Can't reach Clipnera. Check your internet connection.")
  }

  const json = (await response.json().catch(() => null)) as (ApiError & ApiResponse<unknown>) | null
  if (!response.ok) {
    throw new ApiRequestError(response.status, json?.error ?? 'HTTP_ERROR', json?.message ?? `Request failed (${response.status})`)
  }
  return json as T
}

/** POSTs and returns the open response, for server-sent event streams. */
async function openStream(path: string, body: unknown, token: string, signal?: AbortSignal, extra: Record<string, string> = {}): Promise<ReadableStream<Uint8Array>> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { Accept: 'text/event-stream', Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...extra },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ApiRequestError(0, 'OFFLINE', "Can't reach Clipnera. Check your internet connection.")
  }
  if (!response.ok || !response.body) {
    const json = (await response.json().catch(() => null)) as ApiError | null
    throw new ApiRequestError(response.status, json?.error ?? 'HTTP_ERROR', json?.message ?? `Request failed (${response.status})`)
  }
  return response.body
}

async function unwrap<T>(response: Promise<ApiResponse<T>>): Promise<T> {
  const envelope = await response
  if (envelope.data === null) throw new ApiRequestError(200, envelope.error ?? 'EMPTY', envelope.message ?? 'Empty response')
  return envelope.data
}

export const api = {
  get: <T>(path: string, token?: string) => request<T>('GET', path, undefined, token),
  post: <T>(path: string, body: unknown, token?: string) => request<T>('POST', path, body, token),

  /** POST to an endpoint that answers with the {data, message, error} envelope; returns data. */
  postData: <T>(path: string, body: unknown, token?: string) => unwrap(request<ApiResponse<T>>('POST', path, body, token)),
  /** GET from an endpoint that answers with the envelope; returns data. */
  getData: <T>(path: string, token?: string) => unwrap(request<ApiResponse<T>>('GET', path, undefined, token)),
  deleteData: <T>(path: string, token?: string) => unwrap(request<ApiResponse<T>>('DELETE', path, undefined, token)),
  /** Opens a server-sent event stream: POST with a body, or GET without one. */
  stream: openStream
}
