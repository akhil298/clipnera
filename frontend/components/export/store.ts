'use client';

import { create } from 'zustand';

import type { RenderStatus } from '@/components/ui';
import { isApiError, isNotFound, isRetryable } from '@/lib/api/errors';
import { cancelExportJob, createExportJob } from '@/lib/api/export/jobs';
import { exportVideoProject } from '@/lib/api/export/request';
import type { CreateExportRequest, ExportJobResponse, SocialExportRequest, SocialExportResponse } from '@/lib/api/export/types';
import { formatDuration } from '@/lib/utils/videoFile';

import { isWorking } from './source';

/** How the render is asked for: the blocking route today, a job once EB-24 exists. */
export type ExportRequestPlan = { kind: 'blocking'; projectId: string; body: SocialExportRequest } | { kind: 'job'; body: CreateExportRequest };

/** One export as the render card shows it. Lives for the session (survives the dialog and route changes). */
export interface ExportJob {
  id: string;
  projectId: string;
  title: string;
  meta: string;
  poster?: string;
  aspect: '9:16' | '1:1' | '16:9';
  /** The clip when exactly one is exported (Schedule needs it). */
  clipId?: string;
  bundle: boolean;
  status: RenderStatus;
  step?: string;
  percent?: number;
  eta?: string;
  queuePosition?: number;
  error?: string;
  retryable: boolean;
  url?: string;
  shareUrl?: string;
  facts: string[];
  /** Set once EB-24 answers with a job; the card polls it. */
  serverId?: string;
  plan: ExportRequestPlan;
}

export type NewExportJob = Pick<ExportJob, 'projectId' | 'title' | 'meta' | 'poster' | 'aspect' | 'clipId' | 'bundle' | 'plan'>;

interface ExportStore {
  jobs: ExportJob[];
  patch: (id: string, patch: Partial<ExportJob>) => void;
}

export const useExportStore = create<ExportStore>((set) => ({
  jobs: [],
  patch: (id, patch) =>
    set((state) => ({
      jobs: state.jobs.map((job) => (job.id === id ? { ...job, ...patch } : job)),
    })),
}));

/** Blocking requests in flight, so Cancel can abort them. */
const inflight = new Map<string, AbortController>();

const patch = (id: string, changes: Partial<ExportJob>) => useExportStore.getState().patch(id, changes);
const find = (id: string) => useExportStore.getState().jobs.find((job) => job.id === id);

function failure(err: unknown): Pick<ExportJob, 'status' | 'error' | 'retryable'> {
  if (isNotFound(err))
    return {
      status: 'failed',
      error: 'Exporting this isn’t available yet.',
      retryable: false,
    };
  return {
    status: 'failed',
    error: isApiError(err) ? err.message : 'The export didn’t finish.',
    retryable: !isApiError(err) || isRetryable(err),
  };
}

function blockingResult(job: ExportJob, result: SocialExportResponse): Partial<ExportJob> {
  const url = job.bundle
    ? result.bundle_presigned_url
    : (result.exported_clips.find((clip) => clip.clip_id === job.clipId) ?? result.exported_clips[0])?.burned_presigned_url;
  if (!url)
    return {
      status: 'failed',
      error: 'The render finished without a file to download.',
      retryable: true,
    };
  const facts = [result.watermark_enabled ? 'Watermark on' : 'No watermark'];
  if (result.channel_intro) facts.push('Channel intro first');
  return { status: 'done', url, facts };
}

/** Maps an EB-24 job onto the card. Only measured numbers are passed on. */
export function fromServerJob(job: ExportJobResponse): Partial<ExportJob> {
  const status: RenderStatus = job.status === 'running' ? 'rendering' : job.status === 'succeeded' ? 'done' : job.status;
  const eta = job.progress?.eta_seconds;
  return {
    status,
    step: job.step ?? undefined,
    percent: job.progress?.percent,
    eta: eta != null ? `about ${formatDuration(eta)} left` : undefined,
    queuePosition: job.queue_position ?? undefined,
    url: job.result?.url,
    shareUrl: job.result?.share_url ?? undefined,
    error: job.error?.message,
    retryable: job.error?.retryable ?? false,
  };
}

async function run(id: string): Promise<void> {
  const job = find(id);
  if (!job) return;
  const { plan } = job;
  if (plan.kind === 'job') {
    try {
      // NEEDS-BACKEND: EB-24
      const created = await createExportJob(plan.body, crypto.randomUUID());
      patch(id, { serverId: created.id, ...fromServerJob(created) });
    } catch (err) {
      patch(id, failure(err));
    }
    return;
  }
  // NEEDS-BACKEND: EB-24 — the route answers once every render is done, so there is no percentage
  // and the tab has to stay open; Cancel only stops waiting (the server finishes the render).
  const controller = new AbortController();
  inflight.set(id, controller);
  patch(id, { status: 'rendering' });
  try {
    const result = await exportVideoProject(plan.projectId, plan.body, controller.signal);
    if (!controller.signal.aborted) patch(id, blockingResult(job, result));
  } catch (err) {
    if (!controller.signal.aborted) patch(id, failure(err));
  } finally {
    inflight.delete(id);
  }
}

/** Adds a job and starts it; returns its id. */
export function startExport(input: NewExportJob): string {
  const id = crypto.randomUUID();
  const job: ExportJob = {
    ...input,
    id,
    status: 'queued',
    retryable: false,
    facts: [],
  };
  useExportStore.setState((state) => ({ jobs: [job, ...state.jobs] }));
  void run(id);
  return id;
}

export async function cancelExport(id: string): Promise<void> {
  const job = find(id);
  if (!job || !isWorking(job.status)) return;
  inflight.get(id)?.abort();
  if (job.serverId) {
    try {
      // NEEDS-BACKEND: EB-24
      patch(id, fromServerJob(await cancelExportJob(job.serverId)));
      return;
    } catch {
      // The job may have finished meanwhile; the next poll tells.
    }
  }
  patch(id, { status: 'cancelled' });
}

/** Runs the same request again in place (failed, cancelled or expired). */
export function retryExport(id: string): void {
  patch(id, {
    status: 'queued',
    error: undefined,
    retryable: false,
    serverId: undefined,
    percent: undefined,
    step: undefined,
    url: undefined,
    facts: [],
  });
  void run(id);
}
