'use client';

import { useQuery } from '@tanstack/react-query';

import { getMe, listRecentProjects, listWorkspaces, type ProjectStatus } from '@/lib/api/account';
import { accountKeys } from '@/lib/query/keys/account';

const MINUTE = 60_000;

/** `GET /me`: cache times from frontend.md §3.4. */
export function useMe() {
  return useQuery({ queryKey: accountKeys.me(), queryFn: ({ signal }) => getMe(signal), staleTime: 5 * MINUTE, gcTime: 30 * MINUTE });
}

export function useWorkspaces() {
  return useQuery({ queryKey: accountKeys.workspaces(), queryFn: ({ signal }) => listWorkspaces(signal), staleTime: 5 * MINUTE, gcTime: 30 * MINUTE });
}

export const isRunning = (status: ProjectStatus) => status === 'pending' || status === 'processing' || status === 'uploaded';

/** Polls every 20 s only while something runs and the tab is visible: the fallback until the event stream lands. */
export function useRecentProjects() {
  return useQuery({
    queryKey: accountKeys.recentProjects(),
    queryFn: ({ signal }) => listRecentProjects(signal),
    staleTime: 30_000,
    refetchInterval: (query) => (query.state.data?.some((project) => isRunning(project.status)) ? 20_000 : false),
  });
}

/** "pro" → "Pro". */
export const planName = (plan: string) => plan.charAt(0).toUpperCase() + plan.slice(1);
