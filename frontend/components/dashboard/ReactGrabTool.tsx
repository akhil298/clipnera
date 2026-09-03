"use client";
import React, { useState, useEffect, useRef } from 'react';
import {
  Youtube,
  Link as LinkIcon,
  Sparkles,
  Download,
  Pause,
  Play,
  AlertCircle,
  CheckCircle2,
  X,
  Clock,
  Tv,
  Music,
  HardDrive,
  ExternalLink,
  Film,
} from 'lucide-react';
import {
  YouTubeMetadataResponse,
  AvailableFormatsResponse,
  FormatInfo,
  DownloadProgress,
} from '@/lib/api';
import { clipApi } from '@/lib/api';
import { useDownloadProgress } from '@/hooks/useDownloadProgress';

export interface GrabResult {
  id: string;
  title: string;
  thumbnailUrl: string;
  channelTitle: string;
  durationFormatted: string;
  resolution: string;
  fileSize?: number;
  presignedUrl?: string;
  originalUrl: string;
}

export interface ReactGrabToolProps {
  onVideoGrabbed?: (result: GrabResult) => void;
  defaultUrl?: string;
  maxW?: string;
}

const YOUTUBE_URL_REGEX = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)/;

const formatFileSize = (bytes: number): string => {
  if (!bytes || bytes === 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
};

const formatTime = (seconds: number): string => {
  if (!seconds) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

export const ReactGrabTool: React.FC<ReactGrabToolProps> = ({
  onVideoGrabbed,
  defaultUrl = '',
  maxW = 'max-w-xl',
}) => {
  const [url, setUrl] = useState(defaultUrl);
  const [metadata, setMetadata] = useState<YouTubeMetadataResponse | null>(null);
  const [formats, setFormats] = useState<AvailableFormatsResponse | null>(null);
  const [selectedFormatId, setSelectedFormatId] = useState<string | null>(null);
  const [metaLoading, setMetaLoading] = useState(false);
  const [formatsLoading, setFormatsLoading] = useState(false);
  const [grabState, setGrabState] = useState<'idle' | 'fetching_meta' | 'fetching_formats' | 'grabbing' | 'complete' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const debouncedMetaRef = useRef<NodeJS.Timeout | null>(null);

  const { progress, start: startProgress, stop: stopProgress, reset: resetProgress } = useDownloadProgress();

  useEffect(() => {
    if (debouncedMetaRef.current) {
      clearTimeout(debouncedMetaRef.current);
    }

    const trimmed = url.trim();
    setMetadata(null);
    setFormats(null);
    setSelectedFormatId(null);
    setError(null);

    if (!trimmed || trimmed.length < 8) return;

    const isYoutube = YOUTUBE_URL_REGEX.test(trimmed);
    if (!isYoutube) return;

    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        setMetaLoading(true);
        setGrabState('fetching_meta');
        const meta = await clipApi.fetchYoutubeMetadata(trimmed);
        if (!cancelled) {
          setMetadata(meta);
          setGrabState('idle');
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message || 'Could not fetch video metadata.');
          setGrabState('error');
        }
      } finally {
        if (!cancelled) setMetaLoading(false);
      }
    }, 600);

    debouncedMetaRef.current = timer as unknown as NodeJS.Timeout;

    return () => {
      clearTimeout(timer);
      cancelled = true;
    };
  }, [url]);

  const fetchFormats = async () => {
    const trimmed = url.trim();
    if (!trimmed || !metadata) return;

    try {
      setFormatsLoading(true);
      setGrabState('fetching_formats');
      const data = await clipApi.fetchFormats(trimmed);
      setFormats(data);

      const defaultFormat = data.video.find((f) => f.height >= 1080) || data.video[0] || data.audio[0];
      if (defaultFormat) {
        setSelectedFormatId(defaultFormat.format_id);
      }
    } catch (err) {
      setError((err as Error).message || 'Could not fetch available formats.');
      setGrabState('error');
    } finally {
      setFormatsLoading(false);
    }
  };

  useEffect(() => {
    if (metadata && !formats && grabState !== 'fetching_formats') {
      // formats aren't auto-fetched; user triggers via the grab button
    }
  }, [metadata, formats, grabState]);

  const handleGrab = async () => {
    const trimmed = url.trim();
    if (!trimmed) {
      setError('Please enter a YouTube URL.');
      return;
    }

    if (!YOUTUBE_URL_REGEX.test(trimmed)) {
      setError('Please enter a valid YouTube URL.');
      return;
    }

    try {
      setError(null);
      resetProgress();

      if (!formats) {
        const data = await clipApi.fetchFormats(trimmed);
        setFormats(data);
        const defaultFormat = data.video.find((f) => f.height >= 1080) || data.video[0] || data.audio[0];
        if (defaultFormat) {
          setSelectedFormatId(defaultFormat.format_id);
        }
      }

      const selectedFormat = formats?.video.find((f) => f.format_id === selectedFormatId)
        || formats?.audio.find((f) => f.format_id === selectedFormatId)
        || null;

      setGrabState('grabbing');
      const downloadResult = await clipApi.downloadYoutube(trimmed, selectedFormat?.format_id);

      const pid = downloadResult?.id || downloadResult?.project_id || null;
      if (pid) {
        setProjectId(pid);
        startProgress(pid);
      }

      setGrabState('complete');
      setGrabState('idle');

      const result: GrabResult = {
        id: downloadResult?.id || `grabbed-${Date.now()}`,
        title: downloadResult?.title || metadata?.title || 'Unknown Video',
        thumbnailUrl: downloadResult?.thumbnail_url || metadata?.thumbnail_url || '',
        channelTitle: downloadResult?.channel_title || metadata?.channel_title || '',
        durationFormatted: downloadResult?.duration_formatted || metadata?.duration_formatted || '—',
        resolution: downloadResult?.resolution || metadata?.resolution || 'Unknown',
        fileSize: downloadResult?.file_size,
        presignedUrl: downloadResult?.presigned_url,
        originalUrl: downloadResult?.original_url || trimmed,
      };

      onVideoGrabbed?.(result);
    } catch (err) {
      setError((err as Error).message || 'Failed to grab video. Please try again.');
      setGrabState('error');
    }
  };

  const isLoading = metaLoading || formatsLoading;

  const getFormatLabel = (f: FormatInfo): string => {
    if (f.height > 0) return `${f.height}p`;
    if (f.type === 'audio') return `Audio ${f.abr}kbps`;
    return f.ext;
  };

  const getQualityOptions = (): FormatInfo[] => {
    const video = formats?.video || [];
    const audio = formats?.audio || [];
    const seen = new Set<number>();
    const deduped: FormatInfo[] = [];
    video.forEach((f) => {
      if (!seen.has(f.height) && f.height > 0) {
        seen.add(f.height);
        deduped.push(f);
      }
    });
    return deduped.length > 0 ? deduped : video.concat(audio);
  };

  const isDownloading = progress.status === 'downloading' || progress.status === 'uploading';

  return (
    <div className={`${maxW} w-full mx-auto animate-in fade-in duration-300`}>
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 shadow-xl overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-neutral-800 bg-neutral-950/70">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Youtube className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-bold text-white font-['Syne',sans-serif]">
              React Grab Tool
            </h2>
            <span className="ml-auto text-[10px] font-mono font-semibold bg-amber-500/10 text-amber-300 px-2 py-0.5 rounded border border-amber-500/20">
              yt-dlp
            </span>
          </div>
          <p className="text-[11px] text-neutral-500 mt-0.5">
            Grab YouTube videos with quality selection and real-time progress tracking.
          </p>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* URL Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-neutral-300 flex items-center gap-1.5">
              <LinkIcon className="w-3.5 h-3.5 text-neutral-400" />
              <span>YouTube Video URL:</span>
            </label>
            <div className="relative">
              <Youtube className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-500" />
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                disabled={isDownloading}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white placeholder-neutral-600 focus:outline-none focus:border-amber-400 font-mono transition-colors"
              />
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Metadata Preview */}
          {metaLoading && (
            <div className="flex items-center gap-3 p-3">
              <div className="w-40 aspect-video rounded-lg bg-neutral-900 animate-pulse shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 w-3/4 rounded bg-neutral-800 animate-pulse" />
                <div className="h-3 w-1/2 rounded bg-neutral-800 animate-pulse" />
              </div>
            </div>
          )}

          {/* Metadata Error */}
          {grabState === 'error' && !metadata && !error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>Could not verify this YouTube link. Check the URL or your connection.</span>
            </div>
          )}

          {/* Metadata Success Card */}
          {metadata && !metaLoading && (
            <div className="rounded-xl border border-amber-500/20 bg-neutral-950/80 overflow-hidden">
              <div className="flex gap-3 p-3">
                <div className="relative w-40 aspect-video rounded-lg overflow-hidden bg-neutral-900 border border-neutral-800 shrink-0">
                  {metadata.thumbnail_url ? (
                    <img
                      src={metadata.thumbnail_url}
                      alt={metadata.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-neutral-600">
                      <Youtube className="w-8 h-8" />
                    </div>
                  )}
                  {metadata.duration_formatted && (
                    <span className="absolute bottom-1 right-1 text-[9px] font-mono text-neutral-200 px-1 rounded bg-black/70">
                      {metadata.duration_formatted}
                    </span>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    <span className="text-[11px] font-semibold text-emerald-400">
                      Link verified — ready to grab
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-white line-clamp-2 leading-snug">
                    {metadata.title}
                  </h4>
                  {metadata.channel_title && (
                    <p className="text-[11px] text-amber-300 font-medium mt-0.5 line-clamp-1">
                      {metadata.channel_title}
                    </p>
                  )}
                  <a
                    href={metadata.original_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 flex items-center gap-1 text-[11px] text-neutral-500 hover:text-amber-400 transition-colors break-all"
                  >
                    <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                    <span className="line-clamp-1">{metadata.original_url}</span>
                  </a>
                </div>
              </div>

              {/* Quality Selection */}
              <div className="px-3 py-2.5 border-t border-neutral-800 bg-neutral-900/40">
                <div className="flex items-center gap-2 text-xs">
                  <Tv className="w-3.5 h-3.5 text-neutral-400" />
                  <span className="text-neutral-400 font-medium">Quality:</span>
                  {formatsLoading ? (
                    <span className="text-neutral-500">Loading formats...</span>
                  ) : !formats ? (
                    <button
                      onClick={fetchFormats}
                      className="text-amber-400 hover:text-amber-300 font-semibold underline"
                    >
                      Load available formats
                    </button>
                  ) : (
                    <select
                      value={selectedFormatId || ''}
                      onChange={(e) => setSelectedFormatId(e.target.value)}
                      className="flex-1 px-2 py-1 rounded-lg bg-neutral-800 border border-neutral-700 text-xs text-neutral-200 focus:outline-none focus:border-amber-400"
                    >
                      {getQualityOptions().map((f) => (
                        <option key={f.format_id} value={f.format_id}>
                          {getFormatLabel(f)} — {formatFileSize(f.filesize)}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Download Progress */}
          {projectId && (progress.status === 'downloading' || progress.status === 'uploading' || progress.status === 'done' || progress.status === 'error') && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-950/80 p-4 space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-neutral-300">
                  <div className="relative w-4 h-4 flex items-center justify-center flex-shrink-0">
                    {progress.status === 'downloading' && (
                      <div className="absolute inset-0 rounded-full border-2 border-amber-400/20 border-t-amber-400 animate-spin" />
                    )}
                    {progress.status === 'uploading' && (
                      <HardDrive className="w-3.5 h-3.5 text-rose-400 animate-bounce" />
                    )}
                    {progress.status === 'done' && (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    {progress.status === 'error' && (
                      <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
                    )}
                  </div>
                  <span className="font-semibold">
                    {progress.status === 'downloading' && 'Downloading video...'}
                    {progress.status === 'uploading' && 'Uploading to cloud...'}
                    {progress.status === 'done' && 'Download complete!'}
                    {progress.status === 'error' && 'Download failed'}
                  </span>
                </span>
                <span className="font-mono font-bold text-amber-400">
                  {progress.percent.toFixed(0)}%
                </span>
              </div>

              <div className="h-2 w-full bg-neutral-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 to-rose-500 transition-all duration-300 ease-out"
                  style={{ width: `${Math.min(progress.percent, 100)}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-[10px] text-neutral-500 font-mono">
                <span>{progress.total ? `Size: ${progress.total}` : 'Fetching...'}</span>
                <span>{progress.speed || ''}</span>
                <span>{progress.eta || ''}</span>
              </div>

              {progress.status === 'error' && progress.message && (
                <p className="text-[11px] text-rose-300">{progress.message}</p>
              )}
            </div>
          )}
        </div>

        {/* Footer / Actions */}
        {!isDownloading && (
          <div className="px-5 py-3 border-t border-neutral-800 bg-neutral-950/80 flex items-center justify-between">
            <div className="text-[11px] text-neutral-400 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              <span>Estimated grab time: ~2 min</span>
            </div>
            <button
              id="btn-react-grab"
              onClick={handleGrab}
              disabled={!url.trim() || !!metaLoading || !!formatsLoading || isDownloading}
              className="px-4.5 py-2 rounded-xl bg-gradient-to-r from-amber-500 via-rose-500 to-violet-600 hover:from-amber-400 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-bold shadow-lg shadow-rose-500/15 active:scale-95 transition-all flex items-center gap-1.5"
            >
              <Download className="w-4 h-4 stroke-[2.5]" />
              <span>Grab Video</span>
            </button>
          </div>
        )}

        {isDownloading && (
          <div className="px-5 py-3 border-t border-neutral-800 bg-neutral-950/80">
            <button
              onClick={stopProgress}
              className="w-full py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-300 hover:text-white text-xs font-semibold border border-neutral-700 transition-colors flex items-center justify-center gap-1.5"
            >
              <Pause className="w-3.5 h-3.5" />
              <span>Stop Grab</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
