import { NextResponse, type NextRequest } from 'next/server';

import {
  UI_FLAGS_COOKIE,
  UI_OVERRIDE_COOKIE,
  UI_OVERRIDE_MAX_AGE_SECONDS,
  parseUiOverride,
  type UiOverride,
} from '@/lib/flags/ui-areas';

/**
 * Classic/new UI escape hatch (frontend.md §1.5).
 *   GET  /api/ui/override?mode=classic|new|auto[&next=/dashboard]  support links: set, then redirect
 *   POST /api/ui/override?mode=…  and/or  ?refresh=1                 in-app: JSON envelope; refresh drops cn_ui
 * `new` only works outside production; there the flags decide.
 */

export interface UiOverrideResponse {
  mode: UiOverride | null;
  refreshed: boolean;
}

const NEW_ALLOWED = process.env.NODE_ENV !== 'production';

type Parsed = { ok: true; mode: UiOverride | null } | { ok: false; message: string };

function parseMode(req: NextRequest): Parsed {
  const raw = req.nextUrl.searchParams.get('mode');
  if (raw === null) return { ok: true, mode: null };
  const mode = parseUiOverride(raw);
  if (!mode) return { ok: false, message: 'mode must be classic, new or auto' };
  if (mode === 'new' && !NEW_ALLOWED) return { ok: false, message: 'The new UI is turned on by flags in production' };
  return { ok: true, mode };
}

/** Apply the override; any change also drops the cached area flags so the next request re-reads them. */
function apply(res: NextResponse, mode: UiOverride | null, refresh: boolean): NextResponse {
  if (mode === 'auto') res.cookies.delete(UI_OVERRIDE_COOKIE);
  else if (mode) res.cookies.set(UI_OVERRIDE_COOKIE, mode, { path: '/', sameSite: 'lax', maxAge: UI_OVERRIDE_MAX_AGE_SECONDS });
  if (mode || refresh) res.cookies.delete(UI_FLAGS_COOKIE);
  return res;
}

/** Only same-origin paths, never `//host` or a full URL. */
function safeNext(raw: string | null): string {
  return raw && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/dashboard';
}

export function GET(req: NextRequest) {
  const parsed = parseMode(req);
  if (!parsed.ok) return NextResponse.json({ data: null, message: parsed.message, error: 'INVALID_MODE' }, { status: 400 });
  const res = NextResponse.redirect(new URL(safeNext(req.nextUrl.searchParams.get('next')), req.url), 303);
  return apply(res, parsed.mode, false);
}

export function POST(req: NextRequest) {
  const parsed = parseMode(req);
  if (!parsed.ok) return NextResponse.json({ data: null, message: parsed.message, error: 'INVALID_MODE' }, { status: 400 });
  const refreshed = req.nextUrl.searchParams.get('refresh') === '1';
  const data: UiOverrideResponse = { mode: parsed.mode, refreshed };
  return apply(NextResponse.json({ data, message: null, error: null }), parsed.mode, refreshed);
}
