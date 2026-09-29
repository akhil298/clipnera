export type AspectRatio = '9:16' | '1:1' | '4:5' | '16:9';
import type { CaptionPreset } from '@/lib/utils/captionStyles.generated';
export type { CaptionPreset };
export type LayoutMode = 'single_speaker' | 'split_screen' | 'screen_share_focus';

export interface AudioEnhancementConfig {
  aiDenoise: boolean;
  noiseSuppressionStrength: number; // 0 to 100
  deReverb: boolean;
  vocalClarityEq: boolean;
  humFilter: boolean;
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

export interface WordTimestamp {
  id: string;
  text: string;
  start: number;
  end: number;
  highlighted?: boolean;
  isFiller?: boolean;
  emoji?: string;
  /** The word's start in the source video; keys Transcript-tab edits on the server. */
  sourceStart?: number;
}

export interface TranscriptSegment {
  id: string;
  speaker: string;
  speakerColor: string;
  start: number;
  end: number;
  text: string;
  words: WordTimestamp[];
}

export interface BRollOverlay {
  id: string;
  start: number;
  duration: number;
  title: string;
  imageUrl: string;
  category: 'tech' | 'growth' | 'finance' | 'reaction' | 'lifestyle';
  opacity: number;
  transition: 'cut' | 'zoom' | 'slide_left' | 'fade';
}

export interface SoundEffect {
  id: string;
  time: number;
  name: string;
  type: 'whoosh' | 'pop' | 'ding' | 'camera_shutter' | 'sub_drop' | 'glitch';
  volume: number;
}

export interface CaptionConfig {
  preset: CaptionPreset;
  fontSize: number;
  fontFamily: string;
  textColor: string;
  highlightColor: string;
  secondaryHighlightColor: string;
  hasBgBox: boolean;
  bgBoxColor: string;
  uppercase: boolean;
  animation: 'pop' | 'wave' | 'karaoke' | 'glow' | 'fade' | 'none';
  animationSpeed: number;
  positionY: number;
  emojisEnabled: boolean;
  emojiCollection?: string;
  maxWordsPerLine: number;
  shadowIntensity: number;
  // Static clip headline: size on the same 1080-wide scale as fontSize, top
  // offset as a percentage of frame height.
  titleFontSize: number;
  titlePositionY: number;
}

export interface AutoZoomConfig {
  enabled: boolean;
  frequency: 'high' | 'medium' | 'subtle';
  scale: number; // 1.05 to 1.3
}

export interface AutoReframeConfig {
  mode: 'speaker_tracking' | 'center' | 'split_top_bottom' | 'side_by_side';
  speakerCropX: number; // 0 to 1
  speakerSmoothing: number;
}

export interface SocialOptimization {
  hashtags: string[];
  optimizedHooks: Array<{
    type: string;
    text: string;
    strength: number;
    predictedRetention: string;
  }>;
  targetPlatforms: ('tiktok' | 'instagram' | 'youtube' | 'x')[];
  recommendedTiming?: {
    platform: string;
    optimalTime: string;
    bestDays: string[];
    algorithmInsight: string;
  };
  scheduledDate?: string;
  postStatus: 'draft' | 'scheduled' | 'published';
}

export interface ViralClip {
  id: string;
  projectId?: string;
  title: string;
  hook: string;
  posterUrl?: string;
  presignedUrl?: string;
  burnedPresignedUrl?: string;
  viralityScore: number;
  hookScore: number;
  engagementScore: number;
  startTime: number;
  endTime: number;
  duration: number;
  rationale: string;
  suggestedAspectRatio: AspectRatio;
  suggestedLayout: LayoutMode;
  aspectRatio: AspectRatio;
  layoutMode: LayoutMode;
  keywords: string[];
  emojiHighlights: string[];
  autoBrollKeywords: string[];
  transcriptSegments: TranscriptSegment[];
  bRollOverlays: BRollOverlay[];
  soundEffects: SoundEffect[];
  captionConfig: CaptionConfig;
  autoZoom: AutoZoomConfig;
  autoReframe: AutoReframeConfig;
  socialOptimization: SocialOptimization;
  thumbnailTime?: number;
  audioEnhancement?: AudioEnhancementConfig;
  /** Bridge between the hook and the clip; absent means Auto. */
  hookTransition?: HookTransitionConfig;
  /** The user's watermark choice; paid plans only can turn it off. */
  watermarkEnabled?: boolean;
  /** Words cut in the Transcript tab, by source start time. */
  removedWords?: number[];
  /** Whether the server has saved editor settings for this clip. */
  hasSavedSettings?: boolean;
}

// --- Clip editor settings: mirror backend/clip_generation/schema.py ----------

/** Mirrors backend TranscriptEdits. Words are keyed by their source start time. */
export interface TranscriptEdits {
  removed: number[];
  highlighted: number[];
}

/** Mirrors backend ClipEditorSettings; each field is omitted until set. */
export interface ClipEditorSettings {
  aspect_ratio?: AspectRatio;
  caption_config?: CaptionConfig;
  hook_transition?: HookTransitionConfig;
  watermark_enabled?: boolean;
  transcript_edits?: TranscriptEdits;
}

// --- Hook transitions: mirror backend/hook_transitions/schema.py ------------

export type HookTransitionMode = 'auto' | 'preset' | 'custom' | 'off';

/** Mirrors backend HookTransitionConfig. Unset parts fall back to the preset's. */
export interface HookTransitionConfig {
  mode: HookTransitionMode;
  preset_id?: string | null;
  source?: string | null;
  effects?: string[] | null;
  sound?: string | null;
  impact?: string | null;
  /** "none" for no impact sound; omit to keep the preset's. */
  impact_sound?: string | null;
  /** A phrase id, "auto" to match the hook, or "none". */
  text_id?: string | null;
  custom_text?: string | null;
  text_style?: string | null;
  duration?: number | null;
}

/** Mirrors backend HookTransitionApplied: the concrete transition a render used. */
export interface HookTransitionApplied {
  preset_id: string;
  source: string;
  effects: string[];
  sound: string;
  impact: string;
  impact_sound: string | null;
  text: string | null;
  text_style: string;
  duration: number;
}

export interface HookTransitionPart {
  id: string;
  name: string;
  description: string;
}

export interface HookTransitionPhrase {
  id: string;
  text: string;
  intents: string[];
}

export interface HookTransitionPreset {
  id: string;
  name: string;
  group: string;
  source: string;
  effects: string[];
  sound: string;
  impact: string;
  impact_sound: string | null;
  text: string | null;
  text_style: string;
  duration: number;
  fits: string[];
  moods: string[];
}

/** Mirrors backend HookTransitionCatalogResponse. */
export interface HookTransitionCatalog {
  sources: HookTransitionPart[];
  effects: HookTransitionPart[];
  sounds: HookTransitionPart[];
  impact_sounds: HookTransitionPart[];
  impacts: HookTransitionPart[];
  text_styles: HookTransitionPart[];
  phrases: HookTransitionPhrase[];
  groups: string[];
  presets: HookTransitionPreset[];
  limits: {
    min_duration: number;
    max_duration: number;
    max_effects: number;
    framing_effects: string[];
  };
  default_preset: string;
}

/** Mirrors backend HookTransitionResolveResponse. */
export interface HookTransitionResolveResponse {
  clip_id: string;
  transition: HookTransitionApplied | null;
}

export interface VideoProject {
  id: string;
  title: string;
  folderName?: string;
  folderCategory?: 'YouTube Ingest' | 'Podcast' | 'Keynote' | 'Webinar' | 'Interview' | 'Masterclass' | 'Upload' | 'AI Story' | 'Custom';
  folderColor?: 'amber' | 'sky' | 'emerald' | 'rose' | 'purple' | 'indigo';
  sourceUrl?: string;
  sourceChannel?: string;
  description?: string;
  tags?: string[];
  genre: string;
  duration: number; // in seconds
  sourceType: 'youtube_url' | 'upload';
  videoUrl: string;
  posterUrl: string;
  uploadedAt: string;
  syncStatus: 'synced' | 'syncing' | 'offline_saved';
  offlineAvailable: boolean;
  clips: ViralClip[];
  transcript: TranscriptSegment[];
  audioEnhancement?: AudioEnhancementConfig;
  audioOriginalUrl?: string;
  audioProcessedUrl?: string;
  audioReverted?: boolean;
  processingProgress?: number; // 0-100
  processingStatus?: 'idle' | 'processing' | 'completed' | 'failed';
  creditsDeducted?: number;
  pipelineSteps?: PipelineStep[];
}

export interface AnalyticsMetric {
  views: number;
  likes: number;
  shares: number;
  avgWatchPercentage: number;
  viralityIndex: number;
  platform: 'all' | 'tiktok' | 'instagram' | 'youtube' | 'x';
}

export type TabType =
  | 'dashboard'
  | 'folders'
  | 'generator'
  | 'editor'
  | 'scheduler'
  | 'analytics'
  | 'brand_kit'
  | 'reels'
  | 'settings';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatarUrl: string;
  avatarInitials: string;
  plan: 'free' | 'pro' | 'pro_plus';
  aiCreditsMinutesRemaining: number;
  aiCreditsTotal: number;
  activeWorkspaceId: string;
  providers: string[];
  role: 'user' | 'admin';
  emailNotifications: boolean;
}

