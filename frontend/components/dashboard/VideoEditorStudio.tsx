"use client";
import React, { useState, useEffect, useRef } from 'react';
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
} from '@/lib/types';
import { getCaptionConfig, getAllCaptionStyles } from '@/lib/utils/captionStyles';
import { sfxEngine } from '@/lib/utils/audioSynth';
import confetti from 'canvas-confetti';
import { AudioEnhancerPanel } from './AudioEnhancerPanel';

interface VideoEditorStudioProps {
  clip: ViralClip;
  onUpdateClip: (updatedClip: ViralClip) => void;
  onBackToGenerator: () => void;
  onScheduleClip: (clip: ViralClip) => void;
}

export const VideoEditorStudio: React.FC<VideoEditorStudioProps> = ({
  clip,
  onUpdateClip,
  onBackToGenerator,
  onScheduleClip,
}) => {
  // Playback & Timing state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(clip.duration || 30);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(0.8);

  // Active studio tabs
  const [activeStudioTab, setActiveStudioTab] = useState<'captions' | 'broll' | 'sfx' | 'audio' | 'reframe' | 'transcript'>('captions');
  const [socialOverlay, setSocialOverlay] = useState<'none' | 'tiktok' | 'reels' | 'shorts'>('none');

  // Export modal state
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [exportComplete, setExportComplete] = useState(false);

  // Editable clip properties
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>(clip.aspectRatio || '9:16');
  const [captionConfig, setCaptionConfig] = useState(clip.captionConfig);
  const [autoZoomConfig, setAutoZoomConfig] = useState(clip.autoZoom);
  const [autoReframeConfig, setAutoReframeConfig] = useState(clip.autoReframe);
  const [bRollOverlays, setBRollOverlays] = useState<BRollOverlay[]>(clip.bRollOverlays || []);
  const [soundEffects, setSoundEffects] = useState<SoundEffect[]>(clip.soundEffects || []);
  const [transcriptSegments, setTranscriptSegments] = useState(clip.transcriptSegments || []);
  const [audioEnhanceConfig, setAudioEnhanceConfig] = useState<AudioEnhancementConfig>(
    clip.audioEnhancement || {
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

  useEffect(() => {
    lastTimeRef.current = performance.now();
  }, []);

  // Flattened words list for text-based editor & sync
  const allWords: WordTimestamp[] = transcriptSegments.flatMap((s) => s.words || []);

  // Update parent when clip settings change
  const syncChangesToParent = () => {
    onUpdateClip({
      ...clip,
      aspectRatio,
      captionConfig,
      autoZoom: autoZoomConfig,
      autoReframe: autoReframeConfig,
      bRollOverlays,
      soundEffects,
      transcriptSegments,
      duration,
      audioEnhancement: audioEnhanceConfig,
    });
  };

  // Playback timer loop
  useEffect(() => {
    if (!isPlaying) {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      return;
    }

    lastTimeRef.current = performance.now();

    const loop = (now: number) => {
      const delta = (now - lastTimeRef.current) / 1000;
      lastTimeRef.current = now;

      setCurrentTime((prev) => {
        const nextTime = prev + delta * playbackSpeed;
        if (nextTime >= duration) {
          setIsPlaying(false);
          playedSfxSet.current.clear();
          return 0;
        }

        // Trigger sound effects at current timestamp
        soundEffects.forEach((sfx) => {
          const key = `${sfx.id}-${Math.floor(nextTime * 2)}`;
          if (
            Math.abs(sfx.time - nextTime) < 0.15 &&
            !playedSfxSet.current.has(key) &&
            !isMuted
          ) {
            playedSfxSet.current.add(key);
            sfxEngine.playEffect(sfx.type, sfx.volume);
          }
        });

        return nextTime;
      });

      animationFrameRef.current = requestAnimationFrame(loop);
    };

    animationFrameRef.current = requestAnimationFrame(loop);

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [isPlaying, duration, playbackSpeed, soundEffects, isMuted]);

  // Find active words at current playhead
  const currentActiveWords = allWords.filter(
    (w) => currentTime >= w.start - 0.2 && currentTime <= w.end + 0.3
  );

  // Active B-Roll overlay
  const activeBRoll = bRollOverlays.find(
    (b) => currentTime >= b.start && currentTime <= b.start + b.duration
  );

  // Calculate dynamic auto-zoom scale
  const isAutoZoomActive =
    autoZoomConfig.enabled &&
    (Math.floor(currentTime * 1.5) % 3 === 0 ||
      currentActiveWords.some((w) => w.highlighted));
  const currentZoomScale = isAutoZoomActive ? autoZoomConfig.scale : 1.0;

  // Handle filler word removal
  const handleRemoveAllFillers = () => {
    const updated = transcriptSegments.map((seg) => ({
      ...seg,
      words: seg.words.filter((w) => !w.isFiller && !['um', 'uh', 'you know', 'like'].includes(w.text.toLowerCase())),
    }));
    setTranscriptSegments(updated);
    sfxEngine.playDing();
  };

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

  // Export video simulation
  const handleStartExport = () => {
    setIsExporting(true);
    setExportProgress(10);
    setExportComplete(false);

    const interval = setInterval(() => {
      setExportProgress((p) => {
        if (p >= 100) {
          clearInterval(interval);
          setExportComplete(true);
          confetti({
            particleCount: 120,
            spread: 80,
            origin: { y: 0.6 },
          });
          return 100;
        }
        return p + 15;
      });
    }, 300);
  };

  return (
    <div className="space-y-4 animate-in fade-in duration-300 pb-12">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-neutral-900/90 border border-neutral-800 p-4 rounded-2xl">
        <div className="flex items-center gap-3">
          <button
            onClick={onBackToGenerator}
            className="p-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white transition-colors"
            title="Back to Clips"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-400/10 text-amber-300 border border-amber-400/20">
                Score {clip.viralityScore}/100
              </span>
              <span className="text-xs text-neutral-400 font-mono">
                {duration.toFixed(1)}s • {aspectRatio}
              </span>
            </div>
            <h2 className="text-sm lg:text-base font-bold text-white font-['Syne',sans-serif] truncate max-w-md">
              {clip.title}
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* AI Noise Reduction Quick Toggle */}
          <button
            onClick={() => {
              const updated = {
                ...audioEnhanceConfig,
                aiDenoise: !audioEnhanceConfig.aiDenoise,
              };
              setAudioEnhanceConfig(updated);
              onUpdateClip({ ...clip, audioEnhancement: updated });
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
            onClick={() => onScheduleClip(clip)}
            className="px-3 py-1.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-sky-400 text-xs font-semibold border border-neutral-700 transition-colors flex items-center gap-1.5"
          >
            <span>Schedule</span>
          </button>

          <button
            onClick={handleStartExport}
            className="px-4 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 hover:from-amber-400 hover:to-rose-400 text-neutral-950 text-xs font-bold shadow-md shadow-rose-500/20 active:scale-95 transition-all flex items-center gap-1.5"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export 4K</span>
          </button>
        </div>
      </div>

      {/* Main Studio Grid: Video Player (Left/Center) + Customizer Panels (Right) */}
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        {/* LEFT/CENTER: 9:16 Canvas & Player Controls (7 cols) */}
        <div className="lg:col-span-7 flex flex-col items-center space-y-4">
          {/* Vertical Video Stage */}
          <div
            className={`relative rounded-2xl bg-black border-2 border-neutral-800 shadow-2xl overflow-hidden flex items-center justify-center select-none transition-all duration-300 ${
              aspectRatio === '9:16'
                ? 'w-[280px] sm:w-[320px] aspect-[9/16]'
                : aspectRatio === '1:1'
                ? 'w-[320px] sm:w-[360px] aspect-square'
                : 'w-full aspect-video'
            }`}
          >
            {/* Raw Video / Animated Background Stream */}
            <div
              className="absolute inset-0 transition-transform duration-300 ease-out flex items-center justify-center overflow-hidden"
              style={{
                transform: `scale(${currentZoomScale})`,
              }}
            >
              <img
                src="https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=1200&auto=format&fit=crop&q=80"
                alt="Video Speaker"
                className="w-full h-full object-cover object-center"
              />
              <div className="absolute inset-0 bg-black/20" />
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
                    className={`font-black tracking-tight leading-tight uppercase transition-all duration-100 ${
                      captionConfig.animation === 'bounce'
                        ? 'animate-bounce'
                        : captionConfig.animation === 'pop'
                        ? 'scale-105'
                        : ''
                    }`}
                    style={{
                      fontFamily: captionConfig.fontFamily,
                      fontSize: `${captionConfig.fontSize}px`,
                      color: captionConfig.textColor,
                      textShadow:
                        captionConfig.shadowIntensity > 0
                          ? `0 2px ${captionConfig.shadowIntensity * 10}px rgba(0,0,0,0.9)`
                          : 'none',
                    }}
                  >
                    {currentActiveWords.map((word, idx) => {
                      const isActive =
                        currentTime >= word.start && currentTime <= word.end;
                      return (
                        <span
                          key={word.id}
                          className="inline-block mx-1 transition-all"
                          style={{
                            color: isActive
                              ? captionConfig.highlightColor
                              : word.highlighted
                              ? captionConfig.secondaryHighlightColor
                              : captionConfig.textColor,
                            transform: isActive ? 'scale(1.15)' : 'scale(1)',
                          }}
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
              ) : (
                /* Fallback preview phrase when paused between timestamps */
                <div
                  className="inline-block p-2 rounded-xl bg-black/70 backdrop-blur-sm border border-neutral-700/50 shadow-xl"
                  style={{
                    fontFamily: captionConfig.fontFamily,
                    fontSize: `${captionConfig.fontSize}px`,
                    color: captionConfig.textColor,
                  }}
                >
                  <span style={{ color: captionConfig.highlightColor }}>
                    99% OF CREATORS
                  </span>{' '}
                  FAIL 🔥
                </div>
              )}
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
                    <p className="text-xs font-bold">@opuscreator</p>
                    <p className="text-[10px] opacity-90 line-clamp-2">
                      {clip.title} {clip.socialOptimization.hashtags.slice(0, 3).join(' ')}
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
                      <p className="text-xs font-bold">opus.official</p>
                    </div>
                    <p className="text-[10px] opacity-90">{clip.title}</p>
                  </div>
                  <div className="flex flex-col items-center gap-2 text-[10px]">
                    <span>❤️ 24K</span>
                    <span>💬 830</span>
                    <span>✈️ 3.4K</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Player Transport Controls */}
          <div className="w-full max-w-lg bg-neutral-900 border border-neutral-800 rounded-2xl p-3 space-y-2.5 shadow-lg">
            {/* Scrubber Bar */}
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-neutral-400 min-w-[38px]">
                00:{String(Math.floor(currentTime)).padStart(2, '0')}
              </span>
              <input
                type="range"
                min={0}
                max={duration}
                step={0.1}
                value={currentTime}
                onChange={(e) => {
                  setCurrentTime(Number(e.target.value));
                  playedSfxSet.current.clear();
                }}
                className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
              />
              <span className="text-xs font-mono text-neutral-400 min-w-[38px]">
                00:{String(Math.floor(duration)).padStart(2, '0')}
              </span>
            </div>

            {/* Buttons Row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setCurrentTime((t) => Math.max(0, t - 2))}
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
                  onClick={() => setCurrentTime((t) => Math.min(duration, t + 2))}
                  className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 text-xs font-semibold"
                  title="Jump Forward 2s"
                >
                  +2s
                </button>

                <button
                  onClick={() => {
                    setCurrentTime(0);
                    playedSfxSet.current.clear();
                  }}
                  className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800"
                  title="Restart"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              </div>

              {/* Speed & Audio controls */}
              <div className="flex items-center gap-2">
                <select
                  value={playbackSpeed}
                  onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
                  className="px-2 py-1 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-neutral-300 font-mono"
                >
                  <option value={0.75}>0.75x</option>
                  <option value={1}>1.0x</option>
                  <option value={1.25}>1.25x</option>
                  <option value={1.5}>1.5x</option>
                  <option value={2}>2.0x</option>
                </select>

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
                <div className="grid grid-cols-2 gap-2">
                  {getAllCaptionStyles().map((style) => {
                    const config = style.config;
                    return (
                      <button
                        key={style.id}
                        onClick={() => {
                          setCaptionConfig({ ...config });
                          syncChangesToParent();
                        }}
                        className={`p-2.5 rounded-xl border text-left transition-all ${
                          captionConfig.preset === style.id
                            ? 'bg-neutral-800 border-amber-400 ring-1 ring-amber-400/30'
                            : 'bg-neutral-950 border-neutral-800 hover:border-neutral-700'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white">{style.name}</span>
                          <span className="text-[9px] px-1 py-0.2 rounded bg-amber-400/10 text-amber-300">
                            {style.badge}
                          </span>
                        </div>
                        <p className="text-[10px] text-neutral-400 mt-1 line-clamp-1">
                          {style.description}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Fine Controls */}
              <div className="space-y-3 pt-2 border-t border-neutral-800/80">
                {/* Font Size & Position Y */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="flex items-center justify-between text-xs text-neutral-400 mb-1">
                      <span>Font Size</span>
                      <span className="font-mono">{captionConfig.fontSize}px</span>
                    </div>
                    <input
                      type="range"
                      min={20}
                      max={56}
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
                    {(['bounce', 'pop', 'karaoke', 'wave', 'glow'] as const).map(
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
              </div>
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
                              setCurrentTime(word.start);
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
                onUpdateClip({ ...clip, audioEnhancement: updated });
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
                <div className="grid grid-cols-3 gap-2">
                  {(['9:16', '1:1', '16:9'] as AspectRatio[]).map((ratio) => (
                    <button
                      key={ratio}
                      onClick={() => setAspectRatio(ratio)}
                      className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all ${
                        aspectRatio === ratio
                          ? 'bg-neutral-800 border-violet-400 text-violet-300 ring-1 ring-violet-400/30'
                          : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-neutral-300'
                      }`}
                    >
                      {ratio} {ratio === '9:16' ? 'Vertical' : ratio === '1:1' ? 'Square' : 'Wide'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Auto Zoom Controls */}
              <div className="space-y-3 pt-2 border-t border-neutral-800/80">
                <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer">
                  <div>
                    <span className="text-xs font-bold text-white block">
                      Dynamic Kinetic Auto-Zoom
                    </span>
                    <span className="text-[10px] text-neutral-400">
                      Zooms in on punch words to reset viewer attention
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
                {exportComplete ? 'Viral Video Export Ready!' : 'Rendering 4K HDR Short...'}
              </h3>
              <p className="text-xs text-neutral-400 mt-1">
                {exportComplete
                  ? 'Burned in Hormozi kinetic subtitles, B-roll overlays & 60fps audio master.'
                  : 'Compiling video frames, active face centering & audio waveform...'}
              </p>
            </div>

            {/* Progress Bar */}
            <div className="space-y-1.5">
              <div className="h-3 w-full bg-neutral-950 rounded-full overflow-hidden border border-neutral-800">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 via-rose-500 to-violet-500 transition-all duration-300"
                  style={{ width: `${exportProgress}%` }}
                />
              </div>
              <p className="text-xs font-mono text-neutral-400">{exportProgress}% Complete</p>
            </div>

            {exportComplete && (
              <div className="space-y-2 pt-2">
                <button
                  onClick={() => {
                    setIsExporting(false);
                    // trigger direct fake download link
                    const link = document.createElement('a');
                    link.href = clip.transcriptSegments[0]?.text || '#';
                    link.download = `${clip.title.replace(/\s+/g, '_')}_Clipnera.mp4`;
                  }}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 text-neutral-950 font-bold text-xs shadow-lg shadow-rose-500/25 active:scale-95 transition-all"
                >
                  Download Master MP4 (1080x1920)
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
