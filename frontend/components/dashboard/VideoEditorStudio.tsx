"use client";
import React, { useState, useEffect, useRef } from 'react';
import { CaptionStylePreview } from './CaptionStylePreview';
import { ClipBrollPanel } from './ClipBrollPanel';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import {
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Maximize,
  Scissors,
  Sparkles,
  Type,
  Film,
  Music,
  Download,
  Share2,
  Eye,
  Sliders,
  Smartphone,
  Check,
  Plus,
  Trash2,
  ZoomIn,
  ZoomOut,
  Layers,
  Zap,
  ArrowLeft,
  Settings2,
  Smile,
  Palette,
  Volume1,
  Headphones,
  SlidersHorizontal,
  ShieldCheck,
  CheckCircle2,
  Mic2
} from 'lucide-react';
import {
  ViralClip,
  CaptionPreset,
  AspectRatio,
  LayoutMode,
  BRollOverlay,
  SoundEffect,
  WordTimestamp,
  AudioEnhancementConfig,
  HookTransitionConfig,
  CaptionConfig,
  ClipEditorSettings,
} from '@/lib/types';
import { getCaptionConfig, getAllCaptionStyles, pillTextColor } from '@/lib/utils/captionStyles';
import { useEntitlements, canUseAspectRatio, canUseCaptionStyle } from '@/hooks/useEntitlements';
import { ProLockBadge, UpgradeHint } from './ProLockBadge';
import { EMOJI_COLLECTIONS, getEmojiCollection } from '@/lib/data/emojiCollections';
import { sfxEngine } from '@/lib/utils/audioSynth';
import confetti from 'canvas-confetti';
import { AudioEnhancerPanel } from './AudioEnhancerPanel';
import { HookTransitionPanel } from './HookTransitionPanel';
import { brandKitApi, clipApi } from '@/lib/api';
import { Select, SelectOption } from '@/components/ui/Select';

const PLAYBACK_SPEED_OPTIONS: SelectOption<number>[] = [
  { value: 0.75, label: '0.75x' },
  { value: 1, label: '1.0x' },
  { value: 1.25, label: '1.25x' },
  { value: 1.5, label: '1.5x' },
  { value: 2, label: '2.0x' },
];

interface VideoEditorStudioProps {
  clip?: ViralClip;
  onUpdateClip: (updatedClip: ViralClip) => void;
  onBackToGenerator: () => void;
  onScheduleClip: (clip: ViralClip) => void;
}

/** Player clock, e.g. 75.4 -> "1:15". */
const formatClock = (seconds: number): string => {
  const whole = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
};

/** Preview width per aspect ratio; the transport bar shares it so the two line up. */
const stageWidthClass = (aspectRatio: string): string =>
  aspectRatio === '9:16'
    ? 'w-[280px] sm:w-[320px]'
    : aspectRatio === '1:1'
    ? 'w-[320px] sm:w-[360px]'
    : aspectRatio === '4:5'
    ? 'w-[300px] sm:w-[340px]'
    : 'w-full';

/** Exported frame size per aspect ratio; mirrors output_dimensions() in video_processor/geometry.py. */
const EXPORT_SIZE: Record<string, string> = {
  '9:16': '1080×1920',
  '4:5': '1080×1350',
  '1:1': '1080×1080',
  '16:9': '1920×1080',
};

/** What the export is doing, judged from the paced progress bar. */
const exportStage = (progress: number): string =>
  progress < 30
    ? 'Preparing your clip...'
    : progress < 60
    ? 'Burning in captions and title...'
    : progress < 85
    ? 'Encoding the video...'
    : 'Almost done, uploading your file...';

/** CSS entrance for a caption line; mirrors _entrance() in ass_generator.py. */
const captionEntrance = (animation: CaptionConfig['animation'], speed: number): string | undefined => {
  const pace = Math.max(0.25, speed || 1);
  if (animation === 'pop' || animation === 'wave') return `caption-rise ${Math.round(170 / pace)}ms ease-out`;
  if (animation === 'fade' || animation === 'glow') return `caption-fade ${Math.round(200 / pace)}ms ease-out`;
  return undefined;
};

/**
 * One caption word's look; mirrors _active_word_tags() in ass_generator.py. On
 * a plate the spoken word sits in a pill of the secondary highlight colour,
 * and the emphasis colour is not used for text.
 */
const activeWordStyle = (config: CaptionConfig, isActive: boolean, highlighted: boolean): React.CSSProperties => {
  const onPlate = config.hasBgBox;
  if (!isActive) {
    return {
      color: highlighted && !onPlate ? config.secondaryHighlightColor : config.textColor,
      transform: 'scale(1)',
    };
  }
  const motion =
    config.animation === 'pop' ? 'scale(1.09)' : config.animation === 'wave' ? 'translateY(-8%) scale(1.06)' : 'scale(1)';
  if (onPlate) {
    const pill = config.secondaryHighlightColor;
    return {
      color: pillTextColor(config),
      backgroundColor: pill,
      borderRadius: '0.3em',
      padding: '0 0.2em',
      transform: motion,
    };
  }
  return {
    color: config.highlightColor,
    transform: motion,
    ...(config.animation === 'glow' ? { textShadow: `0 0 12px ${config.highlightColor}` } : {}),
  };
};

// The studio holds a large amount of hook state derived from `clip`, so the
// "no clip" case is handled by this thin wrapper. Bailing out inside the studio
// itself would mean its hooks only appear once a clip arrives, which React
// reports as an internal static-flag mismatch.
export const VideoEditorStudio: React.FC<VideoEditorStudioProps> = (props) => {
  if (!props.clip) {
    return (
      <div className="flex items-center justify-center h-[60vh] text-neutral-400 text-sm">
        No clip selected. Select a clip from the generator to open the editor.
      </div>
    );
  }

  // The content seeds its editable state (transcript, captions, overlays) from
  // the clip once, on mount. Keying by clip remounts it when a different clip
  // is opened, and again when a summary clip from the project list (no
  // transcript or video URL) is replaced by the full record; otherwise the
  // editor kept the empty summary and showed "No transcript yet".
  const detailKey = props.clip.presignedUrl ? 'full' : 'summary';
  return <VideoEditorStudioContent key={`${props.clip.id}:${detailKey}`} {...props} clip={props.clip} />;
};

