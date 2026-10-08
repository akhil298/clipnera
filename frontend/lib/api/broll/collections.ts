import { apiFetch } from '@/lib/api/client';

import type { CollectionCreate, CollectionSummary, CollectionUpdate } from './types';

/** Collections of library shots: `/library/collections*` from docs/revamp/05-broll.md §7.3. */

const collection = (id: string) => `/library/collections/${encodeURIComponent(id)}`;

/** NEEDS-BACKEND: GET /library/collections?scope=mine|featured (L-API-1). */
export const listCollections = (scope: 'mine' | 'featured', signal?: AbortSignal) =>
  apiFetch<CollectionSummary[]>('/library/collections', { query: { scope }, signal });

/** NEEDS-BACKEND: POST /library/collections (L-API-1). 429 LIMIT_REACHED at the plan's maximum. */
export const createCollection = (body: CollectionCreate, idempotencyKey: string) =>
  apiFetch<CollectionSummary>('/library/collections', { method: 'POST', body, idempotencyKey });

/** NEEDS-BACKEND: PATCH /library/collections/{id} (L-API-1; `order` is L-API-1b). */
export const updateCollection = (id: string, body: CollectionUpdate) =>
  apiFetch<CollectionSummary>(collection(id), { method: 'PATCH', body });

/** NEEDS-BACKEND: DELETE /library/collections/{id} (L-API-1). */
export const deleteCollection = (id: string) => apiFetch<null>(collection(id), { method: 'DELETE' });

/** NEEDS-BACKEND: POST /library/collections/{id}/items (L-API-1). 1–100 asset ids. */
export const addCollectionItems = (id: string, assetIds: readonly string[]) =>
  apiFetch<CollectionSummary>(`${collection(id)}/items`, { method: 'POST', body: { asset_ids: assetIds } });

/** NEEDS-BACKEND: DELETE /library/collections/{id}/items/{asset_id} (L-API-1). */
export const removeCollectionItem = (id: string, assetId: string) =>
  apiFetch<CollectionSummary>(`${collection(id)}/items/${encodeURIComponent(assetId)}`, { method: 'DELETE' });
