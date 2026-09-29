"use client";
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlignLeft, ArrowLeft, Pause, Play } from 'lucide-react';
import confetti from 'canvas-confetti';
import type {
  AspectRatio,
  AutoZoomConfig,
  BRollOverlay,
  CaptionConfig,
  CaptionPreset,
  ClipEditorSettings,
  SoundEffect,
  ViralClip,
  WordTimestamp,
} from '@/lib/types';
import { getAllCaptionStyles, getCaptionConfig } from '@/lib/utils/captionStyles';
import { useEntitlements, canUseAspectRatio, canUseCaptionStyle } from '@/hooks/useEntitlements';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { sfxEngine } from '@/lib/utils/audioSynth';
import { brandKitApi, clipApi } from '@/lib/api';
import { AudioEnhancerPanel } from './AudioEnhancerPanel';
import { StudioTopBar, type SaveState } from './studio/StudioTopBar';
import { ClipDrawer, ClipRail } from './studio/ClipRail';
import { TranscriptPanel } from './studio/TranscriptPanel';
import { CanvasToolbar, CaptionSafetyNote, StudioCanvas, nextPreview } from './studio/StudioCanvas';
import { Transport } from './studio/Transport';
import { Inspector, TOOLS, ToolBadge, type ToolBadges } from './studio/Inspector';
import { Timeline } from './studio/Timeline';
import { ExportDialog } from './studio/ExportDialog';
import { ShortcutsDialog } from './studio/ShortcutsDialog';
import { CaptionsPanel } from './studio/panels/CaptionsPanel';
import { HookPanel } from './studio/panels/HookPanel';
import { BrollPanel } from './studio/panels/BrollPanel';
import { SoundPanel } from './studio/panels/SoundPanel';
import { FormatPanel } from './studio/panels/FormatPanel';
import { useHistory } from './studio/useHistory';
import { useStudioLayout } from './studio/useStudioLayout';
import {
  DEFAULT_AUDIO_ENHANCEMENT,
  EXPORT_SIZE,
  PreviewMode,
  StudioDoc,
  StudioTool,
  cutRanges,
  groupCaptionWords,
  isTypingTarget,
  isWordCut,
} from './studio/studioUtils';

interface VideoEditorStudioProps {
  clip?: ViralClip;
  /** The open project's clips, for the clip rail and [ ] shortcuts. */
  clips: ViralClip[];
  projectTitle?: string;
  onUpdateClip: (updatedClip: ViralClip) => void;
  onBackToGenerator: () => void;
  onScheduleClip: (clip: ViralClip) => void;
  onSelectClip: (clip: ViralClip) => void;
}

type PhoneSheet = StudioTool | 'text';

const PREVIEW_VOLUME = 0.8;
const FILLER_WORDS = new Set(['um', 'uh', 'umm', 'uhh', 'like']);

const initialDoc = (clip: ViralClip): StudioDoc => ({
  aspectRatio: clip.aspectRatio || '9:16',
  captionConfig: clip.captionConfig,
  hookTransition: clip.hookTransition ?? { mode: 'auto' },
  watermarkEnabled: clip.watermarkEnabled ?? true,
  removedWords: clip.removedWords ?? [],
  transcriptSegments: clip.transcriptSegments || [],
  bRollOverlays: clip.bRollOverlays || [],
  soundEffects: clip.soundEffects || [],
  autoZoom: clip.autoZoom,
  audioEnhancement: clip.audioEnhancement || DEFAULT_AUDIO_ENHANCEMENT,
});

/** What the export uses, saved so reopening the clip restores it. */
const editorSettingsFor = (doc: StudioDoc): ClipEditorSettings => ({
  aspect_ratio: doc.aspectRatio,
  caption_config: doc.captionConfig,
  hook_transition: doc.hookTransition,
  watermark_enabled: doc.watermarkEnabled,
  transcript_edits: {
    removed: doc.removedWords,
    highlighted: doc.transcriptSegments
      .flatMap((seg) => seg.words)
      .filter((w) => w.highlighted && w.sourceStart !== undefined)
      .map((w) => w.sourceStart as number),
  },
});

