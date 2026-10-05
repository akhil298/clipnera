'use client';

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useSyncExternalStore } from 'react';

import { isApiError } from '@/lib/api/errors';
import {
  deleteProject,
  exportProjectBundle,
  getProjectStatuses,
  listProjects,
  renameProject,
  stopProject,
  type ProjectListResponse,
} from '@/lib/api/projects';
import { projectKeys } from '@/lib/query/keys/projects';
import { downloadFile } from '@/lib/utils/clipExport';

import { isRunning, projectView, type ProjectView } from './projectState';

/** How often running projects are re-read until the events stream (frontend.md §5) replaces polling. */
const LIVE_POLL_MS = 5_000;

export function useProjectViews() {
  // Ids running at the last render. Read by refetchInterval after each fetch, so polling stops once nothing runs.
  const running = useRef<ReadonlySet<string>>(new Set());

  const list = useQuery({
    queryKey: projectKeys.list(),
    queryFn: ({ signal }) => listProjects(signal),
    placeholderData: keepPreviousData,
  });
  const projects = list.data?.projects;
  const ids = useMemo(() => projects?.map((p) => p.id) ?? [], [projects]);

  const statuses = useQuery({
    queryKey: projectKeys.statuses(ids),
    queryFn: ({ signal }) => getProjectStatuses(ids, signal),
    enabled: ids.length > 0,
    placeholderData: keepPreviousData,
    refetchInterval: () => (running.current.size > 0 ? LIVE_POLL_MS : false),
  });

  const views = useMemo<ProjectView[]>(
    () => (projects ?? []).map((p) => projectView(p, statuses.data?.statuses[p.id])),
    [projects, statuses.data],
  );

  const { refetch: refetchList } = list;
  useEffect(() => {
    const now = new Set(views.filter(isRunning).map((v) => v.project.id));
    const finished = [...running.current].some((id) => !now.has(id));
    running.current = now;
    // A run ended: its clips and posters are only in the list.
    if (finished) void refetchList();
  }, [views, refetchList]);

  return { list, views };
}

function patchList(
  client: ReturnType<typeof useQueryClient>,
  update: (data: ProjectListResponse) => ProjectListResponse,
): ProjectListResponse | undefined {
  const previous = client.getQueryData<ProjectListResponse>(projectKeys.list());
  if (previous) client.setQueryData(projectKeys.list(), update(previous));
  return previous;
}

export function useRenameProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameProject(id, title),
    onMutate: ({ id, title }) => ({
      previous: patchList(client, (d) => ({ ...d, projects: d.projects.map((p) => (p.id === id ? { ...p, title } : p)) })),
    }),
    onError: (_err, _vars, context) => {
      if (context?.previous) client.setQueryData(projectKeys.list(), context.previous);
    },
    onSettled: (_data, _err, { id }) => {
      void client.invalidateQueries({ queryKey: projectKeys.list() });
      void client.invalidateQueries({ queryKey: projectKeys.detail(id) });
    },
  });
}

/** Stops a running project first (nothing to stop is fine), then deletes it for good. */
export function useDeleteProjects() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (targets: readonly ProjectView[]) => {
      const results = await Promise.allSettled(
        targets.map(async (view) => {
          if (isRunning(view)) await stopProject(view.project.id).catch(() => undefined);
          await deleteProject(view.project.id);
          return view.project.id;
        }),
      );
      const deleted = results.flatMap((r) => (r.status === 'fulfilled' ? [r.value] : []));
      patchList(client, (d) => ({ projects: d.projects.filter((p) => !deleted.includes(p.id)), total: d.total - deleted.length }));
      deleted.forEach((id) => client.removeQueries({ queryKey: projectKeys.detail(id) }));
      return { deleted, failed: targets.length - deleted.length };
    },
    onSettled: () => client.invalidateQueries({ queryKey: projectKeys.list() }),
  });
}

/** 409 PIPELINE_NOT_RUNNING means it already stopped; either way the card refreshes. */
export function useStopProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      try {
        await stopProject(id);
      } catch (err) {
        if (!(isApiError(err) && err.code === 'PIPELINE_NOT_RUNNING')) throw err;
      }
    },
    onSettled: () => client.invalidateQueries({ queryKey: projectKeys.all }),
  });
}

/** Renders every clip of each project into one ZIP and saves it, one project at a time. */
export function useDownloadClips() {
  return useMutation({
    mutationFn: async (targets: readonly ProjectView[]) => {
      let failed = 0;
      for (const view of targets) {
        try {
          const result = await exportProjectBundle(view.project.id, view.project.clips.map((c) => c.id));
          if (!result.bundle_presigned_url) throw new Error('No bundle');
          downloadFile(result.bundle_presigned_url, `${view.project.title || 'clips'}.zip`);
        } catch {
          failed += 1;
        }
      }
      return { failed };
    },
  });
}

const subscribeOnline = (notify: () => void) => {
  window.addEventListener('online', notify);
  window.addEventListener('offline', notify);
  return () => {
    window.removeEventListener('online', notify);
    window.removeEventListener('offline', notify);
  };
};

/** `true` on the server and first render, so hydration matches. */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);
}
