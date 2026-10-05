/** Codes the client itself raises; every other `code` is the backend's `error` field. */
export type ClientErrorCode = 'NETWORK' | 'TIMEOUT' | 'BAD_RESPONSE' | 'CONFIG' | 'UNAUTHORIZED' | 'VALIDATION';

/** Errors the API returns when the caller's plan does not cover a request (same set as lib/api.ts). */
export const PLAN_ERROR_CODES: ReadonlySet<string> = new Set([
  'PRO_REQUIRED',
  'LIMIT_REACHED',
  'ASPECT_RATIO_NOT_ENTITLED',
  'CAPTION_STYLE_NOT_ENTITLED',
  'DURATION_NOT_ENTITLED',
  'INSUFFICIENT_CREDITS',
]);

export interface ApiErrorInit {
  status: number;
  code: string;
  message: string;
  requestId: string;
  feature?: string;
  retryAfter?: number;
  fields?: Record<string, string[]>;
}

/** Every failure `apiFetch` throws. Branch on `code`, never on `message`. */
export class ApiError extends Error {
  /** HTTP status; 0 when no response arrived (network failure, timeout). */
  readonly status: number;
  readonly code: string;
  readonly requestId: string;
  /** The feature a plan or flag error refers to. */
  readonly feature?: string;
  /** Seconds, from `Retry-After`. */
  readonly retryAfter?: number;
  /** 422 field errors, keyed by field name. */
  readonly fields?: Record<string, string[]>;

  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = 'ApiError';
    this.status = init.status;
    this.code = init.code;
    this.requestId = init.requestId;
    this.feature = init.feature;
    this.retryAfter = init.retryAfter;
    this.fields = init.fields;
  }
}

export const isApiError = (err: unknown): err is ApiError => err instanceof ApiError;
export const isPlanError = (err: unknown): err is ApiError => isApiError(err) && PLAN_ERROR_CODES.has(err.code);
export const isNotFound = (err: unknown): err is ApiError => isApiError(err) && err.status === 404;
export const isForbidden = (err: unknown): err is ApiError => isApiError(err) && err.status === 403;
export const isUnauthorized = (err: unknown): err is ApiError => isApiError(err) && err.status === 401;
export const isStale = (err: unknown): err is ApiError => isApiError(err) && err.code === 'STALE_VERSION';
export const isFeatureDisabled = (err: unknown): err is ApiError => isApiError(err) && err.code === 'FEATURE_DISABLED';

/** Worth retrying: no response, a timeout, a 5xx or a 429. Other 4xx never are. */
export const isRetryable = (err: unknown): boolean =>
  isApiError(err) && (err.status === 0 || err.status === 429 || err.status >= 500);
