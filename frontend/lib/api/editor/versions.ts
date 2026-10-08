import { apiFetch } from '@/lib/api/client';
import { normalise } from '@/lib/editor/timeline';

import type { RevisionResult, Version, VersionCompare, VersionSummary } from './types';

/**
 * Versions, restore, undo and compare (openapi tag `versions`).
 * NEEDS-BACKEND: EB-10 (list, get, patch, restore, checkpoint, undo) and EB-11 (compare).
 */

const versions = (projectId: string) => `/editor/projects/${encodeURIComponent(projectId)}/versions`;

/** NEEDS-BACKEND: EB-10. Newest first. */
export const listVersions = (projectId: string, params: { bookmarked?: boolean; limit?: number; cursor?: string } = {}, signal?: AbortSignal) =>
  apiFetch<VersionSummary[]>(versions(projectId), { query: params, signal });

/** NEEDS-BACKEND: EB-10. Loads a read-only preview document. */
export const getVersion = async (projectId: string, versionId: string, signal?: AbortSignal) => {
  const version = await apiFetch<Version>(`${versions(projectId)}/${encodeURIComponent(versionId)}`, { signal });
  return { ...version, timeline: normalise(version.timeline) };
};

/** NEEDS-BACKEND: EB-10. */
export const updateVersion = (projectId: string, versionId: string, body: { name?: string; bookmarked?: boolean }) =>
  apiFetch<VersionSummary>(`${versions(projectId)}/${encodeURIComponent(versionId)}`, { method: 'PATCH', body });

const revision = (result: RevisionResult): RevisionResult => ({ ...result, timeline: normalise(result.timeline) });

/** NEEDS-BACKEND: EB-10. Makes it the newest version; nothing is deleted. */
export const restoreVersion = async (projectId: string, versionId: string, idempotencyKey?: string) =>
  revision(await apiFetch<RevisionResult>(`${versions(projectId)}/${encodeURIComponent(versionId)}/restore`, { method: 'POST', idempotencyKey }));

/** NEEDS-BACKEND: EB-10. Groups pending hand edits into one version; `null` when there are none. */
export const checkpointVersion = (projectId: string) =>
  apiFetch<VersionSummary | null>(`${versions(projectId)}/checkpoint`, { method: 'POST' });

/** NEEDS-BACKEND: EB-10 `POST …/undo`. 409 UNDO_WOULD_DISCARD until resent with `force: true`. */
export const undoVersion = async (projectId: string, body: { version_id?: string; force?: boolean }, idempotencyKey?: string) =>
  revision(
    await apiFetch<RevisionResult>(`/editor/projects/${encodeURIComponent(projectId)}/undo`, { method: 'POST', body, idempotencyKey }),
  );

/** NEEDS-BACKEND: EB-11. `from` may be `base:<version_id>` for the state before that version. */
export const compareVersions = async (projectId: string, from: string, to: string, signal?: AbortSignal) => {
  const result = await apiFetch<VersionCompare>(`${versions(projectId)}/compare`, { query: { from, to }, signal });
  return {
    ...result,
    from: { ...result.from, timeline: normalise(result.from.timeline) },
    to: { ...result.to, timeline: normalise(result.to.timeline) },
  };
};
