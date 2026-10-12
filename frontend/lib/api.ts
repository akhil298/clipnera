import {
  BrandKit,
  PipelineProgressEvent,
  PipelineStatus,
  ViralClip,
  CaptionConfig,
  TranscriptSegment,
  WordTimestamp,
  HookTransitionApplied,
  HookTransitionCatalog,
  HookTransitionConfig,
  HookTransitionResolveResponse,
  ClipEditorSettings,
  TranscriptEdits,
  OnboardingRequest,
  OnboardingResponse,
  OnboardingStatusResponse,
  MyReferralsResponse,
  InvitedByResponse,
  ValidateCodeResponse,
  AdminReferralResponse,
  AdminReferralVoidRequest,
  AdminReferralSettingsResponse,
  ReferralRules,
} from '@/lib/types';
import { getToken, clearAuth, setAuth } from '@/lib/auth';
import { emojiForKeyword } from '@/lib/data/emojiCatalog.generated';
import { DEFAULT_CAPTION_PRESET, normalizeCaptionConfig } from '@/lib/utils/captionStyles';
import type { Timeline, TimelineOp } from '@/lib/editor/timeline';

const API_BASE = process.env.NEXT_PUBLIC_API_URL;

function handleUnauthorized(): void {
  clearAuth();
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  username?: string;
  full_name?: string;
  /** The user confirmed they are 18+ and accept the Terms; the backend rejects sign-ups without it. */
  accept_terms: boolean;
}

export interface ForgotPayload {
  email: string;
}

export interface ResetPayload {
  token: string;
  new_password: string;
}

/** Matches the backend's OAuthProvider enum (auth/schema.py). */
export type OAuthProvider = 'google' | 'microsoft';

export interface OAuthLoginPayload {
  code: string;
  redirect_uri: string;
  /** The user confirmed they are 18+ and accept the Terms; required when the sign-in creates the account. */
  accept_terms: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserProfileResponse {
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
  features: Record<PlanFeature, boolean>;
  daily_limits: Record<UsageKey, number | null>;
  usage_today: Record<UsageKey, number>;
  active_workspace_id: string | null;
  providers: string[];
  role: 'user' | 'admin';
  /** Account emails (failed posts, reconnect reminders); false after unsubscribing. */
  email_notifications: boolean;
  /** False until the user has filled in the one-time welcome form. */
  onboarding_completed: boolean;
}

// Mirrors backend/user/schema.py.
export interface EmailPreferencesRequest {
  email_notifications: boolean;
}

export interface UnsubscribeRequest {
  token: string;
}

export interface DeleteAccountRequest {
  /** The account's email, typed to confirm a deletion that cannot be undone. */
  confirm_email: string;
}

export interface WorkspaceResponse {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  role: string;
  member_count: number;
  created_at: string;
}

/** Roles an owner can assign. Mirrors AssignableRole in backend/workspace/schema.py. */
export type AssignableWorkspaceRole = 'member' | 'viewer';

export interface WorkspaceMemberResponse {
  id: string;
  workspace_id: string;
  user_id: string | null;
  email: string;
  name: string | null;
  avatar_url: string | null;
  role: string;
  status: string;
  created_at: string;
}

export interface DownloadProgress {
  status: 'idle' | 'pending' | 'downloading' | 'uploading' | 'done' | 'error';
  percent: number;
  total: string | null;
  speed: string | null;
  eta: string | null;
  message?: string;
}

export interface AudioProcessingResult {
  success: boolean;
  processedUrl?: string;
  processingTimeSeconds: number;
  sampleRate: number;
  durationSeconds: number;
  appliedSettings: Record<string, any>;
  error?: string;
}

export interface AudioPresetZone {
  key: string;
  label: string;
  strengthRange: string;
}

export interface AudioProcessRequest {
  audioUrl: string;
  config: Record<string, any>;
}

export interface AudioPreviewRequest {
  frequencyHz: number;
  durationSeconds: number;
  config: Record<string, any>;
}

async function request<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { message?: string })?.message ?? 'Something went wrong');
  }
  return data as T;
}

export interface YouTubeMetadataResponse {
  title: string;
  thumbnail_url: string;
  channel_title: string;
  duration_seconds: number;
  duration_formatted: string;
  resolution: string;
  aspect_ratio: string | number;
  original_url: string;
}

/** Mirrors backend clip/schema.py VideoMetadataResponse. */
export interface VideoDownloadResponse {
  id: string;
  title: string;
  thumbnail_url: string;
  channel_title: string;
  duration_formatted: string;
  resolution: string;
  aspect_ratio: string | number;
  file_size: number;
  presigned_url: string;
  original_url: string;
  status: string;
  created_at: string;
  /** Charged when the download was requested with a run; 0 otherwise. */
  credits_deducted: number;
}

export interface FormatInfo {
  format_id: string;
  ext: string;
  resolution: string;
  width: number;
  height: number;
  filesize: number;
  vcodec: string;
  acodec: string;
  abr: number;
  type: string;
}

export interface AvailableFormatsResponse {
  title: string;
  duration: number;
  thumbnail: string;
  channel: string;
  video: FormatInfo[];
  audio: FormatInfo[];
}

export interface BackendClip {
  video_id: string;
  clip_id: string;
  id: string;
  project_id: string;
  user_id: string;
  title: string;
  description: string | null;
  /** The Instagram caption to post with the clip; null on clips made before it existed. */
  social_caption: string | null;
  /** 3-5 hashtags to post with the clip. */
  hashtags: string[];
  start_time: number;
  end_time: number;
  duration_seconds: number;
  /** Source-video span of the teaser played before the clip; null when none. */
  hook_start: number | null;
  hook_end: number | null;
  /** Source ranges the clip's body is stitched from, in play order; null plays start_time..end_time. */
  edit_spans: Array<[number, number]> | null;
  timestamps: { start: number; end: number; duration: number };
  reason: string;
  score: number;
  scores: Record<string, number>;
  content_category: string | null;
  presigned_url: string | null;
  poster_url: string | null;
  local_path: string | null;
  status: string;
  burned_presigned_url: string | null;
  transcript: Array<{
    start: number;
    end: number;
    text: string;
    speaker?: string;
    words?: Array<{ start: number; end: number; word: string }>;
  }>;
  /**
   * Word-level captions already rebased onto the clip's own timeline (the
   * rendered mp4 starts at 0, `transcript` carries absolute source times).
   */
  captions?: Array<{
    text: string;
    start: number;
    end: number;
    speaker?: string;
    emoji?: string;
    emphasis?: boolean;
    /** The word's start in the source video; keys Transcript-tab edits. */
    source_start?: number;
  }>;
  /** What the editor last saved for this clip; null until it saves. */
  editor_settings: ClipEditorSettings | null;
  created_at: string | null;
}

export interface BackendProject {
  id: string;
  title: string;
  source_type: string;
  source_url: string | null;
  status: string;
  duration_seconds: number;
  created_at: string | null;
  clips: BackendClip[];
}

export interface ClipListResponse {
  project_id: string;
  clips: BackendClip[];
  total: number;
}

export interface SocialExportResponse {
  project_id: string;
  exported_clips: Array<{
    clip_id: string;
    platform: string;
    aspect_ratio: string;
    burned_presigned_url?: string | null;
    local_path?: string | null;
    s3_key?: string | null;
    hook_transition?: HookTransitionApplied | null;
  }>;
  platforms: string[];
  total_exported: number;
  /** The watermark actually applied: always true on plans that force it. */
  watermark_enabled: boolean;
  /** Whether the creator's channel intro was put in front of the renders. */
  channel_intro: boolean;
  /** One ZIP of every render; set only when the request asked for `bundle`. */
  bundle_presigned_url?: string | null;
}

/** Mirrors backend SocialExportRequest. */
export interface ExportProjectOptions {
  /** Export exactly these clips; omitted exports the top-scored `maxClips`. */
  clipIds?: string[];
  maxClips?: number;
  /** Output size; overrides the platform default (TikTok is 9:16). */
  aspectRatio?: string;
  captionConfig?: CaptionConfig;
  /** Only paid plans can turn the watermark off; the server forces it otherwise. */
  watermarkEnabled?: boolean;
  /** Burn captions in; off renders the clip without captions or title. */
  burnSubtitles?: boolean;
  /** Overlay the clip title; applies only with `burnSubtitles`. */
  showTitle?: boolean;
  /** Omitted means Auto. */
  hookTransition?: HookTransitionConfig;
  /** Also pack every render into one ZIP (`bundle_presigned_url`). */
  bundle?: boolean;
  /** Play the channel intro first; the server applies it only on Pro with a ready intro. */
  channelIntro?: boolean;
}


/**
 * Build the editor's transcript segments on the clip's own timeline.
 *
 * Every timestamp the player compares against `video.currentTime` has to be
 * clip-relative. The backend's `captions` field already is; `transcript` is
 * not, so the fallback path rebases it by the clip's start. Getting this wrong
 * is silent — captions simply never appear, because the playhead (0..duration)
 * is never inside a word window measured in source-video seconds.
 */
function buildTranscriptSegments(clip: BackendClip): TranscriptSegment[] {
  // A teaser ahead of the clip pushes the clip's own words later in the file.
  const hookDuration = clip.hook_start != null && clip.hook_end != null ? clip.hook_end - clip.hook_start : 0;
  const clipStart = (clip.start_time || 0) - hookDuration;
  const SPEAKER_COLOR = '#38bdf8';

  if (clip.captions && clip.captions.length > 0) {
    // One segment per speaker run keeps the transcript panel readable while
    // the caption overlay works off the flattened word list either way.
    const segments: TranscriptSegment[] = [];
    clip.captions.forEach((caption, index) => {
      const word: WordTimestamp = {
        id: `${clip.id}-w-${index}`,
        text: caption.text,
        start: caption.start,
        end: caption.end,
        highlighted: caption.emphasis ?? false,
        emoji: caption.emoji,
        sourceStart: caption.source_start,
      };
      const speaker = caption.speaker || 'Speaker';
      const last = segments[segments.length - 1];
      if (last && last.speaker === speaker && caption.start - last.end < 1.5) {
        last.words.push(word);
        last.end = caption.end;
        last.text = `${last.text} ${caption.text}`;
        return;
      }
      segments.push({
        id: `${clip.id}-seg-${segments.length}`,
        speaker,
        speakerColor: SPEAKER_COLOR,
        start: caption.start,
        end: caption.end,
        text: caption.text,
        words: [word],
      });
    });
    return segments;
  }

  return (clip.transcript || []).map((seg, segIdx) => {
    const segStart = (seg.start || 0) - clipStart;
    const segEnd = (seg.end || 0) - clipStart;
    const tokens = (seg.text || '').split(/\s+/).filter(Boolean);

    // Real word timings when Whisper gave us them; otherwise spread the
    // segment's words evenly across it, which is approximate but in sync.
    // Emoji come from the same catalog the backend annotates with, so this
    // path previews the same emoji the export would burn in.
    const words: WordTimestamp[] = seg.words?.length
      ? seg.words.map((word, wordIdx) => ({
          id: `${clip.id}-w-${segIdx}-${wordIdx}`,
          text: word.word.trim(),
          start: Math.max(0, word.start - clipStart),
          end: Math.max(0, word.end - clipStart),
          emoji: emojiForKeyword(word.word) ?? undefined,
          sourceStart: Math.round(word.start * 1000) / 1000,
        }))
      : tokens.map((token, wordIdx) => {
          const step = (segEnd - segStart) / Math.max(1, tokens.length);
          return {
            id: `${clip.id}-w-${segIdx}-${wordIdx}`,
            text: token,
            start: Math.max(0, segStart + wordIdx * step),
            end: Math.max(0, segStart + (wordIdx + 1) * step),
            emoji: emojiForKeyword(token) ?? undefined,
          };
        });

    return {
      id: `${clip.id}-seg-${segIdx}`,
      speaker: seg.speaker || 'Speaker',
      speakerColor: SPEAKER_COLOR,
      start: Math.max(0, segStart),
      end: Math.max(0, segEnd),
      text: seg.text || '',
      words,
    };
  });
}

/**
 * Re-applies saved highlights to a freshly built transcript. Cut words stay in
 * it: the editor shows them struck through, so they can be restored, and skips
 * them by `removedWords`.
 */
function applyTranscriptEdits(segments: TranscriptSegment[], edits?: TranscriptEdits): TranscriptSegment[] {
  if (!edits) return segments;
  const highlighted = new Set(edits.highlighted);
  return segments.map((seg) => ({
    ...seg,
    words: seg.words.map((w) => (w.sourceStart === undefined ? w : { ...w, highlighted: highlighted.has(w.sourceStart) })),
  }));
}

