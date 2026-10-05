/**
 * Typed wrappers for projects (one project per long video) and their folders.
 *
 * Types mirror the backend exactly:
 * - `ProjectSummary` / `ProjectClipSummary`: `ClipService.list_projects_with_clips` (backend/clip/service.py)
 * - `ProjectRowStatus`: `ProjectStatus` (backend/clip/model.py)
 * - `PipelineRunStatus`: `_status_payload` / `_not_started` (backend/pipeline/service.py)
 * - `ExportResponse`: `SocialExportResponse` (backend/clip_generation/schema.py)
 *
 * Routes that do not exist yet are marked `NEEDS-BACKEND`; they call the
 * endpoint the design asks for (screens/01 §13 API-6, API-7), so they start
 * working the day the backend ships it and fail with a normal `ApiError` until then.
 */
import type { HookTransitionApplied } from '@/lib/types';

import { apiFetch } from './client';
import { ApiError } from './errors';

/** backend/clip/model.py `ProjectStatus`. */
export type ProjectRowStatus = 'pending' | 'processing' | 'uploaded' | 'completed' | 'failed';

/** `source_type` written by `/clips/youtube`, `/clips/download` ("youtube") and `/uploads` ("upload"). */
export type ProjectSource = 'youtube' | 'upload';

export interface ProjectClipSummary {
  id: string;
  title: string;
  score: number;
  duration_seconds: number;
  start_time: number;
  end_time: number;
  content_category: string | null;
  status: string;
  poster_url: string | null;
  created_at: string | null;
}

export interface ProjectSummary {
  id: string;
  title: string;
  source_type: ProjectSource | (string & {});
  source_url: string | null;
  status: ProjectRowStatus;
  /** 0 until the source is measured. */
  duration_seconds: number;
  created_at: string | null;
  clips: ProjectClipSummary[];
}

export interface ProjectListResponse {
  projects: ProjectSummary[];
  total: number;
}

export interface PipelineStepState {
  step: string;
  status: string;
  progress_percent: number | null;
  message: string | null;
  artifact_path: string | null;
  started_at: string | null;
  finished_at: string | null;
}

/** One project's latest run. A project that never ran has only `project_id`, `status` and `steps`. */
export type PipelineRunStatus =
  | { project_id: string; status: 'not_started'; steps: [] }
  | {
      project_id: string;
      status: 'pending' | 'running' | 'completed' | 'error';
      current_step: string | null;
      is_completed: boolean;
      error: string | null;
      steps: PipelineStepState[];
    };

export interface ProjectStatusesResponse {
  statuses: Record<string, PipelineRunStatus>;
}

export interface ExportedClip {
  clip_id: string;
  platform: string;
  aspect_ratio: string;
  burned_presigned_url: string | null;
  local_path: string | null;
  s3_key: string | null;
  hook_transition: HookTransitionApplied | null;
}

export interface ExportResponse {
  project_id: string;
  exported_clips: ExportedClip[];
  platforms: string[];
  total_exported: number;
  watermark_enabled: boolean;
  channel_intro: boolean;
  bundle_presigned_url: string | null;
}

/** API-7 folder shape: name only, no colour or category. */
export interface ProjectFolder {
  id: string;
  name: string;
  project_count: number;
  created_at: string;
}

const PROJECTS = '/clips/projects';

/** Every project of the signed-in user, with clip summaries. */
export function listProjects(signal?: AbortSignal): Promise<ProjectListResponse> {
  return apiFetch<ProjectListResponse>(PROJECTS, { signal });
}

/**
 * Every project, newest first: the sidebar's Recent list, ⌘K and the header's activity.
 * NEEDS-BACKEND: GET /projects?sort=recent&limit= with a Pydantic response schema; today the route returns every clip too.
 */
export async function listRecentProjects(signal?: AbortSignal): Promise<ProjectSummary[]> {
  const { projects } = await listProjects(signal);
  return [...projects].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
}

/**
 * One project with its clip summaries. A missing project throws a 404 `ApiError`.
 * NEEDS-BACKEND: GET /clips/projects/{project_id} (API-9) — until then this reads the list and picks the row.
 */
export async function getProject(projectId: string, signal?: AbortSignal): Promise<ProjectSummary> {
  const { projects } = await listProjects(signal);
  const project = projects.find((item) => item.id === projectId);
  if (!project) {
    throw new ApiError({ status: 404, code: 'NOT_FOUND', message: 'Project not found', requestId: crypto.randomUUID() });
  }
  return project;
}

/** NEEDS-BACKEND: PATCH /clips/projects/{project_id} {title} (API-6). Legacy rename never reached the server. */
export function renameProject(projectId: string, title: string): Promise<ProjectSummary> {
  return apiFetch<ProjectSummary>(`${PROJECTS}/${projectId}`, { method: 'PATCH', body: { title } });
}

/** Deletes the project, its clips and its source file for good (204). */
export async function deleteProject(projectId: string): Promise<void> {
  await apiFetch<null>(`${PROJECTS}/${projectId}`, { method: 'DELETE' });
}

/** Latest run state for up to 200 projects in one request. */
export function getProjectStatuses(projectIds: readonly string[], signal?: AbortSignal): Promise<ProjectStatusesResponse> {
  return apiFetch<ProjectStatusesResponse>('/pipeline/status/batch', {
    method: 'POST',
    body: { project_ids: projectIds },
    signal,
  });
}

/** Stops the running pipeline at its next safe point. 409 `PIPELINE_NOT_RUNNING` when nothing is running. */
export function stopProject(projectId: string): Promise<{ project_id: string; status: 'cancelled' }> {
  return apiFetch(`/pipeline/cancel/${projectId}`, { method: 'POST' });
}

/**
 * Renders the given clips with their saved captions and packs them into one ZIP.
 * Same request the legacy "Download all" sends (lib/utils/clipExport.ts), minus per-clip
 * caption overrides, which the list rows do not carry.
 */
export function exportProjectBundle(projectId: string, clipIds: readonly string[]): Promise<ExportResponse> {
  return apiFetch<ExportResponse>(`/pipeline/export/${projectId}`, {
    method: 'POST',
    body: { platforms: ['tiktok'], clip_ids: clipIds, max_clips: clipIds.length, bundle: true },
    timeoutMs: 300_000,
  });
}

/** NEEDS-BACKEND: GET /folders (API-7). Folders are local-only in the legacy UI today. */
export function listFolders(signal?: AbortSignal): Promise<ProjectFolder[]> {
  return apiFetch<ProjectFolder[]>('/folders', { signal });
}

/** NEEDS-BACKEND: POST /folders {name} (API-7). */
export function createFolder(name: string): Promise<ProjectFolder> {
  return apiFetch<ProjectFolder>('/folders', { method: 'POST', body: { name } });
}

/** NEEDS-BACKEND: PATCH /folders/{folder_id} {name} (API-7). */
export function renameFolder(folderId: string, name: string): Promise<ProjectFolder> {
  return apiFetch<ProjectFolder>(`/folders/${folderId}`, { method: 'PATCH', body: { name } });
}

/** NEEDS-BACKEND: DELETE /folders/{folder_id} (API-7); its projects move to no folder. */
export async function deleteFolder(folderId: string): Promise<void> {
  await apiFetch<null>(`/folders/${folderId}`, { method: 'DELETE' });
}

/** NEEDS-BACKEND: POST /projects/move {project_ids, folder_id} (API-6). `null` = no folder. */
export async function moveProjects(projectIds: readonly string[], folderId: string | null): Promise<void> {
  await apiFetch<null>('/projects/move', { method: 'POST', body: { project_ids: projectIds, folder_id: folderId } });
}
