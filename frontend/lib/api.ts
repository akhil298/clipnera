import { BrandKit } from '@/lib/types';
import { getToken, clearAuth, setAuth } from '@/lib/auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

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

async function authedRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
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

export interface PipelineStatus {
  project_id: string;
  current_step: string;
  is_completed: boolean;
  error: string | null;
  steps: Array<{
    step: string;
    status: string;
    progress_percent: number;
    message: string | null;
    artifact_path: string | null;
    started_at: string | null;
    finished_at: string | null;
  }>;
}

export const pipelineApi = {
  start: (projectId: string, steps: string[] = ['download', 'audio_extraction', 'ai_noise_cancellation'], audioConfig: Record<string, any> = {}) =>
    authedRequest<{ project_id: string; status: string; selected_steps: string[] }>(`/pipeline/start/${projectId}`, {
      method: 'POST',
      body: JSON.stringify({ steps, audio_config: audioConfig }),
    }),
  subscribeProgress: (
    projectId: string,
    onProgress: (data: { message: string; percent: number; status: string }) => void,
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
              if (data.status === 'completed' || data.status === 'error') {
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
  revertStep: (projectId: string, step: string) =>
    authedRequest<{ project_id: string; step: string; status: string }>(`/pipeline/revert/${projectId}/${step}`, {
      method: 'POST',
    }),
  resume: (projectId: string, steps: string[] = ['download', 'audio_extraction', 'ai_noise_cancellation'], audioConfig: Record<string, any> = {}) =>
    authedRequest<{ project_id: string; status: string; selected_steps: string[] }>(`/pipeline/resume/${projectId}`, {
      method: 'POST',
      body: JSON.stringify({ steps, audio_config: audioConfig }),
    }),
};

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

export const subscriptionApi = {
  listPlans: () => authedRequest<PlanResponse[]>('/subscription/plans'),
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