const VideoEditorStudioContent: React.FC<VideoEditorStudioProps & { clip: ViralClip }> = ({
  clip,
  onUpdateClip,
  onBackToGenerator,
  onScheduleClip,
}) => {
  const applyEmojiCollection = (text: string): string => {
    if (!captionConfig.emojiCollection) return text;
    const collection = getEmojiCollection(captionConfig.emojiCollection);
    if (!collection.emojis || collection.emojis.length === 0) return text;
    const spaces = [];
    for (let i = 0; i < text.length; i++) {
      if (text[i] === ' ') spaces.push(i);
    }
    if (spaces.length < 2) {
      return `${text} ${collection.emojis.join(' ')}`;
    }
    const firstBreak = spaces[0] + 1;
    const lastBreak = spaces[spaces.length - 1];
    const prefixEmojis = collection.emojis.slice(0, 2).join(' ');
    const middleText = text.slice(firstBreak, lastBreak).trim();
    const suffixText = text.slice(lastBreak).trim();
    return `${text.slice(0, firstBreak)}${prefixEmojis} ${middleText} ${suffixText}`;
  };

  const safeClip = clip;

  // Playback & Timing state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(safeClip.duration || 30);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(0.8);

  // Active studio tabs
  const { flags } = useFeatureFlags();
  const [activeStudioTab, setActiveStudioTab] = useState<'captions' | 'hook' | 'broll' | 'sfx' | 'audio' | 'reframe' | 'transcript'>('captions');
  const [socialOverlay, setSocialOverlay] = useState<'none' | 'tiktok' | 'reels' | 'shorts'>('none');

  const { entitlements, promptUpgrade } = useEntitlements();

  // Export modal state
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [exportComplete, setExportComplete] = useState(false);
  // The file this export rendered; the download button serves exactly this.
  const [exportedUrl, setExportedUrl] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // Editable safeClip properties
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>(safeClip.aspectRatio || '9:16');
  const [captionConfig, setCaptionConfig] = useState(safeClip.captionConfig);
  const [autoZoomConfig, setAutoZoomConfig] = useState(safeClip.autoZoom);
  const [autoReframeConfig, setAutoReframeConfig] = useState(safeClip.autoReframe);
  const [bRollOverlays, setBRollOverlays] = useState<BRollOverlay[]>(safeClip.bRollOverlays || []);
  // Auto by default: the server picks a bridge that suits the clip's hook.
  const [hookTransition, setHookTransition] = useState<HookTransitionConfig>(
    safeClip.hookTransition ?? { mode: 'auto' },
  );
  // Only paid plans may drop the watermark; the server forces it otherwise.
  const [watermarkEnabled, setWatermarkEnabled] = useState(safeClip.watermarkEnabled ?? true);
  // Source start times of words cut in the Transcript tab; the export drops them too.
  const [removedWords, setRemovedWords] = useState<number[]>(safeClip.removedWords ?? []);

  // A plan change (or a clip saved on a higher tier) can leave a selection the
  // current plan cannot use. Fall back instead of letting the export fail at
  // the API with a 403 the user cannot act on from here.
  useEffect(() => {
    if (!canUseAspectRatio(entitlements, aspectRatio)) {
      setAspectRatio((entitlements.aspect_ratios[0] as AspectRatio) ?? '9:16');
    }
  }, [entitlements, aspectRatio]);

  useEffect(() => {
    if (!canUseCaptionStyle(entitlements, captionConfig.preset)) {
      const fallback = entitlements.caption_styles?.[0];
      if (fallback) setCaptionConfig({ ...getCaptionConfig(fallback as CaptionPreset) });
    }
  }, [entitlements, captionConfig.preset]);
  const [soundEffects, setSoundEffects] = useState<SoundEffect[]>(safeClip.soundEffects || []);
  const [transcriptSegments, setTranscriptSegments] = useState(safeClip.transcriptSegments || []);
  const [audioEnhanceConfig, setAudioEnhanceConfig] = useState<AudioEnhancementConfig>(
    safeClip.audioEnhancement || {
      aiDenoise: true,
      noiseSuppressionStrength: 90,
      deReverb: true,
      vocalClarityEq: true,
      humFilter: true,
    }
  );

  const animationFrameRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number>(0);
  const playedSfxSet = useRef<Set<string>>(new Set());
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  // Moves the video too: while it plays, its own clock overwrites currentTime,
  // so setting the state alone snapped straight back.
  const seekTo = (time: number) => {
    const target = Math.min(Math.max(0, time), duration);
    setCurrentTime(target);
    if (videoRef.current) {
      videoRef.current.currentTime = target;
    }
    playedSfxSet.current.clear();
  };

  // Caption and title sizes in CaptionConfig are authored against a 1080px-wide
  // frame, and the burner scales them by frame width. Scaling the preview by
  // height instead showed 9:16 text ~1.8x larger than the export burns in.
  const CAPTION_REFERENCE_WIDTH = 1080;
  const [stageWidth, setStageWidth] = useState(0);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => {
      setStageWidth(entry.contentRect.width);
    });
    observer.observe(stage);
    setStageWidth(stage.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);

  const previewScale = stageWidth > 0 ? stageWidth / CAPTION_REFERENCE_WIDTH : 0.3;
  const captionFontPx = Math.max(9, captionConfig.fontSize * previewScale);
  const titleFontPx = Math.max(9, captionConfig.titleFontSize * previewScale);

  useEffect(() => {
    lastTimeRef.current = performance.now();
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (isPlaying) {
      video.play().catch(() => {});
    } else {
      video.pause();
    }
  }, [isPlaying]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = isMuted;
    video.volume = volume;
  }, [isMuted, volume]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.playbackRate = playbackSpeed;
  }, [playbackSpeed]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (safeClip.presignedUrl) {
      video.src = safeClip.presignedUrl;
      video.poster = safeClip.posterUrl || '';
      video.load();
      setCurrentTime(0);
      setDuration(safeClip.duration || 30);
    }
  }, [safeClip.presignedUrl, safeClip.posterUrl, safeClip.duration]);

  // Flattened words list for text-based editor & sync
  const allWords: WordTimestamp[] = React.useMemo(
    () => transcriptSegments.flatMap((s) => s.words || []),
    [transcriptSegments],
  );

  // Update parent when safeClip settings change
  const syncChangesToParent = (overrides: Partial<ViralClip> = {}) => {
    onUpdateClip({
      ...safeClip,
      aspectRatio,
      captionConfig,
      autoZoom: autoZoomConfig,
      autoReframe: autoReframeConfig,
      bRollOverlays,
      soundEffects,
      transcriptSegments,
      duration,
      audioEnhancement: audioEnhanceConfig,
      hookTransition,
      watermarkEnabled,
      removedWords,
      ...overrides,
    });
  };

  const handleHookTransitionChange = (next: HookTransitionConfig) => {
    setHookTransition(next);
    syncChangesToParent({ hookTransition: next });
  };

  const handleWatermarkToggle = () => {
    if (entitlements.watermark_forced) {
      promptUpgrade('Removing the watermark');
      return;
    }
    setWatermarkEnabled((on) => !on);
  };

  // Playhead loop.
  //
  // When a video is loaded its own clock is the source of truth, sampled every
  // frame. The previous loop integrated wall-clock deltas instead, so the
  // caption playhead drifted away from the audio on every dropped frame, buffer
  // stall or seek — captions slowly fell out of sync with the speech.
  // The wall-clock path only remains for clips with no video to play.
  useEffect(() => {
    if (!isPlaying) {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      return;
    }

    lastTimeRef.current = performance.now();

    const fireSoundEffects = (time: number) => {
      soundEffects.forEach((sfx) => {
        const key = `${sfx.id}-${Math.floor(time * 2)}`;
        if (
          Math.abs(sfx.time - time) < 0.15 &&
          !playedSfxSet.current.has(key) &&
          !isMuted
        ) {
          playedSfxSet.current.add(key);
          sfxEngine.playEffect(sfx.type, sfx.volume);
        }
      });
    };

    const loop = (now: number) => {
      const delta = (now - lastTimeRef.current) / 1000;
      lastTimeRef.current = now;

      const video = videoRef.current;
      if (video && !video.paused && !Number.isNaN(video.currentTime)) {
        const time = video.currentTime;
        fireSoundEffects(time);
        setCurrentTime(time);
      } else {
        setCurrentTime((prev) => {
          const nextTime = prev + delta * playbackSpeed;
          if (nextTime >= duration) {
            setIsPlaying(false);
            playedSfxSet.current.clear();
            return 0;
          }
          fireSoundEffects(nextTime);
          return nextTime;
        });
      }

      animationFrameRef.current = requestAnimationFrame(loop);
    };

    animationFrameRef.current = requestAnimationFrame(loop);

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [isPlaying, duration, playbackSpeed, soundEffects, isMuted]);

  // Captions flow as short phrases, mirroring the ASS burner's grouping, so
  // the preview shows the same line breaks the exported video will have.
  const captionGroups = React.useMemo(() => {
    const maxWords = Math.max(1, captionConfig.maxWordsPerLine);
    const GAP_BREAK = 0.6; // a pause this long starts a new line
    const groups: WordTimestamp[][] = [];
    let current: WordTimestamp[] = [];
    for (const word of allWords) {
      const previous = current[current.length - 1];
      if (current.length >= maxWords || (previous && word.start - previous.end > GAP_BREAK)) {
        groups.push(current);
        current = [];
      }
      current.push(word);
    }
    if (current.length) groups.push(current);
    return groups;
  }, [allWords, captionConfig.maxWordsPerLine]);

  // The line on screen right now: the group containing the playhead, else the
  // one just spoken, so a paused playhead between words still shows context.
  const activeCaptionGroup = React.useMemo(() => {
    let candidate: WordTimestamp[] | null = null;
    for (const group of captionGroups) {
      const start = group[0].start;
      const end = group[group.length - 1].end;
      if (currentTime >= start && currentTime <= end + 0.35) return group;
      if (start <= currentTime) candidate = group;
      else break;
    }
    return candidate;
  }, [captionGroups, currentTime]);

  const currentActiveWords = activeCaptionGroup ?? [];

  // Active B-Roll overlay
  const activeBRoll = bRollOverlays.find(
    (b) => currentTime >= b.start && currentTime <= b.start + b.duration
  );

  // Auto-zoom punch-ins, derived from the emphasis words the backend marked.
  //
  // This used to be `Math.floor(currentTime * 1.5) % 3 === 0`, a timer that
  // snapped the whole frame in and out every two seconds regardless of what
  // was being said — the "zooming in and out" in the player. Zoom now only
  // happens on a real punch word, and each hold lasts long enough to read.
  const zoomHolds = React.useMemo(() => {
    if (!autoZoomConfig.enabled) return [] as Array<{ start: number; end: number }>;
    const MIN_HOLD = 1.2;
    const MIN_GAP = 2.5;
    const holds: Array<{ start: number; end: number }> = [];
    for (const word of allWords) {
      if (!word.highlighted) continue;
      const last = holds[holds.length - 1];
      if (last && word.start - last.end < MIN_GAP) {
        last.end = Math.max(last.end, word.end + MIN_HOLD / 2);
        continue;
      }
      holds.push({ start: word.start, end: Math.max(word.end, word.start + MIN_HOLD) });
    }
    return holds;
  }, [allWords, autoZoomConfig.enabled]);

  const isAutoZoomActive = zoomHolds.some(
    (hold) => currentTime >= hold.start && currentTime <= hold.end
  );
  const currentZoomScale = isAutoZoomActive ? autoZoomConfig.scale : 1.0;

  // Handle filler word removal
  const handleRemoveAllFillers = () => {
    const isFiller = (w: WordTimestamp) =>
      w.isFiller || ['um', 'uh', 'you know', 'like'].includes(w.text.toLowerCase());
    const cut = transcriptSegments
      .flatMap((seg) => seg.words)
      .filter((w) => isFiller(w) && w.sourceStart !== undefined)
      .map((w) => w.sourceStart as number);
    const updated = transcriptSegments.map((seg) => ({
      ...seg,
      words: seg.words.filter((w) => !isFiller(w)),
    }));
    setTranscriptSegments(updated);
    setRemovedWords((prev) => Array.from(new Set([...prev, ...cut])));
    sfxEngine.playDing();
  };

  // What the export uses, saved so reopening the clip restores it.
  const editorSettings = (): ClipEditorSettings => ({
    aspect_ratio: aspectRatio,
    caption_config: captionConfig,
    hook_transition: hookTransition,
    watermark_enabled: watermarkEnabled,
    transcript_edits: {
      removed: removedWords,
      highlighted: transcriptSegments
        .flatMap((seg) => seg.words)
        .filter((w) => w.highlighted && w.sourceStart !== undefined)
        .map((w) => w.sourceStart as number),
    },
  });

  // A clip nobody has edited yet opens in the user's brand kit style. Fonts are
  // left to the preset: the kit's fonts are not ones the export can render.
  useEffect(() => {
    if (safeClip.hasSavedSettings) return;
    let cancelled = false;
    brandKitApi
      .list()
      .then(([kit]) => {
        if (cancelled || !kit?.isCustomized) return;
        setCaptionConfig({
          ...getCaptionConfig(kit.defaultPreset),
          highlightColor: kit.primaryColor,
          secondaryHighlightColor: kit.secondaryColor,
          emojisEnabled: kit.autoEmojis,
        });
      })
      .catch(() => {
        // No kit, or it could not load: keep the default style.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safeClip.id]);

  const saveTimerRef = useRef<number | null>(null);
  const isFirstRenderRef = useRef(true);
  const saveEditorSettings = () => clipApi.saveEditorSettings(safeClip.id, editorSettings());

  // Autosave a moment after the last change, not on every keystroke or slider tick.
  useEffect(() => {
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      saveEditorSettings().catch((err) => console.warn('Could not save editor settings:', err));
    }, 1000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aspectRatio, captionConfig, hookTransition, watermarkEnabled, transcriptSegments, removedWords]);

  useEffect(
    () => () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    },
    [],
  );

  // Toggle word highlight
  const handleToggleWordHighlight = (wordId: string) => {
    const updated = transcriptSegments.map((seg) => ({
      ...seg,
      words: seg.words.map((w) =>
        w.id === wordId ? { ...w, highlighted: !w.highlighted } : w
      ),
    }));
    setTranscriptSegments(updated);
  };

  // Add B-roll from library
  const handleAddBRoll = (category: BRollOverlay['category'], imageUrl: string, title: string) => {
    const newOverlay: BRollOverlay = {
      id: `broll-${Date.now()}`,
      start: Math.max(0, Math.floor(currentTime)),
      duration: 3.5,
      title,
      imageUrl,
      category,
      opacity: 0.95,
      transition: 'zoom',
    };
    setBRollOverlays([...bRollOverlays, newOverlay]);
    sfxEngine.playWhoosh();
  };

  // Add Sound Effect
  const handleAddSfx = (type: SoundEffect['type'], name: string) => {
    const newSfx: SoundEffect = {
      id: `sfx-${Date.now()}`,
      time: Math.floor(currentTime * 10) / 10,
      name,
      type,
      volume: 0.8,
    };
    setSoundEffects([...soundEffects, newSfx]);
    sfxEngine.playEffect(type);
  };

  // Export video via backend. The request answers once, when the file is
  // ready, so the bar is paced by elapsed time against a rough render
  // estimate; it previously sat at 5% for the whole render.
  const handleStartExport = async () => {
    setIsExporting(true);
    setExportProgress(3);
    setExportComplete(false);
    setExportedUrl(null);
    setExportError(null);

    const startedAt = Date.now();
    const expectedMs = Math.max(15_000, duration * 1000);
    const ticker = window.setInterval(() => {
      const elapsed = Date.now() - startedAt;
      // Eases toward 95% so it keeps moving but never claims to be done.
      setExportProgress(Math.min(95, Math.round(3 + 92 * (1 - Math.exp(-elapsed / expectedMs)))));
    }, 250);

    try {
      const projectId = safeClip.projectId;
      if (!projectId) {
        throw new Error('No project ID found for export');
      }

      // The export reads Transcript-tab edits from the saved settings, so save
      // now rather than racing the autosave.
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      await saveEditorSettings();

      // Export this clip at the size picked in the editor, not the project's
      // top-scored clip at the default 9:16.
      const result = await clipApi.exportProject(projectId, {
        clipIds: [safeClip.id],
        aspectRatio,
        captionConfig,
        hookTransition,
        watermarkEnabled,
      });

      if (result?.exported_clips && result.exported_clips.length > 0) {
        const exported = result.exported_clips[0];
        if (exported.burned_presigned_url) {
          setExportedUrl(exported.burned_presigned_url);
          // The editor keeps previewing the raw cut: the export has captions and
          // the hook bridge baked in, so playing it under the live caption
          // overlay would show captions twice and out of step after the hook.
          syncChangesToParent({ burnedPresignedUrl: exported.burned_presigned_url });
        }
      }
      if (!result?.exported_clips?.some((item) => item.burned_presigned_url)) {
        throw new Error('The export finished without producing a file.');
      }

      // Ready as soon as the file is: this used to wait another 2.5s here.
      setExportProgress(100);
      setExportComplete(true);
      confetti({
        particleCount: 120,
        spread: 80,
        origin: { y: 0.6 },
      });
    } catch (err) {
      setExportError((err as Error).message || 'Something went wrong while exporting.');
    } finally {
      window.clearInterval(ticker);
    }
  };

  return (
    <div className="space-y-4 animate-in fade-in duration-300 pb-12">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-neutral-900/90 border border-neutral-800 p-4 rounded-2xl">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onBackToGenerator}
            className="p-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white transition-colors"
            title="Back to Clips"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-400/10 text-amber-300 border border-amber-400/20">
                Score {safeClip.viralityScore}/100
              </span>
              <span className="text-xs text-neutral-400 font-mono">
                {duration.toFixed(1)}s • {aspectRatio}
              </span>
            </div>
            <h2 className="text-sm lg:text-base font-bold text-white font-['Syne',sans-serif] truncate max-w-md">
              {safeClip.title}
            </h2>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          {/* AI Noise Reduction Quick Toggle */}
          <button
            onClick={() => {
              const updated = {
                ...audioEnhanceConfig,
                aiDenoise: !audioEnhanceConfig.aiDenoise,
              };
              setAudioEnhanceConfig(updated);
              onUpdateClip({ ...safeClip, audioEnhancement: updated });
            }}
            className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all ${
              audioEnhanceConfig.aiDenoise
                ? 'bg-amber-500/10 border-amber-500/40 text-amber-400'
                : 'bg-neutral-950 border-neutral-800 text-neutral-500 hover:text-neutral-300'
            }`}
            title="Toggle AI Background Noise Cancellation"
          >
            <Headphones className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Denoise:</span>
            <span className="font-bold">{audioEnhanceConfig.aiDenoise ? 'ON' : 'OFF'}</span>
          </button>

          {/* Social Platform UI Overlay Toggle */}
          <div className="flex items-center bg-neutral-950 p-1 rounded-xl border border-neutral-800 text-xs">
            <button
              onClick={() => setSocialOverlay('none')}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                socialOverlay === 'none' ? 'bg-neutral-800 text-white' : 'text-neutral-400'
              }`}
            >
              Clean
            </button>
            <button
              onClick={() => setSocialOverlay('tiktok')}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                socialOverlay === 'tiktok' ? 'bg-neutral-800 text-white' : 'text-neutral-400'
              }`}
            >
              TikTok
            </button>
            <button
              onClick={() => setSocialOverlay('reels')}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                socialOverlay === 'reels' ? 'bg-neutral-800 text-white' : 'text-neutral-400'
              }`}
            >
              Reels
            </button>
            <button
              onClick={() => setSocialOverlay('shorts')}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                socialOverlay === 'shorts' ? 'bg-neutral-800 text-white' : 'text-neutral-400'
              }`}
            >
              Shorts
            </button>
          </div>

          <button
            onClick={() => onScheduleClip(safeClip)}
            className="px-3 py-1.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-sky-400 text-xs font-semibold border border-neutral-700 transition-colors flex items-center gap-1.5"
          >
            <span>Schedule</span>
          </button>

          <button
            onClick={handleWatermarkToggle}
            role="switch"
            aria-checked={watermarkEnabled || entitlements.watermark_forced}
            title={
              entitlements.watermark_forced
                ? 'Removing the watermark requires a paid plan'
                : 'Add the Clipnera watermark to the export'
            }
            className="px-3 py-1.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold border border-neutral-700 transition-colors flex items-center gap-2 text-neutral-300"
          >
            <span>Watermark</span>
            <span
              className={`relative w-7 h-4 rounded-full transition-colors ${
                watermarkEnabled || entitlements.watermark_forced ? 'bg-emerald-500' : 'bg-neutral-600'
              }`}
            >
              <span
                className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
                  watermarkEnabled || entitlements.watermark_forced ? 'left-3.5' : 'left-0.5'
                }`}
              />
            </span>
            {entitlements.watermark_forced && <ProLockBadge feature="Removing the watermark" />}
          </button>

          <button
            onClick={handleStartExport}
            className="px-4 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-400 hover:to-rose-400 text-neutral-950 text-xs font-bold shadow-md shadow-rose-500/20 active:scale-95 transition-all flex items-center gap-1.5"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export HD</span>
          </button>
        </div>
      </div>

      {/* Main Studio Grid: Video Player (Left/Center) + Customizer Panels (Right) */}
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        {/* LEFT/CENTER: 9:16 Canvas & Player Controls (7 cols) */}
        <div className="lg:col-span-7 flex flex-col items-center space-y-4 lg:sticky lg:top-20 lg:self-start">
          {/* Vertical Video Stage */}
          <div
            ref={stageRef}
            className={`relative rounded-2xl bg-black border-2 border-neutral-800 shadow-2xl overflow-hidden flex items-center justify-center select-none transition-all duration-300 ${stageWidthClass(aspectRatio)} ${
              aspectRatio === '9:16'
                ? 'aspect-[9/16]'
                : aspectRatio === '1:1'
                ? 'aspect-square'
                : aspectRatio === '4:5'
                ? 'aspect-[4/5]'
                : 'aspect-video'
            }`}
          >
            {/* Raw Video / Animated Background Stream */}
            <div
              className="absolute inset-0 transition-transform duration-700 ease-in-out flex items-center justify-center overflow-hidden"
              style={{
                transform: `scale(${currentZoomScale})`,
              }}
            >
               {safeClip.presignedUrl ? (
                 <video
                   ref={videoRef}
                   src={safeClip.presignedUrl}
                   poster={safeClip.posterUrl || ''}
                   className="w-full h-full object-contain object-center"
                   muted={isMuted}
                   playsInline
                   preload="metadata"
                   onTimeUpdate={(e) => {
                     const vid = e.currentTarget;
                     setCurrentTime(vid.currentTime);
                   }}
                   onLoadedMetadata={(e) => {
                     const vid = e.currentTarget;
                     if (vid.duration && isFinite(vid.duration)) {
                       setDuration(vid.duration);
                     }
                   }}
                   onPlay={() => setIsPlaying(true)}
                   onPause={() => setIsPlaying(false)}
                   onEnded={() => {
                     setIsPlaying(false);
                     setCurrentTime(0);
                   }}
                 />
               ) : (
                 <div className="w-full h-full bg-neutral-800 flex items-center justify-center">
                   <p className="text-neutral-400 text-xs">Video not available</p>
                 </div>
               )}
            </div>

            {/* B-Roll Video Overlay (if active at currentTime) */}
            {activeBRoll && (
              <div className="absolute inset-0 z-20 transition-all duration-300 animate-in fade-in zoom-in-95">
                <img
                  src={activeBRoll.imageUrl}
                  alt={activeBRoll.title}
                  className="w-full h-full object-cover"
                  style={{ opacity: activeBRoll.opacity }}
                />
                <div className="absolute top-3 left-3 px-2 py-0.5 rounded bg-black/70 text-[9px] font-mono text-amber-400 border border-white/10">
                  B-ROLL: {activeBRoll.title}
                </div>
              </div>
            )}

            {/* Static Title Layer — one sentence, pinned near the top for the
                whole clip. Mirrors the ASS "Title" style in the burned export. */}
            {safeClip.title?.trim() && (
              <div
                className="absolute inset-x-4 z-30 pointer-events-none flex justify-center text-center"
                style={{ top: `${captionConfig.titlePositionY}%` }}
              >
                <p
                  className="px-2.5 py-1.5 rounded-lg bg-black/45 backdrop-blur-[2px] font-extrabold leading-snug text-white"
                  style={{
                    fontFamily: captionConfig.fontFamily,
                    fontSize: `${titleFontPx}px`,
                    textShadow: '0 2px 8px rgba(0,0,0,0.9)',
                  }}
                >
                  {captionConfig.emojisEnabled
                    ? applyEmojiCollection(safeClip.title)
                    : safeClip.title}
                </p>
              </div>
            )}

            {/* Dynamic Kinetic Subtitles Canvas Layer */}
            <div
              className="absolute inset-x-4 z-30 pointer-events-none flex flex-col items-center justify-center text-center transition-all"
              style={{
                top: `${captionConfig.positionY}%`,
                transform: 'translateY(-50%)',
              }}
            >
              {currentActiveWords.length > 0 ? (
                <div
                  className={`inline-block p-2 rounded-xl transition-all duration-150 ${
                    captionConfig.hasBgBox
                      ? 'shadow-2xl border border-neutral-700/50'
                      : ''
                  }`}
                  style={{
                    backgroundColor: captionConfig.hasBgBox
                      ? captionConfig.bgBoxColor
                      : 'transparent',
                  }}
                >
                  <p
                    // A new key per caption line replays its entrance animation.
                    key={currentActiveWords[0]?.id}
                    className={`font-black tracking-tight leading-tight transition-all duration-100 ${
                      captionConfig.uppercase ? 'uppercase' : ''
                    }`}
                    style={{
                      animation: captionEntrance(captionConfig.animation, captionConfig.animationSpeed),
                      fontFamily: captionConfig.fontFamily,
                      fontSize: `${captionFontPx}px`,
                      color: captionConfig.textColor,
                      textShadow:
                        captionConfig.shadowIntensity > 0
                          ? `0 2px ${captionConfig.shadowIntensity * 10}px rgba(0,0,0,0.9)`
                          : 'none',
                    }}
                  >
                    {currentActiveWords.map((word, idx) => {
                      const isActive =
                        captionConfig.animation !== 'none' &&
                        currentTime >= word.start && currentTime <= word.end;
                      return (
                        <span
                          key={word.id}
                          className="inline-block mx-1 transition-all"
                          style={activeWordStyle(captionConfig, isActive, Boolean(word.highlighted))}
                        >
                          {word.text}
                          {word.emoji && captionConfig.emojisEnabled && (
                            <span className="ml-1 inline-block animate-pulse">
                              {word.emoji}
                            </span>
                          )}
                        </span>
                      );
                    })}
                  </p>
                </div>
              ) : allWords.length === 0 ? (
                /* No word timings at all — say so instead of echoing the title,
                   which previously made a broken transcript look like captions. */
                <div className="inline-block px-3 py-1.5 rounded-lg bg-black/70 border border-neutral-700/50 text-[10px] text-neutral-400">
                  No transcript yet for this clip
                </div>
              ) : null}
            </div>

            {/* Social Platform UI Mockup Overlays */}
            {socialOverlay === 'tiktok' && (
              <div className="absolute inset-0 z-40 pointer-events-none p-3 flex flex-col justify-between text-white">
                <div className="flex items-center justify-between text-xs font-semibold opacity-80 pt-1">
                  <span>Following</span>
                  <span className="font-bold border-b-2 border-white pb-0.5">For You</span>
                  <Eye className="w-4 h-4" />
                </div>
                <div className="flex justify-between items-end pb-2">
                  <div className="space-y-1 max-w-[180px]">
                    <p className="text-xs font-bold">@clipnera</p>
                    <p className="text-[10px] opacity-90 line-clamp-2">
                      {safeClip.title} {safeClip.socialOptimization.hashtags.slice(0, 3).join(' ')}
                    </p>
                  </div>
                  <div className="flex flex-col items-center gap-2.5 text-center text-[10px]">
                    <div className="w-8 h-8 rounded-full bg-rose-500/80 flex items-center justify-center">❤️</div>
                    <span>42.8K</span>
                    <div className="w-8 h-8 rounded-full bg-neutral-800/80 flex items-center justify-center">💬</div>
                    <span>1.2K</span>
                    <div className="w-8 h-8 rounded-full bg-neutral-800/80 flex items-center justify-center">↗️</div>
                    <span>5.9K</span>
                  </div>
                </div>
              </div>
            )}

            {socialOverlay === 'reels' && (
              <div className="absolute inset-0 z-40 pointer-events-none p-3 flex flex-col justify-between text-white">
                <div className="flex items-center justify-between text-xs font-bold">
                  <span>Reels</span>
                  <Smartphone className="w-4 h-4" />
                </div>
                <div className="flex justify-between items-end pb-2">
                  <div className="space-y-1 max-w-[180px]">
                    <div className="flex items-center gap-1.5">
                      <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-amber-400 to-rose-500" />
                      <p className="text-xs font-bold">clipnera</p>
                    </div>
                    <p className="text-[10px] opacity-90">{safeClip.title}</p>
                  </div>
                  <div className="flex flex-col items-center gap-2 text-[10px]">
                    <span>❤️ 24K</span>
                    <span>💬 830</span>
                    <span>✈️ 3.4K</span>
                  </div>
                </div>
              </div>
            )}

            {socialOverlay === 'shorts' && (
              <div className="absolute inset-0 z-40 pointer-events-none p-3 flex flex-col justify-between text-white">
                <div className="flex items-center justify-between text-xs font-bold">
                  <span>Shorts</span>
                  <Smartphone className="w-4 h-4" />
                </div>
                <div className="flex justify-between items-end pb-2">
                  <div className="space-y-1.5 max-w-[180px]">
                    <div className="flex items-center gap-1.5">
                      <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-rose-500 to-red-600" />
                      <p className="text-xs font-bold">@clipnera</p>
                      <span className="px-2 py-0.5 rounded-full bg-white text-black text-[9px] font-bold">Subscribe</span>
                    </div>
                    <p className="text-[10px] opacity-90 line-clamp-2">{safeClip.title}</p>
                  </div>
                  <div className="flex flex-col items-center gap-2 text-[10px]">
                    <span>👍 18K</span>
                    <span>👎</span>
                    <span>💬 640</span>
                    <span>↗️ 2.1K</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Player Transport Controls */}
          <div className={`${stageWidthClass(aspectRatio)} max-w-full bg-neutral-900 border border-neutral-800 rounded-2xl p-3 space-y-2.5 shadow-lg`}>
            {/* Scrubber Bar */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-neutral-400 min-w-[34px]">
                {formatClock(currentTime)}
              </span>
              <input
                type="range"
                min={0}
                max={duration}
                step={0.1}
                value={currentTime}
                onChange={(e) => seekTo(Number(e.target.value))}
                className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
              />
              <span className="text-xs font-mono text-neutral-400 min-w-[34px] text-right">
                {formatClock(duration)}
              </span>
            </div>

            {/* Buttons Row */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => seekTo(currentTime - 2)}
                  className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 text-xs font-semibold"
                  title="Jump Back 2s"
                >
                  -2s
                </button>

                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="p-3 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-400 hover:to-rose-400 text-neutral-950 shadow-md shadow-rose-500/20 active:scale-95 transition-all"
                >
                  {isPlaying ? (
                    <Pause className="w-5 h-5 fill-current" />
                  ) : (
                    <Play className="w-5 h-5 fill-current ml-0.5" />
                  )}
                </button>

                <button
                  onClick={() => seekTo(currentTime + 2)}
                  className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 text-xs font-semibold"
                  title="Jump Forward 2s"
                >
                  +2s
                </button>

                <button
                  onClick={() => seekTo(0)}
                  className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800"
                  title="Restart"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              </div>

              {/* Speed & Audio controls */}
              <div className="flex items-center gap-2">
                <Select
                  value={playbackSpeed}
                  onChange={setPlaybackSpeed}
                  options={PLAYBACK_SPEED_OPTIONS}
                  aria-label="Playback speed"
                  className="px-2 py-1 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-neutral-300 font-mono"
                />

                <button
                  onClick={() => setIsMuted(!isMuted)}
                  className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800"
                >
                  {isMuted ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT: Studio Tabs & Customizer Panels (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Studio Tab Navigation */}
          <div className="flex items-center p-1 bg-neutral-900 border border-neutral-800 rounded-xl overflow-x-auto">
            <button
              onClick={() => setActiveStudioTab('captions')}
              className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all whitespace-nowrap ${
                activeStudioTab === 'captions'
                  ? 'bg-neutral-800 text-amber-400 shadow'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Type className="w-3.5 h-3.5" />
              <span>Captions</span>
            </button>

            <button
              onClick={() => setActiveStudioTab('hook')}
              className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all whitespace-nowrap ${
                activeStudioTab === 'hook'
                  ? 'bg-neutral-800 text-fuchsia-400 shadow'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Zap className="w-3.5 h-3.5" />
              <span>Hook</span>
            </button>

            <button
              onClick={() => setActiveStudioTab('transcript')}
              className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all whitespace-nowrap ${
                activeStudioTab === 'transcript'
                  ? 'bg-neutral-800 text-rose-400 shadow'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Scissors className="w-3.5 h-3.5" />
              <span>Transcript Edit</span>
            </button>

            <button
              onClick={() => setActiveStudioTab('broll')}
              className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all whitespace-nowrap ${
                activeStudioTab === 'broll'
                  ? 'bg-neutral-800 text-sky-400 shadow'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Film className="w-3.5 h-3.5" />
              <span>B-Roll ({bRollOverlays.length})</span>
            </button>

            <button
              onClick={() => setActiveStudioTab('sfx')}
              className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all whitespace-nowrap ${
                activeStudioTab === 'sfx'
                  ? 'bg-neutral-800 text-emerald-400 shadow'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Music className="w-3.5 h-3.5" />
              <span>SFX ({soundEffects.length})</span>
            </button>

            <button
              onClick={() => setActiveStudioTab('audio')}
              className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all whitespace-nowrap ${
                activeStudioTab === 'audio'
                  ? 'bg-neutral-800 text-amber-400 shadow'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Headphones className="w-3.5 h-3.5 text-amber-400" />
              <span>AI Denoise</span>
              {audioEnhanceConfig.aiDenoise && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              )}
            </button>

            <button
              onClick={() => setActiveStudioTab('reframe')}
              className={`flex-1 py-2 px-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all whitespace-nowrap ${
                activeStudioTab === 'reframe'
                  ? 'bg-neutral-800 text-violet-400 shadow'
                  : 'text-neutral-400 hover:text-neutral-200'
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Auto-Crop</span>
            </button>
          </div>

          {/* PANEL 1: CAPTION STYLER */}
          {activeStudioTab === 'captions' && (
            <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4">
              <div>
                <label className="text-xs font-bold text-neutral-300 uppercase tracking-wider block mb-2">
                  Preset Templates:
                </label>
                {/* Own scroll container: the list is twenty templates long and
                    previously grew the page until the video scrolled off screen. */}
                <div className="caption-preset-scroll max-h-[22rem] space-y-2 overflow-y-auto pr-1.5">
                  {getAllCaptionStyles().map((style) => {
                    const config = style.config;
                    const isActive = captionConfig.preset === style.id;
                    const unlocked = canUseCaptionStyle(entitlements, style.id);
                    return (
                      <button
                        key={style.id}
                        onClick={() => {
                          if (!unlocked) {
                            promptUpgrade(`The ${style.brandName} caption style`);
                            return;
                          }
                          // The title is not part of a caption look, so a
                          // style switch keeps the user's title placement.
                          setCaptionConfig({
                            ...config,
                            titleFontSize: captionConfig.titleFontSize,
                            titlePositionY: captionConfig.titlePositionY,
                          });
                          syncChangesToParent();
                        }}
                        aria-pressed={isActive}
                        aria-disabled={!unlocked}
                        className={`flex w-full items-center gap-3 rounded-xl border p-2.5 text-left transition-all ${
                          isActive && unlocked
                            ? 'bg-neutral-800 border-amber-400 ring-1 ring-amber-400/30'
                            : unlocked
                            ? 'bg-neutral-950 border-neutral-800 hover:border-neutral-700'
                            : 'bg-neutral-950/60 border-neutral-800/60 opacity-70 hover:border-amber-400/40 hover:opacity-100'
                        }`}
                      >
                        <CaptionStylePreview config={config} className="h-14 w-28 shrink-0" />

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-xs font-bold text-white">{style.brandName}</span>
                            {unlocked ? (
                              <span className="shrink-0 rounded bg-amber-400/10 px-1 py-0.5 text-[9px] text-amber-300">
                                {style.badge}
                              </span>
                            ) : (
                              <ProLockBadge feature={`The ${style.brandName} style`} />
                            )}
                          </div>
                          <p className="mt-0.5 line-clamp-2 text-[10px] text-neutral-400">
                            {style.description}
                          </p>
                        </div>

                        {isActive && <Check className="h-4 w-4 shrink-0 text-amber-400" />}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Fine Controls */}
              <div className="space-y-3 pt-2 border-t border-neutral-800/80">
                {/* Font Size & Animation Speed */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                      <span>Font Size</span>
                      <span className="font-mono">{captionConfig.fontSize}px</span>
                    </div>
                    <input
                      type="range"
                      min={8}
                      max={72}
                      value={captionConfig.fontSize}
                      onChange={(e) =>
                        setCaptionConfig({
                          ...captionConfig,
                          fontSize: Number(e.target.value),
                        })
                      }
                      className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                      <span>Animation Speed</span>
                      <span className="font-mono">{captionConfig.animationSpeed.toFixed(2)}x</span>
                    </div>
                    <input
                      type="range"
                      min={0.25}
                      max={3.0}
                      step={0.25}
                      value={captionConfig.animationSpeed}
                      onChange={(e) =>
                        setCaptionConfig({
                          ...captionConfig,
                          animationSpeed: Number(e.target.value),
                        })
                      }
                      className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                    />
                  </div>
                </div>

                {/* Position Y & Other Controls */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                      <span>Vertical Pos (Y)</span>
                      <span className="font-mono">{captionConfig.positionY}%</span>
                    </div>
                    <input
                      type="range"
                      min={20}
                      max={90}
                      value={captionConfig.positionY}
                      onChange={(e) =>
                        setCaptionConfig({
                          ...captionConfig,
                          positionY: Number(e.target.value),
                        })
                      }
                      className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                      <span>Shadow Intensity</span>
                      <span className="font-mono">{captionConfig.shadowIntensity.toFixed(1)}x</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.1}
                      value={captionConfig.shadowIntensity}
                      onChange={(e) =>
                        setCaptionConfig({
                          ...captionConfig,
                          shadowIntensity: Number(e.target.value),
                        })
                      }
                      className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                    />
                  </div>
                </div>

                {/* Title Size & Title Position */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                      <span>Title Size</span>
                      <span className="font-mono">{captionConfig.titleFontSize}px</span>
                    </div>
                    <input
                      type="range"
                      min={24}
                      max={96}
                      value={captionConfig.titleFontSize}
                      onChange={(e) =>
                        setCaptionConfig({
                          ...captionConfig,
                          titleFontSize: Number(e.target.value),
                        })
                      }
                      className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                      <span>Title Pos (Y)</span>
                      <span className="font-mono">{captionConfig.titlePositionY}%</span>
                    </div>
                    <input
                      type="range"
                      min={2}
                      max={40}
                      value={captionConfig.titlePositionY}
                      onChange={(e) =>
                        setCaptionConfig({
                          ...captionConfig,
                          titlePositionY: Number(e.target.value),
                        })
                      }
                      className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                    />
                  </div>
                </div>

                {/* Color pickers */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-neutral-400 block mb-1">
                      Active Highlight Color
                    </label>
                    <div className="flex items-center gap-2 p-1.5 rounded-xl bg-neutral-950 border border-neutral-800">
                      <input
                        type="color"
                        value={captionConfig.highlightColor}
                        onChange={(e) =>
                          setCaptionConfig({
                            ...captionConfig,
                            highlightColor: e.target.value,
                          })
                        }
                        className="w-7 h-7 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="text-xs font-mono text-neutral-300">
                        {captionConfig.highlightColor}
                      </span>
                    </div>
                  </div>

                  <div>
                    <label className="text-xs text-neutral-400 block mb-1">
                      Secondary Accent Color
                    </label>
                    <div className="flex items-center gap-2 p-1.5 rounded-xl bg-neutral-950 border border-neutral-800">
                      <input
                        type="color"
                        value={captionConfig.secondaryHighlightColor}
                        onChange={(e) =>
                          setCaptionConfig({
                            ...captionConfig,
                            secondaryHighlightColor: e.target.value,
                          })
                        }
                        className="w-7 h-7 rounded-lg cursor-pointer bg-transparent border-0"
                      />
                      <span className="text-xs font-mono text-neutral-300">
                        {captionConfig.secondaryHighlightColor}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Animation style */}
                <div>
                  <label className="text-xs text-neutral-400 block mb-1">
                    Kinetic Animation Style:
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {(['pop', 'karaoke', 'wave', 'glow'] as const).map(
                      (anim) => (
                        <button
                          key={anim}
                          onClick={() =>
                            setCaptionConfig({ ...captionConfig, animation: anim })
                          }
                          className={`py-1.5 px-2 rounded-lg text-xs font-semibold capitalize border transition-all ${
                            captionConfig.animation === anim
                              ? 'bg-neutral-800 border-amber-400 text-amber-300'
                              : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-neutral-300'
                          }`}
                        >
                          {anim}
                        </button>
                      )
                    )}
                  </div>
                </div>

                {/* Emojis & Backdrop Box Toggles */}
                <div className="grid grid-cols-2 gap-2 pt-2">
                  <label className="flex items-center gap-2 p-2 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={captionConfig.emojisEnabled}
                      onChange={(e) =>
                        setCaptionConfig({
                          ...captionConfig,
                          emojisEnabled: e.target.checked,
                        })
                      }
                      className="rounded accent-amber-400"
                    />
                    <span className="text-xs text-neutral-200">Auto Kinetic Emojis</span>
                  </label>

                   <label className="flex items-center gap-2 p-2 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer">
                     <input
                       type="checkbox"
                       checked={captionConfig.hasBgBox}
                       onChange={(e) =>
                         setCaptionConfig({
                           ...captionConfig,
                           hasBgBox: e.target.checked,
                         })
                       }
                       className="rounded accent-amber-400"
                     />
                     <span className="text-xs text-neutral-200">Dark Box Backdrop</span>
                   </label>
                 </div>

                {/* Emoji Collection Selector */}
                {captionConfig.emojisEnabled && (
                  <div className="space-y-2 pt-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-neutral-300">Emoji Collection</span>
                      <span className="text-xs text-neutral-500">
                        {captionConfig.emojiCollection
                          ? getEmojiCollection(captionConfig.emojiCollection).emoji
                          : 'None'}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                      {EMOJI_COLLECTIONS.map((col) => (
                        <button
                          key={col.id}
                          onClick={() =>
                            setCaptionConfig({
                              ...captionConfig,
                              emojiCollection:
                                captionConfig.emojiCollection === col.id ? undefined : col.id,
                            })
                          }
                          className={`p-2 rounded-lg text-xs font-semibold transition-all text-center ${
                            captionConfig.emojiCollection === col.id
                              ? 'bg-neutral-800 border-2 border-amber-400 text-amber-300'
                              : 'bg-neutral-950 border border-neutral-800 text-neutral-400 hover:text-neutral-300 hover:border-neutral-700'
                          }}`}
                        >
                          {col.emoji}
                        </button>
                      ))}
                    </div>
                    {captionConfig.emojiCollection && (
                      <button
                        onClick={() =>
                          setCaptionConfig({
                            ...captionConfig,
                            emojiCollection: undefined,
                          })
                        }
                        className="text-[10px] text-neutral-500 hover:text-neutral-300 underline"
                      >
                        Clear Emoji Collection
                      </button>
                    )}
                  </div>
                )}
               </div>
            </div>
          )}

          {/* PANEL: HOOK TRANSITION */}
          {activeStudioTab === 'hook' && (
            <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800">
              <HookTransitionPanel
                clipId={safeClip.id}
                config={hookTransition}
                onChange={handleHookTransitionChange}
              />
            </div>
          )}

          {/* PANEL 2: TEXT-BASED TRANSCRIPT EDITOR */}
          {activeStudioTab === 'transcript' && (
            <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
                    Text-Based Video Editing
                  </h3>
                  <p className="text-[11px] text-neutral-400">
                    Click any word to seek playhead or toggle viral highlights
                  </p>
                </div>
                <button
                  onClick={handleRemoveAllFillers}
                  className="px-3 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                >
                  <Scissors className="w-3.5 h-3.5" />
                  <span>Cut All Fillers</span>
                </button>
              </div>

              {/* Interactive Word Cloud Transcript */}
              <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 max-h-72 overflow-y-auto space-y-3">
                {transcriptSegments.map((segment) => (
                  <div key={segment.id} className="space-y-1">
                    <div className="flex items-center gap-2 text-[10px] text-neutral-500">
                      <span className="font-bold text-sky-400">{segment.speaker}</span>
                      <span>•</span>
                      <span>{segment.start}s - {segment.end}s</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 text-xs leading-relaxed">
                      {segment.words.map((word) => {
                        const isCurrent =
                          currentTime >= word.start && currentTime <= word.end;

                        return (
                          <span
                            key={word.id}
                            onClick={() => {
                              seekTo(word.start);
                              handleToggleWordHighlight(word.id);
                            }}
                            className={`cursor-pointer px-1.5 py-0.5 rounded transition-all select-none ${
                              isCurrent
                                ? 'bg-amber-400 text-black font-extrabold scale-105 ring-2 ring-amber-300'
                                : word.highlighted
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold'
                                : word.isFiller
                                ? 'bg-rose-500/20 text-rose-300 line-through'
                                : 'text-neutral-300 hover:bg-neutral-800 hover:text-white'
                            }`}
                          >
                            {word.text}
                            {word.emoji && (
                              <span className="ml-1 text-[10px]">{word.emoji}</span>
                            )}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* PANEL 3: B-ROLL LIBRARY */}
          {activeStudioTab === 'broll' && (
            <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
                    Smart AI B-Roll Stock Footages
                  </h3>
                  <p className="text-[11px] text-neutral-400">
                    Inserts visual cutaway at current playhead (00:{Math.floor(currentTime)}s)
                  </p>
                </div>
              </div>

              {flags['broll_studio.cutaways'] && <ClipBrollPanel clipId={clip.id} />}

              {/* Preset Stock B-roll catalog */}
              <div className="grid grid-cols-2 gap-2.5">
                {[
                  {
                    title: 'Analytics Surge Spike',
                    category: 'growth' as const,
                    img: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&auto=format&fit=crop&q=80',
                  },
                  {
                    title: 'AI Cyber Matrix Code',
                    category: 'tech' as const,
                    img: 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop&q=80',
                  },
                  {
                    title: 'Cash & Financial Growth',
                    category: 'finance' as const,
                    img: 'https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?w=600&auto=format&fit=crop&q=80',
                  },
                  {
                    title: 'Shocked Viral Reaction',
                    category: 'reaction' as const,
                    img: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&auto=format&fit=crop&q=80',
                  },
                ].map((item, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleAddBRoll(item.category, item.img, item.title)}
                    className="group relative h-24 rounded-xl overflow-hidden border border-neutral-800 cursor-pointer hover:border-amber-400 transition-all"
                  >
                    <img
                      src={item.img}
                      alt={item.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30 flex items-end p-2 justify-between">
                      <span className="text-[10px] font-bold text-white leading-tight">
                        {item.title}
                      </span>
                      <Plus className="w-3.5 h-3.5 text-amber-400 group-hover:scale-125 transition-transform" />
                    </div>
                  </div>
                ))}
              </div>

              {/* Active Overlays List */}
              {bRollOverlays.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-neutral-800">
                  <span className="text-xs font-bold text-neutral-400">
                    Inserted B-Roll Tracks:
                  </span>
                  {bRollOverlays.map((b) => (
                    <div
                      key={b.id}
                      className="flex items-center justify-between p-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <img
                          src={b.imageUrl}
                          alt={b.title}
                          className="w-8 h-8 rounded object-cover"
                        />
                        <div>
                          <p className="font-bold text-white text-[11px]">{b.title}</p>
                          <p className="text-[10px] text-neutral-500 font-mono">
                            {b.start}s - {b.start + b.duration}s ({b.transition})
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setBRollOverlays(bRollOverlays.filter((x) => x.id !== b.id))
                        }
                        className="p-1 text-neutral-500 hover:text-rose-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* PANEL 4: SOUND EFFECTS (SFX) */}
          {activeStudioTab === 'sfx' && (
            <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
                  Sound Effects (SFX) Trigger Bank
                </h3>
                <p className="text-[11px] text-neutral-400">
                  Click any effect to preview sound and stamp it onto timeline
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {[
                  { type: 'whoosh' as const, name: 'Whoosh Fast Sweep', icon: '💨' },
                  { type: 'ding' as const, name: 'Ding Cash Chime', icon: '🔔' },
                  { type: 'pop' as const, name: 'Pop Bubble Impact', icon: '🫧' },
                  { type: 'sub_drop' as const, name: 'Sub Drop 808 Bass', icon: '💥' },
                  { type: 'glitch' as const, name: 'Glitch Cyber Static', icon: '⚡' },
                  { type: 'camera_shutter' as const, name: 'Camera Shutter', icon: '📸' },
                ].map((sfx) => (
                  <button
                    key={sfx.type}
                    onClick={() => handleAddSfx(sfx.type, sfx.name)}
                    className="p-3 rounded-xl bg-neutral-950 border border-neutral-800 hover:border-emerald-500/50 hover:bg-emerald-500/5 flex items-center justify-between text-left transition-all group"
                  >
                    <div>
                      <span className="text-base">{sfx.icon}</span>
                      <p className="text-xs font-bold text-white mt-1 group-hover:text-emerald-300">
                        {sfx.name}
                      </p>
                    </div>
                    <Plus className="w-3.5 h-3.5 text-neutral-500 group-hover:text-emerald-400" />
                  </button>
                ))}
              </div>

              {/* Active SFX list */}
              {soundEffects.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-neutral-800">
                  <span className="text-xs font-bold text-neutral-400">
                    Timeline Audio Triggers:
                  </span>
                  {soundEffects.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center justify-between p-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <Volume1 className="w-4 h-4 text-emerald-400" />
                        <div>
                          <p className="font-bold text-white text-[11px]">{s.name}</p>
                          <p className="text-[10px] text-neutral-500 font-mono">
                            Timestamp: {s.time.toFixed(1)}s
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setSoundEffects(soundEffects.filter((x) => x.id !== s.id))
                        }
                        className="p-1 text-neutral-500 hover:text-rose-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* PANEL 5: AI BACKGROUND NOISE REMOVAL & AUDIO ENHANCEMENT */}
          {activeStudioTab === 'audio' && (
            <AudioEnhancerPanel
              config={audioEnhanceConfig}
              onConfigChange={(updated) => {
                setAudioEnhanceConfig(updated);
                onUpdateClip({ ...safeClip, audioEnhancement: updated });
              }}
              onProcessed={(result) => {
                if (result.processedUrl) {
                  sfxEngine.playEffect('ding', 0.5);
                }
              }}
            />
          )}

          {/* PANEL 6: AUTO-CROP & AUTO-ZOOM */}
          {activeStudioTab === 'reframe' && (
            <div className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
                  Auto-Reframe & Dynamic Zoom
                </h3>
                <p className="text-[11px] text-neutral-400">
                  Clipnera AI speaker tracking and eye-attention kinetic zooming
                </p>
              </div>

              {/* Aspect Ratio Selector */}
              <div>
                <label className="text-xs text-neutral-400 block mb-1.5">
                  Output Format:
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {(['9:16', '1:1', '4:5', '16:9'] as AspectRatio[]).map((ratio) => {
                    const unlocked = canUseAspectRatio(entitlements, ratio);
                    return (
                      <button
                        key={ratio}
                        onClick={() =>
                          unlocked
                            ? setAspectRatio(ratio)
                            : promptUpgrade(`The ${ratio} output format`)
                        }
                        aria-disabled={!unlocked}
                        className={`relative py-2 px-3 rounded-xl border text-xs font-bold transition-all ${
                          aspectRatio === ratio && unlocked
                            ? 'bg-neutral-800 border-violet-400 text-violet-300 ring-1 ring-violet-400/30'
                            : unlocked
                            ? 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-neutral-300'
                            : 'bg-neutral-950/60 border-neutral-800/60 text-neutral-500 hover:border-amber-400/40'
                        }`}
                      >
                        <span className="flex items-center justify-center gap-1.5">
                          {ratio} {ratio === '9:16' ? 'Vertical' : ratio === '1:1' ? 'Square' : ratio === '4:5' ? 'Portrait' : 'Wide'}
                          {!unlocked && <ProLockBadge feature={`The ${ratio} format`} />}
                        </span>
                      </button>
                    );
                  })}
                </div>
                {entitlements.aspect_ratios.length < 4 && (
                  <UpgradeHint
                    className="mt-2"
                    message="Unlock 1:1, 4:5 and 16:9 exports with a paid plan."
                    onUpgrade={() => promptUpgrade('Additional output formats')}
                  />
                )}
              </div>

              {/* Auto Zoom Controls */}
              <div className="space-y-3 pt-2 border-t border-neutral-800/80">
                <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer">
                  <div>
                    <span className="text-xs font-bold text-white block">
                      Dynamic Kinetic Auto-Zoom
                    </span>
                    <span className="text-[10px] text-neutral-400">
                      Preview only — zooms in on punch words. Not applied to the
                      exported file yet.
                    </span>
                  </div>
                  <input
                    type="checkbox"
                    checked={autoZoomConfig.enabled}
                    onChange={(e) =>
                      setAutoZoomConfig({
                        ...autoZoomConfig,
                        enabled: e.target.checked,
                      })
                    }
                    className="w-4 h-4 rounded accent-violet-400"
                  />
                </label>

                <div>
                  <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                    <span>Zoom Scale Intensity</span>
                    <span className="font-mono">{autoZoomConfig.scale}x</span>
                  </div>
                  <input
                    type="range"
                    min={1.05}
                    max={1.35}
                    step={0.05}
                    value={autoZoomConfig.scale}
                    onChange={(e) =>
                      setAutoZoomConfig({
                        ...autoZoomConfig,
                        scale: Number(e.target.value),
                      })
                    }
                    className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-violet-400"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* EXPORT MODAL */}
      {isExporting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md p-6 rounded-2xl bg-neutral-900 border border-neutral-800 text-center space-y-4 shadow-2xl">
            <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-amber-500 to-rose-500 mx-auto flex items-center justify-center text-white shadow-lg shadow-rose-500/30">
              <Download className="w-8 h-8 animate-bounce" />
            </div>

            <div>
              <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">
                {exportError ? 'Export failed' : exportComplete ? 'Your clip is ready!' : 'Exporting your clip...'}
              </h3>
              <p className="text-xs text-neutral-400 mt-1">
                {exportError
                  ? exportError
                  : exportComplete
                  ? [
                      `${getAllCaptionStyles().find((s) => s.id === captionConfig.preset)?.name ?? 'Styled'} captions`,
                      'title',
                      watermarkEnabled || entitlements.watermark_forced ? 'Clipnera watermark' : 'no watermark',
                      `${aspectRatio} HD`,
                    ].join(' · ')
                  : exportStage(exportProgress)}
              </p>
            </div>

            {exportError && (
              <div className="space-y-2 pt-2">
                <button
                  onClick={handleStartExport}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 text-neutral-950 font-bold text-xs shadow-lg shadow-rose-500/25 active:scale-95 transition-all"
                >
                  Try again
                </button>
                <button
                  onClick={() => setIsExporting(false)}
                  className="w-full py-2 rounded-xl text-neutral-400 hover:text-white text-xs font-semibold"
                >
                  Close
                </button>
              </div>
            )}

            {/* Progress Bar */}
            {!exportError && (
            <div className="space-y-1.5">
              <div className="h-3 w-full bg-neutral-950 rounded-full overflow-hidden border border-neutral-800">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 via-rose-500 to-violet-500 transition-all duration-300"
                  style={{ width: `${exportProgress}%` }}
                />
              </div>
              <p className="text-xs font-mono text-neutral-400">{exportProgress}% Complete</p>
            </div>
            )}

            {exportComplete && (
              <div className="space-y-2 pt-2">
                <button
                  disabled={!exportedUrl}
                  onClick={() => {
                    if (!exportedUrl) return;
                    setIsExporting(false);
                    // The URL is signed to download as an attachment, so a
                    // same-tab click saves the file without leaving the editor.
                    // Never fall back to the raw cut: it has no captions.
                    const link = document.createElement('a');
                    link.href = exportedUrl;
                    link.download = `${safeClip.title.replace(/\s+/g, '_')}_Clipnera.mp4`;
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                  }}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 text-neutral-950 font-bold text-xs shadow-lg shadow-rose-500/25 active:scale-95 transition-all"
                >
                  Download MP4 ({EXPORT_SIZE[aspectRatio] ?? 'HD'})
                </button>

                <button
                  onClick={() => setIsExporting(false)}
                  className="w-full py-2 rounded-xl text-neutral-400 hover:text-white text-xs font-semibold"
                >
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
