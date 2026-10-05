'use client';

import { useQuery } from '@tanstack/react-query';

import { homeApi } from '@/lib/api/home';
import { homeKeys } from '@/lib/query/keys/home';

/** Title, poster and duration of the attached link; the duration drives the credit hint. */
export function useYoutubeSource(url: string | null) {
  return useQuery({
    queryKey: homeKeys.youtube(url ?? ''),
    queryFn: ({ signal }) => homeApi.youtubeMetadata(url!, signal),
    enabled: url !== null,
    staleTime: 10 * 60_000,
    retry: false,
  });
}
