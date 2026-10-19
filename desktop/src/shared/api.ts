/** Backend contracts the app uses. Each type mirrors the Pydantic schema named beside it. */

import type { Timeline, TimelineOp } from '@timeline'

/** core/responses.py ApiResponse */
export interface ApiResponse<T> {
  data: T | null
  message: string | null
  error: string | null
}

/** core/exceptions.py CustomException.to_dict() */
export interface ApiError {
  error: string
  message: string
}

/** auth/schema.py DesktopStartRequest */
export interface DesktopStartRequest {
  code_challenge: string
  redirect_port: number
  accept_terms: boolean
}

/** auth/schema.py DesktopStartResponse */
export interface DesktopStartResponse {
  authorize_url: string
}

/** auth/schema.py DesktopExchangeRequest */
export interface DesktopExchangeRequest {
  code: string
  code_verifier: string
}

/** auth/schema.py TokenResponse */
export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

/** user/schema.py UserProfileResponse (GET /me, not wrapped in the envelope) */
export interface UserProfileResponse {
  id: string
  name: string
  email: string
  avatar_url: string | null
  avatar_initials: string
  plan: string
  plan_expires_at: string | null
  ai_credits_minutes_remaining: number
  ai_credits_total: number
  features: Record<string, boolean>
  daily_limits: Record<string, number | null>
  usage_today: Record<string, number>
  active_workspace_id: string | null
  providers: string[]
  role: 'user' | 'admin'
  email_notifications: boolean
  onboarding_completed: boolean
}
// ── Editor projects (backend/editor/schema.py). Timeline and ops: frontend/lib/editor/timeline.ts ──


export type AspectRatio = '9:16' | '1:1' | '4:5' | '16:9'

/** editor/schema.py EditorAssetType */
export type EditorAssetType =
  | 'video/mp4' | 'video/quicktime' | 'video/webm'
  | 'image/jpeg' | 'image/png' | 'image/webp' | 'image/gif'
  | 'audio/mpeg' | 'audio/wav' | 'audio/x-wav' | 'audio/mp4' | 'audio/x-m4a' | 'audio/webm' | 'audio/ogg'

/** editor/schema.py EditorProjectCreate */
export interface EditorProjectCreate {
  title?: string
  aspect?: AspectRatio
}

/** editor/schema.py EditorOpsRequest */
export interface EditorOpsRequest {
  base_version: number
  ops: TimelineOp[]
}

/** editor/schema.py EditorProjectSummary */
export interface EditorProjectSummary {
  id: string
  title: string
  version: number
  duration_s: number
  created_at: string
  updated_at: string
}

/** editor/schema.py EditorProjectResponse */
export interface EditorProjectResponse extends EditorProjectSummary {
  timeline: Timeline
  asset_urls: Record<string, string>
}

/** editor/schema.py EditorAssetInitRequest */
export interface EditorAssetInitRequest {
  filename: string
  content_type: EditorAssetType
  size_bytes: number
}

/** editor/schema.py EditorAssetUpload */
export interface EditorAssetUpload {
  key: string
  url: string
  content_type: string
}

/** editor/schema.py EditorOpsResponse */
export interface EditorOpsResponse {
  version: number
  timeline: Timeline
}

/** understanding/findings.py FoundMoment (seconds) */
export interface FoundMoment {
  t0: number
  t1: number
  text: string
}

/** understanding/findings.py AnalysisFindings */
export interface AnalysisFindings {
  kind: 'video' | 'image' | 'audio'
  duration: number
  summary: string | null
  topics: string[]
  language: string | null
  words: number
  fillers: number
  dead_air: number
  shots: number
  tempo_bpm: number | null
  moments: FoundMoment[]
  problems: string[]
  suggestions: string[]
}

/** editor/schema.py MediaAnalysisResponse */
export interface MediaAnalysisResponse {
  asset_id: string
  status: 'pending' | 'running' | 'ready' | 'failed'
  stage: string | null
  findings: AnalysisFindings | null
  error: string | null
  updated_at: string
}

// ── What the server render draws over the picture (brain/schema.py, brain/preview.py) ──

/** PreviewWord: a caption word in timeline seconds. */
export interface PreviewWord {
  word: string
  start: number
  end: number
}

/** PreviewText: a title in one of the renderer's three kinds. */
export interface PreviewText {
  kind: 'hook' | 'pop' | 'line'
  text: string
  at: number
  dur: number
}

/** PreviewSound: a sound effect the export plays, starting at `at`. */
export interface PreviewSound {
  name: string
  at: number
  gain_db: number
}

/** CaptionLook: the parts of a caption template a preview draws. */
export interface CaptionLook {
  name: string
  font_family: string
  /** On a 1080-wide frame. */
  font_size: number
  font_color: string
  highlight_color: string
  emphasis_color: string | null
  stroke_color: string | null
  stroke_width: number
  uppercase: boolean
  background: boolean
  background_color: string | null
  max_words_per_line: number
  /** Share of the frame's height. */
  position_y: number
  animation: string
}

/** ProjectPreview — GET /editor/projects/{id}/preview */
export interface ProjectPreview {
  version: number
  look: string
  caption_style: string | null
  caption_look: CaptionLook | null
  words: PreviewWord[]
  texts: PreviewText[]
  sounds: PreviewSound[]
}

/** CaptionStyleOption — GET /editor/caption-styles */
export interface CaptionStyleOption {
  id: string
  name: string
  description: string
  look: CaptionLook
}

/** brain/schema.py LibrarySound — `url` is made absolute by the app (it is a path under the API host). */
export interface LibrarySound {
  id: string
  name: string
  tags: string[]
  seconds: number
  url: string
  licence: string
  category: string
}

/** brain/schema.py LibraryGraphic — GET /editor/graphics. Packed alpha: colour left half, matte right half. `url` is made absolute by the app. */
export interface LibraryGraphic {
  id: string
  name: string
  seconds: number
  moods: string[]
  url: string
}

/** brain/schema.py SoundSearchResponse — GET /editor/sounds?q=&page=&page_size= */
export interface SoundSearchResponse {
  results: LibrarySound[]
  count: number
  has_more: boolean
}

/** brain/schema.py LookOption — GET /editor/looks */
export interface LookOption {
  id: string
  label: string
}

/** brain/schema.py StylePreference — GET /editor/style, DELETE /editor/style/{key} */
export interface StylePreference {
  key: string
  label: string
  value: string
  confidence: number
  in_use: boolean
}
