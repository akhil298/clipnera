/** The `{ data, message, error }` body every backend route returns (backend/core/responses.py ApiResponse). */
export interface ApiEnvelope<T> {
  data: T | null;
  message: string | null;
  error: string | null;
}

export function isEnvelope(body: unknown): body is ApiEnvelope<unknown> {
  return typeof body === 'object' && body !== null && 'data' in body && ('message' in body || 'error' in body);
}

/** The envelope's `data`; a bare body is passed through while older routes still return one. */
export function unwrap<T>(body: unknown): T {
  return (isEnvelope(body) ? body.data : body) as T;
}

/**
 * List meta (backend.md §11.3, openapi `PageMeta`). Everything is optional because today's
 * `core/responses.py ApiResponse` has no `meta` yet. NEEDS-BACKEND: `ok()` gains `meta`.
 * Routes with extra meta (`total`, `suggestions`, …) extend this through `apiFetchPage`'s `M`.
 */
export interface PageMeta {
  next_cursor?: string | null;
  has_more?: boolean;
  total?: number;
}

export interface Page<T, M extends PageMeta = PageMeta> {
  data: T;
  meta: M;
}

/** `{ data, meta }` from a list body; a bare body (older routes) becomes the data with empty meta. */
export function toPage<T, M extends PageMeta = PageMeta>(body: unknown): Page<T, M> {
  const meta = isEnvelope(body) ? (body as { meta?: unknown }).meta : undefined;
  return { data: unwrap<T>(body), meta: (typeof meta === 'object' && meta !== null ? meta : {}) as M };
}

/** The cursor for the page after this one, or undefined at the end (React Query's `getNextPageParam`). */
export function nextCursor(meta: PageMeta): string | undefined {
  if (meta.has_more === false) return undefined;
  return meta.next_cursor ?? undefined;
}
