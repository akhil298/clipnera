/**
 * The user event stream's envelope (docs/revamp/architecture/events.md §1.1). Domain payloads are
 * typed by their owners (e.g. `RunEvent` in lib/api/editor/types.ts); clients ignore unknown types
 * and fields (events.md §8).
 *
 * NEEDS-BACKEND: `GET /events/stream` and `GET /events/poll` (openapi.yaml, events.md §7.3) and
 * `backend/realtime/events.py`, from which these types are meant to be generated.
 */
export interface RealtimeEvent<D = unknown> {
  type: string;
  v: number;
  /** "run:<id>" | "job:<id>" | "project:<id>" | "user:<id>"; subscribers match on this. */
  stream: string;
  /** Gapless per stream for durable events; the last durable seq for ephemeral ones. */
  seq: number;
  /** Ephemeral only: order since that durable seq. */
  sub?: number;
  durable: boolean;
  ts: string;
  workspace_id?: string;
  project_id?: string;
  run_id?: string;
  job_id?: string;
  data: D;
}

export type RealtimeHandler = (event: RealtimeEvent) => void;

/**
 * - `idle`: nobody is listening, or there's no session.
 * - `connecting` / `open`: the SSE stream.
 * - `polling`: SSE keeps failing, so events come from the long-poll fallback.
 * - `down`: neither transport works right now; queries fall back to `refetchInterval`.
 */
export type RealtimeStatus = 'idle' | 'connecting' | 'open' | 'polling' | 'down';

/** Statuses in which pushed events arrive, so per-query fallback polling can stay off. */
export const isLive = (status: RealtimeStatus): boolean => status === 'open' || status === 'polling';

/** Types that mean "snapshots may be stale, refetch them" (events.md §6 `sync.reset`; frontend.md §4.2 `resync`). */
export const RESYNC_TYPES: ReadonlySet<string> = new Set(['sync.reset', 'resync']);
