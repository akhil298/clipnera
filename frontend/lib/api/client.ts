import { clearAuth, getToken } from '@/lib/auth';

import { toPage, unwrap, type Page, type PageMeta } from './envelope';
import { ApiError, PLAN_ERROR_CODES } from './errors';

/**
 * The one typed fetch for the new UI (docs/revamp/architecture/frontend.md §3.2).
 * Returns the envelope's `data`, throws `ApiError` for everything else. Legacy code keeps lib/api.ts.
 */

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
type QueryValue = string | number | boolean | null | undefined;

export interface ApiFetchOptions {
  method?: Method;
  /** Appended as a query string; null, undefined and '' are left out. */
  query?: Record<string, QueryValue | readonly QueryValue[]>;
  /** Sent as JSON, or as-is for FormData and Blob. */
  body?: unknown;
  /** The query's or caller's signal; aborting it rethrows the AbortError untouched. */
  signal?: AbortSignal;
  /** Default 15 s. Uploads and exports pass a longer one. */
  timeoutMs?: number;
  /** For calls that spend credits or create things; make it once, when the action is triggered. */
  idempotencyKey?: string;
  /**
   * `required` (default): no token or a 401 ends the session and sends the user to sign in.
   * `optional`: send the token when there is one; a 401 is just thrown.
   */
  auth?: 'required' | 'optional';
  headers?: Record<string, string>;
}

const DEFAULT_TIMEOUT_MS = 15_000;

/** Fired on window for any plan error so the upsell can open wherever the call came from (same as lib/api.ts). */
const UPGRADE_REQUIRED_EVENT = 'clipnera:upgrade-required';

/** The full URL of an API path plus query, for callers that can't use `apiFetch` (the event stream). */
export function apiUrl(path: string, query?: ApiFetchOptions['query'], requestId: string = crypto.randomUUID()): string {
  const origin = process.env.NEXT_PUBLIC_API_URL;
  if (!origin) {
    throw new ApiError({ status: 0, code: 'CONFIG', message: 'NEXT_PUBLIC_API_URL is not set', requestId });
  }
  return `${origin}/api/v1${path}${queryString(query)}`;
}

function queryString(query: ApiFetchOptions['query']): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, raw] of Object.entries(query)) {
    for (const value of Array.isArray(raw) ? raw : [raw]) {
      if (value !== null && value !== undefined && value !== '') params.append(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

/** The caller's signal plus our timeout; `AbortSignal.any` is missing before Safari 17.4. */
function withTimeout(signal: AbortSignal | undefined, timeoutMs: number): AbortSignal {
  const timeout = AbortSignal.timeout(timeoutMs);
  if (!signal) return timeout;
  if (typeof AbortSignal.any === 'function') return AbortSignal.any([signal, timeout]);
  const controller = new AbortController();
  const forward = (source: AbortSignal) => () => controller.abort(source.reason);
  signal.addEventListener('abort', forward(signal), { once: true });
  timeout.addEventListener('abort', forward(timeout), { once: true });
  return controller.signal;
}

function encodeBody(body: unknown, headers: Record<string, string>): BodyInit | undefined {
  if (body === undefined) return undefined;
  if (body instanceof FormData || body instanceof Blob) return body;
  headers['Content-Type'] = 'application/json';
  return JSON.stringify(body);
}

/** FastAPI's default 422 body: `{ detail: [{ loc: [..., field], msg }] }`. */
function validationFields(detail: unknown): Record<string, string[]> | undefined {
  if (!Array.isArray(detail)) return undefined;
  const fields: Record<string, string[]> = {};
  for (const item of detail as Array<{ loc?: unknown[]; msg?: string }>) {
    const field = String(item.loc?.[item.loc.length - 1] ?? '_');
    (fields[field] ??= []).push(item.msg ?? 'Invalid value');
  }
  return fields;
}

/** Clears the token and sends the user to sign in, coming back here afterwards. */
export function endSession(): void {
  clearAuth();
  if (typeof window === 'undefined') return;
  const next = `${window.location.pathname}${window.location.search}`;
  window.location.assign(`/login?next=${encodeURIComponent(next)}`);
}

function toApiError(res: Response, body: unknown, requestId: string): ApiError {
  const record = (typeof body === 'object' && body !== null ? body : {}) as Record<string, unknown>;
  const fields = validationFields(record.detail);
  const retryAfter = Number(res.headers.get('Retry-After'));
  return new ApiError({
    status: res.status,
    code: typeof record.error === 'string' ? record.error : fields ? 'VALIDATION' : body === undefined ? 'BAD_RESPONSE' : `HTTP_${res.status}`,
    message: typeof record.message === 'string' ? record.message : 'Something went wrong',
    feature: typeof record.feature === 'string' ? record.feature : undefined,
    retryAfter: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined,
    fields,
    requestId,
  });
}

/** Sends the request and returns the parsed success body (still enveloped); throws `ApiError` otherwise. */
async function request(path: string, options: ApiFetchOptions): Promise<unknown> {
  const { method = 'GET', query, body, signal, timeoutMs = DEFAULT_TIMEOUT_MS, idempotencyKey, auth = 'required' } = options;
  const requestId = crypto.randomUUID();
  const url = apiUrl(path, query, requestId);

  const token = getToken();
  if (!token && auth === 'required') {
    endSession();
    throw new ApiError({ status: 401, code: 'UNAUTHORIZED', message: 'Your session has ended. Sign in again.', requestId });
  }

  const headers: Record<string, string> = { 'X-Request-ID': requestId, ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: encodeBody(body, headers),
      credentials: 'include',
      cache: 'no-store',
      signal: withTimeout(signal, timeoutMs),
    });
  } catch (err) {
    if (signal?.aborted) throw err;
    const timedOut = err instanceof DOMException && err.name === 'TimeoutError';
    throw new ApiError({
      status: 0,
      code: timedOut ? 'TIMEOUT' : 'NETWORK',
      message: timedOut ? 'The server took too long to answer.' : 'Could not reach Clipnera. Check your connection.',
      requestId,
    });
  }

  const text = await res.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = undefined;
  }

  if (!res.ok || (parsed as { error?: unknown } | null)?.error) {
    const error = toApiError(res, parsed, requestId);
    if (error.status === 401 && auth === 'required') endSession();
    if (PLAN_ERROR_CODES.has(error.code) && typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent(UPGRADE_REQUIRED_EVENT, {
          detail: { error: error.code, feature: error.feature, message: error.message },
        }),
      );
    }
    throw error;
  }
  if (parsed === undefined) {
    throw new ApiError({ status: res.status, code: 'BAD_RESPONSE', message: 'The server sent an unreadable answer.', requestId });
  }
  return parsed;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  return unwrap<T>(await request(path, options));
}

/**
 * For list routes: the envelope's `data` plus its `meta` (`next_cursor`, `has_more`, and any extras the
 * route declares through `M`). A route that sends no `meta` yet gives `{}`.
 */
export async function apiFetchPage<T, M extends PageMeta = PageMeta>(path: string, options: ApiFetchOptions = {}): Promise<Page<T, M>> {
  return toPage<T, M>(await request(path, options));
}
