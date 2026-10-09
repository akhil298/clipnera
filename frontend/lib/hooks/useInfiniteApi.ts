'use client';

import { infiniteQueryOptions, useInfiniteQuery, type InfiniteData, type QueryKey } from '@tanstack/react-query';

import { apiFetchPage, type ApiFetchOptions } from '@/lib/api/client';
import { nextCursor, type Page, type PageMeta } from '@/lib/api/envelope';

export interface InfiniteApiParams {
  /** From your domain's key factory (`lib/query/keys/<domain>.ts`). */
  queryKey: QueryKey;
  path: string;
  /** Filters; `limit` and `cursor` are added per page. */
  query?: ApiFetchOptions['query'];
  pageSize?: number;
  enabled?: boolean;
  staleTime?: number;
}

/**
 * Cursor-paged list options (`?limit&cursor` → `meta.next_cursor`). Usable with `useInfiniteQuery`,
 * `prefetchInfiniteQuery` or `setQueryData`; `useInfiniteApi` below is the common case.
 */
export function infiniteApiOptions<T, M extends PageMeta = PageMeta>({ queryKey, path, query, pageSize = 30, enabled, staleTime }: InfiniteApiParams) {
  return infiniteQueryOptions({
    queryKey,
    enabled,
    staleTime,
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      apiFetchPage<T[], M>(path, { query: { ...query, limit: pageSize, cursor: pageParam }, signal }),
    getNextPageParam: (last: Page<T[], M>) => nextCursor(last.meta),
  });
}

export function useInfiniteApi<T, M extends PageMeta = PageMeta>(params: InfiniteApiParams) {
  return useInfiniteQuery(infiniteApiOptions<T, M>(params));
}

/** Every loaded row, in order. */
export const flattenPages = <T, M extends PageMeta>(data: InfiniteData<Page<T[], M>> | undefined): T[] =>
  data?.pages.flatMap((page) => page.data) ?? [];
