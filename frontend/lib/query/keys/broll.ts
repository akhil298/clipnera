import type { LibrarySearchQuery } from '@/lib/api/broll/types';

/**
 * Query keys for the B-roll library (Area 6). One file per domain; see docs/revamp/wave6/01-platform-api.md.
 * Cache times (frontend.md §3.4): search and browse 5 min.
 */
export const brollKeys = {
  all: ['broll'] as const,
  browse: () => [...brollKeys.all, 'browse'] as const,
  search: (query: LibrarySearchQuery) => [...brollKeys.all, 'search', query] as const,
  item: (assetId: string) => [...brollKeys.all, 'item', assetId] as const,
  collections: (scope: 'mine' | 'featured') => [...brollKeys.all, 'collections', scope] as const,
};

/** Five minutes, for search results and browse rows. */
export const BROLL_STALE_MS = 5 * 60_000;
