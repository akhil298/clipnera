"use client";
import React from 'react';
import { Sparkles, Zap, CheckCircle2, Loader2, XCircle, HardDrive, CloudUpload } from 'lucide-react';
import { usePipelineProgress } from '@/hooks/usePipelineProgress';

interface PipelineProgressTrackerProps {
  projectId: string;
  selectedSteps: string[];
  creditsDeducted: number;
  isDownloadComplete?: boolean;
  downloadProgress?: { percent: number; status: string; total?: string | null; speed?: string | null; eta?: string | null };
}

const STEP_LABELS: Record<string, string> = {
  download: 'Download Video',
  audio_extraction: 'Extract Audio',
  ai_noise_cancellation: 'AI Noise Cancellation',
  transcription: 'Transcription',
  topic_research: 'Topic Research',
  visual_analysis: 'Visual Analysis',
  content_classification: 'Content Classification',
  highlight_detection: 'Highlight Detection',
  bounding_box_detection: 'Bounding Box Detection',
  scoring: 'Clip Scoring',
  metadata_generation: 'Clip Metadata',
  aspect_ratio_render: 'Aspect Ratio & Tracking',
  auto_reframe: 'Aspect Ratio & Tracking',
  clip_generation: 'Clip Generation',
  caption_styling: 'Caption Styling',
  export: 'Export',
};

const STEP_DESCRIPTIONS: Record<string, string> = {
  download: 'Ingesting YouTube video and uploading to cloud storage',
  audio_extraction: 'Extracting raw audio track from video',
  ai_noise_cancellation: 'AI-powered noise removal and vocal enhancement',
  transcription: 'Transcribing audio with speaker diarization',
  topic_research: 'Analyzing content and researching context',
  visual_analysis: 'Detecting key frames and visual elements',
  content_classification: 'Classifying content for optimal clipping',
  highlight_detection: 'Identifying viral-worthy highlight moments',
  bounding_box_detection: 'Tracking subjects with bounding boxes',
  scoring: 'Scoring each clip for virality potential',
  metadata_generation: 'Generating captions and clip titles',
  aspect_ratio_render: 'Calculating aspect-ratio crops for all platforms',
  clip_generation: 'Rendering and generating viral clips',
  caption_styling: 'Applying kinetic caption styles',
  export: 'Final burn-in and export',
};

export const PipelineProgressTracker: React.FC<PipelineProgressTrackerProps> = ({
  projectId,
  selectedSteps,
  creditsDeducted = 0,
  isDownloadComplete = false,
  downloadProgress,
}) => {
  const {
    steps,
    progress,
    currentStep,
    error,
  } = usePipelineProgress(projectId, selectedSteps, creditsDeducted);

  const completedCount = steps.filter((s) => s.status === 'completed' || s.status === 'skipped').length;
  const runningCount = steps.filter((s) => s.status === 'running').length;
  const overallPercent = isDownloadComplete ? progress.percent : (downloadProgress?.percent ?? 0);

  return (
    <div className="space-y-4">
      {/* Header with Credits Info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">
              {isDownloadComplete ? 'AI Pipeline Processing' : 'Uploading Video to Cloud'}
            </h3>
            <p className="text-[11px] text-neutral-400">
              {isDownloadComplete
                ? `Step ${completedCount + runningCount}/${steps.length} • ${currentStep ? STEP_LABELS[currentStep] || currentStep : 'Starting...'}`
                : 'Fast parallel upload to S3 (10 workers, 50MB chunks)'}
            </p>
          </div>
        </div>

        {creditsDeducted > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-[11px] font-mono font-bold text-amber-300">
              {creditsDeducted} credit{creditsDeducted !== 1 ? 's' : ''} charged
            </span>
          </div>
        )}
      </div>

      {/* Download / Upload Progress (pre-pipeline phase) */}
      {!isDownloadComplete && downloadProgress && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 text-neutral-300">
              {downloadProgress.status === 'uploading' ? (
                <CloudUpload className="w-4 h-4 text-amber-400" />
              ) : (
                <HardDrive className="w-4 h-4 text-amber-400" />
              )}
              <span className="font-semibold">
                {downloadProgress.status === 'uploading' ? 'Uploading to S3...' : 'Downloading video...'}
              </span>
            </span>
            <span className="font-mono font-bold text-amber-400">
              {Math.round(downloadProgress.percent ?? 0)}%
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
        </div>
      )}

      {/* Pipeline Steps List */}
      {isDownloadComplete && steps.length > 0 && (
        <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              <span>Processing Pipeline — {overallPercent}% Complete</span>
            </h4>
            <span className="text-[10px] font-mono text-neutral-500">
              {completedCount}/{steps.length} steps done
            </span>
          </div>

          <div className="space-y-2">
            {steps.map((step, idx) => {
              const isCompleted = step.status === 'completed' || step.status === 'skipped';
              const isRunning = step.status === 'running';
              const isFailed = step.status === 'failed';
              const isPending = step.status === 'pending' || step.status === 'reverted';
              const isCurrent = currentStep === step.step;
              const pct = step.progress_percent ?? (isCompleted ? 100 : isRunning ? progress.percent : 0);

              return (
                <div
                  key={step.step}
                  className={`flex items-center justify-between p-2.5 rounded-lg border transition-all ${
                    isRunning
                      ? 'bg-amber-500/5 border-amber-500/30'
                      : isCompleted
                        ? 'bg-emerald-500/5 border-emerald-500/20'
                        : isFailed
                          ? 'bg-rose-500/5 border-rose-500/20'
                          : 'bg-neutral-950 border-neutral-800'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    {isCompleted && <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />}
                    {isRunning && <Loader2 className="w-4 h-4 text-amber-400 animate-spin flex-shrink-0" />}
                    {isFailed && <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />}
                    {isPending && <div className="w-4 h-4 rounded-full border-2 border-neutral-600 flex-shrink-0" />}

                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-neutral-200 block">
                        {STEP_LABELS[step.step] || step.step}
                      </span>
                      <span className="text-[10px] text-neutral-500 block">
                        {STEP_DESCRIPTIONS[step.step] || ''}
                      </span>
                      {step.message && isRunning && (
                        <span className="text-[9px] text-neutral-400 block truncate max-w-[260px] mt-0.5">
                          {step.message}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {isRunning && (
                      <span className="text-[10px] font-mono text-amber-400 font-bold">
                        {Math.round(pct)}%
                      </span>
                    )}
                    {isFailed && step.message && (
                      <span className="text-[9px] text-rose-400 max-w-[120px] truncate">
                        {step.message}
                      </span>
                    )}
                    {isCompleted && (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Live Progress Message */}
      {isDownloadComplete && progress.message && (
        <div className="flex items-center gap-2 text-[11px] text-neutral-400 font-mono">
          <Loader2 className={`w-3.5 h-3.5 ${progress.status === 'running' ? 'animate-spin text-amber-400' : 'text-emerald-400'}`} />
          <span>{progress.message}</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-500/5 border border-rose-500/20 flex items-center gap-2">
          <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span className="text-xs text-rose-300">{error}</span>
        </div>
      )}
    </div>
  );
};
