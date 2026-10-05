'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';

import { listProjectClips } from '@/lib/api/clips';
import { cancelPipeline, getDownloadProgress, getPipelineStatus, getProjectCredits, resumePipeline, startPipeline } from '@/lib/api/jobs';
import { getProject } from '@/lib/api/projects';
import { clipKeys } from '@/lib/query/keys/clips';
import { jobKeys } from '@/lib/query/keys/jobs';
import { projectKeys } from '@/lib/query/keys/projects';

import { isLive, phaseOf, STAGES } from './run';

const STATUS_POLL_MS = 3_000;
const DOWNLOAD_POLL_MS = 1_500;
const PROJECT_POLL_MS = 5_000;
const CLIPS_POLL_MS = 6_000;
/** No answer for this long while live: show "Reconnecting". */
const STALE_AFTER_MS = 12_000;

const CLIP_STEPS: readonly string[] = STAGES.find((stage) => stage.id === 'clips')!.steps;

/**
 * Everything the project page reads and does, polled only while work is live.
 * Clips are fetched once the run starts making them, so they stream in before it ends.
 */
export function useProjectRun(projectId: string) {
  const queryClient = useQueryClient();

  const project = useQuery({
    queryKey: projectKeys.detail(projectId),
    queryFn: ({ signal }) => getProject(projectId, signal),
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? PROJECT_POLL_MS : false),
  });

  const status = useQuery({
    queryKey: jobKeys.status(projectId),
    queryFn: ({ signal }) => getPipelineStatus(projectId, signal),
    enabled: project.isSuccess,
    staleTime: 0,
    refetchInterval: (query) => {
      if (!project.data) return false;
      return isLive(phaseOf(project.data, query.state.data)) ? STATUS_POLL_MS : false;
    },
  });

  const phase = project.data ? phaseOf(project.data, status.data) : undefined;
  const live = phase !== undefined && isLive(phase);
  const steps = status.data?.steps ?? [];
  const makingClips = steps.some((log) => CLIP_STEPS.includes(log.step) && log.status !== 'pending');

  const download = useQuery({
    queryKey: jobKeys.download(projectId),
    queryFn: ({ signal }) => getDownloadProgress(projectId, signal),
    enabled: phase === 'importing',
    refetchInterval: phase === 'importing' ? DOWNLOAD_POLL_MS : false,
  });

  const clips = useQuery({
    queryKey: clipKeys.list(projectId),
    queryFn: ({ signal }) => listProjectClips(projectId, signal),
    enabled: phase === 'done' || ((phase === 'running' || phase === 'failed' || phase === 'stopped') && makingClips),
    refetchInterval: phase === 'running' ? CLIPS_POLL_MS : false,
  });

  const credits = useQuery({
    queryKey: jobKeys.credits(projectId),
    queryFn: ({ signal }) => getProjectCredits(projectId, signal),
    enabled: project.isSuccess,
  });

  // When a live run settles, pull the final clips, the project row and the credits once.
  const previous = useRef(phase);
  useEffect(() => {
    const was = previous.current;
    previous.current = phase;
    if (was === undefined || was === phase) return;
    if (was === 'importing') void queryClient.invalidateQueries({ queryKey: jobKeys.status(projectId) });
    if (isLive(was) && !live) {
      void queryClient.invalidateQueries({ queryKey: clipKeys.list(projectId) });
      void queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
      void queryClient.invalidateQueries({ queryKey: projectKeys.recent() });
      void queryClient.invalidateQueries({ queryKey: jobKeys.credits(projectId) });
    }
  }, [phase, live, projectId, queryClient]);

  const refreshRun = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: jobKeys.status(projectId) }),
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) }),
      queryClient.invalidateQueries({ queryKey: jobKeys.credits(projectId) }),
    ]);

  const cancel = useMutation({ mutationFn: () => cancelPipeline(projectId), onSettled: refreshRun });

  // One key per attempt, made when the action is triggered.
  const retry = useMutation({
    mutationFn: (key: string) => resumePipeline(projectId, steps.map((log) => log.step), key),
    onSuccess: refreshRun,
  });
  const start = useMutation({ mutationFn: (key: string) => startPipeline(projectId, key), onSuccess: refreshRun });

  return {
    project,
    status,
    download,
    clips,
    credits,
    phase,
    steps,
    reconnecting: useReconnecting(live, status.dataUpdatedAt, status.isError),
    cancel,
    retry: () => retry.mutate(crypto.randomUUID()),
    retrying: retry.isPending,
    retryError: retry.error,
    start: () => start.mutate(crypto.randomUUID()),
    starting: start.isPending,
    startError: start.error,
  };
}

/** True while live and the last good status answer is older than STALE_AFTER_MS. */
function useReconnecting(live: boolean, updatedAt: number, failing: boolean): boolean {
  const now = useNow(live);
  return live && updatedAt > 0 && (failing || now - updatedAt > STALE_AFTER_MS);
}

/** Seconds-precision clock for the elapsed counter, ticking only while `running`. */
export function useNow(running: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(timer);
  }, [running]);
  return now;
}
