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
  clip_generation: 'Clip Generation',
  caption_styling: 'Caption Styling',
  auto_reframe: 'Auto Reframe',
  export: 'Export',
};

export const PipelineStepIndicator: React.FC<PipelineStepIndicatorProps> = ({ steps, onRevert }) => {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="rounded-xl bg-neutral-900 border border-neutral-800 p-4 space-y-3">
      <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
        Processing Pipeline
      </h3>
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
                    <span className="text-[10px] text-neutral-400 block truncate max-w-[200px]">
                      {step.message}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {isRunning && (
                  <span className="text-[10px] font-mono text-amber-400 font-bold">
                    {step.progress_percent}%
                  </span>
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