// The studio holds a large amount of hook state derived from `clip`, so the
// "no clip" case is handled by this thin wrapper. Bailing out inside the studio
// itself would mean its hooks only appear once a clip arrives, which React
// reports as an internal static-flag mismatch.
export const VideoEditorStudio: React.FC<VideoEditorStudioProps> = (props) => {
  if (!props.clip) {
    return (
      <div className="h-[100dvh] w-full flex flex-col items-center justify-center gap-4 bg-neutral-950 text-sm text-neutral-400">
        No clip selected. Pick a clip to open the editor.
        <button
          type="button"
          onClick={props.onBackToGenerator}
          className="h-9 px-4 inline-flex items-center gap-2 rounded-xl border border-neutral-700 bg-neutral-900 text-white font-semibold hover:bg-neutral-800"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden />
          Back to clips
        </button>
      </div>
    );
  }

  // The content seeds its editable state (transcript, captions, overlays) from
  // the clip once, on mount. Keying by clip remounts it when a different clip
  // is opened, and again when a summary clip from the project list (no
  // transcript or video URL) is replaced by the full record; otherwise the
  // editor kept the empty summary and showed "No transcript yet".
  const detailKey = props.clip.presignedUrl ? 'full' : 'summary';
  return <StudioContent key={`${props.clip.id}:${detailKey}`} {...props} clip={props.clip} />;
};