export function mapBackendClip(clip: BackendClip): ViralClip {
  const settings: ClipEditorSettings = clip.editor_settings ?? {};
  const viralityScore = Math.round(clip.score ?? 50);
  // Scores arrive normalised to 0-1. A component of exactly 0 is a real
  // reading, not a missing one, so only a non-number falls back to the overall
  // score -- `|| viralityScore` would have hidden every genuine zero.
  const asPercent = (value: unknown): number =>
    typeof value === 'number' && Number.isFinite(value)
      ? Math.round(Math.min(1, Math.max(0, value)) * 100)
      : viralityScore;
  const hookScore = asPercent(clip.scores?.hook_score);
  const engagementScore = asPercent(clip.scores?.engagement_score);
  // The clip's own headline is the hook; `reason` is the model's rationale for
  // picking it and read as a duplicate of the rationale line beneath it.
  const hook = (clip.description || clip.title || '').trim();
  return {
    id: clip.id,
    projectId: clip.project_id,
    title: clip.title,
    hook,
    posterUrl: clip.poster_url || '',
    presignedUrl: clip.presigned_url || clip.burned_presigned_url || '',
    burnedPresignedUrl: clip.burned_presigned_url || '',
    viralityScore,
    hookScore,
    engagementScore,
    startTime: clip.start_time,
    endTime: clip.end_time,
    duration: Math.round(clip.duration_seconds || (clip.end_time - clip.start_time)),
    rationale: clip.reason || '',
    suggestedAspectRatio: '9:16',
    suggestedLayout: 'single_speaker',
    aspectRatio: settings.aspect_ratio ?? '9:16',
    layoutMode: 'single_speaker',
    keywords: [],
    emojiHighlights: [],
    autoBrollKeywords: [],
    transcriptSegments: applyTranscriptEdits(buildTranscriptSegments(clip), settings.transcript_edits),
    bRollOverlays: [],
    soundEffects: [],
    captionConfig: normalizeCaptionConfig(settings.caption_config),
    hookTransition: settings.hook_transition,
    watermarkEnabled: settings.watermark_enabled,
    captionsEnabled: settings.captions_enabled,
    titleEnabled: settings.title_enabled,
    removedWords: settings.transcript_edits?.removed ?? [],
    hasSavedSettings: clip.editor_settings != null,
    // Off by default: the render pipeline applies no zoom, so leaving it on
    // made the preview show motion the exported file never has.
    autoZoom: { enabled: false, frequency: 'subtle', scale: 1.1 },
    autoReframe: { mode: 'center', speakerCropX: 0.5, speakerSmoothing: 0.5 },
    socialOptimization: {
      hashtags: clip.hashtags ?? [],
      optimizedHooks: [],
      targetPlatforms: ['tiktok', 'instagram', 'youtube'],
      postStatus: 'draft',
    },
    thumbnailTime: 1.0,
  };
}

interface ApiErrorBody {
  message?: string;
  error?: string;
  feature?: string;
}

/** Errors the API returns when the caller's plan does not cover a request. */
const PLAN_ERROR_CODES = new Set([
  'PRO_REQUIRED',
  'LIMIT_REACHED',
  'ASPECT_RATIO_NOT_ENTITLED',
  'CAPTION_STYLE_NOT_ENTITLED',
  'DURATION_NOT_ENTITLED',
  'INSUFFICIENT_CREDITS',
]);

/** Fired on window for any plan error, so the dashboard can open the upsell
 * modal wherever the request came from. */
export const UPGRADE_REQUIRED_EVENT = 'clipnera:upgrade-required';

/** Fired on window when a request has changed the credit balance (a run was
 * charged, or a failed one refunded), so every balance on screen refetches. */
export const CREDITS_CHANGED_EVENT = 'clipnera:credits-changed';

export function notifyCreditsChanged(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(CREDITS_CHANGED_EVENT));
}

/** Passes a response through after announcing the balance it changed. */
function creditsChanged<T>(response: T): T {
  notifyCreditsChanged();
  return response;
}

export interface UpgradeRequiredDetail {
  error: string;
  feature?: string;
  message: string;
}

function queryString(params: object): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value));
  });
  const qs = query.toString();
  return qs ? `?${qs}` : '';
}

/** A refused API call. Still an Error with the server's message; `code` is its error code (e.g. STALE_VERSION). */
export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string | null) {
    super(message);
    this.name = 'ApiError';
  }
}

async function authedRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  if (!token) {
    handleUnauthorized();
    throw new Error('Unauthorized: Your session has expired.');
  }

  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers: {
      // The browser sets the multipart boundary itself for FormData bodies.
      ...(options?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
  });

  if (res.status === 401) {
    handleUnauthorized();
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const { message = 'Something went wrong', error, feature } = data as ApiErrorBody;
    if (res.status === 401) {
      throw new ApiError(`Unauthorized: ${message}`, res.status, error ?? null);
    }
    if (error && PLAN_ERROR_CODES.has(error) && typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent<UpgradeRequiredDetail>(UPGRADE_REQUIRED_EVENT, { detail: { error, feature, message } }),
      );
    }
    throw new ApiError(message, res.status, error ?? null);
  }
  return data as T;
}

export const authApi = {
  login: (payload: LoginPayload) =>
    request<TokenResponse>('/auth/login', payload).then((data) => {
      setAuth(data.access_token, data.expires_in);
      return data;
    }),
  oauthLogin: (provider: OAuthProvider, payload: OAuthLoginPayload) =>
    request<TokenResponse>(`/auth/oauth/${provider}`, payload).then((data) => {
      setAuth(data.access_token, data.expires_in);
      return data;
    }),
  register: (payload: RegisterPayload) => request('/auth/register', payload),
  forgotPassword: (payload: ForgotPayload) => request('/auth/forgot-password', payload),
  resetPassword: (payload: ResetPayload) => request('/auth/reset-password', payload),
  logout: () => authedRequest<void>('/auth/logout', { method: 'POST' }),
};

export const userApi = {
  getMe: () => authedRequest<UserProfileResponse>('/me'),
  dismissPlanNotice: () => authedRequest<void>('/me/plan-notice/dismiss', { method: 'POST' }),
  setEmailPreferences: (payload: EmailPreferencesRequest) =>
    envelopeRequest<UserProfileResponse>('/me/email-preferences', { method: 'PUT', body: JSON.stringify(payload) }),
  /** Public: the token from an email's unsubscribe link identifies the user. */
  unsubscribe: (payload: UnsubscribeRequest) => request<ApiEnvelope<null>>('/email/unsubscribe', payload),
  deleteAccount: (payload: DeleteAccountRequest) =>
    envelopeRequest<null>('/me/delete', { method: 'POST', body: JSON.stringify(payload) }),
};

export const workspaceApi = {
  list: () => authedRequest<WorkspaceResponse[]>('/workspaces'),
  create: (name: string) => authedRequest<WorkspaceResponse>('/workspaces', {
    method: 'POST',
    body: JSON.stringify({ name }),
  }),
  get: (id: string) => authedRequest<WorkspaceResponse>(`/workspaces/${id}`),
  listMembers: (workspaceId: string) => authedRequest<WorkspaceMemberResponse[]>(`/workspaces/${workspaceId}/members`),
  inviteMember: (workspaceId: string, email: string, role: AssignableWorkspaceRole) => authedRequest<WorkspaceMemberResponse>(`/workspaces/${workspaceId}/members`, {
    method: 'POST',
    body: JSON.stringify({ email, role }),
  }),
  createAndAddMember: (workspaceId: string, email: string, password: string, fullName: string, role: AssignableWorkspaceRole) => authedRequest<WorkspaceMemberResponse>(`/workspaces/${workspaceId}/members/create`, {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name: fullName, role }),
  }),
  updateMemberRole: (workspaceId: string, memberId: string, role: AssignableWorkspaceRole) => authedRequest<WorkspaceMemberResponse>(`/workspaces/${workspaceId}/members/${memberId}`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  }),
  removeMember: (workspaceId: string, memberId: string) => authedRequest<void>(`/workspaces/${workspaceId}/members/${memberId}`, {
    method: 'DELETE',
  }),
};

