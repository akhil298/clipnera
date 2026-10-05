'use client';

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { homeApi, type HomeProject, type PipelineRunStatus } from '@/lib/api/home';
import { homeKeys } from '@/lib/query/keys/home';

import { byNewest, isUnfinished, runStateOf, type ProjectRunState } from './projectState';

const LIVE_REFRESH_MS = 5_000;

export interface ProjectWithRun {
  project: HomeProject;
  run: ProjectRunState;
}

export const useHomeUser = () => useQuery({ queryKey: homeKeys.me(), queryFn: ({ signal }) => homeApi.me(signal), staleTime: 5 * 60_000 });

export const useHomeEntitlements = () =>
  useQuery({ queryKey: homeKeys.entitlements(), queryFn: ({ signal }) => homeApi.entitlements(signal), staleTime: 60_000 });

/**
 * Projects newest first, each with its live run state. The list paints from the
 * project rows; run detail for unfinished ones arrives in one batched request
 * and refreshes every few seconds while anything is running.
 */
export function useHomeProjects() {
  const projects = useQuery({
    queryKey: homeKeys.projects(),
    queryFn: ({ signal }) => homeApi.projects(signal),
    select: (data) => [...data.projects].sort(byNewest),
  });

  const unfinishedIds = useMemo(() => (projects.data ?? []).filter(isUnfinished).map((project) => project.id), [projects.data]);

  const runs = useQuery({
    queryKey: homeKeys.runStatuses(unfinishedIds),
    queryFn: ({ signal }) => homeApi.runStatuses(unfinishedIds, signal),
    enabled: unfinishedIds.length > 0,
    refetchInterval: (query) => {
      const statuses = query.state.data?.statuses ?? {};
      const live = (projects.data ?? []).some((project) => isUnfinished(project) && runStateOf(project, statuses[project.id]).kind === 'running');
      return live ? LIVE_REFRESH_MS : false;
    },
  });

  const items = useMemo<ProjectWithRun[] | undefined>(() => {
    const statuses: Record<string, PipelineRunStatus> = runs.data?.statuses ?? {};
    return projects.data?.map((project) => ({ project, run: runStateOf(project, statuses[project.id]) }));
  }, [projects.data, runs.data]);

  return { items, isPending: projects.isPending, isError: projects.isError, refetch: projects.refetch };
}
