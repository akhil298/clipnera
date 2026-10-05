'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { runPercent, stepWords } from '@/components/projects/detail/run';
import { isRunning, useRecentProjects } from '@/components/shell/useAccount';
import type { RecentProject } from '@/lib/api/account';
import { CANCELLED_ERROR, type PipelineStatus } from '@/lib/api/jobs';
import { getRunStatuses } from '@/lib/api/jobs-activity';
import { accountKeys } from '@/lib/query/keys/account';
import { activityKeys } from '@/lib/query/keys/activity';
import { creditKeys } from '@/lib/query/keys/credits';
import { notificationKeys } from '@/lib/query/keys/notifications';

/** Fast enough that the step line feels live; only while something runs and the tab is visible. */
const LIVE_POLL_MS = 5_000;

export interface ActivityJob {
  projectId: string;
  title: string;
  /** The live step in plain words: "Transcribing the speech". */
  step: string;
  /** 0–100 across the whole run, when the server has said how far it is. */
  percent: number | null;
  failed: boolean;
}

/** One working project's row, or null once it is no longer working (done, stopped, never started). */
function jobOf(project: RecentProject, run: PipelineStatus | undefined): ActivityJob | null {
  const base = { projectId: project.id, title: project.title, percent: null, failed: false };
  if (project.status === 'pending') return { ...base, step: stepWords('download') };
  if (!run || run.status === 'not_started') return project.status === 'processing' ? { ...base, step: 'Starting' } : null;
  if (run.status === 'error') return run.error === CANCELLED_ERROR ? null : { ...base, step: 'Stopped with an error', failed: true };
  if (run.status === 'completed' || run.is_completed) return null;
  const current = run.steps.find((log) => log.status === 'running')?.step ?? run.current_step;
  return { ...base, step: current ? stepWords(current) : 'Starting', percent: runPercent(run.steps) };
}

/**
 * Server work across projects for the header (screens/01 §5.4). Live rows come
 * from the shell's project list plus one batched run-state call; a run that
 * fails while this tab is open keeps a rose row until the popover is opened.
 * When a run ends, the inbox, balance and project list are refreshed.
 */
export function useActivity() {
  const queryClient = useQueryClient();
  const projects = useRecentProjects();
  const working = useMemo(() => (projects.data ?? []).filter((project) => isRunning(project.status)), [projects.data]);
  const ids = useMemo(() => working.map((project) => project.id), [working]);

  const runs = useQuery({
    queryKey: activityKeys.active(ids),
    queryFn: ({ signal }) => getRunStatuses(ids, signal),
    enabled: ids.length > 0,
    staleTime: LIVE_POLL_MS,
    // Uploaded-but-idle and failed projects still count as "running" rows, so poll only while one is really live.
    refetchInterval: (query) =>
      working.some((project) => {
        const job = jobOf(project, query.state.data?.statuses[project.id]);
        return job !== null && !job.failed;
      })
        ? LIVE_POLL_MS
        : false,
  });

  const jobs = useMemo(
    () => working.map((project) => jobOf(project, runs.data?.statuses[project.id])).filter((job): job is ActivityJob => job !== null),
    [working, runs.data],
  );
  const live = useMemo(() => jobs.filter((job) => !job.failed), [jobs]);

  const [failed, setFailed] = useState<ActivityJob[]>([]);
  const previous = useRef<Map<string, ActivityJob>>(new Map());

  // A job that leaves the live set has ended: remember failures, refresh what its end changed.
  useEffect(() => {
    const now = new Map(live.map((job) => [job.projectId, job]));
    const ended = [...previous.current.values()].filter((job) => !now.has(job.projectId));
    previous.current = now;
    if (ended.length === 0) return;
    const failedNow = jobs.filter((job) => job.failed);
    const rows = projects.data ?? [];
    const newlyFailed = ended
      .filter((job) => failedNow.some((row) => row.projectId === job.projectId) || rows.find((row) => row.id === job.projectId)?.status === 'failed')
      .map((job) => ({ ...job, step: 'Stopped with an error', percent: null, failed: true }));
    if (newlyFailed.length) setFailed((list) => [...list.filter((job) => !newlyFailed.some((row) => row.projectId === job.projectId)), ...newlyFailed]);
    for (const key of [accountKeys.recentProjects(), accountKeys.me(), notificationKeys.inbox(), creditKeys.entitlements()]) {
      void queryClient.invalidateQueries({ queryKey: key });
    }
  }, [live, jobs, projects.data, queryClient]);

  const acknowledgeFailures = useCallback(() => setFailed([]), []);

  return { live, failed, acknowledgeFailures };
}
