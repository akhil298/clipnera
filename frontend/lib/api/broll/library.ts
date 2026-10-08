import { apiFetch } from '@/lib/api/client';

import type { LibraryBrowse, LibraryItem, LibraryItemDetail, LibrarySearchQuery, MediaRef, ReportCreate } from './types';

/**
 * The user-facing B-roll library: `/library/*` from docs/revamp/05-broll.md §7.3. Types in ./types.ts.
 * Until the routes exist each call fails with a 404 `ApiError`, which the screens show as their error state.
 */

const item = (assetId: string) => `/library/items/${encodeURIComponent(assetId)}`;
const favourite = (assetId: string) => `/library/favourites/${encodeURIComponent(assetId)}`;

/**
 * NEEDS-BACKEND: GET /library/search (L-API-1).
 * Returns `data` only: `meta.next_cursor` needs a paged apiFetch (Platform request), so callers page by `limit` (max 60).
 */
export const searchLibrary = (query: LibrarySearchQuery, signal?: AbortSignal) =>
  apiFetch<LibraryItem[]>('/library/search', { query: { ...query }, signal });

/** NEEDS-BACKEND: GET /library/browse (L-API-1). Featured rows, categories and popular shots. */
export const getLibraryBrowse = (signal?: AbortSignal) => apiFetch<LibraryBrowse>('/library/browse', { signal });

/** NEEDS-BACKEND: GET /library/items/{asset_id} (L-API-1). 404 also for another workspace's private item. */
export const getLibraryItem = (assetId: string, signal?: AbortSignal) => apiFetch<LibraryItemDetail>(item(assetId), { signal });

/** NEEDS-BACKEND: PUT / DELETE /library/favourites/{asset_id} (L-API-1). */
export const setLibraryFavourite = (assetId: string, on: boolean) =>
  apiFetch<{ favourite: boolean }>(favourite(assetId), { method: on ? 'PUT' : 'DELETE' });

/** NEEDS-BACKEND: POST /library/items/{asset_id}/report (L-API-1). 429 RATE_LIMITED after 10 a day. */
export const reportLibraryItem = (assetId: string, body: ReportCreate) =>
  apiFetch<{ reported: true }>(`${item(assetId)}/report`, { method: 'POST', body });

/** NEEDS-BACKEND: GET /library/media?refs=broll:<id>,…&fps= (L-API-1). Up to 100 refs; missing ones are left out. */
export const getLibraryMedia = (refs: readonly string[], fps?: number, signal?: AbortSignal) =>
  apiFetch<MediaRef[]>('/library/media', { query: { refs: refs.join(','), fps }, signal });
