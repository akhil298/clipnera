import { apiFetch } from '@/lib/api/client';

import type { ActivityItem, Run, RunCreate, RunEstimate, RunEvent, RunMode, WireChip } from './types';

/**
 * Runs: one prompt, its plan, steps and result (docs/revamp/architecture/openapi.yaml, tag `runs`).
 * NEEDS-BACKEND: EB-3 for every call here unless marked otherwise. Until the routes exist these
 * calls fail with a 404 ApiError; lib/editor/dev/simulator.ts drives the run store meanwhile.
 * List calls return only `data`: the page cursor (`meta.next_cursor`) needs a paged apiFetch (Platform request).
 */

const projectRuns = (projectId: string) => `/editor/projects/${encodeURIComponent(projectId)}/runs`;
const run = (runId: string) => `/runs/${encodeURIComponent(runId)}`;

/** NEEDS-BACKEND: EB-3. 202 with the Run (active or queued). Make the key once, when Send is pressed. */
export const createRun = (projectId: string, body: RunCreate, idempotencyKey: string) =>
  apiFetch<Run>(projectRuns(projectId), { method: 'POST', body, idempotencyKey });

/** NEEDS-BACKEND: EB-3. Newest first. */
export const listRuns = (
  projectId: string,
  params: { limit?: number; cursor?: string; status?: 'active' | 'queued' | 'terminal' } = {},
  signal?: AbortSignal,
) => apiFetch<Run[]>(projectRuns(projectId), { query: params, signal });

/** NEEDS-BACKEND: EB-4. Heuristic, free, no AI call. */
export const estimateRun = (projectId: string, body: { prompt: string; mode: RunMode; chips?: WireChip[] }, signal?: AbortSignal) =>
  apiFetch<RunEstimate>(`${projectRuns(projectId)}/estimate`, { method: 'POST', body, signal });

/** NEEDS-BACKEND: EB-3. */
export const getRun = (runId: string, signal?: AbortSignal) => apiFetch<Run>(run(runId), { signal });

/** NEEDS-BACKEND: EB-3. Durable events after `afterSeq`, for gap backfill. */
export const listRunEvents = (runId: string, afterSeq: number, signal?: AbortSignal) =>
  apiFetch<RunEvent[]>(`${run(runId)}/events`, { query: { after_seq: afterSeq }, signal });

/** NEEDS-BACKEND: EB-3. Stops at the next safe point; idempotent. */
export const stopRun = (runId: string) => apiFetch<Run>(`${run(runId)}/stop`, { method: 'POST' });

/** NEEDS-BACKEND: EB-3. */
export const answerRun = (runId: string, body: { question_id: string; choice_id?: string; text?: string; skip?: boolean }) =>
  apiFetch<Run>(`${run(runId)}/answer`, { method: 'POST', body });

/** NEEDS-BACKEND: EB-3. "Add credits" continues after the top-up with `continue`. */
export const continueRun = (runId: string, decision: 'continue' | 'finish') =>
  apiFetch<Run>(`${run(runId)}/continue`, { method: 'POST', body: { decision } });

/** NEEDS-BACKEND: EB-3. Creates a new run for the remaining work. */
export const retryRun = (runId: string, body: { step_id?: string; prompt?: string }, idempotencyKey: string) =>
  apiFetch<Run>(`${run(runId)}/retry`, { method: 'POST', body, idempotencyKey });

/** NEEDS-BACKEND: EB-3. Edit or reorder a queued prompt. */
export const updateQueuedRun = (runId: string, body: { prompt?: string; chips?: WireChip[]; queue_position?: number }) =>
  apiFetch<Run>(run(runId), { method: 'PATCH', body });

/** NEEDS-BACKEND: EB-3. 409 RUN_NOT_QUEUED once it started (use stopRun). */
export const removeQueuedRun = (runId: string) => apiFetch<null>(run(runId), { method: 'DELETE' });

/** NEEDS-BACKEND: EB-6. Older turns, merged with jobs and versions, newest first. */
export const getProjectActivity = (projectId: string, params: { limit?: number; cursor?: string } = {}, signal?: AbortSignal) =>
  apiFetch<ActivityItem[]>(`/editor/projects/${encodeURIComponent(projectId)}/activity`, { query: params, signal });
