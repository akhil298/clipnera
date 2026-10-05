import { apiFetch } from './client';

/**
 * The signed-in account as the app shell needs it: who, which plan, which workspaces.
 * Types mirror the Pydantic schemas named on each one; keep them in step.
 */

/** backend/user/schema.py UserProfileResponse (`GET /me`). */
export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatar_url: string | null;
  avatar_initials: string;
  /** The effective plan: "free" as soon as a paid period ends. */
  plan: string;
  /** When paid access ends, counting queued renewals; null on Free. */
  plan_expires_at: string | null;
  ai_credits_minutes_remaining: number;
  ai_credits_total: number;
  /** Capability name → allowed, as enforced by the API. */
  features: Record<string, boolean>;
  /** Per UTC day; null means unlimited. */
  daily_limits: Record<string, number | null>;
  usage_today: Record<string, number>;
  active_workspace_id: string | null;
  providers: string[];
  /** Display only: admin pages are guarded server-side. */
  role: 'user' | 'admin';
  email_notifications: boolean;
}

/** backend/workspace/schema.py WorkspaceResponse (`GET /workspaces`). */
export interface Workspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  role: string;
  member_count: number;
  created_at: string;
}

/** backend/auth/schema.py MessageResponse (`POST /auth/logout`). */
export interface MessageResponse {
  message: string;
}

/** backend/clip/model.py ProjectStatus. */
export type ProjectStatus = 'pending' | 'processing' | 'uploaded' | 'completed' | 'failed';

/** The fields the shell reads from one project of `GET /clips/projects` (backend/clip/service.py list_projects_with_clips). */
export interface RecentProject {
  id: string;
  title: string;
  status: ProjectStatus;
  duration_seconds: number;
  created_at: string | null;
  clips: ReadonlyArray<{ id: string; poster_url: string | null }>;
}

export const getMe = (signal?: AbortSignal) => apiFetch<UserProfile>('/me', { signal });

/** Never empty: the backend creates a personal workspace for anyone without one. */
export const listWorkspaces = (signal?: AbortSignal) => apiFetch<Workspace[]>('/workspaces', { signal });

/**
 * Every project, newest first: the sidebar shows four, ⌘K searches them all. The route has no
 * response schema and returns every clip too.
 * NEEDS-BACKEND: GET /projects?sort=recent&limit= with a Pydantic response schema (move to lib/api/projects once Area 3 adds it).
 */
export async function listRecentProjects(signal?: AbortSignal): Promise<RecentProject[]> {
  const { projects } = await apiFetch<{ projects: RecentProject[]; total: number }>('/clips/projects', { signal });
  return [...projects].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
}

/** Ends the server session. `optional` so an already-expired token doesn't bounce through /login first. */
export const logout = () => apiFetch<MessageResponse>('/auth/logout', { method: 'POST', auth: 'optional' });
