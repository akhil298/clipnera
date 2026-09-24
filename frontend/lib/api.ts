import { BrandKit, PipelineProgressEvent, PipelineStatus, ViralClip, CaptionConfig, TranscriptSegment, WordTimestamp } from '@/lib/types';
import { getToken, clearAuth, setAuth } from '@/lib/auth';
import { emojiForKeyword } from '@/lib/data/emojiCatalog.generated';

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
}

export interface ForgotPayload {
  email: string;
}

export interface ResetPayload {
  token: string;
  new_password: string;
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
  plan: string;
  ai_credits_minutes_remaining: number;
  ai_credits_total: number;
  active_workspace_id: string | null;
  providers: string[];
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
  start_time: number;
  end_time: number;
  duration_seconds: number;
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
  }>;
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
  }>;
  platforms: string[];
  total_exported: number;
}

const DEFAULT_CAPTION_CONFIG: CaptionConfig = {
  preset: 'bold_captions',
  fontSize: 48,
  fontFamily: 'Inter, sans-serif',
  textColor: '#ffffff',
  highlightColor: '#fbbf24',
  secondaryHighlightColor: '#f8fafc',
  hasBgBox: true,
  bgBoxColor: '#000000',
  uppercase: true,
  animation: 'pop',
  animationSpeed: 1.0,
  positionY: 78,
   emojisEnabled: true,
  emojiCollection: 'skull_fire',
  maxWordsPerLine: 6,
  shadowIntensity: 0.8,
  titleFontSize: 56,
  titlePositionY: 7,
};

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
  const clipStart = clip.start_time || 0;
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

export function mapBackendClip(clip: BackendClip): ViralClip {
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
    aspectRatio: '9:16',
    layoutMode: 'single_speaker',
    keywords: [],
    emojiHighlights: [],
    autoBrollKeywords: [],
    transcriptSegments: buildTranscriptSegments(clip),
    bRollOverlays: [],
    soundEffects: [],
    captionConfig: DEFAULT_CAPTION_CONFIG,
    // Off by default: the render pipeline applies no zoom, so leaving it on
    // made the preview show motion the exported file never has.
    autoZoom: { enabled: false, frequency: 'subtle', scale: 1.1 },
    autoReframe: { mode: 'center', speakerCropX: 0.5, speakerSmoothing: 0.5 },
    socialOptimization: {
      hashtags: [],
      optimizedHooks: [],
      targetPlatforms: ['tiktok', 'instagram', 'youtube'],
      postStatus: 'draft',
    },
    thumbnailTime: 1.0,
  };
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
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
  });

  if (res.status === 401) {
    handleUnauthorized();
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = (data as { message?: string })?.message ?? 'Something went wrong';
    if (res.status === 401) {
      throw new Error(`Unauthorized: ${message}`);
    }
    throw new Error(message);
  }
  return data as T;
}

