/**
 * B-roll library types. Field for field with the provisional Pydantic models in
 * docs/revamp/05-broll.md §7.2–7.3 (`broll/schema.py`, not written yet). Today's routes
 * (`/broll/*`, backend/broll/schema.py) are not used by the library pages.
 *
 * NEEDS-BACKEND: L-API-1 / L-API-2 — none of these models exist in backend/broll/schema.py yet.
 * Fields marked "U9-B…" are additions this screen asks for on top of 05 §7.2.
 */

export type LibraryScope = 'platform' | 'mine';
export type Orientation = 'portrait' | 'landscape' | 'square';
export type Aspect = '9:16' | '1:1' | '4:5' | '16:9';
export type Mood = 'calm' | 'energetic' | 'dramatic' | 'hopeful' | 'dark' | 'playful' | 'professional';
export type ColorFamily = 'warm' | 'cool' | 'neutral' | 'mono' | 'vivid';
export type LibraryKind = 'stock' | 'upload' | 'generated';
export type Tier = 'free' | 'pro';
export type MatchKind = 'keyword' | 'meaning' | 'both';

/** List responses carry `meta` beside `data` (backend.md §11.1). `apiFetch` returns only `data` today. */
export interface ListMeta {
  next_cursor: string | null;
  has_more: boolean;
}

export interface LicenceInfo {
  /** Registry key: pexels | pd_us_gov | cc0 | public_domain | cc_by | ai_generated | owned | licensed. */
  code: string;
  name: string;
  url: string | null;
  author: string | null;
  author_url: string | null;
  attribution_text: string | null;
  attribution_required: boolean;
  commercial_ok: boolean;
}

/** Ready to send as the `asset` of an editor `add_asset` op (mirrors editor.timeline.Asset). */
export interface TimelineAssetRef {
  /** "b_<asset_id>" */
  id: string;
  kind: 'video';
  /** "broll:<asset_id>" */
  key: string;
  proxy: string | null;
  frames: number;
  width: number | null;
  height: number | null;
  has_audio: boolean;
}

/** One shot as a user sees it in a grid. */
export interface LibraryItem {
  id: string;
  scope: LibraryScope;
  kind: LibraryKind;
  title: string;
  /** Vision caption: alt text and the "why" line. */
  caption: string | null;
  duration_s: number;
  /** Into its source (0 for stock shots). */
  start_s: number;
  source_id: string;
  source_title: string | null;
  width: number;
  height: number;
  orientation: Orientation;
  mood: Mood | null;
  color_family: ColorFamily | null;
  tier: Tier;
  /** Tier above the caller's plan. */
  locked: boolean;
  favourite: boolean;
  thumb_url: string | null;
  proxy_url: string | null;
  sprite_url: string | null;
  /** Null for the caller's own uploads. */
  licence: LicenceInfo | null;
  /** Present when `aspect` / `fps` were given and the shot fits. */
  timeline_asset: TimelineAssetRef | null;
  /** Only on search results. */
  match: MatchKind | null;
}

/** NEEDS-BACKEND: U9-B1 — `sort` is not in 05 §7.2 `LibrarySearchQuery`; the page offers it (screens/03 §4). */
export type LibrarySort = 'relevance' | 'newest' | 'most_used';

/** GET /library/search query parameters. */
export interface LibrarySearchQuery {
  q?: string;
  scope?: 'all' | 'platform' | 'mine';
  kind?: LibraryKind[];
  orientation?: Orientation[];
  aspect?: Aspect;
  fps?: 24 | 25 | 30 | 60;
  min_duration?: number;
  max_duration?: number;
  min_short_side?: number;
  mood?: Mood[];
  color?: ColorFamily[];
  people?: boolean;
  category?: string;
  collection_id?: string;
  favourites?: boolean;
  attribution_free?: boolean;
  /** NEEDS-BACKEND: U9-B1. */
  sort?: LibrarySort;
  cursor?: string;
  /** 1–60, default 30. */
  limit?: number;
}

export interface CategoryOut {
  slug: string;
  name: string;
  parent: string | null;
  count: number;
}

export interface CollectionSummary {
  id: string;
  name: string;
  description: string;
  /** True = a Clipnera collection, read-only for users. */
  curated: boolean;
  count: number;
  cover_thumb_url: string | null;
  /** Filled only by browse (up to 12 preview items). */
  items: LibraryItem[];
}

export interface LibraryBrowse {
  featured: CollectionSummary[];
  categories: CategoryOut[];
  popular: LibraryItem[];
}

export interface CollectionCreate {
  name: string;
  description?: string;
  asset_ids?: string[];
  /** "Save a copy" of a curated collection. */
  copy_of?: string | null;
}

export interface CollectionUpdate {
  name?: string | null;
  description?: string | null;
  /** Asset ids in the new order. */
  order?: string[] | null;
}

export type ReportReason = 'wrong_tags' | 'low_quality' | 'offensive' | 'copyright' | 'other';

export interface ReportCreate {
  reason: ReportReason;
  /** Up to 500 characters. */
  note?: string;
}

export interface LibraryItemDetail extends LibraryItem {
  tags: string[];
  categories: CategoryOut[];
  fps: number;
  /** Up to 8 vector neighbours, same visibility rules. */
  similar: LibraryItem[];
  /**
   * NEEDS-BACKEND: U9-B2 — where the shot came from, so the drawer can show its source beside the
   * licence. Same values as BrollAssetResponse.source / .source_url (backend/broll/schema.py):
   * "nasa" | "wikimedia" | "pixabay" | "pexels" | "upload" | "generated".
   */
  source: string;
  source_url: string | null;
}

/** Resolves `broll:` keys for the editor preview; `renderable: false` drives the "Missing clip" placeholder. */
export interface MediaRef {
  ref: string;
  proxy_url: string | null;
  thumb_url: string | null;
  renderable: boolean;
  reason: 'taken_down' | 'deleted' | 'held' | 'blocked' | null;
}

// --- Your uploads (Area 7 wrappers in sources.ts / usage.ts use these) ---

export interface LibraryUsage {
  used_bytes: number;
  reserved_bytes: number;
  trash_bytes: number;
  quota_bytes: number;
  items: number;
  max_items: number;
  upload_seconds_today: number;
  upload_seconds_per_day: number;
  max_file_bytes: number;
  max_file_seconds: number;
  over_quota: boolean;
}

export type SourceStateOut = 'uploading' | 'processing' | 'ready' | 'failed';

export interface LibrarySource {
  id: string;
  title: string;
  kind: LibraryKind;
  state: SourceStateOut;
  /** User-facing roll-up of its shots. */
  status: 'live' | 'held' | 'deleted';
  error: string | null;
  /** "Preparing preview" | "Finding shots" | "Describing scenes". */
  processing_step: string | null;
  duration_s: number;
  width: number;
  height: number;
  has_audio: boolean;
  stored_bytes: number;
  shot_count: number;
  thumb_url: string | null;
  proxy_url: string | null;
  sprite_url: string | null;
  deleted_at: string | null;
  purge_after: string | null;
  created_at: string;
}

export interface UsedIn {
  kind: 'editor_project' | 'clip' | 'reel';
  id: string;
  title: string;
}

export interface LibrarySourceDetail extends LibrarySource {
  tags: string[];
  shots: LibraryItem[];
  used_in: UsedIn[];
}
