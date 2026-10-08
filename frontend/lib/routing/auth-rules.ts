/**
 * Signed-out and signed-in redirects (frontend.md §1.4, screens/01 §3.3).
 *
 * Pure: no Next, no cookies, no globals, so middleware and the sign-in page
 * can share it and `node --test` can run it. Middleware (Platform) passes
 * `enabled` from the `auth_cookie_enforce` flag; until then every call returns
 * null and the client guards keep doing the work.
 */

export const HOME_PATH = '/dashboard';
/** The httpOnly session cookie the backend sets once the cookie migration lands (frontend.md §1.6). */
export const SESSION_COOKIE = 'cn_session';
export const LOGIN_PATH = '/login';

const AUTH_PAGES = new Set([LOGIN_PATH, '/signup']);
const PROTECTED_PREFIXES = ['/dashboard', '/admin'];
/** OAuth returns and email links must reach their page signed out (a redirect would lose the `code`). */
const EXEMPT_PREFIXES = ['/login/google', '/dashboard/connect', '/unsubscribe', '/data-deletion'];
/** Only for building a URL; never fetched. */
const PARSE_BASE = 'http://clipnera.invalid';

export interface AuthRuleOptions {
  /** The request's query string, with or without the leading `?`. */
  search?: string;
  /** `auth_cookie_enforce`. Off (the default) returns null for every request. */
  enabled?: boolean;
}

const trimSlash = (path: string) => (path.length > 1 && path.endsWith('/') ? path.slice(0, -1) : path);

const underPrefix = (path: string, prefixes: readonly string[]) =>
  prefixes.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));

/**
 * A `next` value that is safe to send someone to: a same-origin path outside
 * the sign-in pages. Anything else (absolute URLs, `//host`, backslashes,
 * control characters, the v2 tree) gives null.
 */
export function safeNextPath(raw: string | null | undefined): string | null {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || /[\\\u0000-\u001f]/.test(raw)) return null;
  let url: URL;
  try {
    url = new URL(raw, PARSE_BASE);
  } catch {
    return null;
  }
  if (url.origin !== PARSE_BASE) return null;
  const path = trimSlash(url.pathname);
  if (AUTH_PAGES.has(path) || path === '/login/google' || underPrefix(path, ['/v2'])) return null;
  return `${url.pathname}${url.search}${url.hash}`;
}

/** `/login?next=<path+query>`, plus `reason=expired` when a session ran out mid-visit. */
export function loginUrl(next: string | null, reason?: 'expired'): string {
  const params = new URLSearchParams();
  const safe = safeNextPath(next);
  if (safe) params.set('next', safe);
  if (reason) params.set('reason', reason);
  const query = params.toString();
  return query ? `${LOGIN_PATH}?${query}` : LOGIN_PATH;
}

/**
 * Where to send this request, or null to let it through.
 * - Signed out on `/dashboard/**` or `/admin/**` → `/login?next=<path+query>`.
 * - Signed in on `/login` or `/signup` → their `next`, else `/dashboard`.
 */
export function authRedirect(pathname: string, hasSessionCookie: boolean, options: AuthRuleOptions = {}): string | null {
  if (!options.enabled) return null;
  const path = trimSlash(pathname);
  const search = options.search ? (options.search.startsWith('?') ? options.search : `?${options.search}`) : '';

  if (hasSessionCookie) {
    if (!AUTH_PAGES.has(path)) return null;
    return safeNextPath(new URLSearchParams(search).get('next')) ?? HOME_PATH;
  }
  if (underPrefix(path, EXEMPT_PREFIXES) || !underPrefix(path, PROTECTED_PREFIXES)) return null;
  return loginUrl(`${pathname}${search}`);
}
