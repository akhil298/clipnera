# Wave 6 Phase 0: platform API for screen builders

Written by the Platform agent, 4 October 2026. Every file listed here belongs to Platform. Don't edit them; put change requests under "Requests" in your report.

## Previewing v2 locally

- `next dev`, then open any area URL with `?ui=new`, for example `/dashboard?ui=new`. This sets the `cn_ui_override=new` cookie, so later navigation stays on v2. Use `?ui=classic` to force the legacy UI, or `?ui=auto` to go back to flags. `?ui=` only works when NODE_ENV is not production.
- Support link: `GET /api/ui/override?mode=classic|new|auto&next=/dashboard` sets the cookie and then redirects. `POST /api/ui/override?mode=…&refresh=1` returns `{data:{mode,refreshed},message,error}`. `refresh=1` clears the cached `cn_ui` flags cookie. In production, `mode=new` is refused, so v2 is reached only through flags.
- A direct request to `/v2/...` returns 404. Always link to the public URL (`/dashboard/projects/42`) and never to `/v2/...`.

## Routing (`frontend/middleware.ts`, `lib/flags/ui-areas.ts`)

| Flag | URLs it moves to `app/v2` |
|---|---|
| `new_ui_auth` | `/`, `/login`, `/signup`, `/editor` |
| `new_ui_editor` | `/dashboard/editor/**`, `/dashboard/projects/[id]/edit/[clipId]` |
| `new_ui_export` | `/dashboard/scheduler/**` |
| `new_ui_settings` | `/dashboard/settings/**`, `/dashboard/brand-kit/**` |
| `new_ui_reels` | `/dashboard/reels/**` |
| `new_ui_dashboard` | `/dashboard`, `/dashboard/{projects,folders,analytics,library,upload}/**` |
| `new_ui_admin` | `/admin/**` |

- The registry has no `new_ui_library`, so Library falls under `new_ui_dashboard`. "My uploads" is gated inside the page by `broll_user_library`.
- These paths are never rewritten: `/login/google`, `/dashboard/connect/*`, `/unsubscribe`, `/data-deletion` and the legal pages.
- When an area is on, middleware also returns 308 redirects: `/dashboard/folders` → `/dashboard/projects` and `/dashboard/settings?tab=x` → `/dashboard/settings/x`.
- Middleware reads the area flags from the `cn_ui` cookie (5 min, not signed, not a security boundary). If the cookie is missing, it asks `GET /flags/bootstrap` anonymously with a 300 ms timeout and falls back to the legacy UI on failure. Middleware can't see a signed-in user's flags because the token is still in localStorage. `FlagsProvider` therefore rewrites `cn_ui` from the user's own bootstrap, and the user's next navigation is routed by their flags.
- Auth redirects aren't implemented yet. Area 2 adds them in `lib/routing/auth-rules.ts`, and Platform wires that file into middleware.

## v2 tree

`app/v2/(app)/dashboard` has the placeholder shell, which Area 1 replaces. It also has the `@modal` slot with `default.tsx`. `app/v2/(editor)/dashboard` is full screen. `app/v2/(admin)/admin` is a placeholder wrapped in the legacy `AdminGate`. `app/v2/(marketing)` and `app/v2/(auth)` are placeholders. Every route in frontend.md §1.2 has a `page.tsx` that renders `<Placeholder>`. Replace the page file with your screen.

`loading.tsx`, `error.tsx` and `not-found.tsx` exist for `(app)/dashboard`, `projects/[projectId]`, `(editor)/.../editor/[editorProjectId]` and `(admin)/admin`. `error.tsx` exists for `(marketing)` and `(auth)`. Their building blocks are in `app/v2/_platform/` (`SegmentLoading`, `SegmentError`, `SegmentNotFound`, `Placeholder`). Import them, but don't edit them.

## `apiFetch` (`lib/api/client.ts`)

```ts
apiFetch<T>(path: string, options?: {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  query?: Record<string, string | number | boolean | null | undefined | readonly (...)[]>; // empty values dropped
  body?: unknown;              // JSON; FormData/Blob sent as-is
  signal?: AbortSignal;        // pass React Query's signal
  timeoutMs?: number;          // default 15000
  idempotencyKey?: string;     // credit-spending / creating mutations
  auth?: 'required' | 'optional'; // default 'required'
  headers?: Record<string, string>;
}): Promise<T>                 // T = the envelope's `data`
```

