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
  RotateCcw
} from 'lucide-react';
import { VideoProject, ViralClip, TabType, PipelineStep } from '@/lib/types';
import { clipApi } from '@/lib/api';
import { PipelineStepIndicator } from './PipelineStepIndicator';
import { AudioBeforeAfter } from './AudioBeforeAfter';
import confetti from 'canvas-confetti';

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
  const [isPlayingClip, setIsPlayingClip] = useState(false);

  useEffect(() => {
    if (safeProject.clips.length > 0 && !selectedClip) {
      setSelectedClip(safeProject.clips[0]);
    } else if (safeProject.clips.length > 0 && selectedClip && !safeProject.clips.find((c) => c.id === selectedClip.id)) {
      setSelectedClip(safeProject.clips[0]);
    }
  }, [safeProject.clips, selectedClip]);
  const [isPlayingRaw, setIsPlayingRaw] = useState(false);
  const [copiedHookId, setCopiedHookId] = useState<string | null>(null);
  const [filterScore, setFilterScore] = useState<number>(0);
  const [quickExportingId, setQuickExportingId] = useState<string | null>(null);
  const [isBatchExporting, setIsBatchExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newFolderName, setNewFolderName] = useState(safeProject.folderName || safeProject.title || '');

  const handleCopyHook = (clipId: string, hookText: string) => {
    navigator.clipboard.writeText(hookText);
    setCopiedHookId(clipId);
    setTimeout(() => setCopiedHookId(null), 2000);
  };

  const downloadExport = (url: string, filename: string) => {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const handleQuickExport = (clip: ViralClip) => {
    if (!clip.presignedUrl) {
      setExportError('This clip is not ready for download yet.');
      return;
    }

    setExportError(null);
    setQuickExportingId(clip.id);
    try {
      downloadExport(clip.presignedUrl, `${safeProject.title || 'clip'}-${clip.id}.mp4`);
      confetti({ particleCount: 75, spread: 60, origin: { y: 0.7 } });
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
      // Use the first clip's caption config for batch export, or default
      const firstClipCaptionConfig = safeProject.clips[0]?.captionConfig;
      const result = await clipApi.exportProject(safeProject.id, safeProject.clips.length, firstClipCaptionConfig);
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

  const filteredClips = safeProject.clips.filter((c) => c.viralityScore >= filterScore);

  useEffect(() => {
    if (!safeProject.clips.length) {
      setSelectedClip(null);
      return;
    }
    if (!filteredClips.length) {
      setSelectedClip(null);
      return;
    }
    if (!selectedClip || !filteredClips.find((c) => c.id === selectedClip.id)) {
      setSelectedClip(filteredClips[0]);
    }
  }, [safeProject.clips, filteredClips, selectedClip]);

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

      {/* Main Grid: Viral Clips List & Side Preview Card */}
      <div className="grid lg:grid-cols-12 gap-6">
        {/* Left Column: Clips Leaderboard */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">
                Extracted Viral Clips
              </h2>
              <span className="px-2 py-0.5 rounded-full bg-neutral-800 text-neutral-300 text-xs font-semibold">
                {filteredClips.length} clips
              </span>
            </div>

            {/* Filter Bar */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-neutral-400 flex items-center gap-1">
                <Filter className="w-3.5 h-3.5 text-neutral-400" />
                Score &ge;
              </span>
              <select
                value={filterScore}
                onChange={(e) => setFilterScore(Number(e.target.value))}
                className="px-2.5 py-1 rounded-lg bg-neutral-900 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400"
              >
                <option value={0}>All (0+)</option>
                <option value={70}>Standard (70+)</option>
                <option value={85}>High (85+)</option>
                <option value={90}>Ultra Viral (90+)</option>
                <option value={95}>Superstar (95+)</option>
              </select>
            </div>
          </div>

          {/* List of Clips */}
          <div className="space-y-3.5">
            {filteredClips.map((clip, index) => {
              const isSelected = selectedClip?.id === clip.id;
              const isSuperViral = clip.viralityScore >= 95;

              return (
                <div
                  key={clip.id}
                  onClick={() => setSelectedClip(clip)}
                  className={`rounded-xl p-4 lg:p-5 border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-neutral-900 border-amber-500/60 ring-1 ring-amber-500/30 shadow-lg'
                      : 'bg-neutral-900/60 border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900/80'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: Score Badge & Index */}
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex flex-col items-center justify-center w-13 h-13 rounded-xl border flex-shrink-0 font-mono shadow-sm ${
                          isSuperViral
                            ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
                            : 'bg-neutral-800 border-neutral-700 text-white'
                        }`}
                      >
                        <span className="text-base font-black leading-none">
                          {clip.viralityScore}
                        </span>
                        <span className="text-[8px] font-bold uppercase tracking-wider text-neutral-400 mt-0.5">
                          Score
                        </span>
                      </div>

                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-semibold text-neutral-400">
                            Clip #{index + 1}
                          </span>
                          <span className="text-[11px] px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-300 font-mono">
                            {clip.duration}s
                          </span>
                          <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 font-medium">
                            {clip.suggestedAspectRatio} Vertical
                          </span>
                        </div>
                        <h3 className="text-sm font-bold text-white mt-1 group-hover:text-amber-300 transition-colors">
                          {clip.title}
                        </h3>
                      </div>
                    </div>

                    {/* Right: Quick Action Buttons */}
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectClipForEdit(clip);
                        }}
                        className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-white text-xs font-semibold border border-neutral-700 transition-all flex items-center gap-1.5 shadow-sm"
                      >
                        <Scissors className="w-3.5 h-3.5 text-neutral-300" />
                        <span>Edit Studio</span>
                      </button>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onScheduleClip(clip);
                        }}
                        className="p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-amber-400 border border-neutral-700 transition-colors"
                        title="Schedule Post"
                      >
                        <Calendar className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Hook Box */}
                  <div className="mt-3.5 p-2.5 rounded-lg bg-neutral-950 border border-neutral-800/80 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-xs">
                      <Zap className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                      <span className="text-neutral-400 font-medium">Hook:</span>
                      <span className="text-neutral-200 italic font-medium truncate">
                        "{clip.hook}"
                      </span>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopyHook(clip.id, clip.hook);
                      }}
                      className="p-1 text-neutral-400 hover:text-white rounded transition-colors flex-shrink-0"
                      title="Copy Hook Text"
                    >
                      {copiedHookId === clip.id ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>

                  {/* Metrics Bar & AI Rationale */}
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs pt-2 border-t border-neutral-800/60">
                    <p className="text-[11px] text-neutral-400 max-w-xl truncate">
                      <span className="text-amber-400 font-semibold">AI Rationale: </span>
                      {clip.rationale}
                    </p>

                    <div className="flex items-center gap-3 text-[11px] font-mono">
                      <span className="text-emerald-400">Hook: {clip.hookScore}%</span>
                      <span className="text-amber-400">Engage: {clip.engagementScore}%</span>
                    </div>
                  </div>
                </div>
              );
            })}
            {safeProject.clips.length > 0 && filteredClips.length === 0 && (
              <div className="rounded-xl border border-dashed border-neutral-800 bg-neutral-900/60 p-4 text-center">
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
              <div className="rounded-xl border border-dashed border-neutral-800 bg-neutral-900/60 p-4 text-center">
                <p className="text-xs text-neutral-400">No clips generated yet. Please wait for the pipeline to complete.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Active Clip Preview & Quick Actions */}
        <div className="lg:col-span-5 xl:col-span-4">
          <div className="sticky top-20 rounded-xl bg-neutral-900 border border-neutral-800 p-5 space-y-4 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
                  9:16 Vertical Preview
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-400/10 text-amber-300">
                {selectedClip ? `${selectedClip.duration}s • Score ${selectedClip.viralityScore}` : 'Select a clip'}
              </span>
            </div>

            {/* Vertical Video Phone Frame Mockup */}
            {selectedClip && (
              <div className="relative mx-auto w-56 aspect-[9/16] rounded-2xl bg-black border-2 border-neutral-800 shadow-xl overflow-hidden flex flex-col justify-between p-3">
                {/* Video Preview with Play Overlay */}
                 <div className="absolute inset-0">
                   {selectedClip.presignedUrl ? (
                      <>
                        <video
                          src={selectedClip.presignedUrl}
                          autoPlay={isPlayingClip}
                          muted
                          loop
                          playsInline
                          poster={selectedClip.posterUrl || ''}
                          className="w-full h-full object-cover"
                          onPlay={() => setIsPlayingClip(true)}
                          onPause={() => setIsPlayingClip(false)}
                          onError={() => {
                            console.error('Clip preview failed to load:', selectedClip.presignedUrl);
                            setIsPlayingClip(false);
                          }}
                        />
                        {!isPlayingClip && selectedClip.posterUrl && (
                          <img
                            src={selectedClip.posterUrl}
                            alt={selectedClip.title}
                            className="absolute inset-0 w-full h-full object-cover opacity-40"
                          />
                        )}
                       {!isPlayingClip && (
                         <div className="absolute inset-0 flex items-center justify-center">
                           <button
                             onClick={() => setIsPlayingClip(true)}
                             className="w-14 h-14 rounded-full bg-amber-500/90 hover:bg-amber-400 text-neutral-950 flex items-center justify-center shadow-xl transition-all active:scale-90"
                           >
                             <Play className="w-6 h-6 fill-current" />
                           </button>
                         </div>
                       )}
                     </>
                   ) : (
                     <div className="absolute inset-0 flex items-center justify-center">
                       <div className="text-center space-y-2">
                         <div className="w-14 h-14 rounded-full bg-neutral-800/60 flex items-center justify-center mx-auto">
                           <Play className="w-6 h-6 text-neutral-400" />
                         </div>
                         <p className="text-[10px] text-neutral-400">Video not available</p>
                       </div>
                     </div>
                   )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-transparent to-black/60" />
                </div>

                {/* Top UI: Virality & Duration */}
                <div className="relative z-10 flex items-center justify-between text-[10px]">
                  <span className="px-2 py-0.5 rounded-full bg-black/70 backdrop-blur-md text-amber-300 font-bold border border-white/10">
                    ⚡ {selectedClip.viralityScore} Virality
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-black/70 text-white font-mono">
                    00:{selectedClip.duration}
                  </span>
                </div>

                {/* Middle: Kinetic Animated Caption Mockup */}
                <div className="relative z-10 text-center my-auto px-2">
                  <div className="inline-block p-1.5 rounded-lg bg-black/80 backdrop-blur-sm border border-neutral-700 shadow-lg">
                    <p
                      className="font-extrabold text-xs tracking-tight uppercase"
                      style={{
                        fontFamily: selectedClip.captionConfig.fontFamily,
                        color: selectedClip.captionConfig.textColor,
                      }}
                    >
                      {selectedClip.hook || selectedClip.title || 'Your caption'}
                    </p>
                  </div>
                </div>

                {/* Bottom UI: Title */}
                <div className="relative z-10 space-y-1">
                  <p className="text-[11px] font-bold text-white line-clamp-1">
                    {selectedClip.title}
                  </p>
                  <p className="text-[9px] text-neutral-300 line-clamp-1">
                    {selectedClip.socialOptimization.hashtags.slice(0, 3).join(' ')}
                  </p>
                </div>
              </div>
            )}

            {/* Quick Action Trigger to open Studio */}
            {selectedClip && (
              <div className="space-y-2 pt-2">
                <button
                  id="btn-open-full-editor"
                  onClick={() => onSelectClipForEdit(selectedClip)}
                  className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center justify-center gap-2"
                >
                  <Scissors className="w-4 h-4 stroke-[2.5]" />
                  <span>Open in Studio Editor</span>
                  <ChevronRight className="w-4 h-4" />
                </button>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => onScheduleClip(selectedClip)}
                    className="py-2 px-3 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-200 border border-neutral-700 transition-colors flex items-center justify-center gap-1.5"
                  >
                    <Calendar className="w-3.5 h-3.5 text-neutral-400" />
                    <span>Schedule</span>
                  </button>

                  <button
                    onClick={() => handleQuickExport(selectedClip)}
                    disabled={quickExportingId === selectedClip.id}
                    className="py-2 px-3 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-200 border border-neutral-700 transition-colors flex items-center justify-center gap-1.5"
                  >
                    {quickExportingId === selectedClip.id ? (
                      <span className="text-amber-400 animate-pulse">Exporting...</span>
                    ) : (
                      <>
                        <Download className="w-3.5 h-3.5 text-neutral-400" />
                        <span>Quick Export</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