export const clipApi = {
  listProjects: () => authedRequest<{ projects: BackendProject[]; total: number }>('/clips/projects'),
  fetchYoutubeMetadata: (url: string) => authedRequest<YouTubeMetadataResponse>('/clips/youtube/metadata', {
    method: 'POST',
    body: JSON.stringify({ url }),
  }),
  fetchFormats: (url: string) => authedRequest<AvailableFormatsResponse>('/clips/formats', {
    method: 'POST',
    body: JSON.stringify({ url }),
  }),
  /** Saves the editor's state for a clip; the export reads transcript edits from it. */
  saveEditorSettings: (clipId: string, settings: ClipEditorSettings) =>
    envelopeRequest<ClipEditorSettings>(`/clips/item/${clipId}/editor-settings`, {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  /** `pipeline` is started by the server once the video is stored. */
  /** With `pipeline`, the run is charged now, before the download finishes. */
  downloadYoutube: (url: string, formatId?: string, pipeline?: PipelineStartRequest) => authedRequest<VideoDownloadResponse>('/clips/download', {
    method: 'POST',
    body: JSON.stringify({ url, format_id: formatId, ...(pipeline ? { pipeline } : {}) }),
  }).then(creditsChanged),
  exportProject: (
    projectId: string,
    { clipIds, maxClips, aspectRatio, captionConfig, watermarkEnabled = true, burnSubtitles = true, showTitle = true, hookTransition, bundle, channelIntro = true }: ExportProjectOptions = {},
  ) => authedRequest<SocialExportResponse>(`/pipeline/export/${projectId}`, {
    method: 'POST',
    body: JSON.stringify({
      platforms: ['tiktok'],
      ...(clipIds?.length ? { clip_ids: clipIds } : {}),
      ...(aspectRatio ? { aspect_ratio: aspectRatio } : {}),
      max_clips: maxClips,
      burn_subtitles: burnSubtitles,
      show_title: showTitle,
      enable_emoji: captionConfig?.emojisEnabled ?? true,
      watermark_enabled: watermarkEnabled,
      channel_intro: channelIntro,
      ...(hookTransition ? { hook_transition: hookTransition } : {}),
      ...(bundle ? { bundle } : {}),
      style_type: captionConfig?.preset || DEFAULT_CAPTION_PRESET,
      custom_config: captionConfig ? {
        font_size: captionConfig.fontSize,
        font_family: captionConfig.fontFamily,
        font_color: captionConfig.textColor,
        highlight_color: captionConfig.highlightColor,
        secondary_highlight_color: captionConfig.secondaryHighlightColor,
        has_bg_box: captionConfig.hasBgBox,
        bg_box_color: captionConfig.bgBoxColor,
        word_box_color: captionConfig.wordBoxColor,
        uppercase: captionConfig.uppercase,
        animation: captionConfig.animation,
        animation_speed: captionConfig.animationSpeed,
        position_y: captionConfig.positionY,
         emojis_enabled: captionConfig.emojisEnabled,
         emoji_collection: captionConfig.emojiCollection,
         max_words_per_line: captionConfig.maxWordsPerLine,
        shadow_intensity: captionConfig.shadowIntensity,
        title_font_size: captionConfig.titleFontSize,
        title_position_y: captionConfig.titlePositionY,
      } : undefined,
    }),
  }),
  subscribeDownloadProgress: (
    projectId: string,
    onProgress: (progress: DownloadProgress) => void,
    onError?: (err: Error) => void,
  ): (() => void) => {
    let isCancelled = false;

    const pollProgress = async () => {
      try {
        while (!isCancelled) {
          try {
            const token = getToken();
            if (!token) {
              onError?.(new Error('Not authenticated'));
              break;
            }

            const res = await fetch(`${API_BASE}/api/v1/clips/progress/${projectId}`, {
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
              },
            });

            if (res.status === 401) {
              handleUnauthorized();
              onError?.(new Error('Session expired'));
              break;
            }

            if (!res.ok) {
              onError?.(new Error(`Failed to fetch progress: ${res.status}`));
              break;
            }

            const data = (await res.json()) as DownloadProgress;
            onProgress(data);

            if (data.status === 'done' || data.status === 'error') {
              // Done: the server has started (and charged for) the run.
              // Error: whatever the run was charged up front was refunded.
              notifyCreditsChanged();
              break;
            }

            await new Promise((r) => setTimeout(r, 500));
          } catch (err) {
            onError?.(err as Error);
            break;
          }
        }
      } catch (err) {
        onError?.(err as Error);
      }
    };

     pollProgress();

    return () => {
      isCancelled = true;
    };
  },
  listClips: (projectId: string) => authedRequest<ClipListResponse>(`/clips/${projectId}`),
  deleteProject: (projectId: string) => authedRequest<void>(`/clips/projects/${projectId}`, {
    method: 'DELETE',
  }),
};

export interface AudioProcessRequest {
  audioUrl: string;
  config: Record<string, any>;
}

export interface AudioPreviewRequest {
  frequencyHz: number;
  durationSeconds: number;
  config: Record<string, any>;
}

export const audioApi = {
  process: (payload: AudioProcessRequest) =>
    authedRequest<AudioProcessingResult>('/audio/process', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  preview: (payload: AudioPreviewRequest) =>
    authedRequest<AudioProcessingResult>('/audio/preview', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getPresets: () =>
    authedRequest<{ zones: AudioPresetZone[] }>('/audio/presets'),
};

export const DEFAULT_PIPELINE_STEPS = [
  'audio_extraction',
  'ai_noise_cancellation',
  'transcription',
  'topic_research',
  'visual_analysis',
  'content_classification',
  'highlight_detection',
  'scoring',
  'metadata_generation',
  'aspect_ratio_render',
  'clip_generation',
];
/**
 * Shapes to render. Left undefined the backend renders 9:16; a plan without
 * custom_aspect_ratios always gets 9:16 whatever is sent.
 */
/**
 * Opens a server-sent event stream (fetch rather than EventSource, which cannot
 * send the bearer token) and calls `onEvent` with each parsed `data:` payload.
 * `onEvent` returning false closes the stream. `onError` fires on any failure
 * or when the server ends the stream, but never after the returned
 * unsubscribe is called.
 */
function subscribeEvents<T>(
  path: string,
  onEvent: (data: T) => boolean | void,
  onError?: (err: Error) => void,
): () => void {
  const ctrl = new AbortController();
  (async () => {
    const token = getToken();
    if (!token) throw new Error('Not authenticated');
    const res = await fetch(`${API_BASE}/api/v1${path}`, {
      headers: { Accept: 'text/event-stream', Authorization: `Bearer ${token}` },
      signal: ctrl.signal,
    });
    if (res.status === 401) {
      handleUnauthorized();
      throw new Error('Session expired');
    }
    if (!res.ok || !res.body) throw new Error(`Failed to subscribe: ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) throw new Error('Stream closed');
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        const line = part.split('\n').find((l) => l.startsWith('data:'));
        if (!line) continue;
        let data: T;
        try {
          data = JSON.parse(line.slice(5).trim());
        } catch {
          continue; // skip malformed
        }
        if (onEvent(data) === false) {
          ctrl.abort();
          return;
        }
      }
    }
  })().catch((err: unknown) => {
    if (!ctrl.signal.aborted) onError?.(err as Error);
  });
  return () => ctrl.abort();
}

/** Script Hindi and Telugu captions are written in; mirrors backend transcription/transliterate.py. */
export type CaptionScript = 'auto' | 'roman' | 'native';

/** The subset of the backend's run `clip_settings` the upload flow sets. */
export interface PipelineClipSettings {
  caption_script?: CaptionScript;
  /** Add B-roll cutaways to each clip (charged per clip that gets them). */
  broll?: boolean;
  /** Also cut story clips: moments from across the video stitched into one clip. */
  story_clips?: boolean;
}

/** Run settings; mirrors backend pipeline/schema.py PipelineStartRequest. Sent to
 * /pipeline/start, or with a download/upload so the server starts the run itself. */
export interface PipelineStartRequest {
  steps?: string[];
  audio_config?: Record<string, any>;
  output_aspect_ratios?: string[];
  clip_settings?: PipelineClipSettings;
  watermark_enabled?: boolean;
}

export const pipelineApi = {
  start: (
    projectId: string,
    steps: string[] = DEFAULT_PIPELINE_STEPS,
    audioConfig: Record<string, any> = {},
    outputAspectRatios?: string[],
    clipSettings?: PipelineClipSettings,
  ) =>
    authedRequest<{ project_id: string; status: string; selected_steps: string[]; credits_deducted: number }>(`/pipeline/start/${projectId}`, {
      method: 'POST',
      body: JSON.stringify({
        steps,
        audio_config: audioConfig,
        ...(outputAspectRatios?.length ? { output_aspect_ratios: outputAspectRatios } : {}),
        ...(clipSettings ? { clip_settings: clipSettings } : {}),
      }),
    }).then(creditsChanged),
  subscribeProgress: (
    projectId: string,
    onProgress: (data: PipelineProgressEvent) => void,
    onError?: (err: Error) => void,
  ): (() => void) =>
    subscribeEvents<PipelineProgressEvent>(
      `/pipeline/progress/${projectId}`,
      (data) => {
        onProgress(data);
        return data.status !== 'completed' && data.status !== 'error' && data.status !== 'cancelled';
      },
      onError,
    ),
  getStatus: (projectId: string) =>
    authedRequest<PipelineStatus>(`/pipeline/status/${projectId}`),
  /**
   * Status for many projects in one request. Loading the dashboard used to fire
   * one getStatus per project and block the whole list on the slowest of them.
   */
  getStatusBatch: (projectIds: string[]) =>
    authedRequest<{ statuses: Record<string, PipelineStatus> }>(`/pipeline/status/batch`, {
      method: 'POST',
      body: JSON.stringify({ project_ids: projectIds }),
    }),
  cancel: (projectId: string) =>
    authedRequest<{ project_id: string; status: string }>(`/pipeline/cancel/${projectId}`, {
      method: 'POST',
    }),
  revertStep: (projectId: string, step: string) =>
    authedRequest<{ project_id: string; step: string; status: string }>(`/pipeline/revert/${projectId}/${step}`, {
      method: 'POST',
    }),
  resume: (
    projectId: string,
    steps: string[] = DEFAULT_PIPELINE_STEPS,
    audioConfig: Record<string, any> = {},
    outputAspectRatios?: string[],
  ) =>
    authedRequest<{ project_id: string; status: string; selected_steps: string[]; credits_deducted: number }>(`/pipeline/resume/${projectId}`, {
      method: 'POST',
      body: JSON.stringify({
        steps,
        audio_config: audioConfig,
        ...(outputAspectRatios?.length ? { output_aspect_ratios: outputAspectRatios } : {}),
      }),
    }).then(creditsChanged),
};

/**
 * Waits for a YouTube download to finish, then starts the AI pipeline.
 *
 * `POST /pipeline/start` rejects with 409 VIDEO_NOT_READY until the project is
 * marked UPLOADED with a known duration, so starting the pipeline immediately
 * after kicking off a download is a race. Every ingest entry point goes through
 * this helper so the handoff is done the same way in one place.
 */
export function startPipelineWhenReady(
  projectId: string,
  options: {
    steps?: string[];
    audioConfig?: Record<string, any>;
    onDownloadProgress?: (progress: DownloadProgress) => void;
    signal?: { cancelled: boolean };
  } = {},
): Promise<{ project_id: string; status: string; selected_steps: string[]; credits_deducted: number }> {
  const { steps = DEFAULT_PIPELINE_STEPS, audioConfig = {}, onDownloadProgress, signal } = options;

  return new Promise((resolve, reject) => {
    let settled = false;

    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      unsubscribe();
      fn();
    };

    const unsubscribe = clipApi.subscribeDownloadProgress(
      projectId,
      (progress) => {
        onDownloadProgress?.(progress);
        if (signal?.cancelled) {
          finish(() => reject(new Error('Cancelled')));
          return;
        }
        if (progress.status === 'done') {
          finish(() => {
            pipelineApi.start(projectId, steps, audioConfig).then(resolve).catch(reject);
          });
        } else if (progress.status === 'error') {
          finish(() => reject(new Error(progress.message || 'Download failed')));
        }
      },
      (err) => finish(() => reject(err)),
    );
  });
}

export interface CreateBrandKitPayload {
  brand_name: string;
  logo_url?: string;
  logo_position: string;
  logo_opacity: number;
  logo_size: number;
  primary_color: string;
  secondary_color: string;
  preferred_font: string;
  default_preset: string;
  auto_emojis: boolean;
  outro_cta_text: string;
}

export const hookTransitionApi = {
  getCatalog: () => authedRequest<HookTransitionCatalog>('/hook-transitions/catalog'),
  /** What a config renders as for one clip, e.g. what Auto picks for it. */
  resolveForClip: (clipId: string, config: HookTransitionConfig) =>
    authedRequest<HookTransitionResolveResponse>(`/hook-transitions/clips/${clipId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),
};

export const brandKitApi = {
  getMe: () => authedRequest<BrandKit>('/brand-kits/me'),
  list: () => authedRequest<BrandKit[]>('/brand-kits'),
  create: (payload: CreateBrandKitPayload) =>
    authedRequest<BrandKit>('/brand-kits', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    authedRequest<void>(`/brand-kits/${id}`, {
      method: 'DELETE',
    }),
};

export interface PlanResponse {
  id: string;
  name: string;
  slug: string;
  credit_minutes: number;
  price_monthly: number;
  currency: string;
  price_inr: number | null;
  is_active: boolean;
  features: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentTransactionResponse {
  id: string;
  user_id: string;
  /** Set for a plan payment; credit_pack and credits for a credit-pack one. */
  plan_id: string | null;
  plan: PlanResponse | null;
  credit_pack: string | null;
  credits: number | null;
  amount: number;
  currency: string;
  status: string;
  payment_uuid: string;
  payment_method: string | null;
  notes: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreditLedgerResponse {
  id: string;
  user_id: string;
  amount: number;
  balance_after: number;
  reason: string;
  reference_id: string | null;
  reference_type: string | null;
  created_at: string;
}

// Plans. Mirrors PlanCapabilities / EntitlementsResponse / PlansResponse in
// backend/subscription/schema.py; the rules live in subscription/entitlements.py.

export type PlanFeature =
  | 'remove_watermark'
  | 'pro_ai'
  | 'all_hook_transitions'
  | 'brand_kit_edit'
  | 'depth_captions'
  | 'batch_processing'
  | 'team_members'
  | 'social_scheduling'
  | 'custom_aspect_ratios'
  | 'creator_intro';

export type UsageKey = 'exports' | 'audio_enhancements' | 'reel_renders' | 'ai_shots' | 'auto_edits' | 'intro_renders';

export type BillingPeriod = 'monthly' | 'yearly';

export interface PlanCapabilities {
  plan: string;
  aspect_ratios: string[];
  /** null means every caption style is available. */
  caption_styles: string[] | null;
  max_clips_per_video: number;
  watermark_forced: boolean;
  pro_ai_provider: boolean;
  priority_rendering: boolean;
  max_upload_duration_seconds: number;
  /** Credit minutes granted every 30 days. */
  credit_minutes: number;
  all_hook_transitions: boolean;
  brand_kit_edit: boolean;
  depth_captions: boolean;
  batch_processing: boolean;
  team_members: boolean;
  /** Per UTC day; null means unlimited. */
  daily_limits: Record<UsageKey, number | null>;
  /** Connected publishing platforms (backend social/). */
  social_max_accounts: number;
  social_platforms: SocialPlatform[];
  social_scheduling: boolean;
  social_max_schedule_days: number;
  social_posts_per_day: number;
  /** Picking output ratios at upload; without it every run renders 9:16. */
  custom_aspect_ratios: boolean;
  /** A channel intro played before every export (backend creator_intro/). */
  creator_intro: boolean;
  /** AI editor: plan candidates the director compares. */
  ai_plan_candidates_k: number;
  /** AI editor: critic repair rounds (cap 3). */
  ai_critic_max_rounds: number;
  /** AI editor: the planner's model, "provider:model" or a bare provider. */
  ai_planner_model: string;
  features: Record<PlanFeature, boolean>;
}

export interface EntitlementsResponse extends PlanCapabilities {
  credit_minutes_total: number;
  credit_minutes_remaining: number;
  /** The bought part of credit_minutes_remaining; never expires. */
  purchased_credits_remaining: number;
  /** The bonus part (referral rewards), which expires grant by grant. */
  bonus_credits_remaining: number;
  /** The soonest bonus expiry, and how many credits expire then. */
  bonus_credits_expiring_at: string | null;
  bonus_credits_expiring: number;
  current_period_end: string | null;
  subscription_status: string;
  /** When paid access ends, counting queued renewals; null on Free. */
  plan_expires_at: string | null;
  next_credit_reset_at: string | null;
  usage_today: Record<UsageKey, number>;
  has_pending_payment: boolean;
  /** One-time "features moved to Pro" notice for accounts that predate it. */
  show_plan_notice: boolean;
  /** Pricing; see estimateVideoCredits in hooks/useEntitlements.ts. */
  credits_per_video_minute: number;
  extra_aspect_ratio_credit_share: number;
}

export interface PlanPriceResponse {
  plan_type: BillingPeriod;
  amount: number;
  currency: string;
  days: number;
}

export interface PlanOfferResponse {
  slug: string;
  name: string;
  capabilities: PlanCapabilities;
  /** Empty for plans that are not sold (Free). */
  prices: PlanPriceResponse[];
}

/** A one-off credit pack. Mirrors CreditPackResponse in backend/subscription/schema.py. */
export interface CreditPackResponse {
  slug: string;
  name: string;
  credits: number;
  amount: number;
  currency: string;
}

export interface PlansResponse {
  plans: PlanOfferResponse[];
  credit_packs: CreditPackResponse[];
}

export const subscriptionApi = {
  getPlans: () => authedRequest<PlansResponse>('/subscription/plans'),
  /** Public: the same plans and prices, for signed-out visitors (landing page). */
  getPublicPlans: async (): Promise<PlansResponse> => {
    const res = await fetch(`${API_BASE}/api/v1/subscription/plans`);
    if (!res.ok) throw new Error('Could not load plans');
    return res.json();
  },
  /** Capabilities of the caller's current plan. The UI gates on this rather
   * than reimplementing the tier rules. */
  getEntitlements: () => authedRequest<EntitlementsResponse>('/subscription/entitlements'),
  getMyTransactions: () => authedRequest<PaymentTransactionResponse[]>('/subscription/transactions'),
  getCreditLedger: (limit?: number) => authedRequest<CreditLedgerResponse[]>(`/subscription/ledger${limit ? `?limit=${limit}` : ''}`),
};

// Manual UPI payments. Mirrors backend/payment/schema.py.

export type PaymentStatus = 'pending' | 'success' | 'failed' | 'rejected';

/** A plan period (plan_*) or a credit pack (credit_pack, credits). */
export interface UpiCheckoutResponse {
  plan_slug: string | null;
  plan_name: string | null;
  plan_type: BillingPeriod | null;
  credit_pack: string | null;
  credits: number | null;
  amount: number;
  currency: string;
  upi_id: string;
  payee_name: string;
  /** upi://pay deep link with the amount pre-filled. */
  upi_uri: string;
  /** SVG data URI of the QR code for upi_uri. */
  qr_image: string;
}

export interface PaymentResponse {
  id: string;
  /** Set for a plan payment; credit_pack and credits for a credit-pack one. */
  plan_slug: string | null;
  plan_name: string | null;
  plan_type: BillingPeriod | null;
  credit_pack: string | null;
  credits: number | null;
  amount: number;
  currency: string;
  utr_number: string | null;
  status: PaymentStatus;
  rejection_reason: string | null;
  /** Short-lived signed URL; refetch the payment when it expires. */
  screenshot_url: string | null;
  verified_at: string | null;
  created_at: string;
}

export interface AdminPaymentResponse extends PaymentResponse {
  user_id: string;
  user_email: string;
  user_name: string | null;
  verified_by: string | null;
}

export interface SubmitPaymentPayload {
  plan_slug: string;
  plan_type: BillingPeriod;
  utr_number: string;
  screenshot: File;
}

export interface SubmitCreditPackPaymentPayload {
  credit_pack: string;
  utr_number: string;
  screenshot: File;
}

export const paymentsApi = {
  getCheckout: (planSlug: string, planType: BillingPeriod) =>
    authedRequest<UpiCheckoutResponse>(`/payments/qr${queryString({ plan_slug: planSlug, plan_type: planType })}`),
  getCreditPackCheckout: (packSlug: string) =>
    authedRequest<UpiCheckoutResponse>(`/payments/credit-packs/${encodeURIComponent(packSlug)}/qr`),
  submitCreditPack: ({ credit_pack, utr_number, screenshot }: SubmitCreditPackPaymentPayload) => {
    const form = new FormData();
    form.append('credit_pack', credit_pack);
    form.append('utr_number', utr_number);
    form.append('screenshot', screenshot);
    return authedRequest<PaymentResponse>('/payments/credit-packs', { method: 'POST', body: form });
  },
  submit: ({ plan_slug, plan_type, utr_number, screenshot }: SubmitPaymentPayload) => {
    const form = new FormData();
    form.append('plan_slug', plan_slug);
    form.append('plan_type', plan_type);
    form.append('utr_number', utr_number);
    form.append('screenshot', screenshot);
    return authedRequest<PaymentResponse>('/payments', { method: 'POST', body: form });
  },
  getMine: () => authedRequest<PaymentResponse[]>('/payments/my'),
};

export interface AdminPaymentListParams {
  status?: PaymentStatus;
  q?: string;
  limit?: number;
  offset?: number;
}

export const adminPaymentsApi = {
  list: (params: AdminPaymentListParams = {}) =>
    authedRequest<AdminPaymentResponse[]>(`/admin/payments${queryString(params)}`),
  get: (id: string) => authedRequest<AdminPaymentResponse>(`/admin/payments/${id}`),
  approve: (id: string) =>
    authedRequest<AdminPaymentResponse>(`/admin/payments/${id}/approve`, { method: 'PATCH' }),
  reject: (id: string, reason: string) =>
    authedRequest<AdminPaymentResponse>(`/admin/payments/${id}/reject`, {
      method: 'PATCH',
      body: JSON.stringify({ reason }),
    }),
};

// Manual credit top-ups. Mirrors CreditTopupRequest / AdminCreditTopupResponse
// in backend/subscription/schema.py. Admin only.
export interface CreditTopupRequest {
  user_email: string;
  amount: number;
  reason: string;
}

export interface AdminCreditTopupResponse {
  id: string;
  user_id: string;
  user_email: string;
  user_name: string | null;
  amount: number;
  balance_after: number;
  reason: string;
  created_by: string | null;
  created_by_email: string | null;
  created_at: string;
}

export const adminCreditsApi = {
  topup: (body: CreditTopupRequest) =>
    authedRequest<AdminCreditTopupResponse>('/subscription/topup', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  list: (params: AdminListParams = {}) =>
    authedRequest<AdminCreditTopupResponse[]>(`/subscription/topups${queryString(params)}`),
};

// Admin users and overview. Mirrors backend/admin/schema.py.

export interface AdminListParams {
  q?: string;
  limit?: number;
  offset?: number;
}

export interface AdminUserResponse {
  id: string;
  email: string;
  name: string | null;
  role: 'user' | 'admin';
  /** Effective plan right now. */
  plan: string;
  plan_expires_at: string | null;
  created_at: string;
  last_login_at: string | null;
  /** Last UTC day with a signed-in request (YYYY-MM-DD); tracked from launch of this field. */
  last_active_on: string | null;
  projects: number;
  clips: number;
  credits_left: number;
  /** Approved payments, in INR. */
  total_paid: number;
  ai_cost_usd: number;
}

export type AdminUserSort = 'newest' | 'last_active' | 'projects' | 'ai_cost';

export interface AdminUserListParams extends AdminListParams {
  sort?: AdminUserSort;
}

export interface AdminUserProject {
  id: string;
  title: string;
  source_type: string;
  source_url: string | null;
  status: string;
  duration_seconds: number | null;
  clips: number;
  /** Net of refunds. */
  credits_charged: number;
  ai_cost_usd: number;
  created_at: string;
}

export interface AdminLoginEntry {
  created_at: string;
  method: string;
  ip: string | null;
  user_agent: string | null;
}

export interface AdminUserPayment {
  id: string;
  amount: number;
  currency: string;
  status: string;
  /** A payment buys either a plan period or a credit pack. */
  plan_type: string | null;
  credit_pack: string | null;
  credits: number | null;
  created_at: string;
  verified_at: string | null;
}

export interface AdminCreditEntry {
  created_at: string;
  amount: number;
  balance_after: number;
  reason: string;
}

export interface AdminUserDetailResponse {
  user: AdminUserResponse;
  credits_total: number;
  next_credit_reset_at: string | null;
  active_days: number;
  projects: AdminUserProject[];
  logins: AdminLoginEntry[];
  payments: AdminUserPayment[];
  credit_history: AdminCreditEntry[];
}

export interface AdminClip {
  id: string;
  title: string;
  duration_seconds: number;
  score: number;
  status: string;
  /** Signed links that expire; refetch to play again later. */
  video_url: string | null;
  /** The render with captions burned in, once the user has exported one. */
  captioned_video_url: string | null;
  poster_url: string | null;
  created_at: string;
}

export interface AdminProjectClipsResponse {
  project_id: string;
  title: string;
  /** The video the user uploaded or we downloaded, while it is still stored. */
  source_video_url: string | null;
  clips: AdminClip[];
}

export interface AdminDailyGrowth {
  /** UTC day, YYYY-MM-DD. */
  day: string;
  signups: number;
  active_users: number;
  logins: number;
  projects: number;
  clips: number;
  /** Approved payments by the day they were verified, in INR. */
  revenue: number;
  ai_cost_usd: number;
}

export interface AdminGrowthResponse {
  days: number;
  total_users: number;
  new_users: number;
  /** Distinct users active at any point in the range. */
  active_in_window: number;
  active_today: number;
  active_7d: number;
  active_30d: number;
  pro_users: number;
  projects: number;
  clips: number;
  revenue: number;
  currency: string;
  ai_cost_usd: number;
  daily: AdminDailyGrowth[];
}

export interface AdminUserPlanRequest {
  plan: 'pro' | 'free';
  /** Required when granting Pro. */
  days?: number;
}

export interface AdminOverviewResponse {
  total_users: number;
  free_users: number;
  pro_users: number;
  pending_payments: number;
  revenue_this_month: number;
  currency: string;
}

export const adminUsersApi = {
  list: (params: AdminUserListParams = {}) => authedRequest<AdminUserResponse[]>(`/admin/users${queryString(params)}`),
  getDetail: (userId: string) => envelopeRequest<AdminUserDetailResponse>(`/admin/users/${userId}/detail`),
  getProjectClips: (userId: string, projectId: string) =>
    envelopeRequest<AdminProjectClipsResponse>(`/admin/users/${userId}/projects/${projectId}/clips`),
  setPlan: (userId: string, body: AdminUserPlanRequest) =>
    authedRequest<AdminUserResponse>(`/admin/users/${userId}/plan`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  getOverview: () => authedRequest<AdminOverviewResponse>('/admin/overview'),
  getGrowth: (days = 30) => envelopeRequest<AdminGrowthResponse>(`/admin/growth${queryString({ days })}`),
};

export interface DashboardStatsResponse {
  total_viral_shorts: number;
  manual_hours_saved: number;
  avg_virality_score: number;
  best_post_window: string;
}

export const analyticsApi = {
  getDashboardStats: () => authedRequest<DashboardStatsResponse>('/analytics/dashboard'),
};

// -- Connected publishing platforms (backend social/, feature_flags/) ---------
// These endpoints use the { data, message, error } envelope.

interface ApiEnvelope<T> {
  data: T | null;
  message: string | null;
  error: string | null;
}

function envelopeRequest<T>(path: string, options?: RequestInit): Promise<T> {
  return authedRequest<ApiEnvelope<T>>(path, options).then((body) => body.data as T);
}

// -- AI usage and cost (backend usage/) ---------------------------------------
// Mirrors backend/usage/schema.py.

export interface StepUsage {
  step: string;
  provider: string;
  model: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  audio_seconds: number;
  cost_usd: number;
}

export interface ProjectUsage {
  project_id: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  audio_seconds: number;
  cost_usd: number;
  by_step: StepUsage[];
}

export interface DailyUsage {
  day: string;
  calls: number;
  cost_usd: number;
}

export interface ModelUsage {
  provider: string;
  model: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface TopProjectUsage {
  project_id: string;
  user_id: string | null;
  calls: number;
  cost_usd: number;
}

export interface CostPerMinute {
  tier: 'pro' | 'free' | string;
  projects: number;
  source_minutes: number;
  cost_per_source_minute_usd: number;
}

export interface AdminUsageSummary {
  days: number;
  calls: number;
  cost_usd: number;
  cost_per_minute: CostPerMinute[];
  by_day: DailyUsage[];
  by_model: ModelUsage[];
  top_projects: TopProjectUsage[];
}

export const usageApi = {
  getProjectUsage: (projectId: string) => envelopeRequest<ProjectUsage>(`/usage/projects/${projectId}`),
};

export const adminUsageApi = {
  getSummary: (days = 30) => envelopeRequest<AdminUsageSummary>(`/admin/usage${queryString({ days })}`),
  getClipQuality: (days = 30) => envelopeRequest<ClipQualityReport>(`/admin/clip-quality${queryString({ days })}`),
};

// Mirrors backend/feedback/schema.py.
export interface VersionQuality {
  director_version: string;
  clips: number;
  exported_share: number;
  edited_share: number;
  published_share: number;
}

export interface ClipQualityReport {
  days: number;
  versions: VersionQuality[];
}

export type SocialPlatform = 'youtube' | 'tiktok' | 'instagram' | 'x';
export type SocialAccountStatus = 'active' | 'needs_reconnect' | 'disconnecting' | 'disconnected';
export type SocialPostStatus = 'scheduled' | 'publishing' | 'published' | 'failed' | 'cancelled';

export interface SocialPlatformInfo {
  platform: SocialPlatform;
  label: string;
  /** Switched on by an admin and configured on the server. */
  available: boolean;
  allowed_by_plan: boolean;
  caption_max_chars: number;
  max_duration_seconds: number;
  pending_review_note: string | null;
}

export interface ConnectedAccountResponse {
  id: string;
  platform: SocialPlatform;
  handle: string | null;
  display_name: string | null;
  avatar_url: string | null;
  follower_count: number | null;
  follower_count_updated_at: string | null;
  status: SocialAccountStatus;
  status_reason: string | null;
  connected_at: string;
  /** When Clipnera disconnects the account on its own; reconnecting restarts it. */
  expires_at: string | null;
}

export interface SocialConnectionsResponse {
  platforms: SocialPlatformInfo[];
  accounts: ConnectedAccountResponse[];
  max_accounts: number;
  can_schedule: boolean;
  max_schedule_days: number;
  posts_per_day: number;
}

export interface ConnectStartResponse {
  authorize_url: string;
}

export interface ConnectCallbackRequest {
  code: string;
  state: string;
}

export interface DisconnectPreviewResponse {
  account_id: string;
  pending_posts: number;
}

export interface TikTokCreatorInfoResponse {
  nickname: string | null;
  username: string | null;
  avatar_url: string | null;
  privacy_level_options: string[];
  comment_disabled: boolean;
  duet_disabled: boolean;
  stitch_disabled: boolean;
  max_video_post_duration_sec: number | null;
}

/** Instagram's keys in SocialPostTarget.options; validated by backend/social/providers/instagram.py. */
export interface InstagramPostOptions {
  share_to_feed?: boolean;
  /** The Reels cover: milliseconds into the clip. Omitted lets Instagram choose. */
  thumb_offset?: number;
}

export interface SocialPostTarget {
  account_id: string;
  caption: string;
  options: Record<string, unknown>;
}

export interface CreateSocialPostsRequest {
  clip_id: string;
  targets: SocialPostTarget[];
  /** ISO 8601 with an offset; omit to publish now. */
  scheduled_at?: string | null;
  /** Generated once per submit; a retried submit returns the same posts. */
  idempotency_key: string;
}

export interface SocialPostResponse {
  id: string;
  publish_group_id: string;
  account_id: string;
  platform: SocialPlatform;
  account_handle: string | null;
  clip_id: string;
  clip_title: string;
  caption: string;
  platform_options: Record<string, unknown>;
  scheduled_at: string;
  status: SocialPostStatus;
  post_url: string | null;
  error_code: string | null;
  error_message: string | null;
  attempts: number;
  published_at: string | null;
  created_at: string;
}

export interface SocialPostListResponse {
  posts: SocialPostResponse[];
}

export const socialApi = {
  getConnections: () => envelopeRequest<SocialConnectionsResponse>('/social/connections'),
  startConnect: (platform: SocialPlatform) =>
    envelopeRequest<ConnectStartResponse>(`/social/oauth/${platform}/start`, { method: 'POST' }),
  completeConnect: (platform: SocialPlatform, body: ConnectCallbackRequest) =>
    envelopeRequest<ConnectedAccountResponse>(`/social/oauth/${platform}/callback`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  disconnectPreview: (accountId: string) =>
    envelopeRequest<DisconnectPreviewResponse>(`/social/accounts/${accountId}/disconnect-preview`),
  disconnect: (accountId: string) =>
    envelopeRequest<DisconnectPreviewResponse>(`/social/accounts/${accountId}`, { method: 'DELETE' }),
  getTikTokCreatorInfo: (accountId: string) =>
    envelopeRequest<TikTokCreatorInfoResponse>(`/social/accounts/${accountId}/tiktok-creator-info`),
  createPosts: (body: CreateSocialPostsRequest) =>
    envelopeRequest<SocialPostListResponse>('/social/posts', { method: 'POST', body: JSON.stringify(body) }),
  listPosts: (statuses: SocialPostStatus[] = [], limit = 50) => {
    const query = new URLSearchParams({ limit: String(limit) });
    statuses.forEach((status) => query.append('status', status));
    return envelopeRequest<SocialPostListResponse>(`/social/posts?${query.toString()}`);
  },
  cancelPost: (postId: string) =>
    envelopeRequest<SocialPostResponse>(`/social/posts/${postId}/cancel`, { method: 'POST' }),
};

export interface DataDeletionStatusResponse {
  confirmation_code: string;
  platform: SocialPlatform;
  completed: boolean;
  accounts_deleted: number;
  requested_at: string;
}

/** Public: the status page Meta links users to after a data deletion request. */
export async function getDataDeletionStatus(code: string): Promise<DataDeletionStatusResponse> {
  const res = await fetch(`${API_BASE}/api/v1/social/webhooks/data-deletion/${encodeURIComponent(code)}`);
  const body = (await res.json().catch(() => ({}))) as ApiEnvelope<DataDeletionStatusResponse> & { message?: string };
  if (!res.ok || !body.data) throw new Error(body.message || 'Deletion request not found');
  return body.data;
}

export type FeatureFlagKey =
  | 'social_publishing'
  | 'social_publishing.youtube'
  | 'social_publishing.tiktok'
  | 'social_publishing.instagram'
  | 'social_publishing.x'
  | 'video_upload'
  | 'broll_studio'
  | 'broll_studio.cutaways'
  | 'broll_studio.reels'
  | 'broll_studio.ai_shots'
  | 'broll_studio.reels.footage'
  | 'broll_studio.reels.footage.opus_director'
  | 'agent_editor'
  | 'referral_program';

export interface FeatureFlagsResponse {
  flags: Record<FeatureFlagKey, boolean>;
}

export interface AdminFeatureFlagResponse {
  key: FeatureFlagKey;
  label: string;
  description: string;
  parent: FeatureFlagKey | null;
  /** The switch as set; `effective` is false while the parent is off. */
  enabled: boolean;
  effective: boolean;
  updated_at: string | null;
  /** Emails the flag is on for even while it's off (a staged rollout). */
  test_users: string[];
}

export interface AdminFeatureFlagListResponse {
  flags: AdminFeatureFlagResponse[];
}

/** Mirrors NotificationKind in backend/notifications/model.py. */
export type InAppNotificationKind =
  | 'pipeline_completed' | 'pipeline_failed' | 'payment_approved' | 'reel_ready' | 'reel_failed'
  | 'social_expiring' | 'social_expired' | 'referral_reward' | 'referral_update';

export interface InAppNotificationResponse {
  id: string;
  kind: InAppNotificationKind;
  title: string;
  message: string;
  project_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface InAppNotificationListResponse {
  notifications: InAppNotificationResponse[];
}

export const notificationsApi = {
  list: (limit = 30) => envelopeRequest<InAppNotificationListResponse>(`/notifications?limit=${limit}`),
  markAllRead: () => envelopeRequest<InAppNotificationListResponse>('/notifications/read-all', { method: 'POST' }),
  clear: () => envelopeRequest<InAppNotificationListResponse>('/notifications', { method: 'DELETE' }),
  /** Pushes each notification as it is created. Missed ones come back via list(). */
  subscribe: (onNotification: (notification: InAppNotificationResponse) => void, onError: (err: Error) => void) =>
    subscribeEvents<InAppNotificationResponse>('/notifications/stream', onNotification, onError),
};

/** How the AI editor is doing over the last ``days`` (backend brain/schema.py RolloutMetrics). */
export interface RolloutMetrics {
  days: number;
  turns: number;
  plans: number;
  plans_approved: number;
  ai_steps: number;
  ai_steps_undone: number;
  /** Share of AI steps a person undid. */
  undo_rate: number;
  cost_per_turn_usd: number;
  spend: Record<string, { calls: number; usd: number }>;
}

export const adminAiEditorApi = {
  metrics: (days = 7) => envelopeRequest<RolloutMetrics>(`/admin/ai-editor/metrics?days=${days}`),
};

export const featuresApi = {
  get: () => envelopeRequest<FeatureFlagsResponse>('/features'),
};

export const adminFeaturesApi = {
  list: () => envelopeRequest<AdminFeatureFlagListResponse>('/admin/features'),
  set: (key: FeatureFlagKey, enabled: boolean) =>
    envelopeRequest<AdminFeatureFlagListResponse>(`/admin/features/${encodeURIComponent(key)}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  /** Turns a flag on (or back off) for one user while it stays off for everyone else. */
  setTestUser: (key: FeatureFlagKey, email: string, allowed: boolean) =>
    envelopeRequest<AdminFeatureFlagListResponse>(`/admin/features/${encodeURIComponent(key)}/users`, {
      method: 'PUT',
      body: JSON.stringify({ email, allowed }),
    }),
};

export interface AdminSocialPlatformStats {
  platform: SocialPlatform;
  accounts: Partial<Record<SocialAccountStatus, number>>;
  posts: Partial<Record<SocialPostStatus, number>>;
  success_rate: number | null;
}

export interface AdminSocialFailure {
  post_id: string;
  platform: SocialPlatform;
  account_handle: string | null;
  user_email: string;
  error_code: string | null;
  error_message: string | null;
  attempts: number;
  failed_at: string;
}

export interface AdminSocialOverviewResponse {
  window_days: number;
  platforms: AdminSocialPlatformStats[];
  quota: Record<string, Record<string, number>>;
  recent_failures: AdminSocialFailure[];
}

export interface AdminSocialAccountResponse {
  id: string;
  platform: SocialPlatform;
  handle: string | null;
  display_name: string | null;
  follower_count: number | null;
  status: SocialAccountStatus;
  status_reason: string | null;
  user_id: string;
  user_email: string;
  connected_at: string;
}

export interface AdminSocialAccountListResponse {
  accounts: AdminSocialAccountResponse[];
}

export const adminSocialApi = {
  getOverview: (days = 7) => envelopeRequest<AdminSocialOverviewResponse>(`/admin/social/overview?days=${days}`),
  listAccounts: (params: { q?: string; limit?: number; offset?: number } = {}) =>
    envelopeRequest<AdminSocialAccountListResponse>(`/admin/social/accounts${queryString(params)}`),
  forceDisconnect: (accountId: string) =>
    envelopeRequest<DisconnectPreviewResponse>(`/admin/social/accounts/${accountId}/disconnect`, { method: 'POST' }),
};

// -- Direct video upload (backend uploads/) ------------------------------------
// Mirrors backend/uploads/schema.py. The browser sends the file straight to S3
// in parts; the API only signs the parts and stitches them.

export type VideoContentType = 'video/mp4' | 'video/quicktime' | 'video/webm' | 'video/x-matroska';

export interface VideoUploadInitRequest {
  filename: string;
  content_type: VideoContentType;
  size_bytes: number;
  duration_seconds?: number | null;
}

export interface VideoUploadInitResponse {
  project_id: string;
  upload_id: string;
  part_size: number;
  part_urls: string[];
}

export interface UploadedPart {
  part_number: number;
  etag: string;
}

export interface VideoUploadCompleteRequest {
  upload_id: string;
  parts: UploadedPart[];
  /** Started by the server once the upload is ready. */
  pipeline?: PipelineStartRequest;
}

export interface VideoUploadAbortRequest {
  upload_id: string;
}

export interface VideoUploadCompleteResponse {
  project_id: string;
  status: string;
}

export const VIDEO_UPLOAD_TYPES: readonly VideoContentType[] = [
  'video/mp4',
  'video/quicktime',
  'video/webm',
  'video/x-matroska',
];

const UPLOAD_CONCURRENCY = 4;
const UPLOAD_PART_ATTEMPTS = 3;

export interface VideoUploadOptions {
  /** Read from the file's metadata so an over-long video is refused before upload. */
  durationSeconds?: number;
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
  /** Run to start once the upload is ready. */
  pipeline?: PipelineStartRequest;
}

/** PUTs one part and resolves its ETag; `onBytes` reports bytes sent so far for this part. */
function putPart(url: string, body: Blob, onBytes: (sent: number) => void, signal?: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', url);
    xhr.upload.onprogress = (event) => onBytes(event.loaded);
    xhr.onload = () => {
      // S3's bucket CORS must expose the ETag header for this to be readable.
      const etag = xhr.getResponseHeader('ETag');
      if (xhr.status >= 200 && xhr.status < 300 && etag) resolve(etag);
      else reject(new Error(`Part upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'));
    signal?.addEventListener('abort', () => xhr.abort(), { once: true });
    xhr.send(body);
  });
}

async function putPartWithRetry(url: string, body: Blob, onBytes: (sent: number) => void, signal?: AbortSignal) {
  for (let attempt = 1; ; attempt += 1) {
    try {
      return await putPart(url, body, onBytes, signal);
    } catch (err) {
      onBytes(0);
      if (signal?.aborted || attempt >= UPLOAD_PART_ATTEMPTS) throw err;
      await new Promise((r) => setTimeout(r, 1000 * 2 ** (attempt - 1)));
    }
  }
}

export const uploadApi = {
  initVideo: (payload: VideoUploadInitRequest) =>
    envelopeRequest<VideoUploadInitResponse>('/uploads/video/init', { method: 'POST', body: JSON.stringify(payload) }),
  completeVideo: (projectId: string, payload: VideoUploadCompleteRequest) =>
    envelopeRequest<VideoUploadCompleteResponse>(`/uploads/video/${projectId}/complete`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  abortVideo: (projectId: string, payload: VideoUploadAbortRequest) =>
    envelopeRequest<null>(`/uploads/video/${projectId}/abort`, { method: 'POST', body: JSON.stringify(payload) }),

  /**
   * Uploads a video file end to end and returns its project id. The project is
   * ready for the pipeline once `clipApi` progress for it reports `done`.
   */
  async uploadVideo(file: File, options: VideoUploadOptions = {}): Promise<string> {
    const { durationSeconds, onProgress, signal, pipeline } = options;
    const init = await uploadApi.initVideo({
      filename: file.name,
      content_type: file.type as VideoContentType,
      size_bytes: file.size,
      duration_seconds: durationSeconds ?? null,
    });
    const sent = new Array<number>(init.part_urls.length).fill(0);
    const report = () => onProgress?.(Math.min(99, (sent.reduce((a, b) => a + b, 0) / file.size) * 100));
    const parts: UploadedPart[] = [];
    let next = 0;

    const worker = async () => {
      while (next < init.part_urls.length) {
        const index = next++;
        const start = index * init.part_size;
        const blob = file.slice(start, Math.min(start + init.part_size, file.size));
        const etag = await putPartWithRetry(
          init.part_urls[index],
          blob,
          (bytes) => {
            sent[index] = bytes;
            report();
          },
          signal,
        );
        parts.push({ part_number: index + 1, etag });
      }
    };

    try {
      await Promise.all(Array.from({ length: Math.min(UPLOAD_CONCURRENCY, init.part_urls.length) }, worker));
      await uploadApi.completeVideo(init.project_id, { upload_id: init.upload_id, parts, ...(pipeline ? { pipeline } : {}) });
    } catch (err) {
      await uploadApi.abortVideo(init.project_id, { upload_id: init.upload_id }).catch(() => undefined);
      throw err;
    }
    onProgress?.(100);
    return init.project_id;
  },
};

// -- B-roll library admin (backend broll/) --------------------------------------
// Mirrors backend/broll/schema.py.

export type BrollAssetStatus = 'ingesting' | 'live' | 'blocked' | 'taken_down' | 'failed';

export interface BrollAssetResponse {
  id: string;
  kind: string;
  source: string;
  source_id: string;
  source_url: string | null;
  title: string;
  tags: string[];
  duration_s: number;
  width: number;
  height: number;
  orientation: string;
  quality_score: number;
  status: BrollAssetStatus;
  status_reason: string | null;
  license_code: string | null;
  attribution_text: string | null;
  thumb_url: string | null;
  proxy_url: string | null;
  created_at: string;
}

export interface BrollAssetListResponse {
  items: BrollAssetResponse[];
  total: number;
}

export interface BrollIngestRequest {
  query: string;
  per_source?: number;
  sources?: string[] | null;
}

export interface BrollIngestResponse {
  query: string;
  queued: boolean;
}

export interface BrollStatusRequest {
  status: 'live' | 'blocked' | 'taken_down';
  reason?: string | null;
}

export const adminBrollApi = {
  listAssets: (params: { q?: string; status?: BrollAssetStatus; limit?: number; offset?: number } = {}) =>
    envelopeRequest<BrollAssetListResponse>(`/admin/broll/assets${queryString(params)}`),
  setStatus: (assetId: string, payload: BrollStatusRequest) =>
    envelopeRequest<BrollAssetResponse>(`/admin/broll/assets/${assetId}/status`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  ingest: (payload: BrollIngestRequest) =>
    envelopeRequest<BrollIngestResponse>('/admin/broll/ingest', { method: 'POST', body: JSON.stringify(payload) }),
};

// -- Clip B-roll cutaways (backend broll/route.py) --------------------------------
// Mirrors BrollPreview, BrollPlacementResponse, ClipBrollResponse, BrollPlacementUpdate.

export interface BrollPreview {
  id: string;
  title: string;
  duration_s: number;
  thumb_url: string | null;
  proxy_url: string | null;
  attribution_text: string | null;
}

export interface BrollPlacement {
  index: number;
  start: number;
  end: number;
  query: string;
  score: number;
  generating: boolean;
  asset: BrollPreview | null;
  alternates: BrollPreview[];
}

export interface ClipBrollResponse {
  clip_id: string;
  placements: BrollPlacement[];
}

export interface BrollPlacementUpdate {
  asset_id?: string | null;
  remove?: boolean;
}

export const brollApi = {
  getClip: (clipId: string) => envelopeRequest<ClipBrollResponse>(`/broll/clips/${clipId}`),
  updatePlacement: (clipId: string, index: number, payload: BrollPlacementUpdate) =>
    envelopeRequest<ClipBrollResponse>(`/broll/clips/${clipId}/placements/${index}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  search: (q: string, minDuration = 0) =>
    envelopeRequest<BrollPreview[]>(`/broll/search${queryString({ q, min_duration: minDuration })}`),
  /** Pro: an AI-generated shot for this cutaway (charged now, refunded if it fails). */
  generatePlacement: (clipId: string, index: number, shot?: string) =>
    envelopeRequest<ClipBrollResponse>(`/broll/clips/${clipId}/placements/${index}/generate`, {
      method: 'POST',
      body: JSON.stringify({ shot: shot || null }),
    }),
};

/** Mirrors backend GenerateShotRequest. */
export interface GenerateShotRequest {
  shot?: string | null;
}

/** Credits one AI-generated shot costs; mirrors backend VEO_SCENE_CREDITS. */
export const AI_SHOT_CREDITS = 120;

// -- Reels from images (backend reels/) -------------------------------------------
// Mirrors backend/reels/schema.py.

export type ReelStyle = 'clean' | 'bold' | 'neon' | 'warm';
export type ReelStatus = 'draft' | 'planning' | 'ready' | 'rendering' | 'done' | 'failed';
export type ReelSceneKind = 'image' | 'broll' | 'text';
export type ReelAssetType =
  | 'image/jpeg' | 'image/png' | 'image/webp'
  | 'audio/mpeg' | 'audio/wav' | 'audio/x-wav' | 'audio/mp4' | 'audio/x-m4a' | 'audio/webm';

export interface ReelCreateRequest {
  title: string;
  topic?: string | null;
  script?: string | null;
  language?: string;
  style?: ReelStyle;
}

export interface ReelAssetFile {
  filename: string;
  content_type: ReelAssetType;
  size_bytes: number;
}

export interface ReelAssetUpload {
  key: string;
  url: string;
  content_type: string;
}

export interface ReelScene {
  index: number;
  start: number;
  end: number;
  text: string;
  kind: ReelSceneKind;
  image_index: number | null;
  headline: string;
  query: string;
  generating: boolean;
  image_url: string | null;
  footage: BrollPreview | null;
  alternates: BrollPreview[];
}

export interface ReelResponse {
  id: string;
  title: string;
  status: ReelStatus;
  topic: string | null;
  script: string | null;
  language: string;
  style: string;
  image_urls: string[];
  has_voiceover: boolean;
  duration_s: number;
  scenes: ReelScene[];
  credits_estimate: number;
  credits_charged: number;
  output_url: string | null;
  error: string | null;
  created_at: string;
}

export interface ReelSummary {
  id: string;
  title: string;
  status: ReelStatus;
  duration_s: number;
  created_at: string;
  /** The reel's first image, shown as its cover; null without images. */
  cover_url: string | null;
}

export interface ReelSceneUpdate {
  kind: ReelSceneKind;
  image_index?: number | null;
  asset_id?: string | null;
  headline?: string | null;
}

export const REEL_IMAGE_TYPES: readonly ReelAssetType[] = ['image/jpeg', 'image/png', 'image/webp'];
export const REEL_AUDIO_TYPES: readonly ReelAssetType[] = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/x-m4a', 'audio/webm'];

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });

export const reelsApi = {
  create: (payload: ReelCreateRequest) => envelopeRequest<ReelResponse>('/reels', post(payload)),
  list: () => envelopeRequest<ReelSummary[]>('/reels'),
  get: (reelId: string) => envelopeRequest<ReelResponse>(`/reels/${reelId}`),
  initAssets: (reelId: string, files: ReelAssetFile[]) =>
    envelopeRequest<{ uploads: ReelAssetUpload[] }>(`/reels/${reelId}/assets/init`, post({ files })),
  completeAssets: (reelId: string, keys: string[]) =>
    envelopeRequest<ReelResponse>(`/reels/${reelId}/assets/complete`, post({ keys })),
  plan: (reelId: string) => envelopeRequest<ReelResponse>(`/reels/${reelId}/plan`, post({})),
  updateScene: (reelId: string, index: number, payload: ReelSceneUpdate) =>
    envelopeRequest<ReelResponse>(`/reels/${reelId}/scenes/${index}`, post(payload)),
  render: (reelId: string) => envelopeRequest<ReelResponse>(`/reels/${reelId}/render`, post({})),
  generateScene: (reelId: string, index: number, shot?: string) =>
    envelopeRequest<ReelResponse>(`/reels/${reelId}/scenes/${index}/generate`, post({ shot: shot || null })),

  /** Uploads images and an optional voiceover straight to S3, then attaches them to the reel. */
  async uploadAssets(reelId: string, files: File[]): Promise<ReelResponse> {
    const { uploads } = await reelsApi.initAssets(
      reelId,
      files.map((f) => ({ filename: f.name, content_type: f.type as ReelAssetType, size_bytes: f.size })),
    );
    await Promise.all(
      uploads.map(async (upload, i) => {
        const res = await fetch(upload.url, { method: 'PUT', body: files[i], headers: { 'Content-Type': upload.content_type } });
        if (!res.ok) throw new Error(`Upload of ${files[i].name} failed (${res.status})`);
      }),
    );
    return reelsApi.completeAssets(reelId, uploads.map((u) => u.key));
  },
};

// -- Channel intro (backend creator_intro/) --------------------------------------------
// Mirrors backend/creator_intro/schema.py.

export type IntroPlatform = 'youtube' | 'tiktok' | 'instagram' | 'twitch' | 'x' | 'facebook' | 'kick' | 'linkedin' | 'other';
export type IntroTheme = 'auto' | 'light' | 'dark';
export type IntroStatus = 'draft' | 'rendering' | 'ready' | 'failed';
export type IntroAvatarType = 'image/jpeg' | 'image/png' | 'image/webp';
/** Rendition names: 9:16, 16:9 and 1:1. */
export type IntroRendition = '9x16' | '16x9' | '1x1';

export interface CreatorIntroSaveRequest {
  platform: IntroPlatform;
  niche?: string | null;
  channel_name: string;
  handle?: string | null;
  about: string;
  /** Empty lets the AI write the line from `about`. */
  tagline?: string | null;
  theme: IntroTheme;
  /** A key from `uploadAvatar`; omitted keeps the current picture. */
  avatar_key?: string | null;
  remove_avatar?: boolean;
  enabled: boolean;
}

export interface CreatorIntroAvatarUpload {
  key: string;
  url: string;
  content_type: string;
}

export interface CreatorIntro {
  status: IntroStatus;
  platform: IntroPlatform;
  niche: string | null;
  channel_name: string;
  handle: string | null;
  about: string;
  tagline: string | null;
  theme: IntroTheme;
  theme_used: 'light' | 'dark' | null;
  avatar_url: string | null;
  enabled: boolean;
  /** Empty until the first render finishes. */
  preview_urls: Partial<Record<IntroRendition, string>>;
  duration_s: number;
  error: string | null;
  updated_at: string;
}

export const INTRO_AVATAR_TYPES: readonly IntroAvatarType[] = ['image/jpeg', 'image/png', 'image/webp'];

export const creatorIntroApi = {
  /** null until the user saves one; readable on every plan. */
  get: () => envelopeRequest<CreatorIntro | null>('/creator-intro'),
  save: (payload: CreatorIntroSaveRequest) =>
    envelopeRequest<CreatorIntro>('/creator-intro', { method: 'PUT', body: JSON.stringify(payload) }),
  render: () => envelopeRequest<CreatorIntro>('/creator-intro/render', post({})),

  /** Uploads the picture straight to S3; pass the returned key as `avatar_key` when saving. */
  async uploadAvatar(file: File): Promise<string> {
    const upload = await envelopeRequest<CreatorIntroAvatarUpload>(
      '/creator-intro/avatar',
      post({ content_type: file.type as IntroAvatarType, size_bytes: file.size }),
    );
    const res = await fetch(upload.url, { method: 'PUT', body: file, headers: { 'Content-Type': upload.content_type } });
    if (!res.ok) throw new Error(`Upload of ${file.name} failed (${res.status})`);
    return upload.key;
  },
};

// -- Reels from raw footage (backend edit_engine/) -------------------------------------
// Mirrors backend/edit_engine/schema.py.

export type EditScriptMode = 'auto' | 'spoken' | 'voiceover' | 'onscreen' | 'direction';
/** How the planner actually used the script; `none` when there was none. */
export type EditResolvedScriptMode = 'none' | 'spoken' | 'voiceover' | 'onscreen' | 'direction';
export type EditTargetSeconds = 0 | 15 | 30 | 45 | 60 | 90;
export type EditStatus = 'draft' | 'analyzing' | 'planned' | 'rendering' | 'done' | 'failed';
export type EditLayout = 'talking' | 'voiceover' | 'montage';
export type EditSourceType =
  | 'video/mp4' | 'video/quicktime' | 'video/webm'
  | 'image/jpeg' | 'image/png' | 'image/webp'
  | 'audio/mpeg' | 'audio/wav' | 'audio/x-wav' | 'audio/mp4' | 'audio/x-m4a' | 'audio/webm';
export type EditChangeOp =
  | 'set_script_mode' | 'restore_line' | 'remove_line' | 'set_hook' | 'set_music' | 'set_look'
  | 'set_caption_style' | 'set_length' | 'remove_pop' | 'skip_missing_lines';

export interface EditCreateRequest {
  title?: string;
  script?: string | null;
  script_mode?: EditScriptMode;
  intent?: string | null;
  language?: string;
  caption_style?: string;
  target_seconds?: EditTargetSeconds;
  autopilot?: boolean;
}

export interface EditSourceFile {
  filename: string;
  content_type: EditSourceType;
  size_bytes: number;
  duration_s?: number | null;
}

export interface EditUpload {
  key: string;
  url: string;
  content_type: string;
}

export interface EditChange {
  op: EditChangeOp;
  value?: string | null;
}

export interface EditSourceResponse {
  key: string;
  kind: 'video' | 'image' | 'voice';
  name: string;
  duration_s: number;
  url: string | null;
}

export interface EditLine {
  id: string;
  text: string;
}

export interface EditMusicResponse {
  id: string;
  title: string;
  artist: string;
  licence: string;
  credit_text: string;
  url: string | null;
}

export interface EditPlanResponse {
  content_type: string;
  layout: EditLayout;
  script_mode: EditResolvedScriptMode;
  script_lines_found: number;
  script_lines_total: number;
  missing_lines: string[];
  skip_missing: boolean;
  removed_lines: EditLine[];
  hook: string;
  title: string;
  look: string;
  caption_style: string;
  music: EditMusicResponse | null;
  music_mood: string;
  broll_count: number;
  own_broll_count: number;
  pop_count: number;
  director_model: string;
  caption: string;
  hashtags: string[];
}

export interface EditPicture {
  kind: 'video' | 'image' | 'card';
  at: number;
  dur: number;
  src: number | null;
  source_start: number | null;
  source_end: number | null;
  zoom: number | null;
  crop_x: number | null;
  text: string | null;
}

export interface EditVoicePiece {
  src: number;
  source_start: number;
  source_end: number;
  at: number;
}

export interface EditText {
  kind: 'hook' | 'pop' | 'line';
  text: string;
  at: number;
  dur: number;
}

export interface EditWord {
  word: string;
  start: number;
  end: number;
}

export interface EditTimelineMusic {
  track_id: string;
  offset: number;
  gain_db: number;
  duck: boolean;
}

export interface EditTimelineResponse {
  duration: number;
  width: number;
  height: number;
  look: string;
  picture: EditPicture[];
  voice: EditVoicePiece[];
  voiceover_src: number | null;
  texts: EditText[];
  words: EditWord[];
  music: EditTimelineMusic | null;
}

export interface EditResponse {
  id: string;
  title: string;
  status: EditStatus;
  progress: string | null;
  script: string | null;
  script_mode: EditScriptMode;
  intent: string | null;
  language: string;
  caption_style: string;
  target_seconds: number;
  autopilot: boolean;
  sources: EditSourceResponse[];
  raw_seconds: number;
  duration_s: number;
  plan: EditPlanResponse | null;
  timeline: EditTimelineResponse | null;
  credits_estimate: number;
  credits_charged: number;
  renders: number;
  replans_left: number;
  chat_edits_left: number;
  output_url: string | null;
  music_credit: string | null;
  error: string | null;
  created_at: string;
}

export interface EditSummary {
  id: string;
  title: string;
  status: EditStatus;
  duration_s: number;
  created_at: string;
}

export interface EditLimitsResponse {
  max_raw_seconds: number;
  max_files: number;
  max_output_seconds: number;
  output_height: number;
  opus_director: boolean;
}

export interface MusicTrackResponse {
  id: string;
  title: string;
  artist: string;
  source: string;
  source_url: string;
  licence: string;
  licence_url: string;
  credit_text: string;
  mood: string;
  energy: number;
  bpm: number | null;
  duration_s: number;
  status: 'live' | 'pulled';
  used_by: number;
  created_at: string;
}

export const EDIT_VIDEO_TYPES: readonly EditSourceType[] = ['video/mp4', 'video/quicktime', 'video/webm'];
export const EDIT_IMAGE_TYPES: readonly EditSourceType[] = ['image/jpeg', 'image/png', 'image/webp'];
export const EDIT_AUDIO_TYPES: readonly EditSourceType[] = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/x-m4a', 'audio/webm'];
/** Mirrors LOOKS / LOOK_LABELS in backend/edit_engine/looks.py. */
export const EDIT_LOOKS: Record<string, string> = {
  natural: 'Natural', clean_bright: 'Clean & bright', warm_film: 'Warm film', teal_orange: 'Teal & orange',
  moody: 'Moody', vivid: 'Vivid', bw_punch: 'Black & white',
};
/** Mirrors MOODS in backend/edit_engine/music.py. */
export const EDIT_MOODS = ['upbeat', 'chill', 'lofi', 'inspiring', 'cinematic', 'dramatic', 'emotional', 'funny', 'energetic', 'corporate'] as const;

export const editsApi = {
  limits: () => envelopeRequest<EditLimitsResponse>('/edits/limits'),
  create: (payload: EditCreateRequest) => envelopeRequest<EditResponse>('/edits', post(payload)),
  list: () => envelopeRequest<EditSummary[]>('/edits'),
  get: (editId: string) => envelopeRequest<EditResponse>(`/edits/${editId}`),
  initSources: (editId: string, files: EditSourceFile[]) =>
    envelopeRequest<{ uploads: EditUpload[] }>(`/edits/${editId}/sources/init`, post({ files })),
  completeSources: (editId: string, keys: string[]) =>
    envelopeRequest<EditResponse>(`/edits/${editId}/sources/complete`, post({ keys })),
  analyze: (editId: string) => envelopeRequest<EditResponse>(`/edits/${editId}/analyze`, post({})),
  replan: (editId: string) => envelopeRequest<EditResponse>(`/edits/${editId}/plan`, post({})),
  change: (editId: string, changes: EditChange[]) =>
    envelopeRequest<EditResponse>(`/edits/${editId}/changes`, post({ changes })),
  chat: (editId: string, message: string) => envelopeRequest<EditResponse>(`/edits/${editId}/chat`, post({ message })),
  render: (editId: string) => envelopeRequest<EditResponse>(`/edits/${editId}/render`, post({})),

  /** Uploads footage, photos and a voiceover straight to S3 (with per-file progress), then attaches them. */
  async uploadSources(
    editId: string,
    files: { file: File; durationS: number | null }[],
    onProgress?: (index: number, fraction: number) => void,
  ): Promise<EditResponse> {
    const { uploads } = await editsApi.initSources(
      editId,
      files.map(({ file, durationS }) => ({
        filename: file.name, content_type: file.type as EditSourceType, size_bytes: file.size, duration_s: durationS,
      })),
    );
    await Promise.all(uploads.map((upload, i) => putWithProgress(upload, files[i].file, (f) => onProgress?.(i, f))));
    return editsApi.completeSources(editId, uploads.map((u) => u.key));
  },
};

function putWithProgress(upload: EditUpload, file: File, onProgress: (fraction: number) => void): Promise<void> {
  // XHR rather than fetch: only XHR reports upload progress, which matters for large videos.
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', upload.url);
    xhr.setRequestHeader('Content-Type', upload.content_type);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => (xhr.status < 300 ? resolve() : reject(new Error(`Upload of ${file.name} failed (${xhr.status})`)));
    xhr.onerror = () => reject(new Error(`Upload of ${file.name} failed`));
    xhr.send(file);
  });
}

export const adminMusicApi = {
  list: () => envelopeRequest<MusicTrackResponse[]>('/admin/music'),
  /** Adds a free-licence track; the form carries the licence record (see backend edit_engine/route.py). */
  add: (form: FormData) => envelopeRequest<MusicTrackResponse>('/admin/music', { method: 'POST', body: form }),
  setStatus: (trackId: string, status: 'live' | 'pulled') =>
    envelopeRequest<MusicTrackResponse>(`/admin/music/${trackId}/status`, post({ status })),
};

// --- Editor (backend editor/schema.py) ----------------------------------------

export type EditorAspect = '9:16' | '1:1' | '4:5' | '16:9';

export interface EditorProjectCreate {
  title?: string;
  aspect?: EditorAspect;
}

export interface EditorProjectSummary {
  id: string;
  title: string;
  version: number;
  /** Seconds, for the project list. */
  duration_s: number;
  created_at: string;
  updated_at: string;
}

export interface EditorProjectResponse extends EditorProjectSummary {
  timeline: Timeline;
  /** Asset id -> a signed URL the studio plays and decodes it from; valid for an hour. */
  asset_urls: Record<string, string>;
}

export type EditorAssetType =
  | 'video/mp4' | 'video/quicktime' | 'video/webm'
  | 'image/jpeg' | 'image/png' | 'image/webp' | 'image/gif'
  | 'audio/mpeg' | 'audio/wav' | 'audio/x-wav' | 'audio/mp4' | 'audio/x-m4a' | 'audio/webm' | 'audio/ogg';

export interface EditorAssetInitRequest {
  filename: string;
  content_type: EditorAssetType;
  size_bytes: number;
}

// -- AI editor turns (backend brain/schema.py) ---------------------------------------

export type RouteIntent =
  | 'new_edit' | 'refine_edit' | 'undo' | 'redo' | 'direct_op' | 'question' | 'export_request'
  | 'asset_search' | 'chitchat' | 'unsafe';
export type RoutePath = 'plan' | 'micro' | 'answer' | 'deterministic' | 'refuse';
export type RouteAgent = 'cut' | 'audio' | 'text' | 'color' | 'transitions' | 'curator' | 'reframe' | 'brand';
export type RouteRefKind =
  | 'clip' | 'title' | 'caption' | 'music' | 'effect' | 'transition' | 'step' | 'range' | 'selection' | 'unknown';

/** How the router classified a prompt (brain/route.py RouteDecision). */
export interface RouteDecision {
  intent: RouteIntent;
  path: RoutePath;
  agents: RouteAgent[];
  references: { phrase: string; kind: RouteRefKind }[];
  constraints: {
    targetDurationSec: number | null;
    aspect: '16:9' | '9:16' | '1:1' | '4:5' | null;
    mood: string | null;
    mustKeep: string[];
  };
  complexity: 1 | 2 | 3 | 4 | 5;
  clarify: string | null;
  safety: 'ok' | 'borderline' | 'block';
  preference: string | null;
}

export interface TurnRequest {
  prompt: string;
  /** Ids of the items selected in the studio. */
  selection?: string[];
  /** The playhead, in timeline frames. */
  playhead?: number;
  /** The user's last few prompts, oldest first. */
  recent_turns?: string[];
}

export type TurnKind = 'edit' | 'answer' | 'clarify' | 'choices' | 'plan' | 'plan_needed' | 'refused';
export type PlanStatus = 'proposed' | 'approved' | 'running' | 'paused' | 'done' | 'failed' | 'rejected' | 'stopped';
export type PlanStepStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped';

/** One step of a plan card (backend brain/schema.py PlanCardStep). */
export interface PlanCardStep {
  id: string;
  kind: string;
  intent: string;
  why: string;
  enabled: boolean;
  optional: boolean;
  status: PlanStepStatus;
  credits: number;
  depends_on: string[];
  note: string;
  /** Once done: pass to editorApi.undoStep to undo just this step. */
  undo_step_id: string | null;
}

/** A shot the plan would place, for the dashed preview on the timeline (frames). */
export interface GhostClip {
  at: number;
  end: number;
  label: string;
}

export interface PlanCard {
  id: string;
  status: PlanStatus;
  title: string;
  summary: string;
  result_line: string;
  /** The most this plan can cost, in credits. */
  credits: number;
  credits_charged: number;
  steps: PlanCardStep[];
  assumptions: string[];
  warnings: string[];
  premium: string[];
  ghost: GhostClip[];
  fps: number;
  runner_up_title: string | null;
  error: string | null;
}

export interface PlanPatch {
  enabled?: Record<string, boolean>;
  order?: string[] | null;
}

/** Live events while a plan runs (GET /editor/plans/{id}/stream). */
export type PlanEvent =
  | { event: 'plan.updated'; data: PlanCard }
  | { event: 'agent.step'; data: { step_id: string; status: PlanStepStatus; note: string } }
  | { event: 'op.applied'; data: { version: number; cursor: { author: string; items: string[] } | null } }
  | { event: 'done'; data: { status: PlanStatus } };

export interface TurnChoice {
  id: string;
  label: string;
}

export interface TurnResult {
  kind: TurnKind;
  message: string;
  /** Set when the project changed. */
  version: number | null;
  /** Pass to editorApi.undoStep for this turn's Undo chip. */
  undo_step_id: string | null;
  choices: TurnChoice[];
  /** Chips for a clarifying question; picking one sends it as the next prompt. */
  options: string[];
  plan: PlanCard | null;
  route: RouteDecision | null;
}

/** How far the AI has got understanding one asset of an editor project (backend understanding/). */
export interface MediaAnalysisResponse {
  asset_id: string;
  status: 'pending' | 'running' | 'ready' | 'failed';
  error: string | null;
  updated_at: string;
}

/** Where to PUT the file (sending `content_type`), and the key to add it under with an `add_asset` op. */
export interface EditorAssetUpload {
  key: string;
  url: string;
  content_type: string;
}

export interface EditorOpsRequest {
  /**
   * The project version the ops were made against. An older one is applied on top of the newer
   * changes when they don't clash (409 CONFLICT when a person changed the same field since, or
   * STALE_VERSION when the ops no longer fit).
   */
  base_version: number;
  ops: TimelineOp[];
}

export interface EditorOpsResponse {
  version: number;
  timeline: Timeline;
}

/** A sound effect from Clipnera's own clean-licensed library (backend brain/schema.py LibrarySound). */
export interface LibrarySound {
  id: string;
  name: string;
  tags: string[];
  seconds: number;
  /** Path on the API host, e.g. /static/sfx/pop.wav; see apiUrl. */
  url: string;
  licence: string;
}

export interface SoundSearchResponse {
  results: LibrarySound[];
  count: number;
  has_more: boolean;
}

/** A server render of an editor project (backend brain/schema.py RenderStatus). */
export interface RenderStatus {
  id: string;
  status: 'queued' | 'rendering' | 'done' | 'failed';
  stage: string;
  version: number;
  /** A signed link once done; valid for an hour. */
  download_url: string | null;
  error: string | null;
}

export const rendersApi = {
  start: (projectId: string) => envelopeRequest<RenderStatus>(`/editor/projects/${projectId}/renders`, post({})),
  get: (projectId: string, renderId: string) =>
    envelopeRequest<RenderStatus>(`/editor/projects/${projectId}/renders/${renderId}`),
};

export const soundsApi = {
  search: (params: { q?: string; page?: number; page_size?: number }) =>
    envelopeRequest<SoundSearchResponse>(`/editor/sounds${queryString(params)}`),
};

/** A full URL for a path the API serves directly (static files). */
export const apiUrl = (path: string) => `${API_BASE}${path}`;

/** Something the AI editor learned from the user's corrections (backend brain/schema.py StylePreference). */
export interface StylePreference {
  key: string;
  label: string;
  value: string;
  confidence: number;
  /** Confident enough to shape plans. */
  in_use: boolean;
}

export const styleApi = {
  list: () => envelopeRequest<StylePreference[]>('/editor/style'),
  forget: (key: string) => envelopeRequest<StylePreference[]>(`/editor/style/${encodeURIComponent(key)}`, { method: 'DELETE' }),
};

export const plansApi = {
  get: (planId: string) => envelopeRequest<PlanCard>(`/editor/plans/${planId}`),
  /** Holds the plan's credit ceiling and starts it; 402 INSUFFICIENT_CREDITS when it doesn't fit. */
  approve: (planId: string) => envelopeRequest<PlanCard>(`/editor/plans/${planId}/approve`, post({})),
  reject: (planId: string) => envelopeRequest<PlanCard>(`/editor/plans/${planId}/reject`, post({})),
  edit: (planId: string, patch: PlanPatch) =>
    envelopeRequest<PlanCard>(`/editor/plans/${planId}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  pause: (planId: string) => envelopeRequest<PlanCard>(`/editor/plans/${planId}/pause`, post({})),
  resume: (planId: string) => envelopeRequest<PlanCard>(`/editor/plans/${planId}/resume`, post({})),
  /** Stops for good and keeps every applied step ("Take over"). */
  stop: (planId: string) => envelopeRequest<PlanCard>(`/editor/plans/${planId}/stop`, post({})),
  /** The runner-up as a new proposed plan ("Try the other version"). */
  alternative: (planId: string) => envelopeRequest<PlanCard>(`/editor/plans/${planId}/alternative`, post({})),

  /** Follows a running plan; calls onEvent per server-sent event until the plan finishes or ``signal`` aborts. */
  async stream(planId: string, onEvent: (event: PlanEvent) => void, signal?: AbortSignal): Promise<void> {
    const token = getToken();
    const res = await fetch(`${API_BASE}/api/v1/editor/plans/${planId}/stream`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal,
    });
    if (!res.ok || !res.body) throw new ApiError(`Couldn't follow the plan (${res.status})`, res.status, null);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      let split: number;
      while ((split = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        const name = /^event: (.+)$/m.exec(block)?.[1];
        const data = /^data: (.+)$/m.exec(block)?.[1];
        if (name && data) onEvent({ event: name, data: JSON.parse(data) } as PlanEvent);
      }
    }
  },
};

export const editorApi = {
  create: (payload: EditorProjectCreate) => envelopeRequest<EditorProjectResponse>('/editor/projects', post(payload)),
  /** Opens a footage reel's current edit as a new editor project. */
  openReel: (editId: string) => envelopeRequest<EditorProjectResponse>(`/editor/projects/from-reel/${editId}`, post({})),
  list: () => envelopeRequest<EditorProjectSummary[]>('/editor/projects'),
  get: (projectId: string) => envelopeRequest<EditorProjectResponse>(`/editor/projects/${projectId}`),
  applyOps: (projectId: string, payload: EditorOpsRequest) =>
    envelopeRequest<EditorOpsResponse>(`/editor/projects/${projectId}/ops`, post(payload)),
  /** Undo the last change still in effect (an AI step undoes as one); 409 NOTHING_TO_UNDO when there's none. */
  undo: (projectId: string) => envelopeRequest<EditorOpsResponse>(`/editor/projects/${projectId}/undo`, post({})),
  redo: (projectId: string) => envelopeRequest<EditorOpsResponse>(`/editor/projects/${projectId}/redo`, post({})),
  /** Undo everything one AI step changed, even with later edits on top. */
  undoStep: (projectId: string, stepId: string) =>
    envelopeRequest<EditorOpsResponse>(`/editor/projects/${projectId}/steps/${encodeURIComponent(stepId)}/undo`, post({})),
  /** One prompt from the studio's AI tab. */
  turn: (projectId: string, payload: TurnRequest) =>
    envelopeRequest<TurnResult>(`/editor/projects/${projectId}/turns`, post(payload)),
  /** The AI's analysis of each asset; it starts by itself when an asset is added. */
  analysis: (projectId: string) => envelopeRequest<MediaAnalysisResponse[]>(`/editor/projects/${projectId}/analysis`),
  retryAnalysis: (projectId: string, assetId: string) =>
    envelopeRequest<MediaAnalysisResponse>(
      `/editor/projects/${projectId}/analysis/${encodeURIComponent(assetId)}/retry`, post({}),
    ),
  initAsset: (projectId: string, payload: EditorAssetInitRequest) =>
    envelopeRequest<EditorAssetUpload>(`/editor/projects/${projectId}/assets/init`, post(payload)),

  /** PUTs a file straight to S3, reporting the share sent so far (0-1); resolves with its storage key. */
  uploadAsset(projectId: string, file: File, contentType: EditorAssetType, onProgress?: (share: number) => void): Promise<string> {
    return editorApi.initAsset(projectId, { filename: file.name, content_type: contentType, size_bytes: file.size }).then(
      (upload) => new Promise<string>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', upload.url);
        xhr.setRequestHeader('Content-Type', upload.content_type);
        xhr.upload.onprogress = (event) => event.lengthComputable && onProgress?.(event.loaded / event.total);
        xhr.onload = () => (xhr.status >= 200 && xhr.status < 300
          ? resolve(upload.key)
          : reject(new Error(`Upload of ${file.name} failed (${xhr.status})`)));
        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.send(file);
      }),
    );
  },
};

// -- Welcome form (backend onboarding/) and referrals (backend referral/) ----
// Types live in lib/types.ts and mirror onboarding/schema.py and referral/schema.py.

export const onboardingApi = {
  status: () => envelopeRequest<OnboardingStatusResponse>('/onboarding'),
  complete: (body: OnboardingRequest) =>
    envelopeRequest<OnboardingResponse>('/onboarding', { method: 'POST', body: JSON.stringify(body) }),
};

export const referralApi = {
  mine: () => envelopeRequest<MyReferralsResponse>('/referrals/me'),
  invitedBy: () => envelopeRequest<InvitedByResponse | null>('/referrals/invited-by'),
  validate: (code: string) =>
    envelopeRequest<ValidateCodeResponse>(`/referrals/validate/${encodeURIComponent(code)}`),
};

export const adminReferralApi = {
  list: (params: { status?: string; review_state?: string; q?: string; limit?: number; offset?: number } = {}) =>
    envelopeRequest<AdminReferralResponse[]>(`/admin/referrals${queryString(params)}`),
  approve: (id: string) =>
    envelopeRequest<null>(`/admin/referrals/${encodeURIComponent(id)}/approve`, { method: 'POST' }),
  void: (id: string, body: AdminReferralVoidRequest) =>
    envelopeRequest<null>(`/admin/referrals/${encodeURIComponent(id)}/void`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  settings: () => envelopeRequest<AdminReferralSettingsResponse>('/admin/referrals/settings'),
  updateSettings: (body: ReferralRules) =>
    envelopeRequest<AdminReferralSettingsResponse>('/admin/referrals/settings', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
};