export const authApi = {
  login: (payload: LoginPayload) =>
    request<TokenResponse>('/auth/login', payload).then((data) => {
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
};

export const workspaceApi = {
  list: () => authedRequest<WorkspaceResponse[]>('/workspaces'),
  create: (name: string) => authedRequest<WorkspaceResponse>('/workspaces', {
    method: 'POST',
    body: JSON.stringify({ name }),
  }),
  get: (id: string) => authedRequest<WorkspaceResponse>(`/workspaces/${id}`),
  listMembers: (workspaceId: string) => authedRequest<WorkspaceMemberResponse[]>(`/workspaces/${workspaceId}/members`),
  inviteMember: (workspaceId: string, email: string, role: string) => authedRequest<WorkspaceMemberResponse>(`/workspaces/${workspaceId}/members`, {
    method: 'POST',
    body: JSON.stringify({ email, role }),
  }),
  createAndAddMember: (workspaceId: string, email: string, password: string, fullName: string, role: string) => authedRequest<WorkspaceMemberResponse>(`/workspaces/${workspaceId}/members/create`, {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name: fullName, role }),
  }),
  updateMemberRole: (workspaceId: string, memberId: string, role: string) => authedRequest<WorkspaceMemberResponse>(`/workspaces/${workspaceId}/members/${memberId}`, {
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
  downloadYoutube: (url: string, formatId?: string) => authedRequest<Record<string, any>>('/clips/download', {
    method: 'POST',
    body: JSON.stringify({ url, format_id: formatId }),
  }),
  exportProject: (projectId: string, maxClips?: number, captionConfig?: CaptionConfig) => authedRequest<SocialExportResponse>(`/pipeline/export/${projectId}`, {
    method: 'POST',
    body: JSON.stringify({
      platforms: ['tiktok'],
      max_clips: maxClips,
      burn_subtitles: true,
      enable_emoji: true,
      watermark_enabled: true,
      style_type: captionConfig?.preset || 'bold_captions',
      custom_config: captionConfig ? {
        font_size: captionConfig.fontSize,
        font_family: captionConfig.fontFamily,
        font_color: captionConfig.textColor,
        highlight_color: captionConfig.highlightColor,
        secondary_highlight_color: captionConfig.secondaryHighlightColor,
        has_bg_box: captionConfig.hasBgBox,
        bg_box_color: captionConfig.bgBoxColor,
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
 * Shapes to render, when the user has picked some.
 *
 * Left undefined the backend decides from the video's content category -- a
 * gaming clip is cut 9:16 only, a tutorial 9:16 and 16:9. Sending all four
 * regardless, as this used to, quadrupled render time to produce files nothing
 * read. Only pass a list when the user actually chose one.
 */
export const pipelineApi = {
  start: (
    projectId: string,
    steps: string[] = DEFAULT_PIPELINE_STEPS,
    audioConfig: Record<string, any> = {},
    outputAspectRatios?: string[],
  ) =>
    authedRequest<{ project_id: string; status: string; selected_steps: string[]; credits_deducted: number }>(`/pipeline/start/${projectId}`, {
      method: 'POST',
      body: JSON.stringify({
        steps,
        audio_config: audioConfig,
        ...(outputAspectRatios?.length ? { output_aspect_ratios: outputAspectRatios } : {}),
      }),
    }),
  subscribeProgress: (
    projectId: string,
    onProgress: (data: PipelineProgressEvent) => void,
    onError?: (err: Error) => void,
  ): (() => void) => {
    const ctrl = new AbortController();
    const base = API_BASE;
    (async () => {
      try {
        const token = getToken();
        if (!token) {
          onError?.(new Error('Not authenticated'));
          return;
        }

        const res = await fetch(`${base}/api/v1/pipeline/progress/${projectId}`, {
          headers: {
            Accept: 'text/event-stream',
            Authorization: `Bearer ${token}`,
          },
          signal: ctrl.signal,
        });

        if (res.status === 401) {
          handleUnauthorized();
          onError?.(new Error('Session expired'));
          return;
        }

        if (!res.ok || !res.body) {
          onError?.(new Error(`Failed to subscribe: ${res.status}`));
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\n\n');
          buffer = parts.pop() || '';
          for (const part of parts) {
            const line = part.split('\n').find((l) => l.startsWith('data:'));
            if (!line) continue;
            try {
              const data = JSON.parse(line.slice(5).trim());
              onProgress(data);
              if (data.status === 'completed' || data.status === 'error' || data.status === 'cancelled') {
                ctrl.abort();
                return;
              }
            } catch {
              // skip malformed
            }
          }
        }
      } catch (err: unknown) {
        if ((err as Error).name !== 'AbortError') {
          onError?.(err as Error);
        }
      }
    })();
    return () => ctrl.abort();
  },
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
    }),
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
  is_active: boolean;
  features: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentTransactionResponse {
  id: string;
  user_id: string;
  plan_id: string;
  plan: PlanResponse;
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

export interface EntitlementsResponse {
  plan: string;
  aspect_ratios: string[];
  /** null means every caption style is available. */
  caption_styles: string[] | null;
  max_clips_per_video: number;
  watermark_forced: boolean;
  pro_ai_provider: boolean;
  priority_rendering: boolean;
  max_upload_duration_seconds: number;
  credit_minutes_total: number;
  credit_minutes_remaining: number;
  current_period_end: string | null;
  subscription_status: string;
}

export interface PlanCatalogEntry {
  id: string;
  name: string;
  slug: string;
  credit_minutes: number;
  price_monthly: number;
  currency: string;
  features: string[];
  entitlements: EntitlementsResponse;
  is_current: boolean;
}

export const subscriptionApi = {
  listPlans: () => authedRequest<PlanResponse[]>('/subscription/plans'),
  /** Capabilities of the caller's current plan. The UI gates on this rather
   * than reimplementing the tier rules. */
  getEntitlements: () => authedRequest<EntitlementsResponse>('/subscription/entitlements'),
  getPlanCatalog: () => authedRequest<PlanCatalogEntry[]>('/subscription/catalog'),
  getMySubscription: () => authedRequest<{ plan: string; credit_minutes_total: number; credit_minutes_remaining: number; subscription_status: string; current_period_end: string | null }>('/subscription/me'),
  activateFreePlan: () => authedRequest<{ plan: string; credit_minutes_total: number; credit_minutes_remaining: number; subscription_status: string; current_period_end: string | null }>('/subscription/activate-free', { method: 'POST' }),
  topupCredits: (amount: number, notes?: string) =>
    authedRequest<{ plan: string; credit_minutes_total: number; credit_minutes_remaining: number; subscription_status: string; current_period_end: string | null }>('/subscription/topup', {
      method: 'POST',
      body: JSON.stringify({ amount, notes }),
    }),
  getMyTransactions: () => authedRequest<PaymentTransactionResponse[]>('/subscription/transactions'),
  getCreditLedger: (limit?: number) => authedRequest<CreditLedgerResponse[]>(`/subscription/ledger${limit ? `?limit=${limit}` : ''}`),
  initiatePayment: (planSlug: string, paymentMethod?: string, notes?: string) =>
    authedRequest<PaymentTransactionResponse>('/subscription/payment/initiate', {
      method: 'POST',
      body: JSON.stringify({ plan_slug: planSlug, payment_method: paymentMethod, notes }),
    }),
  verifyPayment: (paymentUuid: string, status: string, notes?: string) =>
    authedRequest<PaymentTransactionResponse>('/subscription/payment/verify', {
      method: 'POST',
      body: JSON.stringify({ payment_uuid: paymentUuid, status, notes }),
    }),
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
