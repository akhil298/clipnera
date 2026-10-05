import { apiFetch } from './client';
import type { PipelineStatus } from './jobs';

/**
 * Live run state for the header activity indicator (screens/01 §5.4).
 *
 * NEEDS-BACKEND: GET /jobs?status=active (docs/revamp/architecture/openapi.yaml `listJobs`)
 * would give every server job (pipeline, reel, export, render) in one call. Until it
 * exists the indicator covers clip runs only: the shell's project list says which
 * projects are working and this asks for their run state in one round trip.
 */

/** POST /pipeline/status/batch: `PipelineRunService.status_batch` (backend/pipeline/service.py); no Pydantic schema yet. */
export interface RunStatusBatch {
  statuses: Record<string, PipelineStatus>;
}

/** Run state for up to 200 projects; ids the caller doesn't own are left out of the answer. */
export const getRunStatuses = (projectIds: readonly string[], signal?: AbortSignal) =>
  apiFetch<RunStatusBatch>('/pipeline/status/batch', { method: 'POST', body: { project_ids: projectIds }, signal });
