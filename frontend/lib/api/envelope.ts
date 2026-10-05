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
