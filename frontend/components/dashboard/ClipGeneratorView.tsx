"use client";
import React, { useState, useEffect } from 'react';
import {
  AlertCircle,
  ArrowDownWideNarrow,
  CheckSquare,
  Copy,
  Download,
  Edit2,
  ExternalLink,
  Film,
  Filter,
  Layers,
  Loader2,
  Sparkles,
  X,
  Zap,
} from 'lucide-react';
import { VideoProject, ViralClip, TabType, PipelineStep } from '@/lib/types';
import { clipApi } from '@/lib/api';
import { downloadFile, exportAllProjectClips } from '@/lib/utils/clipExport';
import { ClipCard } from './ClipCard';
import { PipelineStepIndicator } from './PipelineStepIndicator';
import { AudioBeforeAfter } from './AudioBeforeAfter';
import confetti from 'canvas-confetti';
import { Select, SelectOption } from '@/components/ui/Select';
import { PageHeader } from '@/components/ui/PageHeader';
import { StatusPill } from '@/components/ui/StatusPill';
import { scoreTone } from '@/components/ui/ScoreRing';

type SortMode = 'score' | 'timeline' | 'duration';

const SORT_OPTIONS: SelectOption<SortMode>[] = [
  { value: 'score', label: 'Highest score' },
  { value: 'timeline', label: 'Video order' },
  { value: 'duration', label: 'Longest first' },
];

const SCORE_FILTER_OPTIONS: SelectOption<number>[] = [
  { value: 0, label: 'All scores' },
  { value: 70, label: 'Standard (70+)' },
  { value: 85, label: 'High (85+)' },
  { value: 90, label: 'Ultra viral (90+)' },
];

