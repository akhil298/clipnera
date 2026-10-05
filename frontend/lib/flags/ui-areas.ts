/**
 * Which URLs each new_ui_* flag moves to the app/v2 tree (docs/revamp/architecture/frontend.md §1.5).
 * Written once in Phase 0 and read by middleware.ts (edge) and FlagsProvider, so it imports nothing
 * but types. Removing a row is the cutover for that area.
 *
 * `new_ui_library` is not in backend/feature_flags/registry.py, so /dashboard/library rides on
 * `new_ui_dashboard`. The "My uploads" tab inside it is gated by `broll_user_library`.
 */
import type { FlagKey } from './registry.gen';

export type UiArea = 'auth' | 'dashboard' | 'editor' | 'export' | 'settings' | 'reels' | 'admin';

export interface UiAreaRoute {
  area: UiArea;
  flag: FlagKey;
  /** Wave 6 area that builds it. */
  wave6Area: number;
  paths: readonly RegExp[];
}

/** First match wins, so the editor rows sit above the /dashboard/projects rows they overlap. */
export const UI_AREAS: readonly UiAreaRoute[] = [
  { area: 'auth', flag: 'new_ui_auth', wave6Area: 2, paths: [/^\/$/, /^\/login$/, /^\/signup$/, /^\/editor$/] },
  {
    area: 'editor',
    flag: 'new_ui_editor',
    wave6Area: 4,
    paths: [/^\/dashboard\/editor(\/.*)?$/, /^\/dashboard\/projects\/[^/]+\/edit\/[^/]+$/],
  },
  { area: 'export', flag: 'new_ui_export', wave6Area: 8, paths: [/^\/dashboard\/scheduler(\/.*)?$/] },
  {
    area: 'settings',
    flag: 'new_ui_settings',
    wave6Area: 9,
    paths: [/^\/dashboard\/settings(\/.*)?$/, /^\/dashboard\/brand-kit(\/.*)?$/],
  },
  { area: 'reels', flag: 'new_ui_reels', wave6Area: 4, paths: [/^\/dashboard\/reels(\/.*)?$/] },
  {
    area: 'dashboard',
    flag: 'new_ui_dashboard',
    wave6Area: 3,
    paths: [/^\/dashboard$/, /^\/dashboard\/(projects|folders|analytics|library|upload)(\/.*)?$/],
  },
  { area: 'admin', flag: 'new_ui_admin', wave6Area: 10, paths: [/^\/admin(\/.*)?$/] },
];

/** Never rewritten: OAuth returns whose paths are registered with providers, and links from email or Meta. */
const EXEMPT: readonly RegExp[] = [/^\/login\/google$/, /^\/dashboard\/connect\//, /^\/unsubscribe/, /^\/data-deletion/];

export function uiAreaFor(pathname: string): UiAreaRoute | null {
  if (EXEMPT.some((re) => re.test(pathname))) return null;
  return UI_AREAS.find((route) => route.paths.some((re) => re.test(pathname))) ?? null;
}

// --- cookies shared by middleware.ts, app/api/ui/override and FlagsProvider ---

/** The caller's area flags, cached so middleware calls the backend about once per TTL. Not a security boundary. */
export const UI_FLAGS_COOKIE = 'cn_ui';
export const UI_FLAGS_TTL_SECONDS = 300;
/** `classic` | `new` | `auto`; set by /api/ui/override (and `?ui=` in development). */
export const UI_OVERRIDE_COOKIE = 'cn_ui_override';
export const UI_OVERRIDE_MAX_AGE_SECONDS = 30 * 24 * 3600;

export type UiOverride = 'classic' | 'new' | 'auto';

export const parseUiOverride = (value: string | null | undefined): UiOverride | null =>
  value === 'classic' || value === 'new' || value === 'auto' ? value : null;

const AREA_FLAGS = new Set<FlagKey>(UI_AREAS.map((route) => route.flag));
const NONE = '-';

/** The area flags that are on, as a cookie value. */
export function encodeUiFlags(flags: Partial<Record<FlagKey, boolean>>): string {
  const on = (Object.keys(flags) as FlagKey[]).filter((key) => AREA_FLAGS.has(key) && flags[key]);
  return on.length ? on.join('~') : NONE;
}

export function decodeUiFlags(value: string): ReadonlySet<FlagKey> {
  if (value === NONE) return new Set();
  return new Set(value.split('~').filter((key): key is FlagKey => AREA_FLAGS.has(key as FlagKey)));
}