const StudioContent: React.FC<VideoEditorStudioProps & { clip: ViralClip }> = ({
  clip,
  clips,
  projectTitle,
  onUpdateClip,
  onBackToGenerator,
  onScheduleClip,
  onSelectClip,
}) => {
  const layout = useStudioLayout();
  const { flags } = useFeatureFlags();
  const { entitlements, promptUpgrade } = useEntitlements();

  // Everything editable lives in one undoable document.
  const { state: doc, commit, replace, undo, redo, canUndo, canRedo } = useHistory<StudioDoc>(() => initialDoc(clip));
  const docRef = useRef(doc);
  docRef.current = doc;

  const patch = useCallback(
    (changes: Partial<StudioDoc>, coalesceKey?: string) => commit((d) => ({ ...d, ...changes }), coalesceKey),
    [commit],
  );
  const patchCaption = useCallback(
    (changes: Partial<CaptionConfig>, coalesceKey?: string) =>
      commit((d) => ({ ...d, captionConfig: { ...d.captionConfig, ...changes } }), coalesceKey),
    [commit],
  );

  // Playback
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(clip.duration || 30);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  // Studio chrome
  const [tool, setTool] = useState<StudioTool>('captions');
  const [preview, setPreview] = useState<PreviewMode>('none');
  const [showSafeZones, setShowSafeZones] = useState(true);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [clipDrawerOpen, setClipDrawerOpen] = useState(false);
  const [sheet, setSheet] = useState<PhoneSheet | null>(null);

  // Export
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [exportComplete, setExportComplete] = useState(false);
  // The file this export rendered; the download button serves exactly this.
  const [exportedUrl, setExportedUrl] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const animationFrameRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number>(0);
  const playedSfxSet = useRef<Set<string>>(new Set());
  const videoRef = useRef<HTMLVideoElement>(null);

  // A plan change (or a clip saved on a higher tier) can leave a selection the
  // current plan cannot use. Fall back instead of letting the export fail at
  // the API with a 403 the user cannot act on from here.
  useEffect(() => {
    if (!canUseAspectRatio(entitlements, doc.aspectRatio)) {
      replace((d) => ({ ...d, aspectRatio: (entitlements.aspect_ratios[0] as AspectRatio) ?? '9:16' }));
    }
  }, [entitlements, doc.aspectRatio, replace]);

  useEffect(() => {
    if (!canUseCaptionStyle(entitlements, doc.captionConfig.preset)) {
      const fallback = entitlements.caption_styles?.[0];
      if (fallback) replace((d) => ({ ...d, captionConfig: { ...getCaptionConfig(fallback as CaptionPreset) } }));
    }
  }, [entitlements, doc.captionConfig.preset, replace]);

  // A clip nobody has edited yet opens in the user's brand kit style. Fonts are
  // left to the preset: the kit's fonts are not ones the export can render.
  useEffect(() => {
    if (clip.hasSavedSettings) return;
    let cancelled = false;
    brandKitApi
      .list()
      .then(([kit]) => {
        if (cancelled || !kit?.isCustomized) return;
        replace((d) => ({
          ...d,
          captionConfig: {
            ...getCaptionConfig(kit.defaultPreset),
            highlightColor: kit.primaryColor,
            secondaryHighlightColor: kit.secondaryColor,
            emojisEnabled: kit.autoEmojis,
          },
        }));
      })
      .catch(() => {
        // No kit, or it could not load: keep the default style.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip.id]);

  // --- Derived timeline ------------------------------------------------------

  const removedSet = useMemo(() => new Set(doc.removedWords), [doc.removedWords]);
  const allWords: WordTimestamp[] = useMemo(() => doc.transcriptSegments.flatMap((s) => s.words || []), [doc.transcriptSegments]);
  const keptWords = useMemo(() => allWords.filter((w) => !isWordCut(w, removedSet)), [allWords, removedSet]);
  const cuts = useMemo(() => cutRanges(allWords, removedSet), [allWords, removedSet]);
  const cutsRef = useRef(cuts);
  cutsRef.current = cuts;
  const captionGroups = useMemo(
    () => groupCaptionWords(keptWords, doc.captionConfig.maxWordsPerLine),
    [keptWords, doc.captionConfig.maxWordsPerLine],
  );

  // The line on screen right now: the group containing the playhead, else the
  // one just spoken, so a paused playhead between words still shows context.
  const activeCaptionGroup = useMemo(() => {
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

  const activeBRoll = doc.bRollOverlays.find((b) => currentTime >= b.start && currentTime <= b.start + b.duration);

  // Auto-zoom punch-ins on the emphasis words the backend marked, each held
  // long enough to read, instead of a timer snapping in and out.
  const zoomHolds = useMemo(() => {
    if (!doc.autoZoom.enabled) return [] as Array<{ start: number; end: number }>;
    const MIN_HOLD = 1.2;
    const MIN_GAP = 2.5;
    const holds: Array<{ start: number; end: number }> = [];
    for (const word of keptWords) {
      if (!word.highlighted) continue;
      const last = holds[holds.length - 1];
      if (last && word.start - last.end < MIN_GAP) {
        last.end = Math.max(last.end, word.end + MIN_HOLD / 2);
        continue;
      }
      holds.push({ start: word.start, end: Math.max(word.end, word.start + MIN_HOLD) });
    }
    return holds;
  }, [keptWords, doc.autoZoom.enabled]);
  const zoomScale = zoomHolds.some((h) => currentTime >= h.start && currentTime <= h.end) ? doc.autoZoom.scale : 1;

  // --- Playback --------------------------------------------------------------

  // Moves the video too: while it plays, its own clock overwrites currentTime,
  // so setting the state alone snapped straight back.
  const seekTo = useCallback(
    (time: number) => {
      const target = Math.min(Math.max(0, time), duration);
      setCurrentTime(target);
      if (videoRef.current) videoRef.current.currentTime = target;
      playedSfxSet.current.clear();
    },
    [duration],
  );

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (isPlaying) video.play().catch(() => {});
    else video.pause();
  }, [isPlaying]);

  // A layout change mounts a fresh video element, which starts paused at 0.
  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
  }, [layout]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = isMuted;
    video.volume = PREVIEW_VOLUME;
  }, [isMuted, layout]);

  useEffect(() => {
    if (videoRef.current) videoRef.current.playbackRate = playbackSpeed;
  }, [playbackSpeed, layout]);

  // Playhead loop. With a video loaded its own clock is the source of truth,
  // sampled every frame; the wall-clock path only remains for clips with no
  // video. Cut words are skipped, as the export drops them.
  useEffect(() => {
    if (!isPlaying) {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      return;
    }
    lastTimeRef.current = performance.now();

    const skipCut = (time: number): number => {
      const cut = cutsRef.current.find((r) => time >= r.start && time < r.end - 0.02);
      return cut ? cut.end : time;
    };
    const fireSoundEffects = (time: number) => {
      doc.soundEffects.forEach((sfx) => {
        const key = `${sfx.id}-${Math.floor(time * 2)}`;
        if (Math.abs(sfx.time - time) < 0.15 && !playedSfxSet.current.has(key) && !isMuted) {
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
        const time = skipCut(video.currentTime);
        if (time !== video.currentTime) video.currentTime = time;
        fireSoundEffects(time);
        setCurrentTime(time);
      } else {
        setCurrentTime((prev) => {
          const nextTime = skipCut(prev + delta * playbackSpeed);
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
  }, [isPlaying, duration, playbackSpeed, doc.soundEffects, isMuted]);

  // --- Saving ----------------------------------------------------------------

  const saveTimerRef = useRef<number | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const isFirstRenderRef = useRef(true);
  const saveNow = useCallback(() => clipApi.saveEditorSettings(clip.id, editorSettingsFor(docRef.current)), [clip.id]);

  // Autosave a moment after the last change, not on every keystroke or slider tick.
  useEffect(() => {
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    setSaveState('pending');
    saveTimerRef.current = window.setTimeout(() => {
      saveTimerRef.current = null;
      setSaveState('saving');
      saveNow()
        .then(() => setSaveState('saved'))
        .catch((err) => {
          console.warn('Could not save editor settings:', err);
          setSaveState('error');
        });
    }, 1000);
  }, [doc.aspectRatio, doc.captionConfig, doc.hookTransition, doc.watermarkEnabled, doc.transcriptSegments, doc.removedWords, saveNow]);

  // Leaving within the autosave delay (another clip, back to the list) still saves.
  useEffect(
    () => () => {
      if (!saveTimerRef.current) return;
      window.clearTimeout(saveTimerRef.current);
      saveNow().catch((err) => console.warn('Could not save editor settings:', err));
    },
    [saveNow],
  );

  // Keep the dashboard's copy current, so the clip list and a reopened clip
  // show these edits, including the preview-only ones the server does not store.
  const initialDocRef = useRef(doc);
  const onUpdateClipRef = useRef(onUpdateClip);
  onUpdateClipRef.current = onUpdateClip;
  const clipRef = useRef(clip);
  clipRef.current = clip;
  useEffect(() => {
    if (doc === initialDocRef.current) return;
    onUpdateClipRef.current({
      ...clipRef.current,
      aspectRatio: doc.aspectRatio,
      captionConfig: doc.captionConfig,
      autoZoom: doc.autoZoom,
      bRollOverlays: doc.bRollOverlays,
      soundEffects: doc.soundEffects,
      transcriptSegments: doc.transcriptSegments,
      audioEnhancement: doc.audioEnhancement,
      hookTransition: doc.hookTransition,
      watermarkEnabled: doc.watermarkEnabled,
      removedWords: doc.removedWords,
    });
  }, [doc]);

  // --- Edits -----------------------------------------------------------------

  const handleCut = useCallback(
    (words: WordTimestamp[], cut: boolean) => {
      const keys = words.map((w) => w.sourceStart).filter((s): s is number => s !== undefined);
      if (!keys.length) return;
      commit((d) => {
        const next = new Set(d.removedWords);
        keys.forEach((k) => (cut ? next.add(k) : next.delete(k)));
        return { ...d, removedWords: Array.from(next) };
      });
    },
    [commit],
  );

  const handleHighlight = useCallback(
    (words: WordTimestamp[], highlighted: boolean) => {
      const ids = new Set(words.map((w) => w.id));
      commit((d) => ({
        ...d,
        transcriptSegments: d.transcriptSegments.map((seg) => ({
          ...seg,
          words: seg.words.map((w) => (ids.has(w.id) ? { ...w, highlighted } : w)),
        })),
      }));
    },
    [commit],
  );

  const handleCutFillers = () => {
    const fillers = allWords.filter(
      (w) => w.isFiller || FILLER_WORDS.has(w.text.toLowerCase().replace(/[^a-z']/g, '')),
    );
    if (!fillers.some((w) => w.sourceStart !== undefined && !removedSet.has(w.sourceStart))) return;
    handleCut(fillers, true);
    sfxEngine.playDing();
  };

  const handlePickPreset = (preset: CaptionPreset) => {
    // The title is not part of a caption look, so a style switch keeps the
    // user's title placement.
    commit((d) => ({
      ...d,
      captionConfig: {
        ...getCaptionConfig(preset),
        titleFontSize: d.captionConfig.titleFontSize,
        titlePositionY: d.captionConfig.titlePositionY,
      },
    }));
  };

  const handleAddBRoll = (category: BRollOverlay['category'], imageUrl: string, title: string) => {
    const overlay: BRollOverlay = {
      id: `broll-${Date.now()}`,
      start: Math.max(0, Math.floor(currentTime)),
      duration: 3.5,
      title,
      imageUrl,
      category,
      opacity: 0.95,
      transition: 'zoom',
    };
    commit((d) => ({ ...d, bRollOverlays: [...d.bRollOverlays, overlay] }));
    sfxEngine.playWhoosh();
  };

  const handleAddSfx = (type: SoundEffect['type'], name: string) => {
    const sfx: SoundEffect = { id: `sfx-${Date.now()}`, time: Math.floor(currentTime * 10) / 10, name, type, volume: 0.8 };
    commit((d) => ({ ...d, soundEffects: [...d.soundEffects, sfx] }));
    sfxEngine.playEffect(type);
  };

  const handleWatermarkToggle = () => {
    if (entitlements.watermark_forced) {
      promptUpgrade('Removing the watermark');
      return;
    }
    patch({ watermarkEnabled: !doc.watermarkEnabled });
  };

  // --- Export ----------------------------------------------------------------

  // The request answers once, when the file is ready, so the bar is paced by
  // elapsed time against a rough render estimate.
  const handleStartExport = async () => {
    setExportMenuOpen(false);
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
      const projectId = clip.projectId;
      if (!projectId) throw new Error('No project ID found for export');

      // The export reads transcript edits from the saved settings, so save
      // now rather than racing the autosave.
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      await saveNow();
      setSaveState('saved');

      const current = docRef.current;
      const result = await clipApi.exportProject(projectId, {
        clipIds: [clip.id],
        aspectRatio: current.aspectRatio,
        captionConfig: current.captionConfig,
        hookTransition: current.hookTransition,
        watermarkEnabled: current.watermarkEnabled,
      });

      const burned = result?.exported_clips?.find((item) => item.burned_presigned_url)?.burned_presigned_url;
      if (!burned) throw new Error('The export finished without producing a file.');
      // The editor keeps previewing the raw cut: the export has captions and
      // the hook bridge baked in, so playing it under the live caption overlay
      // would show captions twice.
      setExportedUrl(burned);
      onUpdateClipRef.current({ ...clipRef.current, burnedPresignedUrl: burned });

      setExportProgress(100);
      setExportComplete(true);
      confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 } });
    } catch (err) {
      setExportError((err as Error).message || 'Something went wrong while exporting.');
    } finally {
      window.clearInterval(ticker);
    }
  };

  const handleDownload = () => {
    if (!exportedUrl) return;
    setIsExporting(false);
    // The URL is signed to download as an attachment, so a same-tab click
    // saves the file without leaving the editor. Never fall back to the raw
    // cut: it has no captions.
    const link = document.createElement('a');
    link.href = exportedUrl;
    link.download = `${clip.title.replace(/\s+/g, '_')}_Clipnera.mp4`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  // --- Clips and keyboard ----------------------------------------------------

  const clipIndex = clips.findIndex((c) => c.id === clip.id);
  const stepClip = (step: number) => {
    const next = clips[clipIndex + step];
    if (clipIndex >= 0 && next) onSelectClip(next);
  };

  // One listener for the Studio's lifetime; it reads the latest values from here.
  const keyActions = {
    togglePlay: () => setIsPlaying((p) => !p),
    nudge: (seconds: number) => seekTo(currentTime + seconds),
    undo,
    redo,
    exportNow: () => void handleStartExport(),
    stepClip,
    showShortcuts: () => setShortcutsOpen(true),
    escape: () => {
      if (isExporting) {
        if (exportComplete || exportError) setIsExporting(false);
      } else if (shortcutsOpen) setShortcutsOpen(false);
      else if (exportMenuOpen) setExportMenuOpen(false);
      else if (sheet) setSheet(null);
      else if (clipDrawerOpen) setClipDrawerOpen(false);
      else onBackToGenerator();
    },
  };
  const keyActionsRef = useRef(keyActions);
  keyActionsRef.current = keyActions;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target)) return;
      const actions = keyActionsRef.current;
      const key = e.key.toLowerCase();
      if (e.metaKey || e.ctrlKey) {
        if (key === 'z') {
          e.preventDefault();
          if (e.shiftKey) actions.redo();
          else actions.undo();
        } else if (key === 'y') {
          e.preventDefault();
          actions.redo();
        } else if (key === 'e') {
          e.preventDefault();
          actions.exportNow();
        }
        return;
      }
      if (e.altKey) return;
      if (e.key === 'Escape') actions.escape();
      else if (e.key === ' ') actions.togglePlay();
      else if (key === 'j') actions.nudge(-2);
      else if (key === 'l') actions.nudge(2);
      else if (e.key === '[') actions.stepClip(-1);
      else if (e.key === ']') actions.stepClip(1);
      else if (e.key === '?') actions.showShortcuts();
      else return;
      e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // --- Pieces ----------------------------------------------------------------

  const badges: ToolBadges = { brollCount: doc.bRollOverlays.length, denoiseOn: doc.audioEnhancement.aiDenoise };
  const subtitle = [projectTitle, clipIndex >= 0 && clips.length > 1 ? `clip ${clipIndex + 1} of ${clips.length}` : null]
    .filter(Boolean)
    .join(' · ');

  const topBar = (
    <StudioTopBar
      layout={layout}
      title={clip.title}
      subtitle={subtitle || `${Math.round(duration)} s · ${doc.aspectRatio}`}
      score={clip.viralityScore}
      aspectRatio={doc.aspectRatio}
      saveState={saveState}
      canUndo={canUndo}
      canRedo={canRedo}
      onUndo={undo}
      onRedo={redo}
      onBack={onBackToGenerator}
      onOpenClips={() => setClipDrawerOpen(true)}
      clipCount={clips.length}
      onShowShortcuts={() => setShortcutsOpen(true)}
      menuOpen={exportMenuOpen}
      onMenuOpenChange={setExportMenuOpen}
      onExport={() => void handleStartExport()}
      onSchedule={() => onScheduleClip(clip)}
      watermarkOn={doc.watermarkEnabled}
      watermarkForced={entitlements.watermark_forced}
      onToggleWatermark={handleWatermarkToggle}
    />
  );

  const canvas = (
    <StudioCanvas
      clip={clip}
      videoRef={videoRef}
      onLoadedMetadata={setDuration}
      onPlayingChange={setIsPlaying}
      onEnded={() => {
        setIsPlaying(false);
        setCurrentTime(0);
      }}
      aspectRatio={doc.aspectRatio}
      config={doc.captionConfig}
      captionWords={activeCaptionGroup ?? []}
      hasTranscript={allWords.length > 0}
      currentTime={currentTime}
      zoomScale={zoomScale}
      activeBRoll={activeBRoll}
      preview={preview}
      showSafeZones={showSafeZones}
      onCaptionYChange={(y) => patchCaption({ positionY: y }, 'positionY')}
      onCyclePreview={layout === 'phone' ? () => setPreview(nextPreview) : undefined}
    />
  );

  const transport = (compact: boolean) => (
    <Transport
      isPlaying={isPlaying}
      onTogglePlay={() => setIsPlaying((p) => !p)}
      currentTime={currentTime}
      duration={duration}
      onSeek={seekTo}
      speed={playbackSpeed}
      onSpeed={setPlaybackSpeed}
      muted={isMuted}
      onToggleMute={() => setIsMuted((m) => !m)}
      compact={compact}
    />
  );

  const transcript = (touch: boolean) => (
    <TranscriptPanel
      segments={doc.transcriptSegments}
      removed={removedSet}
      currentTime={currentTime}
      isPlaying={isPlaying}
      onSeek={seekTo}
      onCut={handleCut}
      onHighlight={handleHighlight}
      onCutFillers={handleCutFillers}
      tapToExtend={touch}
      showHeading={!touch}
    />
  );

  const timelineProps = {
    duration,
    currentTime,
    onSeek: seekTo,
    words: allWords,
    removed: removedSet,
    captionGroups,
    cuts,
    bRoll: doc.bRollOverlays,
    soundEffects: doc.soundEffects,
    title: clip.title,
    posterUrl: clip.posterUrl,
    denoiseOn: doc.audioEnhancement.aiDenoise,
  };

  const renderPanel = (panel: StudioTool) => {
    switch (panel) {
      case 'captions':
        return (
          <CaptionsPanel
            config={doc.captionConfig}
            onChange={patchCaption}
            onPickPreset={handlePickPreset}
            preview={preview}
            aspectRatio={doc.aspectRatio}
          />
        );
      case 'hook':
        return (
          <HookPanel
            clipId={clip.id}
            title={clip.title}
            config={doc.captionConfig}
            onCaptionChange={patchCaption}
            hookTransition={doc.hookTransition}
            onHookTransitionChange={(next) => patch({ hookTransition: next })}
          />
        );
      case 'broll':
        return (
          <BrollPanel
            clipId={clip.id}
            showCutaways={Boolean(flags['broll_studio.cutaways'])}
            overlays={doc.bRollOverlays}
            currentTime={currentTime}
            onAdd={handleAddBRoll}
            onRemove={(id) => commit((d) => ({ ...d, bRollOverlays: d.bRollOverlays.filter((b) => b.id !== id) }))}
            onSeek={seekTo}
          />
        );
      case 'sfx':
        return (
          <SoundPanel
            effects={doc.soundEffects}
            currentTime={currentTime}
            onAdd={handleAddSfx}
            onRemove={(id) => commit((d) => ({ ...d, soundEffects: d.soundEffects.filter((s) => s.id !== id) }))}
            onSeek={seekTo}
          />
        );
      case 'audio':
        return (
          <div className="p-3">
            <AudioEnhancerPanel
              config={doc.audioEnhancement}
              onConfigChange={(next) => patch({ audioEnhancement: next }, 'audioEnhancement')}
              onProcessed={(result) => {
                if (result.processedUrl) sfxEngine.playEffect('ding', 0.5);
              }}
            />
          </div>
        );
      case 'format':
        return (
          <FormatPanel
            aspectRatio={doc.aspectRatio}
            onAspectRatio={(ratio) => patch({ aspectRatio: ratio })}
            autoZoom={doc.autoZoom}
            onAutoZoom={(changes: Partial<AutoZoomConfig>, key?: string) =>
              commit((d) => ({ ...d, autoZoom: { ...d.autoZoom, ...changes } }), key)
            }
          />
        );
    }
  };

  const overlays = (
    <>
      {isExporting && (
        <ExportDialog
          progress={exportProgress}
          complete={exportComplete}
          error={exportError}
          summary={[
            `${getAllCaptionStyles().find((s) => s.id === doc.captionConfig.preset)?.name ?? 'Styled'} captions`,
            'title',
            doc.watermarkEnabled || entitlements.watermark_forced ? 'Clipnera watermark' : 'no watermark',
            `${doc.aspectRatio} HD`,
          ].join(' · ')}
          downloadLabel={`Download MP4 (${EXPORT_SIZE[doc.aspectRatio] ?? 'HD'})`}
          canDownload={Boolean(exportedUrl)}
          onDownload={handleDownload}
          onRetry={() => void handleStartExport()}
          onClose={() => setIsExporting(false)}
        />
      )}
      {shortcutsOpen && <ShortcutsDialog onClose={() => setShortcutsOpen(false)} />}
    </>
  );

  // --- Layouts ---------------------------------------------------------------

  if (layout === 'phone') {
    const dock: Array<{ id: PhoneSheet; label: string; icon: React.ComponentType<{ className?: string }> }> = [
      TOOLS[0],
      { id: 'text', label: 'Text', icon: AlignLeft },
      ...TOOLS.slice(1),
    ];
    const sheetLabel = dock.find((d) => d.id === sheet)?.label;
    return (
      <div className="h-[100dvh] w-full flex flex-col overflow-hidden bg-neutral-950 text-neutral-100">
        {topBar}
        <section className="flex-1 min-h-0 flex flex-col">
          <div className="flex-1 min-h-0 flex px-3 pt-2.5 pb-1">{canvas}</div>
          {!sheet && transport(true)}
        </section>
        {sheet ? (
          <div
            role="dialog"
            aria-label={sheetLabel}
            className="h-[55dvh] shrink-0 flex flex-col rounded-t-[18px] border-t border-neutral-700 bg-neutral-900 shadow-[0_-20px_50px_rgba(0,0,0,0.6)]"
          >
            <div className="mx-auto mt-2 mb-0.5 h-1 w-10 rounded-full bg-neutral-600" aria-hidden />
            <div className="flex items-center gap-2 px-3.5 pt-1.5 pb-2 border-b border-neutral-800">
              <h2 className="flex-1 text-[15px] font-extrabold text-white">{sheetLabel}</h2>
              <button
                type="button"
                onClick={() => setIsPlaying((p) => !p)}
                aria-label={isPlaying ? 'Pause' : 'Play'}
                className="w-8 h-8 rounded-[9px] inline-flex items-center justify-center text-neutral-300 hover:bg-neutral-800"
              >
                {isPlaying ? <Pause className="w-4 h-4" aria-hidden /> : <Play className="w-4 h-4" aria-hidden />}
              </button>
              <button type="button" onClick={() => setSheet(null)} className="h-[30px] px-3.5 rounded-[9px] bg-neutral-800 text-[12.5px] font-bold text-white">
                Done
              </button>
            </div>
            {sheet === 'text' ? (
              <div className="flex-1 min-h-0">{transcript(true)}</div>
            ) : (
              <div className="flex-1 min-h-0 overflow-y-auto pb-5">{renderPanel(sheet)}</div>
            )}
          </div>
        ) : (
          <>
            <div className="pb-2">
              <Timeline {...timelineProps} variant="strip" />
            </div>
            <nav aria-label="Edit tools" className="flex gap-0.5 px-1.5 pt-1.5 pb-[max(18px,env(safe-area-inset-bottom))] border-t border-neutral-800 bg-neutral-900 overflow-x-auto [scrollbar-width:none]">
              {dock.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSheet(id)}
                  className="relative flex-1 min-w-[54px] flex flex-col items-center gap-1 py-[7px] px-0.5 rounded-[10px] text-[10.5px] font-semibold text-neutral-400"
                >
                  <Icon className="w-4 h-4" />
                  {label}
                  {id !== 'text' && <ToolBadge tool={id} badges={badges} />}
                </button>
              ))}
            </nav>
          </>
        )}
        {overlays}
      </div>
    );
  }

  const centre = (compact: boolean) => (
    <section className="[grid-area:center] flex flex-col min-h-0 min-w-0 bg-[radial-gradient(60%_50%_at_50%_45%,#161616,#0a0a0a)]">
      <CanvasToolbar
        preview={preview}
        onPreview={setPreview}
        showSafeZones={showSafeZones}
        onToggleSafeZones={() => setShowSafeZones((s) => !s)}
        aspectRatio={doc.aspectRatio}
        compact={compact}
      />
      <div className="flex-1 min-h-0 flex px-4">{canvas}</div>
      <CaptionSafetyNote positionY={doc.captionConfig.positionY} preview={preview} aspectRatio={doc.aspectRatio} />
      {transport(compact)}
    </section>
  );

  const inspector = (
    <Inspector tool={tool} onTool={setTool} badges={badges}>
      {renderPanel(tool)}
    </Inspector>
  );

  if (layout === 'tablet') {
    return (
      <div
        className="h-[100dvh] w-full grid overflow-hidden bg-neutral-950 text-neutral-100"
        style={{
          gridTemplateAreas: '"top top" "center insp" "tx insp" "tl tl"',
          gridTemplateRows: '56px minmax(0,1.6fr) minmax(0,1fr) clamp(150px, 18vh, 200px)',
          gridTemplateColumns: 'minmax(0,1fr) 340px',
        }}
      >
        {topBar}
        {centre(true)}
        <section className="[grid-area:tx] min-h-0 border-t border-neutral-800 bg-neutral-900">{transcript(false)}</section>
        {inspector}
        <Timeline {...timelineProps} />
        {clipDrawerOpen && (
          <ClipDrawer clips={clips} activeId={clip.id} onSelect={onSelectClip} onClose={() => setClipDrawerOpen(false)} projectTitle={projectTitle} />
        )}
        {overlays}
      </div>
    );
  }

  return (
    <div
      className="h-[100dvh] w-full grid overflow-hidden bg-neutral-950 text-neutral-100"
      style={{
        gridTemplateAreas: '"top top top top" "rail tx center insp" "rail tl tl insp"',
        gridTemplateRows: '56px minmax(0,1fr) clamp(160px, 24vh, 236px)',
        gridTemplateColumns: '72px clamp(260px, 20vw, 300px) minmax(0,1fr) 360px',
      }}
    >
      {topBar}
      <ClipRail clips={clips} activeId={clip.id} onSelect={onSelectClip} />
      <section className="[grid-area:tx] min-h-0 min-w-0 border-r border-neutral-800 bg-neutral-900">{transcript(false)}</section>
      {centre(false)}
      {inspector}
      <Timeline {...timelineProps} />
      {overlays}
    </div>
  );
};
