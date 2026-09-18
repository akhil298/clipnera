"use client";
import React, { useState, useEffect, useRef } from 'react';
import {
  Link as LinkIcon,
  Sparkles,
  X,
  CheckCircle2,
  Sliders,
  Scissors,
  Film,
  Zap,
  Volume2,
  AlertCircle,
  Folder,
  Headphones,
  SlidersHorizontal,
  ExternalLink,
  ArrowDown
} from 'lucide-react';
import { VideoProject, CaptionPreset, AudioEnhancementConfig, DownloadProgress } from '@/lib/types';
import { CAPTION_PRESETS } from '@/lib/data/mockProjects';
import { analyzeVideoSource } from '@/lib/utils/urlParser';
import { clipApi, pipelineApi, YouTubeMetadataResponse } from '@/lib/api';
import { PipelineProgressTracker } from './PipelineProgressTracker';

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
  const [urlInput, setUrlInput] = useState('');
  const [customTitle, setCustomTitle] = useState('Alex Hormozi — $100M Leads Masterclass');
  const [customFolderName, setCustomFolderName] = useState('Alex Hormozi — $100M Leads Masterclass');

  const [captionPreset, setCaptionPreset] = useState<CaptionPreset>('hormozi');
  const [autoBroll, setAutoBroll] = useState(true);
  const [autoSfx, setAutoSfx] = useState(true);
  const [removeFillers, setRemoveFillers] = useState(true);
  const [autoZoom, setAutoZoom] = useState(true);

  const [aiDenoise, setAiDenoise] = useState(true);
  const [noiseSuppressionStrength, setNoiseSuppressionStrength] = useState(90);
  const [deReverb, setDeReverb] = useState(true);
  const [vocalClarityEq, setVocalClarityEq] = useState(true);
  const [humFilter, setHumFilter] = useState(true);

  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState(0);
  const [processingLogs, setProcessingLogs] = useState<string[]>([]);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [ytMeta, setYtMeta] = useState<YouTubeMetadataResponse | null>(null);
  const [ytMetaError, setYtMetaError] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);
  const downloadUnsubRef = useRef<(() => void) | null>(null);

  const [pipelineStarted, setPipelineStarted] = useState(false);
  const [pipelineProjectId, setPipelineProjectId] = useState<string | null>(null);
  const [pipelineSteps, setPipelineSteps] = useState<string[]>([]);
  const [creditsDeducted, setCreditsDeducted] = useState<number>(0);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  useEffect(() => {
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
  }, [urlInput]);

  useEffect(() => {
    return () => {
      downloadUnsubRef.current?.();
    };
  }, []);

  if (!isOpen) return null;

  const handleUrlChange = (newUrl: string) => {
    setUrlInput(newUrl);
  };

  const audioEnhanceConfig: AudioEnhancementConfig = {
    aiDenoise,
    noiseSuppressionStrength,
    deReverb,
    vocalClarityEq,
    humFilter,
  };

  const startAiProcessing = async () => {
    setIsProcessing(true);
    setProcessingStep(1);
    setDownloadProgress(null);
    setProcessingLogs(['Ingesting YouTube video stream and initializing project folder...']);

    let projectId: string | null = null;
    let projectPublished = false;

    try {
      const downloadResult: any = await clipApi.downloadYoutube(urlInput);
      projectId = downloadResult?.id || null;

      if (projectId) {
        const meta = analyzeVideoSource(urlInput, { title: ytMeta?.title, channelTitle: ytMeta?.channel_title });
        onProjectCreated({
          id: projectId,
          title: customTitle || meta.cleanTitle,
          folderName: customFolderName || meta.folderName,
          folderCategory: 'YouTube Ingest',
          folderColor: meta.folderColor || 'amber',
          sourceUrl: urlInput,
          sourceChannel: meta.sourceChannel || 'YouTube',
          description: `Project folder for ${customFolderName || meta.folderName}. Processing has started.`,
          tags: meta.tags || ['YouTube', 'AI', 'Shorts'],
          genre: meta.genre,
          duration: meta.duration,
          sourceType: 'youtube_url',
          videoUrl: '',
          posterUrl: meta.posterUrl,
          uploadedAt: new Date().toISOString(),
          syncStatus: 'syncing',
          offlineAvailable: false,
          clips: [],
          transcript: [],
          processingProgress: 0,
          processingStatus: 'processing',
          audioEnhancement: audioEnhanceConfig,
        });
        projectPublished = true;
        onClose();
      }

      if (projectId && downloadResult?.status === 'processing') {
        await new Promise<void>((resolve, reject) => {
          const unsub = clipApi.subscribeDownloadProgress(
            projectId!,
            (progress) => {
              setDownloadProgress(progress);
              if (progress.status === 'done') {
                setProcessingLogs((prev) => [...prev, 'Video source downloaded & stored successfully!']);
                unsub();
                resolve();
              } else if (progress.status === 'error') {
                setProcessingLogs((prev) => [...prev, `Download failed: ${progress.message || 'Unknown error'}`]);
                unsub();
                reject(new Error(progress.message || 'Download failed'));
              }
            },
            (err) => {
              setProcessingLogs((prev) => [...prev, `Download stream error: ${err.message}`]);
              unsub();
              reject(err);
            },
          );
        });
      } else if (!projectId || downloadResult?.status !== 'done') {
        throw new Error('Download did not complete successfully.');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Video download failed.';
      setProcessingLogs((prev) => [...prev, message]);
      setPipelineError(message);
      setIsProcessing(false);
      return;
    }

    const audioConfig = {
      aiDenoise,
      noiseSuppressionStrength,
      deReverb,
      vocalClarityEq,
      humFilter,
    };

    // Pipeline steps (download already done, so skip it)
    const steps = [
      'audio_extraction',
      'ai_noise_cancellation',
      'transcription',
      'topic_research',
      'visual_analysis',
      'content_classification',
      'highlight_detection',
      'bounding_box_detection',
      'scoring',
      'metadata_generation',
      'aspect_ratio_render',
      'clip_generation',
    ];

    try {
      setProcessingLogs((prev) => [...prev, 'Starting AI processing pipeline...']);
      setPipelineError(null);
      setPipelineStarted(false);

      const startResult = await pipelineApi.start(projectId!, steps, audioConfig);
      setPipelineSteps(startResult.selected_steps || steps);
      setCreditsDeducted(startResult.credits_deducted || 0);

      setPipelineStarted(true);
      setPipelineProjectId(projectId!);
      setProcessingLogs((prev) => [...prev, `Pipeline started. Credits deducted: ${startResult.credits_deducted || 0}`]);

      await new Promise((resolve) => {
        const interval = setInterval(async () => {
          try {
            const status = await pipelineApi.getStatus(projectId!);
            if (status.error) {
              clearInterval(interval);
              setPipelineError(status.error);
              setProcessingLogs((prev) => [...prev, `Pipeline error: ${status.error}`]);
              resolve(false);
            } else if (status.is_completed) {
              clearInterval(interval);
              setProcessingStep(5);
              setProcessingLogs((prev) => [...prev, 'Pipeline completed successfully!']);
              resolve(true);
            } else {
              setProcessingLogs((prev) => {
                const last = prev[prev.length - 1] || '';
                const currentSteps = status.steps?.filter((s: any) => s.status === 'running');
                if (currentSteps && currentSteps.length > 0) {
                  const msg = currentSteps[0].message || '';
                  if (msg && msg !== last) {
                    return [...prev.slice(0, -1), msg];
                  }
                }
                return prev;
              });
            }
          } catch {
            clearInterval(interval);
            resolve(false);
          }
        }, 2000);
      });
    } catch (err) {
      setProcessingLogs((prev) => [...prev, 'Pipeline encountered an issue. Using local simulation fallback...']);
    }

    if (projectPublished) {
      setIsProcessing(false);
      return;
    }

    await new Promise((r) => setTimeout(r, 600));
    setProcessingStep(5);
    setProcessingLogs((prev) => [...prev, `Project Folder "${customFolderName}" created with viral clips ready!`]);

    await new Promise((r) => setTimeout(r, 500));

    const meta = analyzeVideoSource(urlInput, { title: ytMeta?.title, channelTitle: ytMeta?.channel_title });

    const newProject: VideoProject = {
      id: projectId || `proj-${Date.now()}`,
      title: customTitle || meta.cleanTitle,
      folderName: customFolderName || meta.folderName,
      folderCategory: 'YouTube Ingest',
      folderColor: meta.folderColor || 'amber',
      sourceUrl: urlInput,
      sourceChannel: meta.sourceChannel || 'YouTube',
      description: `Project folder for ${customFolderName}. AI clips will be generated after processing.`,
      tags: meta.tags || ['Viral', 'Shorts', 'AI', 'Denoised'],
      genre: meta.genre,
      duration: meta.duration,
      sourceType: 'youtube_url',
      videoUrl: '',
      posterUrl: meta.posterUrl,
      uploadedAt: new Date().toISOString(),
      syncStatus: downloadProgress?.status === 'done' ? 'synced' : 'syncing',
      offlineAvailable: downloadProgress?.status === 'done',
      clips: [],
      transcript: [],
      audioEnhancement: audioEnhanceConfig,
      creditsDeducted: creditsDeducted,
      pipelineSteps: pipelineSteps.map((s) => ({
        step: s,
        status: 'pending',
        progress_percent: 0,
        message: null,
        artifact_path: null,
        started_at: null,
        finished_at: null,
      })),
      processingProgress: downloadProgress?.status === 'done' && !pipelineError ? 100 : downloadProgress?.status === 'error' ? 0 : Math.round(downloadProgress?.percent ?? 0),
      processingStatus: pipelineError ? 'failed' : downloadProgress?.status === 'done' ? 'completed' : 'processing',
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
                Generate viral 9:16 Shorts from any YouTube link
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
              {/* YouTube URL Section */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-neutral-300 flex items-center gap-1.5">
                    <LinkIcon className="w-4 h-4 text-red-400" />
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
                            <LinkIcon className="w-6 h-6" />
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

                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={aiDenoise}
                      onChange={(e) => setAiDenoise(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-neutral-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500"></div>
                  </label>
                </div>

                {aiDenoise && (
                  <div className="space-y-3 pt-2 border-t border-neutral-800/80 animate-in fade-in duration-150">
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[11px] text-neutral-300 flex items-center gap-1">
                          <SlidersHorizontal className="w-3 h-3 text-amber-400" />
                          <span>Noise Suppression Strength:</span>
                        </span>
                        <span className="font-mono text-amber-400 font-bold text-xs">
                          {noiseSuppressionStrength}% (Studio Isolation)
                        </span>
                      </div>
                      <input
                        type="range"
                        min={30}
                        max={100}
                        step={5}
                        value={noiseSuppressionStrength}
                        onChange={(e) => setNoiseSuppressionStrength(Number(e.target.value))}
                        className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
                      />
                      <div className="flex justify-between text-[9px] text-neutral-500 font-mono">
                        <span>Mild (Room Hum)</span>
                        <span>Balanced Studio</span>
                        <span>Max Vocal Isolation</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={deReverb}
                          onChange={(e) => setDeReverb(e.target.checked)}
                          className="w-3.5 h-3.5 rounded accent-amber-400"
                        />
                        <span className="text-[11px] text-neutral-300 font-medium truncate">
                          De-Reverb / Echo
                        </span>
                      </label>

                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={vocalClarityEq}
                          onChange={(e) => setVocalClarityEq(e.target.checked)}
                          className="w-3.5 h-3.5 rounded accent-amber-400"
                        />
                        <span className="text-[11px] text-neutral-300 font-medium truncate">
                          Vocal Clarity EQ
                        </span>
                      </label>

                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={humFilter}
                          onChange={(e) => setHumFilter(e.target.checked)}
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
                    Auto-Reframed 9:16
                  </span>
                </div>

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
            <div className="py-6 space-y-6">
              {!pipelineStarted ? (
                <>
                  <div className="text-center py-8">
                    <div className="relative w-20 h-20 mx-auto flex items-center justify-center">
                      <div className="absolute inset-0 rounded-full border-4 border-amber-400/20 border-t-amber-400 animate-spin" />
                      <Sparkles className="w-8 h-8 text-amber-400 animate-pulse" />
                    </div>

                    <div>
                      <h3 className="text-base font-bold text-white font-['Syne',sans-serif]">
                        AI Generation & Denoising Engine Active
                      </h3>
                      <p className="text-xs text-neutral-400 mt-1">
                        Analyzing speech cadence, virality hooks, cleaning audio, and auto-reframing video...
                      </p>
                    </div>
                  </div>

                  {downloadProgress && (
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

                  <div className="max-w-md mx-auto space-y-2 text-left bg-neutral-950 p-4 rounded-xl border border-neutral-800 font-mono text-xs">
                    {processingLogs.map((log, index) => (
                      <div key={index} className="flex items-start gap-2 text-neutral-300">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                        <span>{log}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="max-w-3xl mx-auto w-full">
                  <PipelineProgressTracker
                    projectId={pipelineProjectId || ''}
                    selectedSteps={pipelineSteps}
                    creditsDeducted={creditsDeducted}
                    isDownloadComplete={downloadProgress?.status === 'done'}
                    downloadProgress={downloadProgress ?? undefined}
                  />

                  <div className="mt-4 max-w-md mx-auto space-y-2 text-left bg-neutral-950 p-4 rounded-xl border border-neutral-800 font-mono text-xs">
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
          )}
        </div>

        {/* Footer */}
        {!isProcessing && (
          <div className="px-6 py-4 border-t border-neutral-800 bg-neutral-950/80 flex items-center justify-between">
            <div className="text-[11px] text-neutral-400 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>
                {aiDenoise ? 'AI Audio Denoise & Clean Voice: ON' : 'AI Render Ready'}
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
                <span>Generate Viral Clips Now</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
