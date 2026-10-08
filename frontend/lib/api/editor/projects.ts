import { apiFetch } from '@/lib/api/client';
import { normalise, type TimelineOp } from '@/lib/editor/timeline';

import type {
  EditorOpsResponse,
  EditorProject,
  EditorProjectCreate,
  EditorProjectSummary,
  EditorTranscript,
} from './types';

/**
 * Editor projects and their operations: backend/editor/route.py. The Timeline is normalised on
 * the way in, because the server leaves defaults out (lib/editor/timeline.ts `normalise`).
 */

const path = (projectId: string) => `/editor/projects/${encodeURIComponent(projectId)}`;

const withTimeline = <T extends { timeline: unknown }>(value: T): T => ({ ...value, timeline: normalise(value.timeline) });

export const listEditorProjects = (signal?: AbortSignal) =>
  apiFetch<EditorProjectSummary[]>('/editor/projects', { signal });

export const createEditorProject = async (body: EditorProjectCreate, idempotencyKey?: string) =>
  withTimeline(await apiFetch<EditorProject>('/editor/projects', { method: 'POST', body, idempotencyKey }));

/** Opens a footage reel's current edit as a new project (409 NOT_READY when the reel has no edit yet). */
export const openReelInEditor = async (editId: string, idempotencyKey?: string) =>
  withTimeline(
    await apiFetch<EditorProject>(`/editor/projects/from-reel/${encodeURIComponent(editId)}`, {
      method: 'POST',
      body: {},
      idempotencyKey,
    }),
  );

export const getEditorProject = async (projectId: string, signal?: AbortSignal) =>
  withTimeline(await apiFetch<EditorProject>(path(projectId), { signal }));

/** One batch made against `baseVersion`; 409 STALE_VERSION (`isStale`) when the project moved on. */
export const applyEditorOps = async (projectId: string, baseVersion: number, ops: TimelineOp[]) =>
  withTimeline(
    await apiFetch<EditorOpsResponse>(`${path(projectId)}/ops`, { method: 'POST', body: { base_version: baseVersion, ops } }),
  );

/** NEEDS-BACKEND: EB-2 `GET /editor/projects/{id}/ops?since=` — the ops after a version, for rebase and resync. */
export const getEditorOpsSince = (projectId: string, since: number, signal?: AbortSignal) =>
  apiFetch<{ version: number; batches: { version: number; ops: TimelineOp[] }[] }>(`${path(projectId)}/ops`, {
    query: { since },
    signal,
  });

/** NEEDS-BACKEND: EB-17 `PATCH /editor/projects/{id} {title}`. */
export const renameEditorProject = (projectId: string, title: string) =>
  apiFetch<EditorProjectSummary>(path(projectId), { method: 'PATCH', body: { title } });

/** NEEDS-BACKEND: EB-18 `GET /editor/projects/{id}/transcript`. */
export const getEditorTranscript = (projectId: string, signal?: AbortSignal) =>
  apiFetch<EditorTranscript>(`${path(projectId)}/transcript`, { signal });
