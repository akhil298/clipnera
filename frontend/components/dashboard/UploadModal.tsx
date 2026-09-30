"use client";
import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  Link as LinkIcon,
  Sparkles,
  X,
  CheckCircle2,
  Scissors,
  Film,
  Zap,
  Volume2,
  AlertCircle,
  Folder,
  Headphones,
  SlidersHorizontal,
  ExternalLink,
  ArrowDown,
  Upload,
  FileVideo
} from 'lucide-react';
import { VideoProject, AudioEnhancementConfig, DownloadProgress, AspectRatio } from '@/lib/types';
import { estimateVideoCredits, useEntitlements } from '@/hooks/useEntitlements';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { analyzeVideoSource, extractYoutubeVideoId } from '@/lib/utils/urlParser';
import { formatBytes, formatDuration, readVideoDuration, titleFromFileName } from '@/lib/utils/videoFile';
import { CaptionScript, clipApi, pipelineApi, uploadApi, VIDEO_UPLOAD_TYPES, VideoContentType, YouTubeMetadataResponse } from '@/lib/api';

type SourceMode = 'youtube' | 'upload';
import { PipelineProgressTracker } from './PipelineProgressTracker';
import { OutputFormatPicker } from './OutputFormatPicker';
import { ChannelIntroNudge } from './ChannelIntroNudge';
import { CHANNEL_INTRO_ANCHOR } from './ChannelIntroPanel';
import { NotWiredBadge } from '@/components/ui/NotWiredBadge';

/** A numbered section title, so the form reads as a short sequence. */
const StepHeading: React.FC<{ number: number; title: string }> = ({ number, title }) => (
  <h3 className="flex items-center gap-2 text-[13px] font-bold text-white">
    <span className="w-5 h-5 rounded-full bg-amber-500 text-neutral-950 text-[11px] font-extrabold flex items-center justify-center">
      {number}
    </span>
    {title}
  </h3>
);

