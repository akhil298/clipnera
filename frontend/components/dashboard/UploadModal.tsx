"use client";
import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload,
  Link as LinkIcon,
  Sparkles,
  X,
  CheckCircle2,
  Sliders,
  Scissors,
  Film,
  Zap,
  Volume2,
  Clock,
  Layout,
  Type,
  AlertCircle,
  Folder,
  FolderPlus,
  Youtube,
  Mic,
  Music,
  Palette,
  VolumeX,
  Headphones,
  SlidersHorizontal,
  Wand2,
  Radio,
  BookOpen,
  Compass,
  ExternalLink,
  ArrowDown
} from 'lucide-react';
import { VideoProject, CaptionPreset, StoryPromptConfig, AudioEnhancementConfig, DownloadProgress } from '@/lib/types';
import { SAMPLE_PROJECTS, CAPTION_PRESETS } from '@/lib/data/mockProjects';
import { analyzeVideoSource, generateClipsForProject, generatePromptStoryProject } from '@/lib/utils/urlParser';
import { clipApi, YouTubeMetadataResponse } from '@/lib/api';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (project: VideoProject) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onProjectCreated,
}) => {
  const [sourceType, setSourceType] = useState<'url' | 'upload' | 'prompt_story' | 'sample'>('url');
  const [urlInput, setUrlInput] = useState('');
  const [selectedSampleIndex, setSelectedSampleIndex] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [customTitle, setCustomTitle] = useState('Alex Hormozi — $100M Leads Masterclass');
  const [customFolderName, setCustomFolderName] = useState('Alex Hormozi — $100M Leads Masterclass');

  // Prompt Story Generation State
  const [storyPrompt, setStoryPrompt] = useState('A mind-bending psychological mystery about ancient civilizations discovering lost technology');
  const [storyTone, setStoryTone] = useState<'suspenseful' | 'motivational' | 'mind_blowing' | 'dark_mystery' | 'cinematic_epic' | 'fast_comedy'>('suspenseful');
  const [storyVoice, setStoryVoice] = useState<'american_baritone' | 'british_docu' | 'energetic_creator' | 'deep_mystic' | 'female_calm'>('american_baritone');
  const [storyArtStyle, setStoryArtStyle] = useState<'cinematic_photoreal' | 'dark_cyberpunk' | 'historical_oil' | 'anime_comic' | 'unreal_3d'>('cinematic_photoreal');
  const [storyBgMusic, setStoryBgMusic] = useState<'dark_synth' | 'hans_zimmer_epic' | 'lofi_mystery' | 'dramatic_drums' | 'none'>('dark_synth');
  const [storyTargetDuration, setStoryTargetDuration] = useState<number>(45);

  // AI Pipeline Customization Settings
  const [targetDuration, setTargetDuration] = useState<'short' | 'medium' | 'long'>('medium'); // short: <30s, medium: 30-60s, long: 60-90s
  const [captionPreset, setCaptionPreset] = useState<CaptionPreset>('hormozi');
  const [autoBroll, setAutoBroll] = useState(true);
  const [autoSfx, setAutoSfx] = useState(true);
  const [removeFillers, setRemoveFillers] = useState(true);
  const [autoZoom, setAutoZoom] = useState(true);

  // AI Audio Enhancement & Background Noise Removal Settings
  const [removeBackgroundNoise, setRemoveBackgroundNoise] = useState(true);
  const [noiseReductionLevel, setNoiseReductionLevel] = useState(85);
  const [roomEchoSuppression, setRoomEchoSuppression] = useState(true);
  const [studioVoiceClarity, setStudioVoiceClarity] = useState(true);
  const [voiceLeveling, setVoiceLeveling] = useState(true);
  const [hissFilter, setHissFilter] = useState(true);
  const [showAdvancedAudio, setShowAdvancedAudio] = useState(false);

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState(0);
  const [processingLogs, setProcessingLogs] = useState<string[]>([]);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [ytMeta, setYtMeta] = useState<YouTubeMetadataResponse | null>(null);
  const [ytMetaError, setYtMetaError] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);
  const downloadUnsubRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (sourceType !== 'url') return;
    const trimmed = urlInput.trim();
    setYtMeta(null);
    setYtMetaError(false);
    if (!trimmed || trimmed.length < 8) return;
    const isYoutube = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)/.test(trimmed);
    if (!isYoutube) return;

    let cancelled = false;
    const timeoutId = setTimeout(async () => {
      setMetadataLoading(true);
      try {
        const meta = await clipApi.fetchYoutubeMetadata(trimmed);
        if (!cancelled) {
          setYtMeta(meta);
          setYtMetaError(false);
          setCustomTitle(meta.title);
          setCustomFolderName(meta.title);
        }
      } catch {
        if (!cancelled) {
          setYtMeta(null);
          setYtMetaError(true);
        }
      } finally {
        if (!cancelled) {
          setMetadataLoading(false);
        }
      }
    }, 800);

    return () => {
      clearTimeout(timeoutId);
      cancelled = true;
    };
  }, [urlInput, sourceType]);

  useEffect(() => {
    return () => {
      downloadUnsubRef.current?.();
    };
  }, []);

  if (!isOpen) return null;

  const handleUrlChange = (newUrl: string) => {
    setUrlInput(newUrl);
    const trimmed = newUrl.trim();
    if (trimmed.length > 8) {
      const isYoutube = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)/.test(trimmed);
      if (!isYoutube) {
        const meta = analyzeVideoSource(newUrl);
        setCustomTitle(meta.cleanTitle);
        setCustomFolderName(meta.folderName);
      }
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setUploadedFile(file);
      const clean = file.name.replace(/\.[^/.]+$/, '');
      setCustomTitle(clean);
      setCustomFolderName(`${clean} (Folder)`);
      setSourceType('upload');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setUploadedFile(file);
      const clean = file.name.replace(/\.[^/.]+$/, '');
      setCustomTitle(clean);
      setCustomFolderName(`${clean} (Folder)`);
    }
  };

  const audioEnhanceConfig: AudioEnhancementConfig = {
    removeBackgroundNoise,
    noiseReductionLevel,
    roomEchoSuppression,
    studioVoiceClarity,
    voiceLeveling,
    hissFilter,
  };

  const startAiProcessing = async () => {
    setIsProcessing(true);
    setProcessingStep(1);
    setDownloadProgress(null);

    if (sourceType === 'prompt_story') {
      setProcessingLogs([
        `Prompt Ingestion: "${storyPrompt.slice(0, 45)}..."`,
        'Executing Gemini 3.7 Flash: Crafting high-retention 3-second hook & story script...',
      ]);

      const storyConfig: StoryPromptConfig = {
        prompt: storyPrompt,
        genre: `AI Story (${storyTone})`,
        tone: storyTone,
        voice: storyVoice,
        artStyle: storyArtStyle,
        bgMusic: storyBgMusic,
        targetDuration: storyTargetDuration,
      };

      // Static mode: story is generated locally via generatePromptStoryProject
      let storyData: any = null;

      await new Promise((r) => setTimeout(r, 900));
      setProcessingStep(2);
      setProcessingLogs((prev) => [
        ...prev,
        `Generating cinematic 9:16 scene art (${storyArtStyle.replace('_', ' ')}) & B-roll shots...`,
      ]);

      if (removeBackgroundNoise) {
        await new Promise((r) => setTimeout(r, 800));
        setProcessingStep(3);
        setProcessingLogs((prev) => [
          ...prev,
          `AI Voice Master: Synthesizing ${storyVoice.replace('_', ' ')} speech + Background Noise Filter (${noiseReductionLevel}% Studio Clean)...`,
        ]);
      }

      await new Promise((r) => setTimeout(r, 1000));
      setProcessingStep(4);
      setProcessingLogs((prev) => [
        ...prev,
        `Applying kinetic ${captionPreset.toUpperCase()} typography, sound effects, and tension spikes...`,
      ]);

      await new Promise((r) => setTimeout(r, 700));
      setProcessingStep(5);
      setProcessingLogs((prev) => [
        ...prev,
        `✨ AI Story Folder "${storyData?.folderName || 'AI Story Folder'}" is ready!`,
      ]);

      await new Promise((r) => setTimeout(r, 500));

      const newStoryProject = generatePromptStoryProject(storyConfig, storyData, audioEnhanceConfig);
      setIsProcessing(false);
      onProjectCreated(newStoryProject);
      onClose();
      return;
    }

    // Standard Video Ingestion (YouTube or Upload)
    setProcessingLogs(['Ingesting video stream and initializing project folder...']);

    // Non-blocking download for YouTube URLs
    if (sourceType === 'url') {
      // Fire-and-forget the download, subscribe to progress
      clipApi
        .downloadYoutube(urlInput)
        .then((result: any) => {
          const videoId = result?.id;
          if (videoId && result?.status === 'downloading') {
            // Subscribe to SSE progress updates
            downloadUnsubRef.current = clipApi.subscribeDownloadProgress(
              videoId,
              (progress) => {
                setDownloadProgress(progress);
                if (progress.status === 'done') {
                  setProcessingLogs((prev) => [
                    ...prev,
                    'Video source downloaded & stored successfully!',
                  ]);
                  downloadUnsubRef.current?.();
                } else if (progress.status === 'error') {
                  setProcessingLogs((prev) => [
                    ...prev,
                    `Download failed: ${progress.message || 'Unknown error'}`,
                  ]);
                  downloadUnsubRef.current?.();
                }
              },
              (err) => {
                console.error('Progress subscription error:', err);
                downloadUnsubRef.current?.();
              },
            );
          }
        })
        .catch(() => {
          // Continue with local creation even if backend download fails
          setProcessingLogs((prev) => [
            ...prev,
            'Backend download unavailable, continuing with local processing...',
          ]);
        });
    }

    // Step 1: Audio demuxing & speech recognition
    await new Promise((r) => setTimeout(r, 800));
    setProcessingStep(2);
    setProcessingLogs((prev) => [
      ...prev,
      'Executing Gemini 3.7 Flash: Detecting emotional spikes & virality triggers...',
    ]);

    // Audio Noise Removal Step
    if (removeBackgroundNoise) {
      await new Promise((r) => setTimeout(r, 700));
      setProcessingLogs((prev) => [
        ...prev,
        `AI Audio Denoise: Eliminating room reverberation, air conditioner hum & mic hiss (${noiseReductionLevel}% clarity)...`,
      ]);
    }

    // Static mode: viral clips are generated locally via generateClipsForProject
    // Step 2: Dynamic Auto-Reframe & Speaker Centering
    await new Promise((r) => setTimeout(r, 900));
    setProcessingStep(3);
    setProcessingLogs((prev) => [
      ...prev,
      'Calculating 9:16 vertical crop coordinates & speaker eye-level anchor...',
    ]);

    // Step 3: Subtitles & Karaoke styling
    await new Promise((r) => setTimeout(r, 900));
    setProcessingStep(4);
    setProcessingLogs((prev) => [
      ...prev,
      `Synthesizing ${captionPreset.toUpperCase()} kinetic typography with auto-emojis...`,
      'Injecting smart B-roll overlays & sound effects on climax beats...',
    ]);

    await new Promise((r) => setTimeout(r, 900));
    setProcessingStep(5);
    setProcessingLogs((prev) => [
      ...prev,
      `✨ Project Folder "${customFolderName}" created with viral clips ready!`,
    ]);

    await new Promise((r) => setTimeout(r, 500));

    // Construct final project folder
    const meta = analyzeVideoSource(sourceType === 'url' ? urlInput : customTitle);
    const newProjectId = `proj-${Date.now()}`;
    const generatedClips = generateClipsForProject(meta, newProjectId).map((clip) => ({
      ...clip,
      captionConfig: {
        ...clip.captionConfig,
        preset: captionPreset,
      },
      autoBrollKeywords: autoBroll ? clip.autoBrollKeywords : [],
      soundEffects: autoSfx ? clip.soundEffects : [],
      autoZoom: {
        ...clip.autoZoom,
        enabled: autoZoom,
      },
      audioEnhancement: audioEnhanceConfig,
    }));

    const sample = SAMPLE_PROJECTS[selectedSampleIndex] || SAMPLE_PROJECTS[0];

    const newProject: VideoProject = {
      id: newProjectId,
      title: customTitle || meta.cleanTitle,
      folderName: customFolderName || meta.folderName,
      folderCategory: sourceType === 'url' ? 'YouTube Ingest' : sourceType === 'upload' ? 'Upload' : 'Podcast',
      folderColor: meta.folderColor || 'amber',
      sourceUrl: sourceType === 'url' ? urlInput : '',
      sourceChannel: meta.sourceChannel || 'Uploaded Video',
      description: `Project folder for ${customFolderName}. Contains ${generatedClips.length} AI-extracted viral shorts with Studio Denoise active.`,
      tags: meta.tags || ['Viral', 'Shorts', 'AI', 'Denoised'],
      genre: meta.genre || sample.genre,
      duration: meta.duration || sample.duration,
      sourceType: sourceType === 'url' ? 'youtube_url' : sourceType === 'upload' ? 'upload' : 'sample',
      videoUrl: uploadedFile ? URL.createObjectURL(uploadedFile) : sample.videoUrl,
      posterUrl: meta.posterUrl || sample.posterUrl,
      uploadedAt: new Date().toISOString(),
      syncStatus: 'synced',
      offlineAvailable: true,
      transcript: sample.transcript,
      clips: generatedClips,
      audioEnhancement: audioEnhanceConfig,
    };

    downloadUnsubRef.current?.();
    setIsProcessing(false);
    onProjectCreated(newProject);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl rounded-2xl bg-neutral-900 border border-neutral-800 shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 bg-neutral-950/70">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white font-['Syne',sans-serif]">
                Create Viral Clips with AI
              </h2>
              <p className="text-xs text-neutral-400">
                Generate viral 9:16 Shorts from YouTube links, raw video files, or text prompt stories
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {!isProcessing ? (
            <>
              {/* Source Selector 4-Way Tabs */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-1 bg-neutral-950 rounded-xl border border-neutral-800">
                <button
                  id="tab-source-url"
                  onClick={() => setSourceType('url')}
                  className={`py-2 px-2.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                    sourceType === 'url'
                      ? 'bg-neutral-800 text-amber-400 shadow ring-1 ring-amber-400/20'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Youtube className="w-4 h-4 text-red-400" />
                  <span>YouTube Link</span>
                </button>

                <button
                  id="tab-source-upload"
                  onClick={() => setSourceType('upload')}
                  className={`py-2 px-2.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                    sourceType === 'upload'
                      ? 'bg-neutral-800 text-rose-400 shadow ring-1 ring-rose-400/20'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Upload className="w-4 h-4 text-rose-400" />
                  <span>Upload Video</span>
                </button>

                <button
                  id="tab-source-prompt"
                  onClick={() => setSourceType('prompt_story')}
                  className={`py-2 px-2.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                    sourceType === 'prompt_story'
                      ? 'bg-neutral-800 text-purple-400 shadow ring-1 ring-purple-400/20'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Wand2 className="w-4 h-4 text-purple-400" />
                  <span>Prompt Story AI</span>
                </button>

                <button
                  id="tab-source-sample"
                  onClick={() => setSourceType('sample')}
                  className={`py-2 px-2.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                    sourceType === 'sample'
                      ? 'bg-neutral-800 text-sky-400 shadow ring-1 ring-sky-400/20'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Film className="w-4 h-4 text-sky-400" />
                  <span>Demo Videos</span>
                </button>
              </div>

              {/* 1. YOUTUBE URL TAB */}
              {sourceType === 'url' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-neutral-300 flex items-center gap-1.5">
                      <Youtube className="w-4 h-4 text-red-400" />
                      <span>Paste YouTube Video URL:</span>
                    </label>
                    <span className="text-[10px] text-amber-400 font-semibold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                      Creates Dedicated Project Folder
                    </span>
                  </div>

                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <LinkIcon className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
                      <input
                        type="url"
                        value={urlInput}
                        onChange={(e) => handleUrlChange(e.target.value)}
                        placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                        className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white placeholder-neutral-600 focus:outline-none focus:border-amber-400 font-mono"
                      />
                    </div>
                  </div>

                  {/* Quick YouTube Sample Links */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-[10px] text-neutral-500 mr-1">Trending Suggestions:</span>
                    {[
                      { label: 'Hormozi $100M Leads', url: 'https://youtube.com/watch?v=alex-hormozi-leads' },
                      { label: 'Sam Altman AI Compute', url: 'https://youtube.com/watch?v=lex-sam-altman-ai' },
                      { label: 'Huberman Dopamine', url: 'https://youtube.com/watch?v=huberman-dopamine-focus' },
                      { label: 'Naval Wealth Leverage', url: 'https://youtube.com/watch?v=how-to-get-rich' },
                    ].map((sample) => (
                      <button
                        key={sample.label}
                        type="button"
                        onClick={() => handleUrlChange(sample.url)}
                        className="text-[10px] px-2 py-1 rounded-lg bg-neutral-950 hover:bg-neutral-800 border border-neutral-800 text-neutral-400 hover:text-amber-300 transition-colors"
                      >
                        + {sample.label}
                      </button>
                    ))}
                  </div>

                  {/* YouTube thumbnail + metadata preview */}
                  <div className="rounded-xl border border-amber-500/30 bg-neutral-950/80 overflow-hidden">
                    {metadataLoading && (
                      <div className="flex items-center gap-3 p-3">
                        <div className="w-40 aspect-video rounded-lg bg-neutral-900 animate-pulse shrink-0" />
                        <div className="flex-1 space-y-2">
                          <div className="h-3 w-3/4 rounded bg-neutral-800 animate-pulse" />
                          <div className="h-3 w-1/2 rounded bg-neutral-800 animate-pulse" />
                        </div>
                      </div>
                    )}

                    {ytMetaError && !metadataLoading && (
                      <div className="flex items-center gap-2 p-3 text-[11px] text-rose-400">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>Could not fetch this YouTube link. Check the URL or your connection.</span>
                      </div>
                    )}

                    {ytMeta && !metadataLoading && (
                      <div className="flex gap-3 p-3">
                        <div className="relative w-40 aspect-video rounded-lg overflow-hidden bg-neutral-900 border border-neutral-800 shrink-0">
                          {ytMeta.thumbnail_url ? (
                            <img
                              src={ytMeta.thumbnail_url}
                              alt={ytMeta.title}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-neutral-600">
                              <Youtube className="w-6 h-6" />
                            </div>
                          )}
                          {ytMeta.duration_formatted && (
                            <span className="absolute bottom-1 right-1 text-[9px] font-mono text-neutral-200 px-1 rounded bg-black/70">
                              {ytMeta.duration_formatted}
                            </span>
                          )}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 mb-1">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                            <span className="text-[11px] font-semibold text-emerald-400">
                              Link verified — confirm it&apos;s correct
                            </span>
                          </div>
                          <h4 className="text-sm font-bold text-white line-clamp-2 leading-snug">
                            {ytMeta.title}
                          </h4>
                          {ytMeta.channel_title && (
                            <p className="text-[11px] text-amber-300 font-medium mt-0.5 line-clamp-1">
                              {ytMeta.channel_title}
                            </p>
                          )}
                          <a
                            href={ytMeta.original_url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1.5 flex items-center gap-1.5 text-[11px] text-neutral-400 hover:text-amber-400 transition-colors break-all"
                            title="Open original YouTube link"
                          >
                            <ExternalLink className="w-3 h-3 shrink-0" />
                            <span className="line-clamp-1">{ytMeta.original_url}</span>
                          </a>
                          {ytMeta.resolution && (
                            <span className="inline-block mt-1.5 px-2 py-0.5 rounded text-[10px] font-medium bg-neutral-900 border border-neutral-800 text-neutral-400">
                              {ytMeta.resolution}
                              {ytMeta.aspect_ratio ? ` · ${ytMeta.aspect_ratio}` : ''}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Project Folder Destination Preview Card */}
                  <div className="p-3 rounded-xl bg-neutral-950/80 border border-neutral-800 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5 text-neutral-300 font-semibold text-[11px]">
                        <Folder className="w-3.5 h-3.5 text-amber-400" />
                        <span>Project Folder Output Name:</span>
                      </span>
                      <span className="text-[10px] text-emerald-400 font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded">
                        Auto Organized
                      </span>
                    </div>

                    <input
                      type="text"
                      value={customFolderName}
                      onChange={(e) => setCustomFolderName(e.target.value)}
                      placeholder="Folder name..."
                      className="w-full px-3 py-2 rounded-lg bg-neutral-900 border border-neutral-800 text-xs font-semibold text-white focus:outline-none focus:border-amber-400"
                    />
                  </div>
                </div>
              )}

              {/* 2. UPLOAD RAW VIDEO FILE */}
              {sourceType === 'upload' && (
                <div className="space-y-3">
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragOver(true);
                    }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleFileDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`cursor-pointer border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                      dragOver
                        ? 'border-amber-400 bg-amber-400/5'
                        : uploadedFile
                        ? 'border-emerald-500/50 bg-emerald-500/5'
                        : 'border-neutral-800 bg-neutral-950/40 hover:border-neutral-700'
                    }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="video/*"
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                    <div className="w-12 h-12 rounded-full bg-neutral-800/80 flex items-center justify-center mx-auto mb-3 text-neutral-300">
                      <Upload className="w-6 h-6 text-rose-400" />
                    </div>
                    {uploadedFile ? (
                      <div>
                        <p className="text-sm font-bold text-emerald-400 flex items-center justify-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4" />
                          <span>{uploadedFile.name}</span>
                        </p>
                        <p className="text-xs text-neutral-400 mt-1">
                          {(uploadedFile.size / (1024 * 1024)).toFixed(1)} MB • Click to replace file
                        </p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm font-semibold text-neutral-200">
                          Drag and drop your raw video or podcast file here
                        </p>
                        <p className="text-xs text-neutral-500 mt-1">
                          Supports MP4, MOV, WebM, MKV up to 4K 60fps (Max 2GB)
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-neutral-950/80 border border-neutral-800 space-y-2">
                    <label className="text-[11px] font-semibold text-neutral-300 flex items-center gap-1.5">
                      <Folder className="w-3.5 h-3.5 text-rose-400" />
                      <span>Project Folder Name:</span>
                    </label>
                    <input
                      type="text"
                      value={customFolderName}
                      onChange={(e) => setCustomFolderName(e.target.value)}
                      placeholder="Folder name..."
                      className="w-full px-3 py-2 rounded-lg bg-neutral-900 border border-neutral-800 text-xs font-semibold text-white focus:outline-none focus:border-amber-400"
                    />
                  </div>
                </div>
              )}

              {/* 3. PROMPT-BASED STORIES & AI VIDEO GENERATOR */}
              {sourceType === 'prompt_story' && (
                <div className="space-y-4 animate-in fade-in duration-150">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-purple-300 flex items-center gap-1.5">
                        <Wand2 className="w-4 h-4 text-purple-400" />
                        <span>Enter Story Concept or Script Prompt:</span>
                      </label>
                      <span className="text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20 font-semibold">
                        Prompt to Full 9:16 Video
                      </span>
                    </div>

                    <textarea
                      rows={3}
                      value={storyPrompt}
                      onChange={(e) => setStoryPrompt(e.target.value)}
                      placeholder="e.g. A dark psychological thriller about an AI sentience breakthrough in 2045, with rapid suspense, unexpected twist, and chilling ending..."
                      className="w-full p-3 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white placeholder-neutral-600 focus:outline-none focus:border-purple-400 leading-relaxed"
                    />

                    {/* Quick Inspiration Chips */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-neutral-500 mr-1">Inspirations:</span>
                      {[
                        { label: 'Ancient Rome Tech Secret', text: 'The Antikythera Mechanism: How 2,000-year-old Greek clockwork gears predicted planetary orbits' },
                        { label: 'AI Sentience Glitch 2045', text: 'A thrilling sci-fi story about a rogue AI agent communicating through hidden background audio frequencies' },
                        { label: '5 Dark Psychology Tricks', text: '5 psychological framing secrets used by billionaires and master negotiators to control attention' },
                        { label: 'Deep Mariana Trench Anomaly', text: 'What deep-sea oceanographers discovered at 11,000 meters that governments refuse to declassify' },
                      ].map((item) => (
                        <button
                          key={item.label}
                          type="button"
                          onClick={() => setStoryPrompt(item.text)}
                          className="text-[10px] px-2.5 py-1 rounded-lg bg-neutral-950 hover:bg-neutral-800 border border-neutral-800 text-neutral-300 hover:text-purple-300 transition-colors"
                        >
                          ✨ {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Story Options Grid */}
                  <div className="grid sm:grid-cols-2 gap-3 pt-1">
                    {/* Story Tone */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold text-neutral-400 flex items-center gap-1">
                        <Radio className="w-3 h-3 text-purple-400" />
                        <span>Story Tone & Pacing:</span>
                      </label>
                      <select
                        value={storyTone}
                        onChange={(e: any) => setStoryTone(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 focus:outline-none focus:border-purple-400"
                      >
                        <option value="suspenseful">Suspenseful & Mind-Blowing</option>
                        <option value="dark_mystery">Dark Mystery & True Crime</option>
                        <option value="motivational">High-Energy Motivational</option>
                        <option value="cinematic_epic">Cinematic Historical Epic</option>
                        <option value="fast_comedy">Fast-Paced Contrarian Insight</option>
                      </select>
                    </div>

                    {/* AI Narration Voice */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold text-neutral-400 flex items-center gap-1">
                        <Mic className="w-3 h-3 text-amber-400" />
                        <span>AI Voiceover Narrator:</span>
                      </label>
                      <select
                        value={storyVoice}
                        onChange={(e: any) => setStoryVoice(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 focus:outline-none focus:border-purple-400"
                      >
                        <option value="american_baritone">Deep American Baritone (Dramatic)</option>
                        <option value="british_docu">British Documentarian (Scholarly)</option>
                        <option value="energetic_creator">Fast Gen-Z Creator (High Energy)</option>
                        <option value="deep_mystic">Mystic Whispering Storyteller</option>
                        <option value="female_calm">Calm & Engaging Female Voice</option>
                      </select>
                    </div>

                    {/* Visual Art Style */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold text-neutral-400 flex items-center gap-1">
                        <Palette className="w-3 h-3 text-rose-400" />
                        <span>Visual Art Style (B-Rolls):</span>
                      </label>
                      <select
                        value={storyArtStyle}
                        onChange={(e: any) => setStoryArtStyle(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 focus:outline-none focus:border-purple-400"
                      >
                        <option value="cinematic_photoreal">Photorealistic Cinematic (8K HDR)</option>
                        <option value="dark_cyberpunk">Dark Cyberpunk Neon</option>
                        <option value="historical_oil">Moody Historical Oil Painting</option>
                        <option value="unreal_3d">3D Unreal Engine Hyper-Realistic</option>
                        <option value="anime_comic">Anime / Comic Book Cel-Shaded</option>
                      </select>
                    </div>

                    {/* Background Music & Ambience */}
                    <div className="space-y-1.5">
                      <label className="text-[11px] font-semibold text-neutral-400 flex items-center gap-1">
                        <Music className="w-3 h-3 text-emerald-400" />
                        <span>Background Music & Ambience:</span>
                      </label>
                      <select
                        value={storyBgMusic}
                        onChange={(e: any) => setStoryBgMusic(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 focus:outline-none focus:border-purple-400"
                      >
                        <option value="dark_synth">Dark Suspense Synthwave</option>
                        <option value="hans_zimmer_epic">Hans Zimmer Cinematic Strings</option>
                        <option value="lofi_mystery">Lo-Fi Mystery Piano</option>
                        <option value="dramatic_drums">Intense Battle Drums</option>
                        <option value="none">Voice Only (No Background Track)</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {/* 4. DEMO CURATED SAMPLES */}
              {sourceType === 'sample' && (
                <div className="space-y-3">
                  <label className="text-xs font-bold text-neutral-300 uppercase tracking-wider">
                    Select a high-quality sample video:
                  </label>
                  <div className="grid sm:grid-cols-2 gap-3">
                    {SAMPLE_PROJECTS.map((sample, idx) => (
                      <div
                        key={sample.id}
                        onClick={() => {
                          setSelectedSampleIndex(idx);
                          setCustomTitle(sample.title);
                          setCustomFolderName(sample.folderName || `${sample.title} (Folder)`);
                        }}
                        className={`cursor-pointer rounded-xl border p-3 flex gap-3 items-center transition-all ${
                          selectedSampleIndex === idx
                            ? 'bg-amber-500/10 border-amber-500/50 ring-1 ring-amber-500/30'
                            : 'bg-neutral-950/60 border-neutral-800 hover:border-neutral-700'
                        }`}
                      >
                        <img
                          src={sample.posterUrl}
                          alt={sample.title}
                          className="w-16 h-16 rounded-lg object-cover flex-shrink-0"
                        />
                        <div className="min-w-0 flex-1">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-800 text-amber-400 font-semibold">
                            {sample.genre}
                          </span>
                          <h4 className="text-xs font-bold text-white truncate mt-1">
                            {sample.title}
                          </h4>
                          <p className="text-[11px] text-neutral-400 flex items-center gap-1.5 mt-1">
                            <Clock className="w-3 h-3 text-neutral-500" />
                            <span>{Math.floor(sample.duration / 60)} mins</span>
                            <span>•</span>
                            <span className="text-emerald-400">
                              {sample.clips.length} Viral Clips
                            </span>
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ⭐ SECTION: AI BACKGROUND NOISE REMOVAL & AUDIO ENHANCEMENT */}
              <div className="rounded-xl p-4 bg-gradient-to-r from-neutral-950 via-neutral-900 to-neutral-950 border border-amber-500/30 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <Headphones className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">
                          AI Background Noise Removal & Studio Voice
                        </span>
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">
                          AI DENOISE
                        </span>
                      </div>
                      <p className="text-[10px] text-neutral-400">
                        Isolates dialogue, eliminates room echo, microphone hiss, fan hum & background noise
                      </p>
                    </div>
                  </div>

                  {/* Master Noise Toggle */}
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={removeBackgroundNoise}
                      onChange={(e) => setRemoveBackgroundNoise(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-neutral-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500"></div>
                  </label>
                </div>

                {removeBackgroundNoise && (
                  <div className="space-y-3 pt-2 border-t border-neutral-800/80 animate-in fade-in duration-150">
                    {/* Noise Slider */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[11px] text-neutral-300 flex items-center gap-1">
                          <SlidersHorizontal className="w-3 h-3 text-amber-400" />
                          <span>Noise Suppression Strength:</span>
                        </span>
                        <span className="font-mono text-amber-400 font-bold text-xs">
                          {noiseReductionLevel}% (Studio Isolation)
                        </span>
                      </div>
                      <input
                        type="range"
                        min={30}
                        max={100}
                        step={5}
                        value={noiseReductionLevel}
                        onChange={(e) => setNoiseReductionLevel(Number(e.target.value))}
                        className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                      />
                      <div className="flex justify-between text-[9px] text-neutral-500 font-mono">
                        <span>Mild (Room Hum)</span>
                        <span>Balanced Studio</span>
                        <span>Max Vocal Isolation</span>
                      </div>
                    </div>

                    {/* Sub-Filters */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={roomEchoSuppression}
                          onChange={(e) => setRoomEchoSuppression(e.target.checked)}
                          className="w-3.5 h-3.5 rounded accent-amber-400"
                        />
                        <span className="text-[11px] text-neutral-300 font-medium truncate">
                          De-Reverb / Echo
                        </span>
                      </label>

                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={studioVoiceClarity}
                          onChange={(e) => setStudioVoiceClarity(e.target.checked)}
                          className="w-3.5 h-3.5 rounded accent-amber-400"
                        />
                        <span className="text-[11px] text-neutral-300 font-medium truncate">
                          Vocal Clarity EQ
                        </span>
                      </label>

                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={hissFilter}
                          onChange={(e) => setHissFilter(e.target.checked)}
                          className="w-3.5 h-3.5 rounded accent-amber-400"
                        />
                        <span className="text-[11px] text-neutral-300 font-medium truncate">
                          50/60Hz Hum Filter
                        </span>
                      </label>
                    </div>
                  </div>
                )}
              </div>

              {/* AI Auto-Editing Options */}
              <div className="border-t border-neutral-800/80 pt-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-amber-400" />
                    <span>Viral Style & Captions Setup</span>
                  </h3>
                  <span className="text-[11px] text-amber-400 font-medium">
                    ⚡ Auto-Reframed 9:16
                  </span>
                </div>

                {/* Subtitle Style Preset */}
                <div className="space-y-1.5">
                  <label className="text-xs text-neutral-400">Caption Typography & Animation:</label>
                  <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                    {CAPTION_PRESETS.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => setCaptionPreset(p.id)}
                        className={`p-2 rounded-xl border text-left transition-all ${
                          captionPreset === p.id
                            ? 'bg-neutral-800 border-amber-400 ring-1 ring-amber-400/30'
                            : 'bg-neutral-950 border-neutral-800 hover:border-neutral-700'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-white truncate">
                            {p.name}
                          </span>
                        </div>
                        <div className="mt-1.5 p-1 rounded bg-black/60 text-center font-extrabold text-[10px] truncate" style={{ color: p.previewHighlight }}>
                          {p.name.split(' ')[0]} VIRAL
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Intelligent Toggles */}
                <div className="grid sm:grid-cols-2 gap-3">
                  <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
                    <div className="flex items-center gap-2.5">
                      <Scissors className="w-4 h-4 text-emerald-400" />
                      <div>
                        <span className="text-xs font-bold text-white block">Auto Filler & Silence Cut</span>
                        <span className="text-[10px] text-neutral-400">Cut 'um', 'uh', & pauses &gt;0.5s</span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={removeFillers}
                      onChange={(e) => setRemoveFillers(e.target.checked)}
                      className="w-4 h-4 rounded accent-amber-400"
                    />
                  </label>

                  <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
                    <div className="flex items-center gap-2.5">
                      <Film className="w-4 h-4 text-rose-400" />
                      <div>
                        <span className="text-xs font-bold text-white block">AI B-Roll Cutaways</span>
                        <span className="text-[10px] text-neutral-400">Auto-match video footage to concepts</span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={autoBroll}
                      onChange={(e) => setAutoBroll(e.target.checked)}
                      className="w-4 h-4 rounded accent-amber-400"
                    />
                  </label>

                  <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
                    <div className="flex items-center gap-2.5">
                      <Volume2 className="w-4 h-4 text-sky-400" />
                      <div>
                        <span className="text-xs font-bold text-white block">Auto Sound Effects (SFX)</span>
                        <span className="text-[10px] text-neutral-400">Whooshes, dings, and sub drops</span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={autoSfx}
                      onChange={(e) => setAutoSfx(e.target.checked)}
                      className="w-4 h-4 rounded accent-amber-400"
                    />
                  </label>

                  <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
                    <div className="flex items-center gap-2.5">
                      <Zap className="w-4 h-4 text-amber-400" />
                      <div>
                        <span className="text-xs font-bold text-white block">Dynamic Auto-Zoom</span>
                        <span className="text-[10px] text-neutral-400">Boosts watch retention by +34%</span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={autoZoom}
                      onChange={(e) => setAutoZoom(e.target.checked)}
                      className="w-4 h-4 rounded accent-amber-400"
                    />
                  </label>
                </div>
              </div>
            </>
          ) : (
            /* Live AI Pipeline Processing Visualizer */
            <div className="py-8 space-y-6 text-center">
              <div className="relative w-20 h-20 mx-auto flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-4 border-amber-400/20 border-t-amber-400 animate-spin" />
                <Sparkles className="w-8 h-8 text-amber-400 animate-pulse" />
              </div>

              <div>
                <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">
                  AI Generation & Denoising Engine Active
                </h3>
                <p className="text-xs text-neutral-400 mt-1">
                  {sourceType === 'prompt_story'
                    ? 'Crafting narrative beats, cinematic B-roll scenes, and studio-isolated voiceover...'
                    : 'Analyzing speech cadence, virality hooks, cleaning audio, and auto-reframing video...'}
                </p>
              </div>

              {/* Download Progress Bar */}
              {downloadProgress && sourceType === 'url' && (
                <div className="max-w-md mx-auto p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-2 text-neutral-300">
                      <ArrowDown className="w-4 h-4 text-amber-400" />
                      <span className="font-semibold">
                        {downloadProgress.status === 'uploading' ? 'Uploading to cloud...' : 'Downloading video...'}
                      </span>
                    </span>
                    <span className="font-mono font-bold text-amber-400">
                      {(downloadProgress.percent ?? 0).toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 w-full bg-neutral-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-amber-500 to-rose-500 transition-all duration-300 ease-out"
                      style={{ width: `${Math.min(downloadProgress.percent ?? 0, 100)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-neutral-500 font-mono">
                    <span>{downloadProgress.total ? `Size: ${downloadProgress.total}` : 'Fetching...'}</span>
                    <span>{downloadProgress.speed ? `Speed: ${downloadProgress.speed}` : ''}</span>
                    <span>{downloadProgress.eta ? `ETA: ${downloadProgress.eta}` : ''}</span>
                  </div>
                </div>
              )}

              {/* Progress Steps */}
              <div className="max-w-md mx-auto space-y-2 text-left bg-neutral-950 p-4 rounded-xl border border-neutral-800 font-mono text-xs">
                {processingLogs.map((log, index) => (
                  <div key={index} className="flex items-start gap-2 text-neutral-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <span>{log}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!isProcessing && (
          <div className="px-6 py-4 border-t border-neutral-800 bg-neutral-950/80 flex items-center justify-between">
            <div className="text-[11px] text-neutral-400 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>
                {removeBackgroundNoise ? 'AI Audio Denoise & Clean Voice: ON' : 'AI Render Ready'}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
              >
                Cancel
              </button>
              <button
                id="btn-start-ai-generate"
                onClick={startAiProcessing}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 via-rose-500 to-violet-600 hover:from-amber-400 hover:to-violet-500 text-white text-xs font-bold shadow-lg shadow-rose-500/25 active:scale-95 transition-all flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>
                  {sourceType === 'prompt_story'
                    ? 'Generate AI Video Story'
                    : 'Generate Viral Clips Now'}
                </span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
