'use client';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api/client';

/**
 * The two `/social` calls the welcome needs. Types mirror backend/social/schema.py.
 * Lives here until a shared `lib/api/social.ts` exists (requested from Platform / Area 8).
 */

/** backend/social/schema.py `Platform`. */
export type SocialPlatform = 'youtube' | 'tiktok' | 'instagram' | 'x';

/** backend/social/schema.py `PlatformInfo`. */
export interface PlatformInfo {
  platform: SocialPlatform;
  label: string;
  available: boolean;
  allowed_by_plan: boolean;
  caption_max_chars: number;
  max_duration_seconds: number;
  pending_review_note: string | null;
}

/** backend/social/schema.py `ConnectedAccountResponse`. */
export interface ConnectedAccount {
  id: string;
  platform: SocialPlatform;
  handle: string | null;
  display_name: string | null;
  avatar_url: string | null;
  follower_count: number | null;
  follower_count_updated_at: string | null;
  status: 'active' | 'needs_reconnect' | 'disconnecting' | 'disconnected';
  status_reason: string | null;
  connected_at: string;
  expires_at: string | null;
}

/** backend/social/schema.py `ConnectionsResponse` (`GET /social/connections`). */
export interface ConnectionsResponse {
  platforms: PlatformInfo[];
  accounts: ConnectedAccount[];
  max_accounts: number;
  can_schedule: boolean;
  max_schedule_days: number;
  posts_per_day: number;
}

/** backend/social/schema.py `ConnectStartResponse` (`POST /social/oauth/{platform}/start`). */
export interface ConnectStartResponse {
  authorize_url: string;
}

export const socialKeys = {
  all: ['social'] as const,
  connections: () => [...socialKeys.all, 'connections'] as const,
};

export const getConnections = (signal?: AbortSignal) => apiFetch<ConnectionsResponse>('/social/connections', { signal });

export const startConnect = (platform: SocialPlatform) =>
  apiFetch<ConnectStartResponse>(`/social/oauth/${platform}/start`, { method: 'POST' });

export function useConnections() {
  return useQuery({ queryKey: socialKeys.connections(), queryFn: ({ signal }) => getConnections(signal), staleTime: 60_000 });
}
