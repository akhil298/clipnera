"use client";
import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Play,
  Pause,
  Scissors,
  Calendar,
  Download,
  Share2,
  Check,
  TrendingUp,
  Eye,
  Zap,
  Flame,
  Clock,
  Layers,
  ArrowRight,
  Filter,
  Copy,
  ExternalLink,
  Smartphone,
  ChevronRight,
  Folder,
  FolderOpen,
  Edit2,
  Youtube,
  ArrowLeft,
  Headphones,
  AlertCircle,
  ArrowDownWideNarrow,
  RotateCcw
} from 'lucide-react';
import { VideoProject, ViralClip, TabType, PipelineStep } from '@/lib/types';
import { clipApi } from '@/lib/api';
import { ClipCard } from './ClipCard';
import { PipelineStepIndicator } from './PipelineStepIndicator';
import { AudioBeforeAfter } from './AudioBeforeAfter';
import confetti from 'canvas-confetti';

type SortMode = 'score' | 'timeline' | 'duration';

interface ClipGeneratorViewProps {
  project: VideoProject;
  onSelectClipForEdit: (clip: ViralClip) => void;
  onScheduleClip: (clip: ViralClip) => void;
  onOpenUpload: () => void;
  onRenameFolder?: (projectId: string, newName: string) => void;
  onNavigateTab?: (tab: TabType) => void;
  pipelineSteps?: PipelineStep[];
  onRevertPipelineStep?: (step: string) => void;
  audioBeforeUrl?: string;
  audioAfterUrl?: string;
  isAudioReverted?: boolean;
  onRevertAudio?: () => void;
  onApplyAudio?: () => void;
}