- `path` is relative to `${NEXT_PUBLIC_API_URL}/api/v1`, for example `'/editor/projects'`. Every call sends the bearer token from `lib/auth.ts`, `X-Request-ID` and `credentials: 'include'`.
- With `auth: 'required'`, a missing token or a 401 response clears the token and sends the user to `/login?next=…`. Server components can't see the token yet, so on the server, fetch on the client or use `auth: 'optional'`.
- On failure it throws `ApiError` (`lib/api/errors.ts`), which has `{ status, code, message, requestId, feature?, retryAfter?, fields? }`. `status` is 0 when no response arrived. Client codes are `NETWORK`, `TIMEOUT`, `BAD_RESPONSE`, `CONFIG`, `UNAUTHORIZED` and `VALIDATION`. A 422 response fills `fields`. Any other `code` is the backend's `error` value.
- Use these guards instead of matching on `message`: `isApiError`, `isPlanError`, `isNotFound`, `isForbidden`, `isUnauthorized`, `isStale`, `isFeatureDisabled`, `isRetryable`.
- Plan errors still dispatch `clipnera:upgrade-required` on `window`.
- `lib/api/envelope.ts` exports `ApiEnvelope<T>`, `isEnvelope` and `unwrap`. `apiFetch` already unwraps the envelope, so you rarely need them.
- Put your domain wrappers in `lib/api/<domain>/` with types that exactly match the Pydantic schema. Don't create `lib/api/index.ts`, because it would shadow the legacy `@/lib/api` import.

## React Query (`lib/query/`)

- `QueryClientProvider` is mounted in `app/providers.tsx`. Use `useQuery`, `useMutation` and `useQueryClient` from `@tanstack/react-query`.
- `lib/query/client.ts` exports `makeQueryClient()` and `getQueryClient()`. Defaults: `staleTime` 30 s, `gcTime` 5 min, up to 2 retries only for network, timeout, 5xx and 429 (honouring `Retry-After`), exponential backoff capped at 10 s, and no mutation retries. Set per-query cache times from the table in frontend.md §3.4.
- **Query keys:** each domain gets its own file, `lib/query/keys/<domain>.ts`. Add your own file there and never edit another area's. There is no index file, so import directly. Shape: `[domain, scope, ...params]`.

```ts
// lib/query/keys/projects.ts (example)
export const projectKeys = {
  all: ['projects'] as const,
  list: (ws: string, f: ProjectFilter) => [...projectKeys.all, 'list', ws, f] as const,
  detail: (id: string) => [...projectKeys.all, 'detail', id] as const,
};
```

## Flags (`lib/flags/`)

```ts
import { useFlag, useConfig, useFlagsStatus } from '@/lib/flags/useFlag';
useFlag('broll_user_library'): boolean          // synchronous, never undefined (FLAG_DEFAULTS until loaded)
useConfig('uploads.max_bytes'): number           // typed per key (registry.gen.ts)
useFlagsStatus(): { ready, version, source: 'server' | 'snapshot' | 'defaults' }
```

These hooks are client-only. The server render and the first client render use the defaults so that hydration matches. After that, the user's last 24 h snapshot from localStorage is shown immediately, and `GET /flags/bootstrap` replaces it. The bootstrap is refetched on tab focus and every `poll_seconds`. Use `useFlag` only for in-page sub-flags. Don't use it to pick between old and new screens, because middleware already makes that choice.

## Editor seams (`components/editor/slots.ts`)

- **Export dialog (Area 8, hosted by Area 4):** `ExportDialogSlot = ComponentType<{ open, onOpenChange, projectId, title, version, timeline }>`.
- **Library → timeline (Area 6/7 → Area 5):** `BROLL_DRAG_MIME`, `BrollDropPayload` (`v:1`, `library`, `id`, `title`, `media`, `duration_s`, `width`, `height`, `thumb_url`, `proxy_url`, `attribution_text`, `range?`), `TimelineDropPoint {track, at}` in frames, `InsertBroll`, `writeBrollDrag(dt, payload)` and `readBrollDrag(dt)`.

## Packages added

`@tanstack/react-query`, `@tanstack/react-virtual`, `zustand` and `idb-keyval`. `next` stays at 15.1.6, and `framer-motion` is still installed. Don't install anything else; ask Platform instead.