const formatClock = (seconds: number) => {
  const safe = Math.max(0, Math.round(seconds || 0));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = safe % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
};

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
  const safeProject = project || ({ clips: [] as ViralClip[], title: '', folderName: '', duration: 0 } as unknown as VideoProject);
  const [selectedClip, setSelectedClip] = useState<ViralClip | null>(safeProject.clips[0] || null);

  const [filterScore, setFilterScore] = useState<number>(0);
  const [sortMode, setSortMode] = useState<SortMode>('score');
  const [quickExportingId, setQuickExportingId] = useState<string | null>(null);
  const [isBatchExporting, setIsBatchExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newFolderName, setNewFolderName] = useState(safeProject.folderName || safeProject.title || '');
  const [selectMode, setSelectMode] = useState(false);
  const [checkedIds, setCheckedIds] = useState<string[]>([]);
  const [idCopied, setIdCopied] = useState(false);

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
      downloadFile(url, `${safeProject.title || 'clip'}-${clip.id}.mp4`);
      confetti({ particleCount: 75, spread: 60, origin: { y: 0.7 } });
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Export failed. Please try again.');
    } finally {
      setQuickExportingId(null);
    }
  };

  /** Exports every clip, or only the checked ones in select mode. */
  const handleBatchExport = async (clips: ViralClip[] = safeProject.clips) => {
    setExportError(null);
    setIsBatchExporting(true);
    try {
      await exportAllProjectClips({ ...safeProject, clips });
      confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
      setSelectMode(false);
      setCheckedIds([]);
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

  const copyProjectId = () => {
    navigator.clipboard
      ?.writeText(safeProject.id)
      .then(() => {
        setIdCopied(true);
        setTimeout(() => setIdCopied(false), 1600);
      })
      .catch(() => undefined);
  };

  const toggleChecked = (clip: ViralClip) =>
    setCheckedIds((prev) => (prev.includes(clip.id) ? prev.filter((id) => id !== clip.id) : [...prev, clip.id]));

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

  const isProcessing = safeProject.processingStatus === 'processing';
  const isFailed = safeProject.processingStatus === 'failed';
  const averageScore = Math.round(
    safeProject.clips.reduce((acc, c) => acc + c.viralityScore, 0) / (safeProject.clips.length || 1),
  );
  const rankById = new Map(
    [...safeProject.clips].sort((a, b) => b.viralityScore - a.viralityScore).map((clip, i) => [clip.id, i + 1]),
  );
  const checkedClips = safeProject.clips.filter((c) => checkedIds.includes(c.id));
  const thumb = safeProject.posterUrl || safeProject.clips.find((c) => c.posterUrl)?.posterUrl || '';
  const displayName = safeProject.folderName || safeProject.title;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <PageHeader
        back={onNavigateTab ? { label: 'Projects', onClick: () => onNavigateTab('folders') } : undefined}
        title={
          isRenaming ? (
            <form
              className="flex items-center gap-2 max-w-xl"
              onSubmit={(e) => {
                e.preventDefault();
                handleSaveRename();
              }}
            >
              <label htmlFor="project-rename" className="sr-only">
                Project name
              </label>
              <input
                id="project-rename"
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onKeyDown={(e) => e.key === 'Escape' && setIsRenaming(false)}
                className="flex-1 min-w-0 h-10 px-3 rounded-xl bg-neutral-950 border border-amber-400 text-base font-bold text-white focus:outline-none"
                autoFocus
              />
              <button type="submit" className="h-10 px-3.5 rounded-xl bg-amber-500 text-neutral-950 font-bold text-xs hover:bg-amber-400">
                Save
              </button>
              <button
                type="button"
                onClick={() => setIsRenaming(false)}
                className="h-10 px-3.5 rounded-xl text-neutral-400 text-xs font-semibold hover:bg-neutral-800"
              >
                Cancel
              </button>
            </form>
          ) : (
            <span className="inline-flex items-center gap-2">
              {displayName}
              <button
                type="button"
                onClick={() => {
                  setNewFolderName(displayName);
                  setIsRenaming(true);
                }}
                className="p-1.5 rounded-lg text-neutral-500 hover:text-amber-400 hover:bg-neutral-800 transition-colors"
                title="Rename project"
                aria-label="Rename project"
              >
                <Edit2 className="w-4 h-4" />
              </button>
            </span>
          )
        }
        eyebrow={
          <>
            {isProcessing ? (
              <StatusPill tone="processing">Processing {Math.round(safeProject.processingProgress ?? 0)}%</StatusPill>
            ) : isFailed ? (
              <StatusPill tone="failed">Failed</StatusPill>
            ) : (
              <StatusPill tone={safeProject.clips.length ? 'ready' : 'neutral'}>
                {safeProject.clips.length} clip{safeProject.clips.length === 1 ? '' : 's'} ready
              </StatusPill>
            )}
            <StatusPill tone="neutral" dot={false}>
              {safeProject.folderCategory || 'Project'}
            </StatusPill>
            {(safeProject.creditsDeducted ?? 0) > 0 && (
              <StatusPill tone="neutral" dot={false}>
                <Zap className="w-3 h-3 text-amber-400" />
                {safeProject.creditsDeducted} credit{safeProject.creditsDeducted !== 1 ? 's' : ''} used
              </StatusPill>
            )}
          </>
        }
        description={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>{safeProject.sourceChannel || 'Original source'}</span>
            <span aria-hidden="true">·</span>
            <span className="tabular-nums">{formatClock(safeProject.duration)}</span>
            {safeProject.clips.length > 0 && (
              <>
                <span aria-hidden="true">·</span>
                <span>
                  average virality <span className="font-semibold text-amber-300 tabular-nums">{averageScore}</span>
                </span>
              </>
            )}
            {typeof safeProject.aiCostUsd === 'number' && safeProject.aiCostUsd > 0 && (
              <>
                <span aria-hidden="true">·</span>
                <span className="tabular-nums">AI cost ${safeProject.aiCostUsd.toFixed(2)}</span>
              </>
            )}
            {safeProject.sourceUrl && (
              <a
                href={safeProject.sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-neutral-300 hover:text-amber-300"
              >
                Original video <ExternalLink className="w-3 h-3" />
              </a>
            )}
            {safeProject.id && (
              <button
                type="button"
                onClick={copyProjectId}
                className="inline-flex items-center gap-1 text-neutral-500 hover:text-neutral-300"
                title={`Project ID ${safeProject.id}`}
              >
                <Copy className="w-3 h-3" /> {idCopied ? 'Copied' : 'Copy ID'}
              </button>
            )}
          </span>
        }
        actions={
          <>
            <button
              id="btn-process-another-video"
              type="button"
              onClick={onOpenUpload}
              className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 text-[13px] font-semibold text-white transition-colors"
            >
              <Layers className="w-4 h-4 text-amber-400" />
              Add more
            </button>
            <button
              type="button"
              onClick={() => handleBatchExport()}
              disabled={isBatchExporting || safeProject.clips.length === 0}
              className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-bold shadow-md shadow-amber-500/20 transition-colors disabled:opacity-50"
            >
              {isBatchExporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              {isBatchExporting ? 'Exporting…' : `Export all ${safeProject.clips.length}`}
            </button>
          </>
        }
      />

      {exportError && (
        <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-200">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="flex-1">{exportError}</span>
          <button type="button" onClick={() => setExportError(null)} aria-label="Dismiss" className="text-rose-300 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {isProcessing && (
        <div className="rounded-2xl bg-neutral-900/80 border border-amber-500/25 p-4 sm:p-5 space-y-3">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-amber-400 animate-spin shrink-0" />
            <div className="flex-1 min-w-0">
              <h2 className="text-sm font-semibold text-white">Finding the best moments</h2>
              <p className="text-xs text-neutral-400">Clips show up here as soon as they are rendered. You can leave this page.</p>
            </div>
            <span className="text-sm font-bold text-amber-300 tabular-nums">{Math.round(safeProject.processingProgress ?? 0)}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-neutral-800 overflow-hidden">
            <div className="h-full bg-amber-500 rounded-full transition-all duration-500" style={{ width: `${safeProject.processingProgress ?? 0}%` }} />
          </div>
        </div>
      )}

      {isFailed && (
        <div className="rounded-2xl bg-rose-500/5 border border-rose-500/25 p-4 sm:p-5 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <h2 className="text-sm font-semibold text-white">Processing stopped</h2>
            <p className="text-xs text-neutral-400">
              Something went wrong while processing this video. Add it again from New video to retry.
            </p>
          </div>
        </div>
      )}

      {pipelineSteps && pipelineSteps.length > 0 && <PipelineStepIndicator steps={pipelineSteps} onRevert={onRevertPipelineStep} />}

      {(audioBeforeUrl || audioAfterUrl) && (
        <AudioBeforeAfter
          beforeUrl={audioBeforeUrl}
          afterUrl={audioAfterUrl}
          isReverted={isAudioReverted}
          onRevert={onRevertAudio}
          onApply={onApplyAudio}
        />
      )}

      {/* Where each clip sits in the source */}
      {safeProject.clips.length > 0 && safeProject.duration > 0 && (
        <section className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-4 sm:p-5" aria-labelledby="clip-map-title">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-3">
            <h2 id="clip-map-title" className="text-sm font-semibold text-white flex items-center gap-2">
              {thumb && (
                <span className="hidden sm:block relative w-10 aspect-video rounded overflow-hidden bg-neutral-800">
                  <img src={thumb} alt="" className="absolute inset-0 w-full h-full object-cover" />
                </span>
              )}
              Where the clips come from
            </h2>
            <span className="text-xs text-neutral-500">each block is a clip, numbered by rank</span>
            <span className="ml-auto font-mono text-[11px] text-neutral-500">0:00 – {formatClock(safeProject.duration)}</span>
          </div>
          <div className="relative h-11 w-full rounded-xl bg-neutral-950 border border-neutral-800 overflow-hidden">
            {/* Quarter marks */}
            {[25, 50, 75].map((pct) => (
              <span key={pct} className="absolute inset-y-0 w-px bg-neutral-800" style={{ left: `${pct}%` }} aria-hidden="true" />
            ))}
            {safeProject.clips.map((clip) => {
              const leftPercent = Math.min(97, (clip.startTime / safeProject.duration) * 100);
              const widthPercent = Math.max(2.5, (clip.duration / safeProject.duration) * 100);
              const isSelected = selectedClip?.id === clip.id;
              const tone = scoreTone(clip.viralityScore);
              return (
                <button
                  key={clip.id}
                  type="button"
                  onClick={() => setSelectedClip(clip)}
                  title={`#${rankById.get(clip.id)} ${clip.title} · score ${clip.viralityScore} · ${formatClock(clip.startTime)}`}
                  aria-label={`Clip ${rankById.get(clip.id)}, ${clip.title}, score ${clip.viralityScore}`}
                  aria-pressed={isSelected}
                  style={{ left: `${leftPercent}%`, width: `${widthPercent}%` }}
                  className={`absolute top-1.5 bottom-1.5 rounded-md border flex items-center justify-center text-[10px] font-extrabold transition-all ${
                    isSelected
                      ? 'bg-amber-400 border-white text-neutral-950 z-10'
                      : `${tone.chip} hover:brightness-125`
                  }`}
                >
                  {rankById.get(clip.id)}
                </button>
              );
            })}
          </div>
          <div className="mt-1.5 flex justify-between font-mono text-[10px] text-neutral-600" aria-hidden="true">
            <span>0:00</span>
            <span>{formatClock(safeProject.duration / 4)}</span>
            <span>{formatClock(safeProject.duration / 2)}</span>
            <span>{formatClock((safeProject.duration * 3) / 4)}</span>
            <span>{formatClock(safeProject.duration)}</span>
          </div>
        </section>
      )}

      {/* Clips */}
      <section className="space-y-4" aria-labelledby="clips-title">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="clips-title" className="text-base font-bold text-white">
            Clips
          </h2>
          <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-xs font-semibold text-neutral-300 tabular-nums">
            {visibleClips.length}
            {visibleClips.length !== safeProject.clips.length && ` of ${safeProject.clips.length}`}
          </span>
          <span className="flex-1" />
          {safeProject.clips.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setSelectMode((on) => !on);
                setCheckedIds([]);
              }}
              aria-pressed={selectMode}
              className={`h-8 px-3 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                selectMode ? 'border-amber-500/60 bg-amber-500/10 text-amber-200' : 'border-neutral-800 text-neutral-300 hover:bg-neutral-800'
              }`}
            >
              <CheckSquare className="w-3.5 h-3.5" />
              {selectMode ? 'Done' : 'Select'}
            </button>
          )}
          <div className="flex items-center gap-1.5">
            <ArrowDownWideNarrow className="h-3.5 w-3.5 text-neutral-500" aria-hidden="true" />
            <Select
              value={sortMode}
              onChange={setSortMode}
              options={SORT_OPTIONS}
              className="h-8 rounded-lg border border-neutral-800 bg-neutral-900 px-2.5 text-xs text-white focus:border-amber-400 focus:outline-none"
              aria-label="Sort clips"
            />
          </div>
          <div className="flex items-center gap-1.5">
            <Filter className="h-3.5 w-3.5 text-neutral-500" aria-hidden="true" />
            <Select
              value={filterScore}
              onChange={setFilterScore}
              options={SCORE_FILTER_OPTIONS}
              className="h-8 rounded-lg border border-neutral-800 bg-neutral-900 px-2.5 text-xs text-white focus:border-amber-400 focus:outline-none"
              aria-label="Filter clips by score"
            />
          </div>
        </div>

        {selectMode && (
          <div className="sticky top-16 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-amber-500/30 bg-neutral-900/95 backdrop-blur px-3.5 py-2.5">
            <span className="text-[13px] font-semibold text-white tabular-nums">
              {checkedIds.length ? `${checkedIds.length} selected` : 'Tap clips to select them'}
            </span>
            <button
              type="button"
              onClick={() => setCheckedIds(visibleClips.map((c) => c.id))}
              className="text-xs font-semibold text-amber-300 hover:text-amber-200"
            >
              Select all
            </button>
            <span className="flex-1" />
            <button
              type="button"
              onClick={() => setCheckedIds([])}
              disabled={checkedIds.length === 0}
              className="h-8 px-3 rounded-lg text-xs font-semibold text-neutral-300 hover:bg-neutral-800 disabled:opacity-40"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={() => handleBatchExport(checkedClips)}
              disabled={checkedIds.length === 0 || isBatchExporting}
              className="h-8 px-3 rounded-lg bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold flex items-center gap-1.5 disabled:opacity-40"
            >
              {isBatchExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              Export {checkedIds.length || ''}
            </button>
          </div>
        )}

        {visibleClips.length > 0 && (
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {visibleClips.map((clip) => (
              <ClipCard
                key={clip.id}
                clip={clip}
                index={(rankById.get(clip.id) ?? 1) - 1}
                isSelected={selectedClip?.id === clip.id}
                isExporting={quickExportingId === clip.id}
                onSelect={setSelectedClip}
                onEdit={onSelectClipForEdit}
                onSchedule={onScheduleClip}
                onExport={handleQuickExport}
                selectMode={selectMode}
                checked={checkedIds.includes(clip.id)}
                onToggleChecked={toggleChecked}
              />
            ))}
          </div>
        )}

        {safeProject.clips.length > 0 && visibleClips.length === 0 && (
          <div className="rounded-2xl border border-dashed border-neutral-800 p-8 text-center">
            <p className="text-xs text-neutral-400">No clips match this score filter.</p>
            <button type="button" onClick={() => setFilterScore(0)} className="mt-2 text-xs font-semibold text-amber-300 hover:text-amber-200">
              Show all scores
            </button>
          </div>
        )}

        {safeProject.clips.length === 0 && (
          <div className="rounded-2xl border border-dashed border-neutral-800 p-10 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-neutral-800/70">
              {isProcessing ? <Sparkles className="h-5 w-5 text-amber-400" /> : <Film className="h-5 w-5 text-neutral-500" />}
            </div>
            <p className="text-sm font-semibold text-white">{isProcessing ? 'Finding your best moments' : 'No clips yet'}</p>
            <p className="mt-1 text-xs text-neutral-400">
              {isProcessing
                ? 'Clips appear here as soon as the pipeline finishes rendering them.'
                : 'Run the pipeline on this project to generate clips.'}
            </p>
          </div>
        )}
      </section>
    </div>
  );
};