export const ClipGeneratorView: React.FC<ClipGeneratorViewProps> = ({
  project,
  onSelectClipForEdit,
  onScheduleClip,
  onOpenUpload,
  onRenameFolder,
  onNavigateTab,
  pipelineSteps,
  onRevertPipelineStep,
  audioBeforeUrl,
  audioAfterUrl,
  isAudioReverted,
  onRevertAudio,
  onApplyAudio,
}) => {
  const safeProject = project || { clips: [] as ViralClip[], title: '', folderName: '' };
  const [selectedClip, setSelectedClip] = useState<ViralClip | null>(safeProject.clips[0] || null);

  const [filterScore, setFilterScore] = useState<number>(0);
  const [sortMode, setSortMode] = useState<SortMode>('score');
  const [quickExportingId, setQuickExportingId] = useState<string | null>(null);
  const [isBatchExporting, setIsBatchExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newFolderName, setNewFolderName] = useState(safeProject.folderName || safeProject.title || '');

  const downloadExport = (url: string, filename: string) => {
    const link = document.createElement('a');
    link.href = url;
    // Export URLs are signed to download as attachments; a same-tab click saves
    // the file. `target="_blank"` only opened a tab showing the video.
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  // Renders the clip with its own caption style, size and hook transition, then
  // downloads that. It used to download `presignedUrl`, the raw cut, which has
  // no title, captions, hook bridge or watermark.
  const handleQuickExport = async (clip: ViralClip) => {
    if (!safeProject.id || !clip.presignedUrl) {
      setExportError('This clip is not ready for download yet.');
      return;
    }

    setExportError(null);
    setQuickExportingId(clip.id);
    try {
      const result = await clipApi.exportProject(safeProject.id, {
        clipIds: [clip.id],
        aspectRatio: clip.aspectRatio,
        captionConfig: clip.captionConfig,
        hookTransition: clip.hookTransition,
      });
      const url = result.exported_clips.find((item) => item.clip_id === clip.id)?.burned_presigned_url;
      if (!url) {
        throw new Error('The export completed without producing a downloadable file.');
      }
      downloadExport(url, `${safeProject.title || 'clip'}-${clip.id}.mp4`);
      confetti({ particleCount: 75, spread: 60, origin: { y: 0.7 } });
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Export failed. Please try again.');
    } finally {
      setQuickExportingId(null);
    }
  };

  const handleBatchExport = async () => {
    if (!safeProject.id || safeProject.clips.length === 0) {
      setExportError('There are no clips available to export.');
      return;
    }

    setExportError(null);
    setIsBatchExporting(true);
    try {
      // Batch export uses the first clip's caption style, size and hook
      // transition for every clip (Auto still picks per clip).
      const firstClip = safeProject.clips[0];
      const result = await clipApi.exportProject(safeProject.id, {
        clipIds: safeProject.clips.map((clip) => clip.id),
        aspectRatio: firstClip?.aspectRatio,
        captionConfig: firstClip?.captionConfig,
        hookTransition: firstClip?.hookTransition,
      });
      const downloadableClips = result.exported_clips.filter((clip) => clip.burned_presigned_url);

      downloadableClips.forEach((clip, index) => {
        downloadExport(
          clip.burned_presigned_url as string,
          `${safeProject.title || 'clip'}-${clip.clip_id}-${clip.platform}-${index + 1}.mp4`,
        );
      });

      if (downloadableClips.length === 0) {
        throw new Error('The export completed without producing downloadable files.');
      }
      confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Export failed. Please try again.');
    } finally {
      setIsBatchExporting(false);
    }
  };

  const handleSaveRename = () => {
    if (newFolderName.trim() && onRenameFolder) {
      onRenameFolder(safeProject.id, newFolderName.trim());
    }
    setIsRenaming(false);
  };

  // Memoised so the identity is stable: the selection effect below depends on
  // it, and a fresh array every render would re-run that effect forever.
  const visibleClips = React.useMemo(() => {
    const kept = safeProject.clips.filter((c) => c.viralityScore >= filterScore);
    const bySort: Record<SortMode, (a: ViralClip, b: ViralClip) => number> = {
      score: (a, b) => b.viralityScore - a.viralityScore,
      timeline: (a, b) => a.startTime - b.startTime,
      duration: (a, b) => b.duration - a.duration,
    };
    return [...kept].sort(bySort[sortMode]);
  }, [safeProject.clips, filterScore, sortMode]);

  useEffect(() => {
    if (!visibleClips.length) {
      setSelectedClip(null);
      return;
    }
    setSelectedClip((current) =>
      current && visibleClips.some((c) => c.id === current.id) ? current : visibleClips[0],
    );
  }, [visibleClips]);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Breadcrumb & Quick Back to Folders Hub */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => onNavigateTab && onNavigateTab('folders')}
          className="flex items-center gap-2 text-xs font-semibold text-neutral-400 hover:text-amber-300 transition-colors group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          <span> Back to All Project Folders</span>
        </button>

        <div className="flex items-center gap-2 text-xs text-neutral-400">
          <span className="text-neutral-500 font-mono">Folder ID: {safeProject.id}</span>
        </div>
      </div>

      {/* Processing Overlay */}
      {safeProject.processingStatus === 'processing' && (
        <div className="rounded-2xl bg-neutral-900/90 border border-amber-500/30 p-6 flex items-center justify-center gap-4">
          <div className="relative w-12 h-12 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border-4 border-amber-400/20 border-t-amber-400 animate-spin" />
            <Sparkles className="w-5 h-5 text-amber-400 animate-pulse" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white">Processing Video...</h2>
            <p className="text-xs text-neutral-400">
              Downloading and preparing your project folder. Please wait {safeProject.processingProgress ?? 0}%
            </p>
          </div>
        </div>
      )}

      {safeProject.processingStatus === 'failed' && (
        <div className="rounded-2xl bg-neutral-900/90 border border-rose-500/30 p-6 flex items-center justify-center gap-4">
          <AlertCircle className="w-6 h-6 text-rose-400" />
          <div>
            <h2 className="text-sm font-bold text-white">Processing Failed</h2>
            <p className="text-xs text-neutral-400">There was an error processing this video. Please try again.</p>
          </div>
        </div>
      )}

      {pipelineSteps && pipelineSteps.length > 0 && (
        <PipelineStepIndicator steps={pipelineSteps} onRevert={onRevertPipelineStep} />
      )}

      {(audioBeforeUrl || audioAfterUrl) && (
        <AudioBeforeAfter
          beforeUrl={audioBeforeUrl}
          afterUrl={audioAfterUrl}
          isReverted={isAudioReverted}
          onRevert={onRevertAudio}
          onApply={onApplyAudio}
        />
      )}

      {/* Project Folder Banner & Virality Spikes Timeline */}
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 p-5 lg:p-6 relative overflow-hidden shadow-xl">
        {/* Loading overlay: dark gradient sweep from left to right as processing progresses */}
        {safeProject.processingStatus === 'processing' && (
          <>
            <div
              className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/40 to-black/10 pointer-events-none transition-all duration-500 ease-out"
              style={{ width: `${safeProject.processingProgress ?? 0}%`, left: 0 }}
            />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-amber-400 shadow-lg animate-pulse"
              style={{ left: `calc(${safeProject.processingProgress ?? 0}% - 10px)` }}
            />
          </>
        )}

        {/* Credits Charged Badge */}
        {safeProject.creditsDeducted && safeProject.creditsDeducted > 0 && (
          <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/20">
            <Zap className="w-3 h-3 text-amber-400" />
            <span className="text-[10px] font-mono font-semibold text-amber-300">
              {safeProject.creditsDeducted} credit{safeProject.creditsDeducted !== 1 ? 's' : ''} deducted
            </span>
          </div>
        )}

        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
          <div className="space-y-2 flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-md text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1.5">
                <Folder className="w-3.5 h-3.5" />
                <span>{safeProject.folderCategory || 'Project Folder'}</span>
              </span>
              <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-400">
                {safeProject.clips.length} Respected Videos Ready
              </span>
              {safeProject.sourceUrl && (
                <a
                  href={safeProject.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="px-2.5 py-0.5 rounded-md text-[11px] font-medium bg-neutral-950 text-neutral-400 hover:text-amber-300 border border-neutral-800 flex items-center gap-1 transition-colors"
                >
                  <Youtube className="w-3.5 h-3.5 text-red-400" />
                  <span>Original Link</span>
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              )}
            </div>

            {/* Folder Title + Rename Action */}
            {isRenaming ? (
              <div className="flex items-center gap-2 pt-1 max-w-lg">
                <input
                  type="text"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-neutral-950 border border-amber-400 text-sm font-bold text-white focus:outline-none"
                  autoFocus
                />
                <button
                  onClick={handleSaveRename}
                  className="px-3 py-1.5 rounded-lg bg-amber-500 text-neutral-950 font-bold text-xs hover:bg-amber-400"
                >
                  Save
                </button>
                <button
                  onClick={() => setIsRenaming(false)}
                  className="px-3 py-1.5 rounded-lg bg-neutral-800 text-neutral-400 text-xs hover:bg-neutral-700"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 group/name">
                <h1 className="text-xl lg:text-2xl font-extrabold text-white tracking-tight">
                  {safeProject.folderName || safeProject.title}
                </h1>
                <button
                  onClick={() => {
                    setNewFolderName(safeProject.folderName || safeProject.title);
                    setIsRenaming(true);
                  }}
                  className="opacity-60 hover:opacity-100 p-1.5 rounded-lg hover:bg-neutral-800 text-neutral-400 hover:text-amber-400 transition-all"
                  title="Rename Folder"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            <p className="text-xs text-neutral-400 flex flex-wrap items-center gap-2">
              <span>Channel: <strong className="text-neutral-200">{safeProject.sourceChannel || 'Original Source'}</strong></span>
              <span>•</span>
              <Clock className="w-3.5 h-3.5 text-neutral-500 inline" />
              <span>Duration: {Math.floor(safeProject.duration / 60)}m {safeProject.duration % 60}s</span>
              <span>•</span>
              <span className="text-amber-400 font-semibold">
                Average Virality: {Math.round(safeProject.clips.reduce((acc, c) => acc + c.viralityScore, 0) / (safeProject.clips.length || 1))}/100
              </span>
            </p>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap shrink-0">
            <button
              id="btn-process-another-video"
              onClick={onOpenUpload}
              className="px-3.5 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-200 border border-neutral-700 transition-colors flex items-center gap-2"
            >
              <Layers className="w-3.5 h-3.5 text-amber-400" />
              <span>Add / Ingest More</span>
            </button>

            <button
              onClick={handleBatchExport}
              disabled={isBatchExporting}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              <span>{isBatchExporting ? 'Exporting...' : `Batch Export All (${safeProject.clips.length})`}</span>
            </button>
          </div>
        </div>

        {exportError && (
          <div className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
            {exportError}
          </div>
        )}

        {/* Interactive Virality Spikes Visualizer across Raw Video Duration */}
        <div className="mt-6 pt-5 border-t border-neutral-800/80">
          <div className="flex items-center justify-between text-xs mb-2">
            <div className="flex items-center gap-2 text-neutral-300 font-medium">
              <Flame className="w-4 h-4 text-amber-400" />
              <span>AI Virality Spikes Across Timeline:</span>
            </div>
            <span className="text-[11px] text-neutral-400 font-mono">
              00:00 - {Math.floor(safeProject.duration / 60)}:{String(safeProject.duration % 60).padStart(2, '0')}
            </span>
          </div>

          <div className="relative h-10 w-full bg-neutral-950 rounded-xl border border-neutral-800/80 overflow-hidden flex items-center px-2">
            {/* Background waveform simulation */}
            <div className="absolute inset-0 flex items-center justify-between px-3 opacity-20 pointer-events-none">
              {Array.from({ length: 48 }).map((_, i) => (
                <div
                  key={i}
                  className="w-1 bg-neutral-400 rounded-full"
                  style={{
                    height: `${20 + Math.sin(i * 0.4) * 15 + (i % 3) * 10}%`,
                  }}
                />
              ))}
            </div>

            {/* Render Highlighted Clip Spans */}
            {safeProject.clips.map((clip) => {
              const leftPercent = (clip.startTime / safeProject.duration) * 100;
              const widthPercent = Math.max(3, (clip.duration / safeProject.duration) * 100);
              const isSelected = selectedClip?.id === clip.id;

              return (
                <div
                  key={clip.id}
                  onClick={() => setSelectedClip(clip)}
                  title={`${clip.title} (${clip.viralityScore}/100)`}
                  style={{
                    left: `${leftPercent}%`,
                    width: `${widthPercent}%`,
                  }}
                  className={`absolute h-7 rounded-lg cursor-pointer flex items-center justify-center transition-all ${
                    isSelected
                      ? 'bg-amber-400 text-neutral-950 ring-2 ring-white shadow-md z-10 font-bold'
                      : clip.viralityScore >= 95
                      ? 'bg-amber-500/80 text-neutral-950 hover:bg-amber-400'
                      : 'bg-neutral-700 text-neutral-200 hover:bg-neutral-600'
                  }`}
                >
                  <span className="text-[10px] font-bold font-mono">
                    {clip.viralityScore}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Clip Grid */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-white">Extracted Viral Clips</h2>
            <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-xs font-semibold text-neutral-300">
              {visibleClips.length}
              {visibleClips.length !== safeProject.clips.length && ` of ${safeProject.clips.length}`}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5">
              <ArrowDownWideNarrow className="h-3.5 w-3.5 text-neutral-400" />
              <select
                value={sortMode}
                onChange={(e) => setSortMode(e.target.value as SortMode)}
                className="rounded-lg border border-neutral-800 bg-neutral-900 px-2.5 py-1 text-xs text-white focus:border-amber-400 focus:outline-none"
                aria-label="Sort clips"
              >
                <option value="score">Highest score</option>
                <option value="timeline">Video order</option>
                <option value="duration">Longest first</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <Filter className="h-3.5 w-3.5 text-neutral-400" />
              <select
                value={filterScore}
                onChange={(e) => setFilterScore(Number(e.target.value))}
                className="rounded-lg border border-neutral-800 bg-neutral-900 px-2.5 py-1 text-xs text-white focus:border-amber-400 focus:outline-none"
                aria-label="Filter clips by score"
              >
                <option value={0}>All scores</option>
                <option value={70}>Standard (70+)</option>
                <option value={85}>High (85+)</option>
                <option value={90}>Ultra viral (90+)</option>
              </select>
            </div>
          </div>
        </div>

        {visibleClips.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {visibleClips.map((clip, index) => (
              <ClipCard
                key={clip.id}
                clip={clip}
                index={index}
                isSelected={selectedClip?.id === clip.id}
                isExporting={quickExportingId === clip.id}
                onSelect={setSelectedClip}
                onEdit={onSelectClipForEdit}
                onSchedule={onScheduleClip}
                onExport={handleQuickExport}
              />
            ))}
          </div>
        )}

        {safeProject.clips.length > 0 && visibleClips.length === 0 && (
          <div className="rounded-xl border border-dashed border-neutral-800 bg-neutral-900/60 p-8 text-center">
            <p className="text-xs text-neutral-400">No clips match the current filter.</p>
            <button
              onClick={() => setFilterScore(0)}
              className="mt-2 text-[11px] font-semibold text-amber-300 hover:text-amber-200"
            >
              Reset filter
            </button>
          </div>
        )}

        {safeProject.clips.length === 0 && (
          <div className="rounded-xl border border-dashed border-neutral-800 bg-neutral-900/60 p-10 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-neutral-800/70">
              <Sparkles className="h-5 w-5 text-neutral-500" />
            </div>
            <p className="text-sm font-semibold text-white">
              {safeProject.processingStatus === 'processing' ? 'Finding your best moments' : 'No clips yet'}
            </p>
            <p className="mt-1 text-xs text-neutral-400">
              {safeProject.processingStatus === 'processing'
                ? 'Clips appear here as soon as the pipeline finishes rendering them.'
                : 'Run the pipeline on this project to generate clips.'}
            </p>
          </div>
        )}
      </div>

    </div>
  );
};