interface UploadModalProps {
  isOpen: boolean;
  /** A YouTube link to start from, e.g. one pasted on Home. */
  initialUrl?: string;
  /** Which source tab opens first. */
  initialMode?: SourceMode;
  onClose: () => void;
  onProjectCreated: (project: VideoProject) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  initialUrl,
  initialMode,
  onClose,
  onProjectCreated,
}) => {
  const [sourceMode, setSourceMode] = useState<SourceMode>('youtube');
  const [urlInput, setUrlInput] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDuration, setUploadDuration] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploadAbortRef = useRef<AbortController | null>(null);
  // Filled from the video's title (or file name) once it is known.
  const [customTitle, setCustomTitle] = useState('');
  const [customFolderName, setCustomFolderName] = useState('');

  const { entitlements, promptUpgrade } = useEntitlements();
  const router = useRouter();
  const { flags } = useFeatureFlags();
  const uploadEnabled = flags.video_upload;
  const cutawaysEnabled = flags['broll_studio.cutaways'];
  // 9:16 on every plan; Pro can add more.
  const [outputRatios, setOutputRatios] = useState<AspectRatio[]>(['9:16']);

  const [autoBroll, setAutoBroll] = useState(true);
  const [autoSfx, setAutoSfx] = useState(true);
  const [removeFillers, setRemoveFillers] = useState(true);
  const [autoZoom, setAutoZoom] = useState(true);
  const [captionScript, setCaptionScript] = useState<CaptionScript>('auto');

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
    if (!extractYoutubeVideoId(trimmed)) return;

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

  // Opening from Home with a pasted link (or the Upload button) starts there.
  useEffect(() => {
    if (!isOpen) return;
    if (initialMode) setSourceMode(initialMode);
    if (initialUrl) setUrlInput(initialUrl);
  }, [isOpen, initialUrl, initialMode]);

  useEffect(() => {
    return () => {
      downloadUnsubRef.current?.();
      uploadAbortRef.current?.abort();
    };
  }, []);

  if (!isOpen) return null;

  const isYoutubeUrl = extractYoutubeVideoId(urlInput) !== null;
  const isUpload = uploadEnabled && sourceMode === 'upload';
  const sourceDurationSeconds = (isUpload ? uploadDuration : ytMeta?.duration_seconds) || null;
  // Same estimate the server charges, so a run it would refuse is stopped here.
  const creditsNeeded = sourceDurationSeconds
    ? estimateVideoCredits(entitlements, sourceDurationSeconds, outputRatios.length)
    : null;
  const hasEnoughCredits = creditsNeeded === null || creditsNeeded <= entitlements.credit_minutes_remaining;
  const canStart = (isUpload ? uploadFile !== null : isYoutubeUrl) && hasEnoughCredits;

  const handleFilePicked = async (file: File | undefined) => {
    setUploadFile(null);
    setUploadDuration(null);
    setUploadError(null);
    if (!file) return;
    if (!VIDEO_UPLOAD_TYPES.includes(file.type as VideoContentType)) {
      setUploadError('Use an MP4, MOV, WebM or MKV video.');
      return;
    }
    const duration = await readVideoDuration(file);
    const maxSeconds = entitlements?.max_upload_duration_seconds;
    if (duration && maxSeconds && duration > maxSeconds) {
      setUploadError(`This video is ${Math.floor(duration / 60)} min. Your plan supports up to ${Math.floor(maxSeconds / 60)} min per video.`);
      return;
    }
    const title = titleFromFileName(file.name);
    setUploadFile(file);
    setUploadDuration(duration);
    setCustomTitle(title);
    setCustomFolderName(title);
  };

  /** Sends the picked file to S3; resolves like a YouTube download that is still processing. */
  const uploadSource = async () => {
    const controller = new AbortController();
    uploadAbortRef.current = controller;
    const total = formatBytes(uploadFile!.size);
    const id = await uploadApi.uploadVideo(uploadFile!, {
      durationSeconds: uploadDuration ?? undefined,
      signal: controller.signal,
      onProgress: (percent) => setDownloadProgress({ status: 'uploading', percent, total, speed: null, eta: null }),
    });
    uploadAbortRef.current = null;
    return { id, status: 'processing' };
  };

  /** Fields that depend on where the video came from, shared by both project cards. */
  const sourceFields = () => {
    const meta = isUpload
      ? analyzeVideoSource(customTitle)
      : analyzeVideoSource(urlInput, { title: ytMeta?.title, channelTitle: ytMeta?.channel_title, thumbnailUrl: ytMeta?.thumbnail_url });
    return {
      meta,
      folderCategory: isUpload ? ('Upload' as const) : ('YouTube Ingest' as const),
      sourceUrl: isUpload ? '' : urlInput,
      sourceChannel: isUpload ? 'Upload' : meta.sourceChannel || 'YouTube',
      sourceType: isUpload ? ('upload' as const) : ('youtube_url' as const),
      sourceTag: isUpload ? 'Upload' : 'YouTube',
    };
  };

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
    setUploadError(null);
    setProcessingLogs([isUpload ? 'Uploading your video to the cloud...' : 'Ingesting YouTube video stream and initializing project folder...']);

    let projectId: string | null = null;
    let projectPublished = false;

    try {
      const downloadResult: any = isUpload ? await uploadSource() : await clipApi.downloadYoutube(urlInput);
      projectId = downloadResult?.id || null;

      if (projectId) {
        const { meta, folderCategory, sourceUrl, sourceChannel, sourceType, sourceTag } = sourceFields();
        onProjectCreated({
          id: projectId,
          title: customTitle || meta.cleanTitle,
          folderName: customFolderName || meta.folderName,
          folderCategory,
          folderColor: meta.folderColor || 'amber',
          sourceUrl,
          sourceChannel,
          description: `Project folder for ${customFolderName || meta.folderName}. Processing has started.`,
          tags: isUpload ? [sourceTag, 'AI', 'Shorts'] : meta.tags || [sourceTag, 'AI', 'Shorts'],
          genre: meta.genre,
          duration: isUpload ? Math.round(uploadDuration ?? 0) : meta.duration,
          sourceType,
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
        // The folder card now tracks progress; reset so reopening shows a fresh form.
        setIsProcessing(false);
        setUrlInput('');
        setUploadFile(null);
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
      if (isUpload && !projectPublished) {
        uploadAbortRef.current = null;
        setDownloadProgress(null);
        setUploadError(err instanceof DOMException && err.name === 'AbortError' ? 'Upload cancelled.' : message);
      }
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
      'scoring',
      'metadata_generation',
      'aspect_ratio_render',
      'clip_generation',
    ];

    try {
      setProcessingLogs((prev) => [...prev, 'Starting AI processing pipeline...']);
      setPipelineError(null);
      setPipelineStarted(false);

      const startResult = await pipelineApi.start(projectId!, steps, audioConfig, outputRatios, { caption_script: captionScript, broll: cutawaysEnabled && autoBroll });
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

    if (projectPublished) return;

    await new Promise((r) => setTimeout(r, 600));
    setProcessingStep(5);
    setProcessingLogs((prev) => [...prev, `Project Folder "${customFolderName}" created with viral clips ready!`]);

    await new Promise((r) => setTimeout(r, 500));

    const { meta, folderCategory, sourceUrl, sourceChannel, sourceType } = sourceFields();

    const newProject: VideoProject = {
      id: projectId || `proj-${Date.now()}`,
      title: customTitle || meta.cleanTitle,
      folderName: customFolderName || meta.folderName,
      folderCategory,
      folderColor: meta.folderColor || 'amber',
      sourceUrl,
      sourceChannel,
      description: `Project folder for ${customFolderName}. AI clips will be generated after processing.`,
      tags: meta.tags || ['Viral', 'Shorts', 'AI', 'Denoised'],
      genre: meta.genre,
      duration: isUpload ? Math.round(uploadDuration ?? 0) : meta.duration,
      sourceType,
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
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !isProcessing) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-video-title"
        className="relative w-full sm:max-w-3xl rounded-t-2xl sm:rounded-2xl bg-neutral-900 border border-neutral-800 shadow-2xl overflow-hidden flex flex-col max-h-[94dvh] sm:max-h-[92vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-4 border-b border-neutral-800 bg-neutral-950/70">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 id="new-video-title" className="text-base font-bold text-white">
                New video
              </h2>
              <p className="text-xs text-neutral-400">
                Turn one long video into short clips. You’ll see the cost before anything is charged.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-6 overscroll-contain">
          {!isProcessing ? (
            <>
              <ChannelIntroNudge onCreate={() => { onClose(); router.push(`/dashboard/brand-kit#${CHANNEL_INTRO_ANCHOR}`); }} />

              <StepHeading number={1} title="Source" />

              {/* Source picker: YouTube link or a video from this device (while uploads are switched on) */}
              {uploadEnabled && (
              <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-neutral-950 border border-neutral-800" role="tablist">
                {([
                  ['youtube', 'YouTube link', LinkIcon],
                  ['upload', 'Upload video', Upload],
                ] as const).map(([mode, label, Icon]) => (
                  <button
                    key={mode}
                    type="button"
                    role="tab"
                    aria-selected={sourceMode === mode}
                    onClick={() => setSourceMode(mode)}
                    className={`flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-colors ${
                      sourceMode === mode ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' : 'text-neutral-400 hover:text-white border border-transparent'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{label}</span>
                  </button>
                ))}
              </div>
              )}

              {/* Video source section */}
              <div className="space-y-3">
                {!isUpload && (
                <>
                <div className="flex items-center justify-between">
                  <label htmlFor="new-video-url" className="text-xs font-bold text-neutral-300 flex items-center gap-1.5">
                    <LinkIcon className="w-4 h-4 text-red-400" />
                    <span>YouTube link</span>
                  </label>
                  <span className="text-[11px] text-neutral-500">Creates a new project</span>
                </div>

                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <LinkIcon className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
                    <input
                      id="new-video-url"
                      type="url"
                      inputMode="url"
                      autoComplete="off"
                      value={urlInput}
                      onChange={(e) => handleUrlChange(e.target.value)}
                      placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                      className="w-full h-11 pl-9 pr-4 rounded-xl bg-neutral-950 border border-neutral-800 text-[13px] text-white placeholder-neutral-600 focus:outline-none focus:border-amber-400"
                    />
                  </div>
                </div>

                {urlInput.trim() && !isYoutubeUrl && (
                  <div className="flex items-center gap-2 text-[11px] text-rose-400">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>Only YouTube video links are supported (youtube.com/watch, youtu.be, or Shorts).</span>
                  </div>
                )}

                {/* YouTube thumbnail + metadata preview */}
                {(metadataLoading || ytMetaError || ytMeta) && (
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/80 overflow-hidden">
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
                      <div className="relative w-28 sm:w-40 aspect-video rounded-lg overflow-hidden bg-neutral-900 border border-neutral-800 shrink-0">
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
                )}
                </>
                )}

                {isUpload && (
                  <div className="space-y-2">
                    <label
                      htmlFor="upload-video-file"
                      className="flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed border-neutral-800 bg-neutral-950/80 cursor-pointer hover:border-amber-500/50 transition-colors text-center"
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        handleFilePicked(e.dataTransfer.files?.[0]);
                      }}
                    >
                      <Upload className="w-6 h-6 text-amber-400" />
                      <span className="text-xs font-bold text-white">Drop a video here or click to choose</span>
                      <span className="text-[10px] text-neutral-500">
                        MP4, MOV, WebM or MKV · up to {Math.floor((entitlements?.max_upload_duration_seconds ?? 1800) / 60)} min on your plan
                      </span>
                      <input
                        id="upload-video-file"
                        type="file"
                        accept={VIDEO_UPLOAD_TYPES.join(',')}
                        className="sr-only"
                        onChange={(e) => handleFilePicked(e.target.files?.[0])}
                      />
                    </label>

                    {uploadFile && (
                      <div className="flex items-center gap-3 p-3 rounded-xl border border-amber-500/30 bg-neutral-950/80">
                        <FileVideo className="w-5 h-5 text-amber-400 shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-white truncate">{uploadFile.name}</p>
                          <p className="text-[10px] text-neutral-400 font-mono">
                            {formatBytes(uploadFile.size)}
                            {uploadDuration ? ` · ${formatDuration(uploadDuration)}` : ''}
                          </p>
                        </div>
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      </div>
                    )}

                    {uploadError && (
                      <div className="flex items-center gap-2 text-[11px] text-rose-400">
                        <AlertCircle className="w-4 h-4 shrink-0" />
                        <span>{uploadError}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Project Folder Destination Preview Card */}
                <div className="p-3 rounded-xl bg-neutral-950/80 border border-neutral-800 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <label htmlFor="new-video-project-name" className="flex items-center gap-1.5 text-neutral-300 font-semibold text-[11px]">
                      <Folder className="w-3.5 h-3.5 text-amber-400" />
                      <span>Project name</span>
                    </label>
                    <span className="text-[11px] text-neutral-500">Filled from the video title</span>
                  </div>

                  <input
                    id="new-video-project-name"
                    type="text"
                    value={customFolderName}
                    onChange={(e) => setCustomFolderName(e.target.value)}
                    placeholder={isUpload ? 'Uses the file name if left empty' : 'Uses the video title if left empty'}
                    className="w-full h-10 px-3 rounded-lg bg-neutral-900 border border-neutral-800 text-[13px] font-semibold text-white placeholder:font-normal placeholder:text-neutral-600 focus:outline-none focus:border-amber-400"
                  />
                </div>
              </div>

              <StepHeading number={2} title="Clean up audio" />

              {/* AI background noise removal and audio enhancement */}
              <div className="rounded-xl p-4 bg-neutral-950/80 border border-neutral-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      <Headphones className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">
                          Studio voice
                        </span>
                      </div>
                      <p className="text-[10px] text-neutral-400">
                        Removes room echo, microphone hiss, fan hum and background noise
                      </p>
                    </div>
                  </div>

                  <label className="relative inline-flex items-center cursor-pointer shrink-0">
                    <span className="sr-only">Studio voice</span>
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
                          <span>Strength</span>
                        </span>
                        <span className="text-amber-300 font-bold text-xs tabular-nums">
                          {noiseSuppressionStrength}% · {noiseSuppressionStrength >= 80 ? 'Maximum' : noiseSuppressionStrength >= 55 ? 'Balanced' : 'Light'}
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
                      <div className="flex justify-between text-[10px] text-neutral-500">
                        <span>Light</span>
                        <span>Balanced</span>
                        <span>Maximum</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={deReverb}
                          onChange={(e) => setDeReverb(e.target.checked)}
                          className="w-3.5 h-3.5 rounded accent-amber-400"
                        />
                        <span className="text-[11px] text-neutral-300 font-medium">
                          Remove echo
                        </span>
                      </label>

                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={vocalClarityEq}
                          onChange={(e) => setVocalClarityEq(e.target.checked)}
                          className="w-3.5 h-3.5 rounded accent-amber-400"
                        />
                        <span className="text-[11px] text-neutral-300 font-medium">
                          Voice clarity EQ
                        </span>
                      </label>

                      <label className="flex items-center gap-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800/80 cursor-pointer hover:border-neutral-700">
                        <input
                          type="checkbox"
                          checked={humFilter}
                          onChange={(e) => setHumFilter(e.target.checked)}
                          className="w-3.5 h-3.5 rounded accent-amber-400"
                        />
                        <span className="text-[11px] text-neutral-300 font-medium">
                          50/60 Hz hum filter
                        </span>
                      </label>
                    </div>
                  </div>
                )}
              </div>

              <StepHeading number={3} title="Output formats" />

              <OutputFormatPicker
                value={outputRatios}
                onChange={setOutputRatios}
                durationSeconds={sourceDurationSeconds}
              />

              {!hasEnoughCredits && creditsNeeded !== null && (
                <div className="flex items-center justify-between gap-3 rounded-xl bg-rose-500/10 border border-rose-500/30 px-3 py-2.5">
                  <span className="text-[11px] text-rose-200">
                    This video needs <span className="font-bold">{creditsNeeded} credits</span>; you have{' '}
                    <span className="font-bold">{entitlements.credit_minutes_remaining}</span>. Pick fewer formats or get more credits.
                  </span>
                  <div className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        onClose();
                        router.push('/dashboard/settings?tab=billing');
                      }}
                      className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-white text-[11px] font-bold transition-colors"
                    >
                      Buy credits
                    </button>
                    <button
                      type="button"
                      onClick={() => promptUpgrade('More credits every month')}
                      className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[11px] font-bold transition-colors"
                    >
                      Upgrade plan
                    </button>
                  </div>
                </div>
              )}

              {/* AI Auto-Editing Options */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <StepHeading number={4} title="Clip style" />
                  <span className="text-[11px] text-neutral-500">
                    {`Reframed ${outputRatios.join(' · ')}`}
                  </span>
                </div>

                <div className="grid sm:grid-cols-2 gap-3">
                  <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
                    <div className="flex items-center gap-2.5">
                      <Scissors className="w-4 h-4 text-emerald-400" />
                      <div>
                        <span className="text-xs font-bold text-white flex flex-wrap items-center gap-1.5">Auto filler & silence cut <NotWiredBadge label="Not wired" reason="This switch is not sent to the pipeline yet, so it has no effect." /></span>
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

                  {cutawaysEnabled && (
                  <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
                    <div className="flex items-center gap-2.5">
                      <Film className="w-4 h-4 text-rose-400" />
                      <div>
                        <span className="text-xs font-bold text-white block">AI B-roll cutaways</span>
                        <span className="text-[10px] text-neutral-400">Auto-match footage to concepts · 5 credits per clip that gets B-roll</span>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={autoBroll}
                      onChange={(e) => setAutoBroll(e.target.checked)}
                      className="w-4 h-4 rounded accent-amber-400"
                    />
                  </label>
                  )}

                  <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
                    <div className="flex items-center gap-2.5">
                      <Volume2 className="w-4 h-4 text-sky-400" />
                      <div>
                        <span className="text-xs font-bold text-white flex flex-wrap items-center gap-1.5">Auto sound effects <NotWiredBadge label="Not wired" reason="This switch is not sent to the pipeline yet, so it has no effect." /></span>
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

                  <div className="sm:col-span-2 flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-neutral-950 border border-neutral-800">
                    <div>
                      <span className="text-xs font-bold text-white block">Hindi / Telugu caption script</span>
                      <span className="text-[10px] text-neutral-400">Auto writes Hinglish & Tenglish in Roman letters</span>
                    </div>
                    <div className="flex gap-1 p-0.5 rounded-lg bg-neutral-900 border border-neutral-800" role="radiogroup">
                      {([
                        ['auto', 'Auto'],
                        ['roman', 'Roman'],
                        ['native', 'Native'],
                      ] as const).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          role="radio"
                          aria-checked={captionScript === value}
                          onClick={() => setCaptionScript(value)}
                          className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-colors ${
                            captionScript === value ? 'bg-amber-500/20 text-amber-300' : 'text-neutral-400 hover:text-white'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <label className="flex items-center justify-between p-3 rounded-xl bg-neutral-950 border border-neutral-800 cursor-pointer hover:border-neutral-700">
                    <div className="flex items-center gap-2.5">
                      <Zap className="w-4 h-4 text-amber-400" />
                      <div>
                        <span className="text-xs font-bold text-white flex flex-wrap items-center gap-1.5">Dynamic auto-zoom <NotWiredBadge label="Not wired" reason="This switch is not sent to the pipeline yet, and renders apply no zoom." /></span>
                        <span className="text-[10px] text-neutral-400">Zooms in on key words</span>
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
                      <h3 className="text-base font-bold text-white mt-4">
                        Setting up your project
                      </h3>
                      <p className="text-xs text-neutral-400 mt-1">
                        {isUpload ? 'Uploading your video. Keep this tab open until the upload finishes.' : 'Fetching the video from YouTube.'}
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
                          className="h-full bg-amber-500 transition-all duration-300 ease-out"
                          style={{ width: `${Math.min(downloadProgress.percent ?? 0, 100)}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-neutral-500 font-mono">
                        <span>{downloadProgress.total ? `Size: ${downloadProgress.total}` : 'Fetching...'}</span>
                        <span>{downloadProgress.speed ? `Speed: ${downloadProgress.speed}` : ''}</span>
                        <span>{downloadProgress.eta ? `ETA: ${downloadProgress.eta}` : ''}</span>
                      </div>
                      {isUpload && downloadProgress.status === 'uploading' && (
                        <button
                          type="button"
                          onClick={() => uploadAbortRef.current?.abort()}
                          className="w-full py-1.5 rounded-lg text-[11px] font-semibold text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
                        >
                          Cancel upload
                        </button>
                      )}
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

        {/* Footer: what it costs and the one action */}
        {!isProcessing && (
          <div className="px-4 sm:px-6 py-3.5 border-t border-neutral-800 bg-neutral-950/80 flex flex-wrap items-center gap-3 pb-[max(0.875rem,env(safe-area-inset-bottom))]">
            <div className="min-w-0 flex-1 text-[11.5px] leading-snug">
              {creditsNeeded !== null ? (
                <>
                  <span className="font-bold text-white tabular-nums">{creditsNeeded} credits</span>
                  <span className="text-neutral-400">
                    {' '}· {Math.max(0, entitlements.credit_minutes_remaining - creditsNeeded)} left after
                  </span>
                </>
              ) : (
                <span className="text-neutral-400">
                  {isUpload
                    ? uploadFile
                      ? 'Reading the video length…'
                      : 'Choose a video to see the cost'
                    : isYoutubeUrl
                      ? 'Checking the video length…'
                      : 'Paste a YouTube link to see the cost'}
                </span>
              )}
              <span className="hidden sm:block text-neutral-500">
                {outputRatios.length} format{outputRatios.length === 1 ? '' : 's'}
                {aiDenoise ? ' · studio voice on' : ''}
              </span>
            </div>
            <button
              onClick={onClose}
              className="hidden sm:block h-10 px-4 rounded-xl text-xs font-semibold text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
            >
              Cancel
            </button>
            <button
              id="btn-start-ai-generate"
              onClick={startAiProcessing}
              disabled={!canStart}
              className="h-10 px-5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold shadow-md shadow-amber-500/20 active:scale-[0.98] transition-all flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100"
            >
              <Sparkles className="w-4 h-4" />
              <span>{creditsNeeded !== null ? `Generate clips · ${creditsNeeded} credits` : 'Generate clips'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
