"use client";
import React from 'react';
import { CheckCircle2, Loader2, XCircle, RotateCcw } from 'lucide-react';
import { PipelineStep } from '@/lib/types';

interface PipelineStepIndicatorProps {
  steps: PipelineStep[];
  onRevert?: (step: string) => void;
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

export const PipelineStepIndicator: React.FC<PipelineStepIndicatorProps> = ({ steps, onRevert }) => {
  if (!steps || steps.length === 0) return null;

  const finished = steps.filter((s) => s.status === 'completed' || s.status === 'skipped').length;
  const running = steps.find((s) => s.status === 'running');
  const hasFailure = steps.some((s) => s.status === 'failed');
  const needsAttention = hasFailure || steps.some((s) => s.status === 'reverted');

  // Once every step has landed cleanly the tracker has nothing left to say, and
  // it pushes the clips it was reporting on below the fold. A run that failed or
  // has a reverted step stays visible, since those still need the user.
  if (finished === steps.length && !needsAttention) return null;
  // Partial credit for the step in flight, so the bar moves during a long step
  // instead of sitting still between whole-step jumps.
  const overall = Math.round(
    ((finished + (running ? Math.min(100, Math.max(0, running.progress_percent ?? 0)) / 100 : 0)) / steps.length) * 100,
  );

  return (
    <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300">
          Processing Pipeline
        </h3>
        <span className="font-mono text-[11px] font-semibold text-neutral-400">
          {finished}/{steps.length} steps &middot; {overall}%
        </span>
      </div>

      <div className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-800">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            hasFailure ? 'bg-rose-500' : overall >= 100 ? 'bg-emerald-400' : 'bg-amber-400'
          }`}
          style={{ width: `${overall}%` }}
        />
      </div>

      {running && (
        <p className="text-[11px] text-neutral-400">
          <span className="font-semibold text-amber-300">{STEP_LABELS[running.step] || running.step}</span>
          {running.message ? ` — ${running.message}` : ''}
        </p>
      )}
      <div className="space-y-2">
        {steps.map((step) => {
          const isCompleted = step.status === 'completed';
          const isRunning = step.status === 'running';
          const isFailed = step.status === 'failed';
          const isReverted = step.status === 'reverted';
          const isPending = step.status === 'pending';
          const isSkipped = step.status === 'skipped';

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
                  : isReverted
                  ? 'bg-neutral-800 border-neutral-700'
                  : 'bg-neutral-950 border-neutral-800'
              }`}
            >
              <div className="flex items-center gap-2.5">
                {isCompleted && <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />}
                {isRunning && <Loader2 className="w-4 h-4 text-amber-400 animate-spin flex-shrink-0" />}
                {isFailed && <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />}
                {isReverted && <RotateCcw className="w-4 h-4 text-neutral-400 flex-shrink-0" />}
                {isPending && <div className="w-4 h-4 rounded-full border-2 border-neutral-600 flex-shrink-0" />}
                {isSkipped && <div className="w-4 h-4 rounded-full border-2 border-neutral-700 flex-shrink-0" />}

                <div>
                  <span className="text-xs font-semibold text-neutral-200 block">
                    {STEP_LABELS[step.step] || step.step}
                  </span>
                  {step.message && (
                    <span className="text-[10px] text-neutral-400 block truncate max-w-[340px]">
                      {step.message}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {isRunning && (
                  <div className="flex items-center gap-2">
                    <div className="h-1 w-16 overflow-hidden rounded-full bg-neutral-800">
                      <div
                        className="h-full rounded-full bg-amber-400 transition-all duration-500"
                        style={{ width: `${Math.min(100, Math.max(0, step.progress_percent ?? 0))}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-amber-400 font-bold">
                      {step.progress_percent ?? 0}%
                    </span>
                  </div>
                )}
                {isReverted && onRevert && (
                  <button
                    onClick={() => onRevert(step.step)}
                    className="px-2 py-1 rounded-md bg-neutral-800 hover:bg-neutral-700 text-[10px] font-semibold text-neutral-300 border border-neutral-700 transition-colors flex items-center gap-1"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Re-run
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
