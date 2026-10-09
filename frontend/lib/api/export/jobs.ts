import { apiFetch } from '../client';
import type { CreateExportRequest, ExportJobResponse } from './types';

/** NEEDS-BACKEND: EB-24 `POST /exports` → 202 Job (video_project and editor_project). Fails until it exists. */
export const createExportJob = (body: CreateExportRequest, idempotencyKey: string) =>
  apiFetch<ExportJobResponse>('/exports', {
    method: 'POST',
    body,
    idempotencyKey,
  });

/** NEEDS-BACKEND: EB-24 `GET /jobs/{id}`; polled until the events stream (EB-1, R-1) carries `job.*`. */
export const getExportJob = (jobId: string, signal?: AbortSignal) => apiFetch<ExportJobResponse>(`/jobs/${encodeURIComponent(jobId)}`, { signal });

/** NEEDS-BACKEND: EB-24 `POST /jobs/{id}/cancel`. */
export const cancelExportJob = (jobId: string) =>
  apiFetch<ExportJobResponse>(`/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  });
