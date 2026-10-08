import { NextResponse, type NextRequest } from 'next/server';

import {
  AUTH_ENFORCE_FLAG,
  UI_FLAGS_COOKIE,
  UI_FLAGS_TTL_SECONDS,
  UI_OVERRIDE_COOKIE,
  UI_OVERRIDE_MAX_AGE_SECONDS,
  decodeUiFlags,
  encodeUiFlags,
  parseUiOverride,
  uiAreaFor,
  type UiAreaRoute,
  type UiOverride,
} from '@/lib/flags/ui-areas';
import { authRedirect, SESSION_COOKIE } from '@/lib/routing/auth-rules';

/**
 * Per-area UI routing (docs/revamp/architecture/frontend.md §1.4–1.5). Picks the legacy tree or
 * app/v2 before rendering, so the URL never changes and nothing flickers. Not a security boundary:
 * the API authorizes every call. Auth redirects (lib/routing/auth-rules.ts) run only once the
 * `auth_cookie_enforce` flag is on; until then the client guards do that work.
 */

const DEV = process.env.NODE_ENV !== 'production';
/** Forcing unfinished screens on is a preview tool; production reaches them through flags only. */
const NEW_OVERRIDE_ALLOWED = DEV;
const FLAGS_TIMEOUT_MS = 300;
/** After a failed lookup, try again this soon rather than on every request. */
const FAILED_LOOKUP_TTL_SECONDS = 30;
const ANON_COOKIE = 'cn_anon';
/** Pages the auth rules can redirect; flags are looked up for these even without a UI area. */
const AUTH_RULE_PATHS = /^\/(dashboard|admin|login|signup)(\/|$)/;

interface AreaFlags {
  value: string;
  /** Set when freshly fetched, so the response caches it. */
  maxAge?: number;
}

/** The anonymous bootstrap: the API token is not a cookie yet, so FlagsProvider refreshes the cookie for signed-in users. */
async function lookupAreaFlags(req: NextRequest): Promise<AreaFlags> {
  const cached = req.cookies.get(UI_FLAGS_COOKIE)?.value;
  if (cached) return { value: cached };
  const api = process.env.NEXT_PUBLIC_API_URL;
  const anon = req.cookies.get(ANON_COOKIE)?.value;
  try {
    if (!api) throw new Error('NEXT_PUBLIC_API_URL is not set');
    const res = await fetch(`${api}/api/v1/flags/bootstrap`, {
      headers: { accept: 'application/json', ...(anon ? { cookie: `${ANON_COOKIE}=${anon}` } : {}) },
      cache: 'no-store',
      signal: AbortSignal.timeout(FLAGS_TIMEOUT_MS),
    });
    if (!res.ok) throw new Error(`flags bootstrap ${res.status}`);
    const body = (await res.json()) as { data?: { flags?: Record<string, boolean> } };
    return { value: encodeUiFlags(body.data?.flags ?? {}), maxAge: UI_FLAGS_TTL_SECONDS };
  } catch {
    return { value: encodeUiFlags({}), maxAge: FAILED_LOOKUP_TTL_SECONDS };
  }
}

/** Legacy URLs the new tree names differently (308 so links and bookmarks update). */
function v2Redirect(req: NextRequest, route: UiAreaRoute): URL | null {
  const { pathname, searchParams } = req.nextUrl;
  if (route.area === 'dashboard' && /^\/dashboard\/folders(\/.*)?$/.test(pathname)) {
    return new URL('/dashboard/projects', req.url);
  }
  const tab = searchParams.get('tab');
  if (route.area === 'settings' && pathname === '/dashboard/settings' && tab && /^[a-z-]+$/.test(tab)) {
    const url = req.nextUrl.clone();
    url.pathname = `/dashboard/settings/${tab}`;
    url.searchParams.delete('tab');
    return url;
  }
  return null;
}

function toV2(req: NextRequest, route: UiAreaRoute): NextResponse {
  const redirect = v2Redirect(req, route);
  if (redirect) return NextResponse.redirect(redirect, 308);
  const url = req.nextUrl.clone();
  url.pathname = req.nextUrl.pathname === '/' ? '/v2' : `/v2${req.nextUrl.pathname}`;
  return NextResponse.rewrite(url);
}

function setOverrideCookie(res: NextResponse, override: UiOverride): NextResponse {
  if (override === 'auto') res.cookies.delete(UI_OVERRIDE_COOKIE);
  else res.cookies.set(UI_OVERRIDE_COOKIE, override, { path: '/', sameSite: 'lax', maxAge: UI_OVERRIDE_MAX_AGE_SECONDS });
  return res;
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // The new tree is reachable only through a rewrite.
  if (pathname === '/v2' || pathname.startsWith('/v2/')) {
    // Any path with no route renders app/not-found.tsx with a 404 status.
    return NextResponse.rewrite(new URL('/__v2_direct', req.url));
  }

  // Development preview: `?ui=new|classic|auto` sets the override for this and later requests.
  const queryOverride = DEV ? parseUiOverride(req.nextUrl.searchParams.get('ui')) : null;
  const route = uiAreaFor(pathname);
  const override = queryOverride ?? parseUiOverride(req.cookies.get(UI_OVERRIDE_COOKIE)?.value) ?? 'auto';

  const forcedNew = override === 'new' && NEW_OVERRIDE_ALLOWED;
  const needsFlags = AUTH_RULE_PATHS.test(pathname) || (route !== null && override !== 'classic' && !forcedNew);
  const flags = needsFlags ? await lookupAreaFlags(req) : null;
  const on = flags ? decodeUiFlags(flags.value) : new Set<string>();

  const signInTo = authRedirect(pathname, req.cookies.has(SESSION_COOKIE), {
    search: req.nextUrl.search,
    enabled: on.has(AUTH_ENFORCE_FLAG),
  });

  let res = NextResponse.next();
  if (signInTo) res = NextResponse.redirect(new URL(signInTo, req.url));
  else if (route && override !== 'classic' && (forcedNew || on.has(route.flag))) res = toV2(req, route);
  if (flags?.maxAge) res.cookies.set(UI_FLAGS_COOKIE, flags.value, { path: '/', sameSite: 'lax', maxAge: flags.maxAge });
  return queryOverride ? setOverrideCookie(res, queryOverride) : res;
}

export const config = {
  // Everything but Next internals, route handlers and files with an extension (icon.svg, images, fonts).
  matcher: ['/((?!_next/|api/|.*\\..*).*)'],
};