export interface Workspace {
  id: string;
  name: string;
  role: 'owner' | 'editor' | 'viewer';
  membersCount: number;
}

export interface BrandKit {
  id: string;
  brandName: string;
  logoUrl?: string;
  logoPosition: string;
  logoOpacity: number;
  logoSize: number;
  primaryColor: string;
  secondaryColor: string;
  preferredFont: string;
  defaultPreset: CaptionPreset;
  autoEmojis: boolean;
  outroCtaText: string;
  /** False while the kit still holds its auto-created defaults. */
  isCustomized: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AppNotification {
  id: string;
  title: string;
  message: string;
  type: 'render_complete' | 'render_failed' | 'scheduled_post' | 'virality_alert' | 'credit_update';
  timestamp: string;
  read: boolean;
  actionUrl?: string;
  projectId?: string;
}

export interface RetentionPoint {
  second: number;
  rawRetention: number;
  clipneraAiRetention: number;
  opusAiRetention?: number; // legacy alias
  eventAnnotation?: string;
}

export interface DownloadProgress {
  status: 'idle' | 'pending' | 'downloading' | 'uploading' | 'done' | 'error';
  percent: number;
  total: string | null;
  speed: string | null;
  eta: string | null;
  message?: string;
}

export interface PipelineStep {
  step: string;
  status: string;
  progress_percent: number;
  message: string | null;
  artifact_path: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface PipelineStatus {
  project_id: string;
  status?: 'not_started' | 'pending' | 'running' | 'completed' | 'error';
  current_step: string;
  is_completed: boolean;
  error: string | null;
  steps: PipelineStep[];
}

export interface PipelineProgressEvent {
  message: string;
  percent: number;
  status: 'idle' | 'running' | 'completed' | 'error' | 'cancelled';
  current_step?: string;
  step_status?: string;
}
